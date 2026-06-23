---
title: "Migrating from Cloud Build to GitHub Actions with Workload Identity Federation"
slug: migrating-cloud-build-gha-wif
date: 2026-06-23
category: secure-devops
series: wif-gcp-cicd
series_part: 3
tags: [github-actions, workload-identity-federation, gcp, cloud-run, ci-cd, security, pci-dss]
author: Aya Ibrahim Mehjez
canonical_url: https://www.pcioasis.com/blog/secure-devops/migrating-cloud-build-gha-wif
---

# Migrating from Cloud Build to GitHub Actions with Workload Identity Federation

This post documents the migration of `pcioasis-payments` CI/CD from Cloud Build to GitHub Actions using Workload Identity Federation (WIF). It is a concrete implementation record — specific project IDs, script names, and the exact ordering decisions we made — not a general tutorial.

If you want the conceptual background on WIF, read [Part 1](./2026-04-15-replacing-gcp-credentials-in-cicd-with-wif.md) first. This post assumes you understand what WIF does and focuses on how we applied it.

---

## Why We Left Cloud Build

Cloud Build has a meaningful advantage when your pipeline lives entirely inside GCP: the runner is a GCP resource, so it carries a native GCP identity without any credential negotiation. For a small team deploying a single service, that simplicity is real.

The problem is that Cloud Build triggers are configured in the GCP console, not in the repository. When you want to understand what runs on a push to `main`, you look in two places — the workflow code in the repo and the trigger configuration in the console. Those two sources of truth drift. We had cases where the console trigger pointed to a branch that no longer existed, and cases where a `cloudbuild.yaml` was updated in the repo without anyone updating the trigger substitution variables.

GitHub Actions solves this by putting the entire pipeline definition — triggers, steps, environment variables, approval gates — in the repository. One source of truth, reviewed in PRs, visible in the same `git blame` as the application code. For a PCI-scoped system, the auditability difference matters.

The cost of moving to GHA is that runners are outside GCP, so the native identity is gone. You need a mechanism to authenticate them. The wrong answer is a stored service account key. The right answer is WIF.

---

## What We Had Before

Before this migration, `pcioasis-payments` deployed through a Cloud Build trigger in each GCP project (`payments-pcioasis-stg` and `payments-pcioasis-prd`). The Cloud Build SA had the permissions it needed to push images to Artifact Registry and deploy to Cloud Run. No credentials lived in GitHub — Cloud Build's native GCP identity handled everything.

The gaps were:

- **No approval gate on production.** Cloud Build triggers fire immediately on push. There was no human checkpoint before a commit reached `payments-pcioasis-prd`.
- **Pipeline config split across two systems.** The `cloudbuild.yaml` in the repo and the trigger configuration in the console were separate artifacts.
- **No concurrency control.** Two rapid pushes to `main` could produce two simultaneous Cloud Build runs deploying different images to the same Cloud Run service.

---

## The Architecture We Landed On

### Two service accounts per environment

The design uses two distinct identities per environment — one for the CI/CD pipeline, one for the running service:

**Deploy SA** (`github-cloudrun-deploy@<project>.iam.gserviceaccount.com`): used by GitHub Actions during a deploy run. It has exactly the permissions a deploy needs and nothing more:
- `roles/secretmanager.secretAccessor` — to pull the `.env` secret during build
- `roles/artifactregistry.writer` — to push Docker images to Artifact Registry
- `roles/run.admin` — to deploy to Cloud Run

**Runtime SA** (`cloudrun-runtime@<project>.iam.gserviceaccount.com`): attached to the Cloud Run service itself. It carries only the permissions the running application needs — no deploy permissions. The deploy SA is never attached to the live service.

This separation means a compromised deploy credential cannot be used to escalate permissions at runtime, and a compromised runtime credential cannot be used to push new images or trigger deploys.

### One WIF pool, shared across all projects

The Workload Identity Pool lives in a dedicated shared project — `wif-pcioasis-global` — not in either the stg or prd project. Every service account across all projects references the same pool and provider. Adding a new service's deploy SA to WIF does not require creating new pool infrastructure.

