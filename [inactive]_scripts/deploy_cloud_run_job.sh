#!/usr/bin/env bash
# Deploy (create or update) the Cloud Run Job with the given image.
# Usage: deploy_cloud_run_job.sh <config-path> <docker-image>

set -euo pipefail

CONFIG_PATH="${1:-}"
DOCKER_IMAGE="${2:-}"

if [[ -z "${CONFIG_PATH}" || -z "${DOCKER_IMAGE}" ]]; then
    echo "Usage: $0 <config-path> <docker-image>" >&2
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
    "PROJECT_ID":       ("projectId",),
    "REGION":           ("region",),
    "JOB_NAME":         ("cloudRunJob", "name"),
    "JOB_CPU":          ("cloudRunJob", "cpu"),
    "JOB_MEMORY":       ("cloudRunJob", "memory"),
    "JOB_TIMEOUT":      ("cloudRunJob", "taskTimeout"),
    "JOB_TASKS":        ("cloudRunJob", "tasks"),
    "JOB_PARALLELISM":  ("cloudRunJob", "parallelism"),
    "JOB_MAX_RETRIES":  ("cloudRunJob", "maxRetries"),
    "GCS_BUCKET_NAME":  ("gcs", "bucketName"),
    "MISTRAL_API_KEY": ("secrets", "MISTRAL_API_KEY"),
}

optional_paths = {
    "JOB_SERVICE_ACCOUNT": ("cloudRunJob", "serviceAccount"),
    "GCS_BUCKET_PREFIX": ("gcs", "bucketPrefix"),
    "SCRAPER_PROXY_SECRET": ("secrets", "SCRAPER_PROXY"),
    "CF_MAX_RETRIES": ("runtime", "cloudflareMaxRetries"),
    "CF_RECONNECT_SECONDS": ("runtime", "cloudflareReconnectSeconds"),
    "CF_BACKOFF_SECONDS": ("runtime", "cloudflareBackoffSeconds"),
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

for env_name, path in optional_paths.items():
    try:
        value = lookup(path)
    except KeyError:
        value = ""
    print(f"{env_name}={shlex.quote(str(value or ''))}")
PY
)"

run_args=(
    run jobs deploy "${JOB_NAME}"
    --project "${PROJECT_ID}"
    --region "${REGION}"
    --image "${DOCKER_IMAGE}"
    --tasks "${JOB_TASKS}"
    --parallelism "${JOB_PARALLELISM}"
    --max-retries "${JOB_MAX_RETRIES}"
    --cpu "${JOB_CPU}"
    --memory "${JOB_MEMORY}"
    --task-timeout "${JOB_TIMEOUT}"
)

env_bindings=("GCS_BUCKET_NAME=${GCS_BUCKET_NAME}")
if [[ -n "${GCS_BUCKET_PREFIX}" ]]; then
    env_bindings+=("GCS_BUCKET_PREFIX=${GCS_BUCKET_PREFIX}")
fi

secret_bindings=("MISTRAL_API_KEY=${MISTRAL_API_KEY}:latest")

run_args+=(--set-env-vars "$(IFS=,; echo "${env_bindings[*]}")")
run_args+=(--set-secrets "$(IFS=,; echo "${secret_bindings[*]}")")

if [[ -n "${JOB_SERVICE_ACCOUNT}" ]]; then
    run_args+=(--service-account "${JOB_SERVICE_ACCOUNT}")
fi

gcloud "${run_args[@]}"
echo "Cloud Run job deployed: ${JOB_NAME}"
