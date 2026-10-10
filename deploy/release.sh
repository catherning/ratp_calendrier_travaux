#!/usr/bin/env bash
source "$(dirname -- "$0")/common.sh"

require_existing_services() {
  local service

  for service in "$BACKEND_SERVICE" "$FRONTEND_SERVICE"; do
    gcloud run services describe "$service" \
      --project="$PROJECT_ID" --region="$REGION" >/dev/null
  done
}

fetch_with_retries() {
  curl --fail --silent --show-error \
    --retry 3 --retry-all-errors --max-time 60 "$@"
}

http_status() {
  curl --silent --show-error \
    --output /dev/null --write-out '%{http_code}' --max-time 60 "$1"
}

check_backend_authentication() {
  local backend_url="$1" token code

  token="$(gcloud auth print-identity-token \
    --impersonate-service-account="$RELEASE_SERVICE_ACCOUNT" \
    --audiences="$backend_url" \
    --include-email)"

  fetch_with_retries -H "Authorization: Bearer $token" "$backend_url/health" >/dev/null

  code="$(http_status "$backend_url/health")"
  [[ "$code" == 401 || "$code" == 403 ]] \
    || die "Backend must reject unauthenticated traffic, got HTTP $code"
}

check_frontend_proxy() {
  local frontend_url="$1" response graphs code

  fetch_with_retries "$frontend_url/" >/dev/null

  response="$(fetch_with_retries "$frontend_url/api/lines")"
  printf '%s' "$response" | "$PYTHON" -c '
import json
import sys

lines = json.load(sys.stdin)
assert isinstance(lines, (list, dict)) and lines, "Proxy returned empty or invalid lines JSON"
'

  # Read the seeded graph only; never trigger an administrative refresh.
  graphs="$(fetch_with_retries "$frontend_url/api/lines/stations?lines=2")"
  printf '%s' "$graphs" | "$PYTHON" -c '
import json
import runpy
import sys

validate_line_graph = runpy.run_path(sys.argv[1])["validate_line_graph"]
validate_line_graph(json.load(sys.stdin)["2"])
' "$DEPLOY_DIR/../src/domain/line_graph.py"

  code="$(http_status "$frontend_url/api/admin/lines/stations/refresh")"
  [[ "$code" == 404 ]] \
    || die "Frontend proxy must not expose administration, got HTTP $code"
}

main() {
  local config_path="${1:?Usage: release.sh CONFIG BACKEND_DIGEST FRONTEND_DIGEST}"
  local backend_image="${2:?Backend digest required}"
  local frontend_image="${3:?Frontend digest required}"
  local backend_url frontend_url

  load_config "$config_path"
  validate_images "$backend_image" "$frontend_image"
  require_gcloud
  require_existing_services

  deploy_backend "$backend_image"
  backend_url="$(service_url "$BACKEND_SERVICE")"
  check_backend_authentication "$backend_url"

  deploy_frontend "$frontend_image" "$backend_url"
  frontend_url="$(service_url "$FRONTEND_SERVICE")"
  check_frontend_proxy "$frontend_url"

  echo "Smoke tests passed: public frontend, private backend and authenticated proxy."
}

main "$@"
