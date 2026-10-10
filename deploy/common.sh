#!/usr/bin/env bash
set -euo pipefail

DEPLOY_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${PYTHON:-python3}"

die() {
  echo "ERROR: $*" >&2
  exit 1
}

load_config() {
  local values key value

  values="$("$PYTHON" "$DEPLOY_DIR/config.py" "${1:?config JSON required}" shell)"
  while IFS='=' read -r key value; do
    printf -v "$key" '%s' "$value"
    export "$key"
  done <<< "$values"
}

require_gcloud() {
  local actual

  command -v gcloud >/dev/null || die "Install Google Cloud SDK and authenticate first"
  command -v curl >/dev/null || die "curl is required"
  actual="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
  [[ "$actual" == "$PROJECT_NUMBER" ]] || die "project_id/project_number mismatch"
}

account_email() {
  printf '%s@%s.iam.gserviceaccount.com' "$1" "$PROJECT_ID"
}

ensure_service_account() {
  local name="$1" existing

  existing="$(gcloud iam service-accounts list \
    --project="$PROJECT_ID" \
    --filter="email=$(account_email "$name")" \
    --format='value(email)')"

  if [[ -z "$existing" ]]; then
    gcloud iam service-accounts create "$name" --project="$PROJECT_ID" --quiet
  fi
}

project_role() {
  local identity="$1" role="$2"

  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:$identity" \
    --role="$role" \
    --condition=None \
    --quiet >/dev/null
}

assert_digest() {
  [[ "$1" =~ ^${REGION}-docker\.pkg\.dev/${PROJECT_ID}/${ARTIFACT_REPOSITORY}/(backend|frontend)@sha256:[a-f0-9]{64}$ ]] \
    || die "Expected a digest-pinned backend/frontend image in the configured registry"
}

validate_images() {
  local backend_image="$1" frontend_image="$2"

  assert_digest "$backend_image"
  assert_digest "$frontend_image"
  [[ "$backend_image" == */backend@* && "$frontend_image" == */frontend@* ]] \
    || die "Images are in the wrong order"
}

service_url() {
  local service="$1" url

  url="$(gcloud run services describe "$service" \
    --project="$PROJECT_ID" \
    --region="$REGION" \
    --format='value(status.url)')"
  [[ -n "$url" ]] || die "$service has no URL"
  printf '%s' "$url"
}

deploy_backend() {
  local image="$1"
  shift

  gcloud run deploy "$BACKEND_SERVICE" \
    --project="$PROJECT_ID" \
    --region="$REGION" \
    --image="$image" \
    --service-account="$(account_email "$BACKEND_ACCOUNT")" \
    --port=8000 \
    --invoker-iam-check \
    --set-env-vars="GCS_BUCKET_NAME=$BUCKET_NAME,GCS_BUCKET_PREFIX=$BUCKET_PREFIX,LINE_GRAPH_DATA_DIR=/tmp/line_graphs" \
    --set-secrets=NAVITIA_API_KEY=NAVITIA_API_KEY:latest,ADMIN_API_KEY=ADMIN_API_KEY:latest \
    "$@" \
    --quiet
}

deploy_frontend() {
  local image="$1" backend_url="$2"
  shift 2

  gcloud run deploy "$FRONTEND_SERVICE" \
    --project="$PROJECT_ID" \
    --region="$REGION" \
    --image="$image" \
    --service-account="$(account_email "$FRONTEND_ACCOUNT")" \
    --port=3000 \
    --set-env-vars="BACKEND_API_URL=$backend_url,NEXT_PUBLIC_API_URL=/api" \
    --clear-secrets \
    "$@" \
    --quiet
}
