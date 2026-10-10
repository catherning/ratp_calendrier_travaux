#!/usr/bin/env bash
source "$(dirname -- "$0")/common.sh"

upload_graph() {
  local file="$1" mode="$2" destination generation=0
  destination="gs://$BUCKET_NAME/$BUCKET_PREFIX/$(basename -- "$file")"

  if [[ "$mode" == --replace ]]; then
    generation="$(gcloud storage objects describe "$destination" --format='value(generation)')"
    [[ "$generation" =~ ^[0-9]+$ ]] || die "Cannot safely replace missing/unversioned object"
  fi

  gcloud storage cp "$file" "$destination" --if-generation-match="$generation" --quiet
}

main() {
  local config_path="${1:?Usage: upload-graphs.sh CONFIG GRAPH_DIRECTORY [--replace]}"
  local directory="${2:?Graph directory required}"
  local mode="${3:-initial}"
  local files file

  [[ "$mode" == initial || "$mode" == --replace ]] || die "Only optional --replace is supported"
  load_config "$config_path"

  # Validate the whole batch before contacting GCP or uploading its first object.
  files="$("$PYTHON" "$DEPLOY_DIR/validate-graphs.py" "$directory")"
  require_gcloud

  while IFS= read -r file; do
    upload_graph "$file" "$mode"
  done <<< "$files"

  echo "Validated graphs uploaded unchanged; prior versions retained by the bucket."
}

main "$@"