```
wif-pcioasis-global (project number: 915700598355)
└── Pool: github-actions-pool
    └── Provider: github-oidc

payments-pcioasis-stg
└── SA: github-cloudrun-deploy@payments-pcioasis-stg   ← WIF binding: env == "stg"
└── SA: cloudrun-runtime@payments-pcioasis-stg

payments-pcioasis-prd
└── SA: github-cloudrun-deploy@payments-pcioasis-prd   ← WIF binding: env == "prd"
└── SA: cloudrun-runtime@payments-pcioasis-prd
```

The WIF binding on each deploy SA is scoped to both the repository (`pci-tamper-protect/pcioasis-payments`) and the GitHub environment (`stg` or `prd`). A job running in the `stg` environment cannot impersonate the prd deploy SA — the attribute condition does not match.

---

## The Setup Scripts

The setup is orchestrated through a small set of numbered shell scripts in `deploy/`. They delegate to shared WIF scripts in the `pcioasis-ops` repository, which contain the generic, reusable infrastructure logic. The numbered scripts provide the per-service configuration.

### `01-setup-env.sh`

Run once per environment to provision all GCP infrastructure:

```bash
./01-setup-env.sh --env stg
./01-setup-env.sh --env prd
```

Internally, this runs two steps in order.

**Step A** — creates the deploy SA and configures its WIF binding:

```bash
bash "$WIF_SCRIPTS/02-create-sa.sh" \
  --sa-name     "github-cloudrun-deploy" \
  --sa-project  "payments-pcioasis-stg" \
  --repo        "pci-tamper-protect/pcioasis-payments" \
  --environment "stg" \
  --pool-project "wif-pcioasis-global" \
  --roles       ".:roles/secretmanager.secretAccessor \
                 .:roles/artifactregistry.writer \
                 .:roles/run.admin"
```

**Step B** — creates the Artifact Registry repository, the runtime SA, and the remaining IAM bindings:

```bash
bash "$WIF_SCRIPTS/03-setup-cloudrun-infra.sh" \
  --project         "payments-pcioasis-stg" \
  --service         "payments-pcioasis-stg" \
  --region          "us-central1" \
  --ar-repo         "payments-pcioasis-stg" \
  --runtime-sa-name "cloudrun-runtime" \
  --deploy-sa       "github-cloudrun-deploy@payments-pcioasis-stg.iam.gserviceaccount.com" \
  --env-var         "ENVIRONMENT=stg"
```

Step A must complete before Step B. The infra script grants the deploy SA `iam.serviceAccountUser` on the runtime SA (required for `gcloud run deploy --service-account`), and that grant fails if the deploy SA does not exist yet.

### `03-set-github-vars.sh`

Sets the WIF provider resource name as a repo-level GitHub Actions variable:

```bash
gh variable set WIF_PROVIDER \
  --body "projects/915700598355/locations/global/workloadIdentityPools/github-actions-pool/providers/github-oidc" \
  --repo "pci-tamper-protect/pcioasis-payments"
```

`WIF_PROVIDER` is a GitHub *variable*, not a secret. The provider resource name is not sensitive — it is a public identifier, and treating it as a secret adds friction without adding security. Both `deploy-stg.yml` and `deploy-prd.yml` read it from `vars.WIF_PROVIDER`, so one variable serves both environments.

### `05-switch-runtime-sa.sh`

Switches the live Cloud Run service to use the dedicated runtime SA:

```bash
./05-switch-runtime-sa.sh --env stg
./05-switch-runtime-sa.sh --env prd
```

This script is deliberately separate from `01-setup-env.sh` and is run only after the new GHA workflow has completed a successful end-to-end deploy. Running it before validation would leave the service operating under the new runtime SA but without a confirmed deploy path — if the first GHA deploy then failed, recovering would require switching the SA back manually.

---

## The Workflows

Both `deploy-stg.yml` and `deploy-prd.yml` follow the same structure. The differences are the trigger branches, the project IDs, the environment name, and the secret name.

