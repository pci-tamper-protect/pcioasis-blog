---
title: "Setting Up Workload Identity Federation: An Agent-Assisted Rollout"
slug: replacing-gcp-credentials-cicd-wif-setup
date: 2026-04-15
category: secure-devops
series: wif-gcp-cicd
series_part: 2
tags: [gcp, workload-identity-federation, github-actions, iam, service-accounts, claude-code, ai-agents, pci-dss]
author: Kesten Broughton
canonical_url: https://www.pcioasis.com/blog/secure-devops/replacing-gcp-credentials-cicd-wif-setup
---

# Setting Up Workload Identity Federation: An Agent-Assisted Rollout

*Part 2 of 2 — Implementation*

[Part 1](./2026-04-15-replacing-gcp-credentials-in-cicd-with-wif.md) explained the concepts and the three decisions you need to make: where the WIF pool lives, whether to use branch or environment conditions, and who approves production deploys.

This post walks through the actual rollout using an AI coding agent (Claude Code) to examine your existing infrastructure, propose a plan, and execute it step by step — with you reviewing and approving at every decision point. The agent handles the mechanical work. You make the security decisions.

---

## Why Use an Agent Instead of Running Scripts Directly?

Scripts encode a fixed procedure. Agents can examine what's actually there before proposing what to do.

For a WIF rollout, your existing GCP org structure determines almost everything: where the pool should live, which projects need service accounts, what the current IAM policies look like, and what might break if you change them. Running a script without understanding your current state is how you create IAM drift.

The approach here:
1. **Examine** — agent reads your existing GCP org, projects, and IAM
2. **Plan** — agent proposes a WIF setup based on what it found
3. **Review** — you read the plan and correct any wrong assumptions
4. **Execute** — agent runs the commands step by step, pausing at the critical ones

The critical steps — IAM bindings and GitHub Environment configuration — are ones where you should read exactly what is being set before it happens.

---

## Prerequisites

Before starting, confirm you have:

- `gcloud` CLI authenticated: `gcloud auth list`
- `gh` CLI authenticated: `gh auth status`
- Org-level or folder-level GCP IAM permissions (to create the WIF pool)
- GitHub admin access to the repos you're migrating

If `gcloud auth list` shows no accounts, run:
```
gcloud auth login
gcloud auth application-default login
```

---

## Phase 1: Examine Your Existing Infrastructure

Give the agent this prompt to map what you have before proposing any changes.

> **Agent prompt — Phase 1: Examine**
>
> I want to set up Workload Identity Federation (WIF) for GitHub Actions across our GCP org, replacing FIREBASE_TOKEN-based Firebase deployments.
>
> Before proposing anything, examine our existing infrastructure:
>
> 1. Run `gcloud organizations list` and `gcloud resource-manager folders list --organization=ORG_ID` to map the folder hierarchy
> 2. Run `gcloud projects list --format="table(projectId,parent.id,parent.type)"` to see all projects and which folder they belong to
> 3. For the operations/shared project (look for one named like `ops-*` or `*-global`), check whether a WIF pool already exists: `gcloud iam workload-identity-pools list --location=global --project=OPS_PROJECT`
> 4. For each project that has Firebase resources (look for `ui-firebase-*` or similar), check existing service accounts: `gcloud iam service-accounts list --project=PROJECT_ID`
> 5. Check our GitHub Actions workflows: read all `.github/workflows/*.yml` files in the current repo and identify which ones use `FIREBASE_TOKEN` or `GCP_SA_KEY`
>
> Report back with:
> - The folder hierarchy as a tree
> - Which projects exist and their purpose (infer from naming)
> - Whether a WIF pool already exists anywhere
> - Which workflows need to be migrated and to which GCP projects they deploy
> - Any existing service accounts that might be reusable
>
> Do not make any changes yet. This is a read-only survey.

**What to look for in the agent's report:**

Read the folder tree carefully. The WIF pool should live in the project that is already your shared infrastructure hub. If the agent identifies a project named something like `ops-*-global`, that is almost certainly the right home. If multiple projects could host the pool, ask the agent to explain the tradeoffs before you decide.

---

## Phase 2: Propose a Plan

Once you have the survey, give the agent this prompt.

