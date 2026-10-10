"""Offline deployment validation; no gcloud, containers or real API access."""
import copy
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import alerts
import config

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("graphs", HERE / "validate-graphs.py")
graphs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(graphs)


def valid_config():
    value = json.loads((HERE / "config.example.json").read_text())
    value.update(
        project_id="ratp-demo-project", project_number="123456789012",
        bucket_name="ratp-demo-private-graphs", github_repository="example/ratp",
        billing_account="ABCDEF-123456-ABCDEF", notification_email="operator@example.org")
    return value


class ConfigTests(unittest.TestCase):
    def load_value(self, value):
        with patch.object(config.Path, "read_text", return_value=json.dumps(value)):
            return config.load("unused")

    def test_valid_and_outputs(self):
        value = self.load_value(valid_config())
        output = config.outputs(value)
        self.assertTrue(output["release_service_account"].startswith("ratp-release@"))
        self.assertIn("/workloadIdentityPools/github/providers/ratp", output["workload_identity_provider"])

    def test_placeholders_and_unknown_fields_rejected(self):
        with self.assertRaises(ValueError):
            config.load(HERE / "config.example.json")
        value = valid_config()
        value["admin_secret"] = "not-permitted"
        with self.assertRaises(ValueError):
            self.load_value(value)

    def test_bad_values_rejected(self):
        for key, value in (
            ("errors_per_second", True), ("budget_amount", -1),
            ("frontend_requests_per_second", float("nan")),
            ("github_branch", "main' || true"), ("bucket_prefix", "../graphs"),
            ("notification_email", "user@example.org\nmalicious=value"),
            ("project_number", 123456789012), ("frontend_account", "ratp-backend"),
        ):
            with self.subTest(key=key):
                candidate = valid_config()
                candidate[key] = value
                with self.assertRaises(ValueError):
                    self.load_value(candidate)

    def test_duplicate_json(self):
        with patch.object(config.Path, "read_text", return_value='{"project_id":"one","project_id":"two"}'):
            with self.assertRaisesRegex(ValueError, "Duplicate"):
                config.load("unused")

    def test_workflow_ref_checks(self):
        for repository, ref, valid in (
            ("example/ratp", "refs/heads/main", True),
            ("other/ratp", "refs/heads/main", False),
            ("example/ratp", "refs/pull/1/merge", False),
        ):
            with patch.dict(os.environ, GITHUB_REPOSITORY=repository, GITHUB_REF=ref):
                if valid:
                    config.check_github(valid_config())
                else:
                    with self.assertRaises(ValueError):
                        config.check_github(valid_config())
        # Inspect workflow scripts rather than executing any cloud steps.
        for filename in ("release-gcp.yml", "provision-gcp.yml"):
            text = (HERE.parent / ".github/workflows" / filename).read_text()
            self.assertIn('python3 deploy/config.py "$CONFIG" check-github', text)
            self.assertIn("id-token: write", text)
            self.assertNotIn("secrets.", text)


class AlertTests(unittest.TestCase):
    def test_payloads(self):
        value = valid_config()
        channel = "projects/ratp-demo-project/notificationChannels/1"
        budget = alerts.budget_payload(value, channel)
        self.assertEqual(budget["budgetFilter"]["projects"], ["projects/123456789012"])
        self.assertEqual(budget["budgetFilter"]["calendarPeriod"], "MONTH")
        self.assertNotIn("services", budget["budgetFilter"])
        self.assertEqual([rule["thresholdPercent"] for rule in budget["thresholdRules"]], [.5, .8, 1, 1])
        self.assertEqual(budget["thresholdRules"][-1]["spendBasis"], "FORECASTED_SPEND")
        for kind in ("traffic", "errors"):
            policy = alerts.policy_payload(value, value["frontend_service"], kind, channel)
            condition = policy["conditions"][0]["conditionThreshold"]
            aggregation = condition["aggregations"][0]
            self.assertEqual(aggregation["perSeriesAligner"], "ALIGN_RATE")
            self.assertEqual(aggregation["crossSeriesReducer"], "REDUCE_SUM")
            self.assertEqual(aggregation["groupByFields"], [])
            self.assertEqual('response_code_class = "5xx"' in condition["filter"], kind == "errors")
            self.assertEqual(condition["thresholdValue"], value[
                "errors_per_second" if kind == "errors" else "frontend_requests_per_second"])

    def test_upsert_create_patch_pagination_and_duplicates(self):
        api = object.__new__(alerts.API)
        url = "https://monitoring.googleapis.com/v3/projects/demo/alertPolicies"
        payload = {"displayName": "test"}
        with patch.object(api, "request", return_value={}) as request:
            api.upsert(url, "alertPolicies", payload, "displayName")
            self.assertEqual(request.call_args.args, ("POST", url, payload))
        pages = [
            {"nextPageToken": "page 2"},
            {"alertPolicies": [{"name": "projects/demo/alertPolicies/1", "displayName": "test"}]},
            {"name": "projects/demo/alertPolicies/1"},
        ]
        with patch.object(api, "request", side_effect=pages) as request:
            api.upsert(url, "alertPolicies", payload, "displayName")
            self.assertIn("pageToken=page%202", request.call_args_list[1].args[1])
            self.assertEqual(request.call_args.args[:2], (
                "PATCH", "https://monitoring.googleapis.com/v3/projects/demo/alertPolicies/1?updateMask=displayName"))
        with patch.object(api, "list", return_value=[payload, payload]):
            with self.assertRaisesRegex(ValueError, "Duplicate"):
                api.upsert(url, "alertPolicies", payload, "displayName")

    def test_main_only_mocked_apis(self):
        with patch.object(alerts, "API") as constructor:
            api = constructor.return_value
            api.request.return_value = {
                "billingEnabled": True, "billingAccountName": "billingAccounts/ABCDEF-123456-ABCDEF"}
            api.upsert.return_value = {"name": "projects/demo/notificationChannels/1"}
            alerts.main(valid_config())
            self.assertEqual(api.upsert.call_count, 5)
            api.request.return_value = {"billingEnabled": False}
            with self.assertRaises(ValueError):
                alerts.main(valid_config())


