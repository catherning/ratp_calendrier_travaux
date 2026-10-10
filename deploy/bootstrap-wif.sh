#!/usr/bin/env bash
# Run as an authorized local administrator, never through the WIF being created.
source "$(dirname -- "$0")/common.sh"

enable_identity_apis() {
  gcloud services enable \
    iam.googleapis.com \
    iamcredentials.googleapis.com \
    sts.googleapis.com \
    cloudresourcemanager.googleapis.com \
    serviceusage.googleapis.com \
    cloudbilling.googleapis.com \
    billingbudgets.googleapis.com \
    --project="$PROJECT_ID" --quiet
}

ensure_identity_pool() {
  local existing

  existing="$(gcloud iam workload-identity-pools list \
    --project="$PROJECT_ID" \
    --location=global \
    --filter="name=projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/$WIF_POOL AND state=ACTIVE" \
    --format='value(name)')"

  if [[ -z "$existing" ]]; then
    gcloud iam workload-identity-pools create "$WIF_POOL" \
      --project="$PROJECT_ID" --location=global \
      --display-name="GitHub deployment" --quiet
  fi
}

ensure_github_provider() {
  local existing condition mapping action
  local -a provider_args

  condition="assertion.repository == '$GITHUB_REPOSITORY'"
  condition+=" && assertion.ref == 'refs/heads/$GITHUB_BRANCH'"
  condition+=" && (assertion.environment == 'production' || assertion.environment == 'provisioning')"
  mapping="google.subject=assertion.sub"
  mapping+=",attribute.repository=assertion.repository"
  mapping+=",attribute.environment=assertion.environment"

  existing="$(gcloud iam workload-identity-pools providers list \
    --project="$PROJECT_ID" \
    --location=global \
    --workload-identity-pool="$WIF_POOL" \
    --filter="name=projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/$WIF_POOL/providers/$WIF_PROVIDER AND state=ACTIVE" \
    --format='value(name)')"

  action=update-oidc
  if [[ -z "$existing" ]]; then
    action=create-oidc
  fi

  provider_args=(
    --project="$PROJECT_ID"
    --location=global
    --workload-identity-pool="$WIF_POOL"
    --issuer-uri=https://token.actions.githubusercontent.com
    --attribute-mapping="$mapping"
    --attribute-condition="$condition"
    --quiet
  )
  gcloud iam workload-identity-pools providers "$action" "$WIF_PROVIDER" "${provider_args[@]}"
}

grant_environment_identity() {
  local account="$1" environment="$2" subject principal

  subject="repo:$GITHUB_REPOSITORY:environment:$environment"
  principal="principal://iam.googleapis.com/projects/$PROJECT_NUMBER"
  principal+="/locations/global/workloadIdentityPools/$WIF_POOL/subject/$subject"

  gcloud iam service-accounts add-iam-policy-binding "$(account_email "$account")" \
    --project="$PROJECT_ID" \
    --role=roles/iam.workloadIdentityUser \
    --member="$principal" \
    --quiet >/dev/null
}

grant_provisioner_roles() {
  local provision role
  local -a roles=(
    roles/serviceusage.serviceUsageAdmin
    roles/run.admin
    roles/iam.serviceAccountAdmin
    roles/resourcemanager.projectIamAdmin
    roles/storage.admin
    roles/artifactregistry.admin
    roles/secretmanager.admin
    roles/monitoring.editor
    roles/serviceusage.serviceUsageConsumer
    roles/browser
  )
  provision="$(account_email "$PROVISION_ACCOUNT")"

  for role in "${roles[@]}"; do
    project_role "$provision" "$role"
  done

  gcloud billing accounts add-iam-policy-binding "$BILLING_ACCOUNT" \
    --member="serviceAccount:$provision" \
    --role=roles/billing.costsManager \
    --quiet >/dev/null
}

main() {
  local config_path="${1:?Usage: bootstrap-wif.sh CONFIG}"

  load_config "$config_path"
  require_gcloud
  enable_identity_apis
  ensure_service_account "$RELEASE_ACCOUNT"
  ensure_service_account "$PROVISION_ACCOUNT"
  ensure_identity_pool
  ensure_github_provider
  grant_environment_identity "$RELEASE_ACCOUNT" production
  grant_environment_identity "$PROVISION_ACCOUNT" provisioning
  grant_provisioner_roles

  echo "WIF configured. Review environment protections before running workflows."
}

main "$@"
