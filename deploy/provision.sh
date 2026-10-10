#!/usr/bin/env bash
source "$(dirname -- "$0")/common.sh"

enable_resource_apis() {
  gcloud services enable \
    run.googleapis.com \
    artifactregistry.googleapis.com \
    storage.googleapis.com \
    secretmanager.googleapis.com \
    monitoring.googleapis.com \
    billingbudgets.googleapis.com \
    cloudbilling.googleapis.com \
    --project="$PROJECT_ID" --quiet
}

ensure_graph_bucket() {
  local existing prefix_condition

  existing="$(gcloud storage buckets list \
    --project="$PROJECT_ID" \
    --filter="name=$BUCKET_NAME" \
    --format='value(name)')"

  if [[ -z "$existing" ]]; then
    gcloud storage buckets create "gs://$BUCKET_NAME" \
      --project="$PROJECT_ID" \
      --location="$REGION" \
      --uniform-bucket-level-access \
      --public-access-prevention \
      --quiet
  fi

  gcloud storage buckets update "gs://$BUCKET_NAME" \
    --versioning --uniform-bucket-level-access --public-access-prevention --quiet

  # Object permissions are confined to the graph prefix, without bucket listing.
  prefix_condition="resource.name.startsWith('projects/_/buckets/$BUCKET_NAME/objects/$BUCKET_PREFIX/')"
  gcloud storage buckets add-iam-policy-binding "gs://$BUCKET_NAME" \
    --member="serviceAccount:$(account_email "$BACKEND_ACCOUNT")" \
    --role=roles/storage.objectUser \
    --condition="expression=$prefix_condition,title=graph-prefix" \
    --quiet >/dev/null
}

ensure_image_registry() {
  local existing format

  existing="$(gcloud artifacts repositories list \
    --project="$PROJECT_ID" \
    --location="$REGION" \
    --filter="name=projects/$PROJECT_ID/locations/$REGION/repositories/$ARTIFACT_REPOSITORY" \
    --format='value(name)')"

  if [[ -z "$existing" ]]; then
    gcloud artifacts repositories create "$ARTIFACT_REPOSITORY" \
      --project="$PROJECT_ID" --location="$REGION" \
      --repository-format=docker --immutable-tags --quiet
  else
    format="$(gcloud artifacts repositories describe "$ARTIFACT_REPOSITORY" \
      --project="$PROJECT_ID" --location="$REGION" --format='value(format)')"
    [[ "$format" == DOCKER ]] || die "Existing Artifact Registry is not Docker"
    gcloud artifacts repositories update "$ARTIFACT_REPOSITORY" \
      --project="$PROJECT_ID" --location="$REGION" --immutable-tags --quiet
  fi

  gcloud artifacts repositories add-iam-policy-binding "$ARTIFACT_REPOSITORY" \
    --project="$PROJECT_ID" \
    --location="$REGION" \
    --member="serviceAccount:$(account_email "$RELEASE_ACCOUNT")" \
    --role=roles/artifactregistry.writer \
    --quiet >/dev/null
}

ensure_backend_secrets() {
  local secret existing

  for secret in NAVITIA_API_KEY ADMIN_API_KEY; do
    existing="$(gcloud secrets list \
      --project="$PROJECT_ID" \
      --filter="name=projects/$PROJECT_NUMBER/secrets/$secret" \
      --format='value(name)')"

    if [[ -z "$existing" ]]; then
      gcloud secrets create "$secret" \
        --project="$PROJECT_ID" --replication-policy=automatic --quiet
    fi

    gcloud secrets add-iam-policy-binding "$secret" \
      --project="$PROJECT_ID" \
      --member="serviceAccount:$(account_email "$BACKEND_ACCOUNT")" \
      --role=roles/secretmanager.secretAccessor \
      --quiet >/dev/null
  done
}