```yaml
# deploy-stg.yml (abbreviated for readability)
on:
  push:
    branches: [stg]
  pull_request:
    branches: [stg]

concurrency:
  group: deploy-stg
  cancel-in-progress: false

jobs:
  deploy:
    runs-on: ubuntu-latest
    environment: stg

    permissions:
      contents: read
      id-token: write   # required for WIF OIDC token

    env:
      PROJECT_ID: payments-pcioasis-stg
      REGION: us-central1
      SERVICE: payments-pcioasis-stg
      AR_IMAGE: us-central1-docker.pkg.dev/payments-pcioasis-stg/payments-pcioasis-stg/payments-pcioasis-stg
      RUNTIME_SA: cloudrun-runtime@payments-pcioasis-stg.iam.gserviceaccount.com

    steps:
      - uses: actions/checkout@v4

      - name: Authenticate to GCP
        uses: google-github-actions/auth@v2
        with:
          workload_identity_provider: ${{ vars.WIF_PROVIDER }}
          service_account: github-cloudrun-deploy@payments-pcioasis-stg.iam.gserviceaccount.com

      - uses: google-github-actions/setup-gcloud@v2

      - name: Configure Docker for Artifact Registry
        run: gcloud auth configure-docker ${{ env.REGION }}-docker.pkg.dev --quiet

      - name: Read env secret
        run: |
          gcloud secrets versions access latest \
            --secret=ENV \
            --project=${{ env.PROJECT_ID }} > .env

      - name: Build image
        run: |
          docker build \
            -t ${{ env.AR_IMAGE }}:${{ github.sha }} \
            -t ${{ env.AR_IMAGE }}:latest \
            .

      - name: Push image
        run: |
          docker push ${{ env.AR_IMAGE }}:${{ github.sha }}
          docker push ${{ env.AR_IMAGE }}:latest

      - name: Deploy to Cloud Run
        run: |
          gcloud run deploy ${{ env.SERVICE }} \
            --image ${{ env.AR_IMAGE }}:${{ github.sha }} \
            --platform managed \
            --region ${{ env.REGION }} \
            --service-account ${{ env.RUNTIME_SA }} \
            --set-env-vars ENVIRONMENT=stg \
            --allow-unauthenticated \
            --project ${{ env.PROJECT_ID }} \
            --quiet

      - name: Show service URL
        run: |
          gcloud run services describe ${{ env.SERVICE }} \
            --region ${{ env.REGION }} \
            --project ${{ env.PROJECT_ID }} \
            --format "value(status.url)"
```

Production (`deploy-prd.yml`) is identical except:
- Trigger: `push` to `main` only — no `pull_request` trigger
- `environment: prd` — this environment is configured in GitHub to require manual approval before the job runs
- Secret name: `ENV_PRD`
- All resource names use `payments-pcioasis-prd`

**Key decisions in the workflow design:**

`id-token: write` on the job permissions is non-negotiable — GitHub will not issue an OIDC token to a job that does not declare it.

`cancel-in-progress: false` on concurrency means a running deploy always finishes. We do not want a newer push to cancel a deploy that is mid-flight pushing an image to Artifact Registry or mid-way through a `gcloud run deploy`.

The deploy step references `${{ github.sha }}` for the image tag, not `latest`. The running service is pinned to a specific, auditable commit. `latest` is pushed as a convenience tag but is never used in the deploy command itself.

---

## Challenges

### Challenge 1: Provisioning order

The infra setup script (`03-setup-cloudrun-infra.sh`) grants the deploy SA `iam.serviceAccountUser` on the runtime SA. This fails if the deploy SA does not exist when the script runs. The error from `gcloud` is not immediately obvious about the cause — it reports an IAM policy update failure rather than "SA not found."

The fix is in the script design: Step A and Step B are called in sequence within `01-setup-env.sh`, with Step A unconditionally completing before Step B begins. If you run Step B in isolation against a freshly created project (no deploy SA), it will fail. The numbered script convention makes the ordering explicit.

### Challenge 2: Runtime SA switch timing

We provisioned the runtime SA as part of Step B, but initially did not attach it to the live service immediately. The running Cloud Run service was still using the Cloud Build SA's identity.