> **Agent prompt — Phase 2: Plan**
>
> Based on the infrastructure survey, propose a WIF setup plan. The plan should:
>
> 1. Identify which GCP project will host the single shared WIF pool and explain why
> 2. List every (GitHub repo, GCP project, environment) triple that needs a service account and IAM binding — format as a table
> 3. For each binding, write out the exact attribute condition that will be set (using GitHub Environments, not branch conditions — we want approval gates on prd)
> 4. List the minimum IAM roles needed on each service account for Firebase Functions deployment
> 5. List which GitHub repos need `stg` and `prd` environments created
> 6. Identify any existing service accounts or bindings that would conflict with or be replaced by this setup
>
> Format the plan as numbered steps with the exact `gcloud` and `gh` commands that will be run at each step. For each command, include a one-sentence explanation of what it does and why it is necessary.
>
> Do not run any commands yet.

**What to review in the plan:**

The two sections that require your careful review before proceeding:

**IAM bindings table.** Each row should show: service account email, the attribute condition, and what that condition means in plain English. For example:

```
SA: github-deployer@ui-firebase-pcioasis-prd.iam.gserviceaccount.com
Condition: google.subject == "repo:pci-tamper-protect/e-skimming-app:environment:prd"
Meaning: only a GitHub Actions job that declares 'environment: prd'
         in the pci-tamper-protect/e-skimming-app repo can use this SA
```

If any condition is broader than you intend — for example if it's missing the `repository` scope and could be triggered by any repo in your org — correct the plan before proceeding.

**Roles list.** Firebase Functions deployment requires a specific set of roles. The plan should not include `roles/editor` or `roles/owner`. If you see either of those, push back and ask for the minimum required roles.

---

## Phase 3: Adjust the Plan

This is where you take control. Common adjustments:

**If the pool project is wrong:**
> The survey shows `ops-pcioasis-global-470710` as the shared ops project. Use that for the WIF pool, not `pcioasis-operations`.

**If the roles are too broad:**
> Remove `roles/editor`. The service account only needs to deploy Firebase Functions. Find the minimum roles required for `firebase deploy --only functions` and use those instead.

**If a repo deploys to multiple projects:**
> The `e-skimming-app` repo deploys to both `ui-firebase-pcioasis-stg` and `ui-firebase-pcioasis-prd`. Make sure the plan creates separate service accounts in each project with separate bindings, not a single SA with access to both.

**If you want to add a prd reviewer:**
> Add `kesten.broughton@pcioasis.com` as a required reviewer on the prd GitHub Environment. Set `prevent_self_review: true`.

Ask the agent to revise the plan until it accurately reflects your intent. This back-and-forth is the most valuable part of the process — it surfaces assumptions before anything is changed.

---

## Phase 4: Execute — With You at the Controls

Once the plan is approved, execute it in stages. Do not ask the agent to run everything at once.

### Stage A: Create the WIF Pool (run once, low risk)

> **Agent prompt — Stage A**
>
> Execute Step 1 of the plan: create the WIF pool and GitHub OIDC provider in `ops-pcioasis-global-470710`.
>
> Before running each command, print it and its explanation. After running it, print the output and confirm what was created.
>
> If any command fails, stop and explain why before attempting anything else.

Creating the pool is low-risk — it is a new resource that nothing depends on yet. If it goes wrong, you delete it and try again.

After this stage, the agent should print the full provider resource name. **Save this string.** You will need it in every workflow file you update. It looks like:

```
projects/123456789/locations/global/workloadIdentityPools/github-actions-pool/providers/github-oidc
```

### Stage B: Create Service Accounts and IAM Bindings (one repo at a time)

> **Agent prompt — Stage B (one repo)**
>
> Execute the service account and IAM binding steps for the `e-skimming-app` repo only.
>
> For each IAM binding command, print the full command and the condition expression that will be set. Pause and ask me to confirm before running the binding — I want to verify the condition is correct before it takes effect.
>
> After the binding is created, run `gcloud iam service-accounts get-iam-policy SA_EMAIL` and show me the result so I can verify the binding was set correctly.

**Why pause at the binding?** The attribute condition is the security-critical piece. If you set it incorrectly — too broad, wrong subject format, wrong repo — a workflow that should not have access to a service account might get it. Reading the exact condition before it is applied is worth the extra 30 seconds.

The output you should see after a correct prd binding:

```yaml
bindings:
- condition:
    expression: google.subject == "repo:pci-tamper-protect/e-skimming-app:environment:prd"
    title: github-env-prd
  members:
  - principalSet://iam.googleapis.com/projects/.../workloadIdentityPools/github-actions-pool/attribute.repository/pci-tamper-protect/e-skimming-app
  role: roles/iam.workloadIdentityUser
```

If the condition expression does not exactly match what you intended, correct it before moving to the next repo.

### Stage C: Create GitHub Environments

> **Agent prompt — Stage C**
>
> For the `pci-tamper-protect/e-skimming-app` repo, create `stg` and `prd` GitHub Environments using the `gh` CLI.
>
> - stg: no approval required, restricted to the `stg` branch
> - prd: requires approval from kbroughton, restricted to the `main` branch, prevent self-review enabled
>
> Print each `gh api` call before running it. After creating each environment, fetch it back with `gh api repos/pci-tamper-protect/e-skimming-app/environments/ENVIRONMENT_NAME` and show me the configuration so I can verify it matches the intent.

After this stage, verify in the GitHub UI: `https://github.com/pci-tamper-protect/e-skimming-app/settings/environments`. The prd environment should show the required reviewer and the `main` branch restriction. Seeing it in the UI is the confirmation.

### Stage D: Update the Workflow File

> **Agent prompt — Stage D**
>
> Update `.github/workflows/deploy-functions-stg.yml` to use WIF instead of `FIREBASE_TOKEN`.
>
> The changes needed:
> - Add `id-token: write` to the job's `permissions` block (required for WIF)
> - Add `environment: stg` to the job
> - Replace the deploy step with two steps: one `google-github-actions/auth@v2` step using the WIF provider and stg service account, then the firebase deploy step (without `FIREBASE_TOKEN` in env)
>
> Show me the diff before writing the file. Use these values:
> - WIF provider: [paste the provider resource name from Stage A]
> - Service account: github-deployer@ui-firebase-pcioasis-stg.iam.gserviceaccount.com

Review the diff. The key things to confirm:
- `id-token: write` is in `permissions` — without this, GitHub won't issue an OIDC token to the job
- `environment: stg` is on the job, not the step — this gates the OIDC subject
- There is no `FIREBASE_TOKEN` in the updated workflow
- The `google-github-actions/auth@v2` step uses `v2`, not an older version

Once you've reviewed the diff, tell the agent to apply it. Then push the branch and watch the workflow run in GitHub Actions. The auth step should succeed without any stored secrets.

---

## Phase 5: Validate Before Removing the Old Credential

Do not delete `FIREBASE_TOKEN` from your GitHub secrets until you have confirmed the WIF-based workflow succeeds end-to-end.

Run the updated workflow on `stg` and verify:

1. The "Authenticate to GCP (WIF)" step succeeds
2. The `firebase deploy` step succeeds
3. The deployment appears in the Firebase console
4. No errors in the workflow logs referencing `FIREBASE_TOKEN` or authentication

Only after a successful end-to-end run should you remove `FIREBASE_TOKEN` from `Settings → Secrets and variables → Actions`.

---

## Rolling Out Across Multiple Repos

Once you have one repo working, the pattern repeats. For each additional repo, you run Stages B, C, and D — Stage A (the pool) is already done.

> **Agent prompt — Batch rollout**
>
> I have WIF set up for `e-skimming-app`. Now roll out to these additional repos:
> [list repos]
>
> For each repo, follow the same process: create service accounts, set IAM bindings (pause for my confirmation on each binding), create GitHub Environments, and show me the workflow diff before writing it.
>
> Process one repo at a time. Do not move to the next repo until I confirm the current one is working.

The "one repo at a time, confirm before next" discipline matters when rolling out across 20 repos. A mistake in an IAM binding that you catch on repo 2 is much easier to correct than one you don't notice until repo 15.

---

## What You Now Have

After the full rollout:

- **Zero stored credentials** for Firebase deployments — no `FIREBASE_TOKEN`, no service account keys in GitHub secrets
- **Cryptographic isolation** between stg and prd — enforced by GCP's control plane, not by workflow code anyone can edit
- **Human approval gates** on every production deploy, with a timestamped audit log
- **One pool to maintain** regardless of how many repos and projects you add

The agent did the mechanical work. You made the security decisions. That is the right division of labor.

---

*PCI Oasis publishes engineering content for teams building and operating PCI-compliant systems. Posts reflect real implementation decisions, not theoretical compliance frameworks.*