grant_deployer_permissions() {
  local runtime deployer release
  release="$(account_email "$RELEASE_ACCOUNT")"

  for runtime in "$BACKEND_ACCOUNT" "$FRONTEND_ACCOUNT"; do
    for deployer in "$RELEASE_ACCOUNT" "$PROVISION_ACCOUNT"; do
      gcloud iam service-accounts add-iam-policy-binding "$(account_email "$runtime")" \
        --project="$PROJECT_ID" \
        --member="serviceAccount:$(account_email "$deployer")" \
        --role=roles/iam.serviceAccountUser \
        --quiet >/dev/null
    done
  done

  gcloud iam service-accounts add-iam-policy-binding "$release" \
    --project="$PROJECT_ID" \
    --member="serviceAccount:$release" \
    --role=roles/iam.serviceAccountOpenIdTokenCreator \
    --quiet >/dev/null

  project_role "$release" roles/serviceusage.serviceUsageConsumer
  project_role "$release" roles/browser
}

provision_resources() {
  local config_path="$1"

  enable_resource_apis
  ensure_service_account "$BACKEND_ACCOUNT"
  ensure_service_account "$FRONTEND_ACCOUNT"
  ensure_graph_bucket
  ensure_image_registry
  ensure_backend_secrets
  grant_deployer_permissions
  bash "$DEPLOY_DIR/alerts.sh" "$config_path"

  echo "Resources ready. Populate secrets and push initial images, then run the services phase."
}

require_secret_versions() {
  local secret version

  for secret in NAVITIA_API_KEY ADMIN_API_KEY; do
    version="$(gcloud secrets versions list "$secret" \
      --project="$PROJECT_ID" \
      --filter='state=ENABLED' \
      --format='value(name)' \
      --limit=1)"
    [[ -n "$version" ]] || die "Add an enabled version to $secret before provisioning services"
  done
}

restrict_backend_invokers() {
  local policy member present identity

  policy="$(gcloud run services get-iam-policy "$BACKEND_SERVICE" \
    --project="$PROJECT_ID" --region="$REGION" --format=json)"

  for member in allUsers allAuthenticatedUsers; do
    present="$(printf '%s' "$policy" | "$PYTHON" -c '
import json
import sys

policy = json.load(sys.stdin)
member = sys.argv[1]
print(any(
    binding["role"] == "roles/run.invoker" and member in binding.get("members", [])
    for binding in policy.get("bindings", [])
))
' "$member")"

    if [[ "$present" == True ]]; then
      gcloud run services remove-iam-policy-binding "$BACKEND_SERVICE" \
        --project="$PROJECT_ID" --region="$REGION" \
        --member="$member" --role=roles/run.invoker --quiet >/dev/null
    fi
  done

  for identity in "$FRONTEND_ACCOUNT" "$RELEASE_ACCOUNT"; do
    gcloud run services add-iam-policy-binding "$BACKEND_SERVICE" \
      --project="$PROJECT_ID" --region="$REGION" \
      --member="serviceAccount:$(account_email "$identity")" \
      --role=roles/run.invoker --quiet >/dev/null
  done
}

grant_release_service_access() {
  local service

  for service in "$BACKEND_SERVICE" "$FRONTEND_SERVICE"; do
    gcloud run services add-iam-policy-binding "$service" \
      --project="$PROJECT_ID" --region="$REGION" \
      --member="serviceAccount:$(account_email "$RELEASE_ACCOUNT")" \
      --role=roles/run.developer --quiet >/dev/null
  done
}

provision_services() {
  local backend_image="$1" frontend_image="$2" backend_url

  validate_images "$backend_image" "$frontend_image"
  require_secret_versions

  deploy_backend "$backend_image" \
    --ingress=all --no-allow-unauthenticated --min=0 --max=2
  restrict_backend_invokers
  backend_url="$(service_url "$BACKEND_SERVICE")"

  deploy_frontend "$frontend_image" "$backend_url" \
    --ingress=all --allow-unauthenticated --min=0 --max=3
  grant_release_service_access

  echo "Services ready. Run the release workflow and inspect smoke tests."
}

main() {
  local config_path="${1:?Usage: provision.sh CONFIG resources|services [BACKEND_DIGEST FRONTEND_DIGEST]}"
  local phase="${2:?resources or services required}"

  case "$phase" in
    resources|services) ;;
    *) die "Unknown provisioning phase: $phase" ;;
  esac

  load_config "$config_path"
  require_gcloud

  case "$phase" in
    resources) provision_resources "$config_path" ;;
    services) provision_services "${3:?Backend digest required}" "${4:?Frontend digest required}" ;;
  esac
}

main "$@"