The `05-switch-runtime-sa.sh` script exists specifically to handle this handoff at the right moment. The comments in the script are direct about the risk: switching the service to the new runtime SA before the GHA workflow has completed a full successful deploy creates a window where the service runs under a new identity but there is no proven path to redeploy it if something needs changing. We validated the workflow end-to-end on staging first, confirmed a successful deploy, and only then ran `05-switch-runtime-sa.sh --env stg`. The same sequence for production.

### Challenge 3: `WIF_PROVIDER` is the same for both environments

Because the pool lives in `wif-pcioasis-global` and not in either environment's project, the full provider resource name is identical for staging and production:

```
projects/915700598355/locations/global/workloadIdentityPools/github-actions-pool/providers/github-oidc
```

This is correct by design — the pool is shared — but it is slightly counterintuitive. The security isolation between stg and prd is not in the provider value. It is in the WIF binding condition on each service account (scoped to `environment:stg` or `environment:prd`) and in the `environment:` declaration on the GHA job. Setting `WIF_PROVIDER` once at repo level rather than per-environment reinforces this: the provider is shared infrastructure, and the per-environment scoping is enforced on the GCP side.

---

## What We Have Now

The complete state after the migration:

| | Before (Cloud Build) | After (GHA + WIF) |
|---|---|---|
| Stored credentials in GitHub | None (Cloud Build was GCP-native) | None |
| Pipeline definition location | `cloudbuild.yaml` + GCP console trigger | `.github/workflows/` only |
| Production approval gate | No | Yes (GitHub environment) |
| Concurrency control | No | Yes (`cancel-in-progress: false`) |
| Deploy SA isolation | Cloud Build SA (shared) | Per-environment, per-repo |
| Runtime SA | Cloud Build SA (same as deploy) | Separate, least-privilege |
| Credential lifetime | N/A (native identity) | 1 hour per workflow run |

No service account keys exist in GitHub secrets. No long-lived credentials of any kind. The `WIF_PROVIDER` variable is not sensitive. Each deploy authenticates by proving what it is — a workflow job in a specific repo running in a specific GitHub environment — and receives credentials that expire when the job ends.

The deploy SA and runtime SA are distinct identities. A compromise of the deploy path cannot be used to escalate runtime permissions, and a compromise of the runtime identity cannot be used to push new images or trigger deploys.

Every production deploy requires a human approval recorded in the GitHub environment audit log: timestamp, commit SHA, and approver identity. That record is available to auditors without any additional instrumentation.

---

## Lessons Learned

This migration took longer than I expected when I first looked at it. WIF, service accounts, IAM bindings, GitHub environments — none of it was familiar territory when I started. I had to read the same GCP documentation pages multiple times before the pieces clicked.

A few things I would tell myself at the start:

**The ordering matters more than the commands.** The hardest part was not writing the scripts — it was understanding why Step A had to run before Step B, and why the runtime SA switch had to happen after a validated deploy. Once I understood the dependency chain, the scripts made sense. Before that, they were just commands I was running and hoping would work.

**Errors are information.** When the infra script failed because the deploy SA didn't exist yet, the error message wasn't obvious about the cause. Learning to read IAM errors — and trace them back to a missing resource or wrong ordering — is a skill in itself. Every failure taught me something about how GCP actually works under the hood.

**Infrastructure is just code with consequences.** I came from frontend and application code. Infrastructure felt different — more permanent, harder to undo. But the same discipline applies: understand what each line does before you run it, review changes before they go to production, and test on staging first. The tools are different; the thinking is the same.

**It gets clearer as you go.** The first time I read about WIF, I didn't understand why it was better than a service account key. By the end of this migration, I could explain the threat model to someone else. That shift — from "running commands" to "understanding why" — is what made this worth the time it took.

The task was harder at the beginning than it looked. It always is. But every piece of infrastructure I didn't understand at the start is something I understand now. That's a good trade.

---

*PCI Oasis publishes engineering content for teams building and operating PCI-compliant systems. Posts reflect real implementation decisions, not theoretical compliance frameworks.*
