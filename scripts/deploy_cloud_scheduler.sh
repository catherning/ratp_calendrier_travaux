#!/usr/bin/env bash
# Create or update the Cloud Scheduler job that triggers the Cloud Run Job.
# Only needs to run when schedule, service accounts, or resource names change.
# Usage: configure_cloud_scheduler.sh <config-path>

set -euo pipefail

CONFIG_PATH="${1:-}"

if [[ -z "${CONFIG_PATH}" ]]; then
    echo "Usage: $0 <config-path>" >&2
    exit 1
fi

if [[ ! -f "${CONFIG_PATH}" ]]; then
    echo "Config file not found: ${CONFIG_PATH}" >&2
    exit 1
fi

eval "$(python3 - "${CONFIG_PATH}" <<'PY'
import json
import shlex
import sys

config_path = sys.argv[1]
with open(config_path, "r", encoding="utf-8") as handle:
    config = json.load(handle)

required_paths = {
    "PROJECT_ID":                 ("projectId",),
    "REGION":                     ("region",),
    "JOB_NAME":                   ("cloudRunJob", "name"),
    "SCHEDULER_NAME":             ("cloudScheduler", "name"),
    "SCHEDULER_CRON":             ("cloudScheduler", "cron"),
    "SCHEDULER_TIME_ZONE":        ("cloudScheduler", "timeZone"),
    "SCHEDULER_SERVICE_ACCOUNT":  ("cloudScheduler", "serviceAccount"),
}

def lookup(path):
    current = config
    for part in path:
        current = current[part]
    return current

missing = []
for env_name, path in required_paths.items():
    try:
        value = lookup(path)
    except KeyError:
        missing.append(".".join(path))
        continue
    if value in (None, ""):
        missing.append(".".join(path))

if missing:
    print("echo 'Missing required config keys: {}' >&2".format(", ".join(missing)))
    print("exit 1")
    sys.exit(0)

placeholder_keys = [
    ".".join(path)
    for env_name, path in required_paths.items()
    if str(lookup(path)).startswith("REPLACE_ME_")
]
if placeholder_keys:
    print("echo 'Replace placeholder config values before deploying: {}' >&2".format(", ".join(placeholder_keys)))
    print("exit 1")
    sys.exit(0)

for env_name, path in required_paths.items():
    print(f"{env_name}={shlex.quote(str(lookup(path)))}")
PY
)"

RUN_URI="https://run.googleapis.com/v2/projects/${PROJECT_ID}/locations/${REGION}/jobs/${JOB_NAME}:run"

scheduler_args=(
    --location "${REGION}"
    --schedule "${SCHEDULER_CRON}"
    --time-zone "${SCHEDULER_TIME_ZONE}"
    --uri "${RUN_URI}"
    --http-method POST
    --headers "Content-Type=application/json"
    --message-body '{}'
    --oauth-service-account-email "${SCHEDULER_SERVICE_ACCOUNT}"
    --oauth-token-scope "https://www.googleapis.com/auth/cloud-platform"
)

if gcloud scheduler jobs describe "${SCHEDULER_NAME}" --location "${REGION}" >/dev/null 2>&1; then
    gcloud scheduler jobs update http "${SCHEDULER_NAME}" "${scheduler_args[@]}"
else
    gcloud scheduler jobs create http "${SCHEDULER_NAME}" "${scheduler_args[@]}"
fi

echo "Cloud Scheduler job configured: ${SCHEDULER_NAME}"