class GraphTests(unittest.TestCase):
    def setUp(self):
        self.directory = HERE / f".offline-graphs-{os.getpid()}"
        self.directory.mkdir()
        self.entry = {
            "version": 1, "navitia_id": "C01374", "fetched_at": 1,
            "graph": {"stations": {
                "a": {"name": "A", "lat": 48.0, "lon": 2.0, "neighbors": ["b"]},
                "b": {"name": "B", "lat": 48.1, "lon": 2.1, "neighbors": ["a"]},
            }},
        }
        self.path = self.directory / (hashlib.sha256(b"C01374").hexdigest() + ".json")

    def tearDown(self):
        shutil.rmtree(self.directory)

    def test_valid_bytes_unchanged(self):
        content = json.dumps(self.entry)
        self.path.write_text(content)
        self.assertEqual(graphs.validate_directory(self.directory), [self.path])
        self.assertEqual(self.path.read_text(), content)

    def test_invalid_envelope_and_graph(self):
        candidates = []
        for key, value in (
            ("version", True), ("navitia_id", "C01375"),
            ("fetched_at", float("inf")), ("fetched_at", -1),
        ):
            candidate = copy.deepcopy(self.entry)
            candidate[key] = value
            candidates.append(candidate)
        candidate = copy.deepcopy(self.entry)
        candidate["graph"]["stations"]["b"]["neighbors"] = []
        candidates.append(candidate)
        for candidate in candidates:
            self.path.write_text(json.dumps(candidate))
            with self.assertRaises(ValueError):
                graphs.validate_directory(self.directory)


