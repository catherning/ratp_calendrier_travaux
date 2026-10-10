# Implementation Plan: GitHub Actions CI/CD Deployment to GCP & Vercel

This plan configures a fully automated, secure, and cost-effective GitHub Actions CI/CD pipeline to deploy the FastAPI backend to Google Cloud Run (GCP) and the Next.js frontend to Vercel, ensuring a seamless connection between them.

## Target Architecture

```mermaid
graph TD
    subgraph GitHub Repository
        GHA[GitHub Actions CI/CD]
    end

    subgraph Google Cloud Platform (GCP)
        CR[Cloud Run: ratp-backend]
        AR[Container Registry / Artifact Registry]
        WIF[Workload Identity Federation]
    end

    subgraph Vercel
        V[Vercel: Next.js Frontend]
    end

    GHA -- 1. Authenticate (OIDC/WIF) --> WIF
    GHA -- 2. Push Docker Image --> AR
    GHA -- 3. Deploy Service --> CR
    CR -- 4. Output Service URL --> GHA
    GHA -- 5. Build & Deploy (Inject NEXT_PUBLIC_API_URL) --> V
    V -- 6. Secure HTTPS Calls --> CR
```

---

## User Review Required

### 1. GCP Project & Region Configurations
- **Project ID**: `all-projects-494721`
- **Region**: `us-east1` (Default in GCP config, can be changed to `europe-west9` for low-latency Paris RATP access).
- **Authentication**: Using GCP Workload Identity Federation (WIF). This is highly secure because it eliminates the need to store long-lived service account JSON keys in GitHub Secrets.
- **WIF Provider**: `projects/1048669696258/locations/global/workloadIdentityPools/github-wif/providers/github`
- **GCP Service Account**: `github-actions-deployer@all-projects-494721.iam.gserviceaccount.com`

### 2. Frontend Vercel Configurations
We have designed **two options** for deploying the Next.js frontend:
- **Option 1: Fully Automated GHA Pipeline (Recommended)**
  - GHA deploys the backend, captures its URL, and builds the frontend with this URL injected at build-time.
  - Requires adding Vercel credentials (`VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID`) to GitHub Secrets.
- **Option 2: Decoupled Vercel Dashboard Integration**
  - GHA only deploys the backend. The user links the repository directly to Vercel via Vercel's Web UI and manually inputs the Cloud Run URL in Vercel's Environment Variables dashboard.

---

## Required GitHub Secrets

You will need to configure the following secrets in your GitHub repository (**Settings > Secrets and variables > Actions > Repository secrets**):

| Secret Name | Purpose | How to obtain |
| :--- | :--- | :--- |
| `NAVITIA_API_KEY` | Access Navitia/RATP API from Backend | Provided in local `.env` |
| `VERCEL_TOKEN` | Authenticate GHA with Vercel *(for Option 1)* | [Vercel Tokens Settings](https://vercel.com/account/tokens) |
| `VERCEL_ORG_ID` | Vercel scope/organization ID *(for Option 1)* | Run `vercel login` then copy `orgId` from `.vercel/project.json` or team settings |
| `VERCEL_PROJECT_ID` | Vercel project ID *(for Option 1)* | Run `vercel link` then copy `projectId` from `.vercel/project.json` |

---

## Proposed Changes

We will create a unified GitHub Actions workflow that orchestrates the entire build and deploy pipeline.

### [Component 1] GitHub Actions CI/CD Workflow

#### [NEW] [deploy.yml](file:///\\wsl.localhost\Ubuntu-24.04\home\kaprime\ratp_calendrier_travaux\.github\workflows\deploy.yml)
- Creates the CI/CD pipeline that handles:
  1. Triggering on pushes to `main`, `feat/full-app-revamp` and manual `workflow_dispatch`.
  2. Authenticating with GCP using WIF.
  3. Building the FastAPI Docker image using the root `Dockerfile` and pushing it to GCP Container Registry.
  4. Deploying the image to Google Cloud Run with custom limits (concurrency, max-instances) to keep costs near $0.
  5. Injecting backend environment variables securely.
  6. Extracting the deployed service URL.
  7. *(Optional/Recommended)* Building and deploying the Next.js frontend to Vercel, passing the dynamic backend URL into `NEXT_PUBLIC_API_URL`.

---

## Verification Plan

### Automated Tests
- Verify the GitHub Actions syntax using validation tools.
- Commit and push to `feat/full-app-revamp` branch to trigger the pipeline and monitor run logs in the GitHub repository.

### Manual Verification
- Deploy and verify that the FastAPI backend endpoint returns the transit lines metadata.
- Open the deployed Vercel frontend in a web browser and perform a journey search to verify real-time secure communication with the Cloud Run backend.
