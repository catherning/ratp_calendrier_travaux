#!/usr/bin/env bash
source "$(dirname -- "$0")/common.sh"

main() {
  local config_path="${1:?Usage: alerts.sh CONFIG}"

  load_config "$config_path"
  require_gcloud
  "$PYTHON" "$DEPLOY_DIR/alerts.py" "$config_path"
}

main "$@"