class ScriptTests(unittest.TestCase):
    def test_bash_syntax(self):
        for path in HERE.glob("*.sh"):
            subprocess.run(["bash", "-n", str(path)], check=True)

    def test_release_order_secrets_and_privacy(self):
        script = (HERE / "release.sh").read_text()
        shared = (HERE / "common.sh").read_text()
        self.assertLess(script.index('deploy_backend "$backend_image"'),
                        script.index('deploy_frontend "$frontend_image"'))
        frontend = shared.split("deploy_frontend() {", 1)[1]
        self.assertIn("--clear-secrets", frontend)
        self.assertNotIn("ADMIN_API_KEY", frontend)
        self.assertIn("validate_line_graph", script)
        self.assertIn("401", script)
        self.assertIn("403", script)
        for path in HERE.glob("*.sh"):
            self.assertNotIn("gcloud scheduler", path.read_text())
            self.assertNotIn("eval ", path.read_text())

    def run_script(self, filename, *arguments, existing_provider=False):
        with tempfile.TemporaryDirectory(prefix="ratp-deploy-test-") as directory:
            root = Path(directory)
            config_path = root / "config.json"
            config_path.write_text(json.dumps(valid_config()))
            log = root / "commands"
            fake_gcloud = root / "gcloud"
            fake_gcloud.write_text("""#!/usr/bin/env bash
set -euo pipefail
printf '%s\\t' "$@" >> "$COMMAND_LOG"
printf '\\n' >> "$COMMAND_LOG"
case "$*" in
  "projects describe "*) echo 123456789012 ;;
  "run services get-iam-policy "*)
    echo '{"bindings":[{"role":"roles/run.invoker","members":["allUsers","allAuthenticatedUsers"]}]}'
    ;;
  "run services describe "*)
    if [[ "$*" == *"value(status.url)"* ]]; then
      printf 'https://%s.example\\n' "$4"
    fi
    ;;
  "secrets versions list "*) echo 1 ;;
  "auth print-identity-token "*) echo test-identity-token ;;
  "iam workload-identity-pools providers list "*)
    if [[ "$EXISTING_PROVIDER" == true ]]; then echo existing-provider; fi
    ;;
esac
""")
            fake_curl = root / "curl"
            fake_curl.write_text("""#!/usr/bin/env bash
set -euo pipefail
printf 'curl\\t' >> "$COMMAND_LOG"
printf '%s\\t' "$@" >> "$COMMAND_LOG"
printf '\\n' >> "$COMMAND_LOG"
url=""
for argument in "$@"; do url="$argument"; done
if [[ "$*" == *"%{http_code}"* ]]; then
  if [[ "$url" == *"/api/admin/"* ]]; then echo 404; else echo 403; fi
elif [[ "$url" == *"/api/lines/stations?lines=2" ]]; then
  echo '{"2":{"stations":{"a":{"name":"A","lat":48,"lon":2,"neighbors":["b"]},"b":{"name":"B","lat":48.1,"lon":2.1,"neighbors":["a"]}}}}'
elif [[ "$url" == *"/api/lines" ]]; then
  echo '[{"code":"2"}]'
else
  echo '{"status":"ok"}'
fi
""")
            fake_gcloud.chmod(0o700)
            fake_curl.chmod(0o700)
            subprocess.run(
                ["bash", str(HERE / filename), str(config_path), *arguments],
                env={
                    **os.environ,
                    "PATH": f"{root}:{os.environ['PATH']}",
                    "PYTHON": os.sys.executable,
                    "COMMAND_LOG": str(log),
                    "EXISTING_PROVIDER": str(existing_provider).lower(),
                },
                check=True, capture_output=True, text=True,
            )
            return [line.rstrip("\t").split("\t") for line in log.read_text().splitlines()]

    def image_digests(self):
        value = valid_config()
        registry = (
            f"{value['region']}-docker.pkg.dev/"
            f"{value['project_id']}/{value['artifact_repository']}"
        )
        return tuple(f"{registry}/{name}@sha256:{'a' * 64}" for name in ("backend", "frontend"))

    def test_service_provisioning_commands(self):
        commands = self.run_script("provision.sh", "services", *self.image_digests())
        deploys = [args for args in commands if args[:2] == ["run", "deploy"]]
        self.assertEqual(len(deploys), 2)
        backend, frontend = deploys
        self.assertIn("--no-allow-unauthenticated", backend)
        self.assertIn("--invoker-iam-check", backend)
        self.assertIn("--max=2", backend)
        self.assertIn("--port=8000", backend)
        self.assertIn("--allow-unauthenticated", frontend)
        self.assertIn("--clear-secrets", frontend)
        self.assertIn("--max=3", frontend)
        self.assertNotIn("ADMIN_API_KEY", " ".join(frontend))
        removals = [
            args for args in commands
            if args[:3] == ["run", "services", "remove-iam-policy-binding"]
        ]
        self.assertEqual(len(removals), 2)
        self.assertIn("--member=allUsers", removals[0])
        self.assertIn("--member=allAuthenticatedUsers", removals[1])

    def test_release_uses_shared_deployment_and_smoke_tests(self):
        commands = self.run_script("release.sh", *self.image_digests())
        deploys = [args for args in commands if args[:2] == ["run", "deploy"]]
        self.assertEqual(len(deploys), 2)
        self.assertIn("--invoker-iam-check", deploys[0])
        self.assertIn("--clear-secrets", deploys[1])
        self.assertTrue(any("/api/lines/stations?lines=2" in " ".join(args) for args in commands))
        self.assertTrue(any("/api/admin/" in " ".join(args) for args in commands))
        self.assertTrue(any("Authorization: Bearer test-identity-token" in args for args in commands))

    def test_wif_create_and_update_keep_trust_restrictions(self):
        for exists, action in ((False, "create-oidc"), (True, "update-oidc")):
            with self.subTest(existing=exists):
                commands = self.run_script("bootstrap-wif.sh", existing_provider=exists)
                provider = next(
                    args for args in commands
                    if args[:4] == ["iam", "workload-identity-pools", "providers", action]
                )
                condition = next(arg for arg in provider if arg.startswith("--attribute-condition="))
                self.assertIn("assertion.repository == 'example/ratp'", condition)
                self.assertIn("assertion.ref == 'refs/heads/main'", condition)
                self.assertIn("assertion.environment == 'production'", condition)
                self.assertIn("assertion.environment == 'provisioning'", condition)


if __name__ == "__main__":
    unittest.main()
