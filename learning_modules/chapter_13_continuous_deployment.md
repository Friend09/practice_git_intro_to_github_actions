# Chapter 13: Continuous Deployment: Environments and OIDC

**Reading Time:** ~60 minutes
**Prerequisites:** Chapter 08 (environments, secrets), Chapter 10 (`needs`), Chapter 12 (publishing an image)
**Practice Notebook:** `notebooks/practice_13.ipynb`
**Reference Notebook:** `notebooks/lab_13_continuous_deployment.ipynb`
**Script:** `labs/lab_13_continuous_deployment.py`
**Book Reference:** Laster, Learning GitHub Actions Ch 6, 9 / GitHub Docs: Deployments and environments, OpenID Connect
**Depth:** Core
**Default Runtime:** Live repo (guarded)

---

## Beginner's Guide

**Focus on first:** Sections 3 (what a deployment record is), 4 (the branch rule that stopped a deploy) and 7 (a real OIDC token, taken apart).

**Skip on first read:** Sections 10-12 (provider setup, claim customization, reusable workflows).

**Key concepts in plain English:**

- **Deployment:** a record GitHub keeps each time a job targets an environment: what, where, when, and how it went.
- **Protection rule:** a gate on an environment (a human approval, an allowed-branches list).
- **OIDC (OpenID Connect):** a way for a job to prove who it is to another system using a short-lived signed token, instead of a stored password.
- **Claim:** one fact inside that token (which repo, which branch, which environment).
- **Trust policy:** the rule on the receiving side that says which claims are allowed in.

**If you have ever stored a cloud access key as a secret**, OIDC replaces it: there is nothing to steal, rotate or leak, because each token lives about five minutes.

> **🔬 Platform Engineer's Lens:** Deployment is the one place a pipeline can hurt production. Two failures matter more than any syntax: a deploy that ran from the wrong branch, and a cloud trust policy that is either impossible to satisfy or too loose. Both are shown here with real tokens and real rejections, including a surprise: for repositories created after 2026-07-15 the token's subject has a **new format** that older tutorials' trust policies silently fail to match.

> **🚦 Native vs Marketplace vs Custom:** Environments, approvals, branch rules and OIDC token issuance are native. The cloud-side half (the trust policy and the role) is the provider's. Use the provider's official credentials action (we pin `aws-actions/configure-aws-credentials` by SHA) rather than scripting the token exchange yourself.

## What You'll Learn

- Read a deployment's status history and know what each state means
- Restrict an environment to specific branches and read the rejection
- Explain what a job must declare to receive an OIDC token
- Decode a real GitHub OIDC token's claims and verify its signature
- Explain why the `sub` claim differs with and without an environment, and why that matters
- Evaluate a cloud trust policy against real claims, including the legacy-format trap
- Guard a cloud-dependent job so it skips until you opt in

## Table of Contents

<!-- TOC -->
- [1. What "Continuous Deployment" Adds](#1-what-continuous-deployment-adds)
- [2. Running Example: A Deploy Workflow with Teeth](#2-running-example-a-deploy-workflow-with-teeth)
- [3. Deployments Are Records](#3-deployments-are-records)
- [4. The Branch Rule](#4-the-branch-rule)
- [5. Why OIDC](#5-why-oidc)
- [6. Asking for a Token](#6-asking-for-a-token)
- [7. A Real Token, Taken Apart](#7-a-real-token-taken-apart)
- [8. The `sub` Claim, Four Ways](#8-the-sub-claim-four-ways)
- [9. Evaluating a Trust Policy](#9-evaluating-a-trust-policy)
- [10. Setting Up a Cloud Provider](#10-setting-up-a-cloud-provider)
- [11. Customizing Claims](#11-customizing-claims)
- [12. Reusable Workflows and `job_workflow_ref`](#12-reusable-workflows-and-job_workflow_ref)
- [13. Case Study: The Policy That Worked Last Year](#13-case-study-the-policy-that-worked-last-year)
- [14. Comparison: Deploy Credentials](#14-comparison-deploy-credentials)
- [15. Practical Tips](#15-practical-tips)
- [16. Demonstrated Failure Modes](#16-demonstrated-failure-modes)
- [17. Key Takeaways](#17-key-takeaways)
- [18. Exercises](#18-exercises)
- [19. Additional Resources](#19-additional-resources)
- [20. Appendix A: Code Index](#20-appendix-a-code-index)
   - [A.1 Evaluate a trust policy against real claims](#a1-evaluate-a-trust-policy-against-real-claims)
   - [A.2 Decode and verify a token (runs inside the job)](#a2-decode-and-verify-a-token-runs-inside-the-job)
<!-- /TOC -->

---

## 1. What "Continuous Deployment" Adds

Chapter 11 ended at a green check. Continuous deployment connects that green check to a change in a live system, and that connection needs three controls: **who may deploy** (approvals), **from where** (branches), and **with what credential** (a secret, or better, an OIDC token). Each has a real, testable mechanism in GitHub, and each gets a live demonstration here.

## 2. Running Example: A Deploy Workflow with Teeth

> 📌 **Running Example: `ch13-deploy.yml`.** Jobs: **deploy_staging** (environment `staging`, with a URL), **deploy_production** (environment `production`, `needs` staging, only when the input `production` is true), **oidc_with_environment** and **oidc_without_environment** (each requests an OIDC token and decodes it), **oidc_without_permission** (checks whether it can get a token), and **deploy_cloud_guarded** (assumes an AWS role, skipped until `vars.GHA_ENABLE_AWS_OIDC` is `true`). The `production` environment has a required reviewer and, for this chapter, a **branch rule allowing only `main`**. Real runs: **37322740443** (main, staging only), **37322900067** (dispatched from branch `demo/ch13` with production on), **37322974953** (main, production approved). Data: `fixtures/deploy_ch13_summary.json`, `fixtures/oidc_ch13_*.json`. We return to them throughout.

## 3. Deployments Are Records

Any job with an `environment:` creates a **deployment** in GitHub, with a status history you can read from the API (`GET /repos/OWNER/REPO/deployments/<id>/statuses`). The real history of the approved production deployment (run 37322974953):

| Time (UTC) | State |
| --- | --- |
| 14:14:15 | `waiting` (pending approval) |
| 14:14:15 | `waiting` |
| 14:14:21 | `queued` (approved; waiting for a runner) |
| 14:14:24 | `in_progress` |
| 14:14:27 | `success`, with environment URL `https://tally.example.invalid` |

The staging deployment: `in_progress` then `success` with `https://tally.example.invalid/staging`. (The REST docs list the states you can *set* as `error`, `failure`, `inactive`, `in_progress`, `pending`, `queued` and `success`; `waiting` is set by the platform itself for approval-gated deployments, and we saw it in the real history.) The first lifecycle step that matters is `waiting`: that is the unbilled approval wait from Chapter 08, now visible as a status.

**What to notice:** the deployments list for the repo is an **audit trail**: environment, ref, SHA and time of every deploy. The API returned entries like `env=production ref=main sha=db38263` and `env=staging ref=demo/ch13 sha=db38263`, so you can answer "what was in production at 14:14?" without reading logs.

One workflow run can create **several** deployments: the run 37322740443 created two for `staging`, one from `deploy_staging` and one from `oidc_with_environment`, because both jobs declare that environment. Every job naming an environment is a deployment.

## 4. The Branch Rule

Chapter 08 gave `production` a required reviewer. We added a **deployment branch rule**: only `main` may deploy there (`custom_branch_policies: true`, one policy named `main`, via `POST /repos/OWNER/REPO/environments/production/deployment-branch-policies`). Then we dispatched the workflow from a feature branch, `demo/ch13`, with `production=true` (run 37322900067):

| Job | Result |
| --- | --- |
| `deploy_staging` | success (staging has no branch rule) |
| `deploy_production` | **failure**, immediately |

The job's annotations:

```
Branch "demo/ch13" is not allowed to deploy to production due to environment protection rules.
The deployment was rejected or didn't satisfy other protection rules.
```

and its deployment status history was just `waiting` then `failure`.

**What to notice:**

- The rejection is **instant** and **no approval was requested**: the branch rule is checked before the reviewer gate. A person is never asked to approve a deploy that could not have gone anyway.
- It is enforced by the **platform on the environment**, not by your workflow YAML. A contributor cannot bypass it by editing the workflow on their branch, which is precisely why it belongs on the environment and not in an `if:`.
- The same workflow file ran on the feature branch (`job_workflow_ref` ended `@refs/heads/demo/ch13`), and staging still deployed from it. Only the environment that carried the rule refused.

Docs (verified 2026-10): an environment can allow no restriction, protected branches only, or selected branch and tag name patterns; required reviewers and wait timers are available on public repos for Free/Pro/Team plans (Chapter 08 table).

## 5. Why OIDC

The traditional way to deploy to a cloud is a long-lived access key stored as a secret (Chapter 08). It can leak (Chapter 08, masking), it must be rotated, and it works from anywhere. **OIDC** removes the stored secret:

```
job ──asks GitHub for a signed token──▶ GitHub (issuer)
job ──presents token──▶ cloud provider ──checks signature + claims against a trust policy──▶ short-lived credentials
```

Nothing long-lived exists. The token is valid for minutes, and the cloud decides whether to trust it by looking at **claims** (which repo, which environment, which branch).

## 6. Asking for a Token

A job gets a token only if it declares `permissions: id-token: write`. Two jobs, same workflow, differing in one line:

| Job | `permissions` | `ACTIONS_ID_TOKEN_REQUEST_URL` | Token request token |
| --- | --- | --- | --- |
| `oidc_with_environment` | `contents: read`, **`id-token: write`** | present | present |
| `oidc_without_permission` | `contents: read` only | **`absent`** | not set |

**What to notice:** without the permission the runner does not even provide the request endpoint. A step that tries to call it fails because the variable is empty, not because GitHub refused a request. Grant `id-token: write` to the **one job** that needs it (Chapter 15 returns to least privilege).

## 7. A Real Token, Taken Apart

`oidc_with_environment` requested a token with `audience=sts.amazonaws.com`, then verified and decoded it with the `PyJWT` library (never printing the token itself). Run 37322740443:

| Check | Result |
| --- | --- |
| Signature algorithm | **RS256** |
| Signature verified against the issuer's published keys (`https://token.actions.githubusercontent.com/.well-known/jwks`) | **valid** |
| Wrong audience (`sts.wrong.example`) | **rejected** (`InvalidAudienceError`) |
| Token with the last 4 signature characters altered | **rejected** (`InvalidSignatureError`) |
| Lifetime (`exp` - `iat`) | **300 seconds** |

The claims that matter:

| Claim | Value |
| --- | --- |
| `iss` | `https://token.actions.githubusercontent.com` |
| `aud` | `sts.amazonaws.com` (we asked for it) |
| `sub` | `repo:Friend09@7501015/practice_git_intro_to_github_actions@1405684500:environment:staging` |
| `repository` | `Friend09/practice_git_intro_to_github_actions` |
| `environment` | `staging` |
| `ref` / `ref_type` | `refs/heads/main` / `branch` |
| `sha` | `db3826321acac1133d5f2430d0ce992dcae306ff` |
| `event_name` | `workflow_dispatch` |
| `runner_environment` | `github-hosted` |
| `job_workflow_ref` | `Friend09/practice_git_intro_to_github_actions/.github/workflows/ch13-deploy.yml@refs/heads/main` |

The token carried **33 claim names** in all, including `actor`, `run_id`, `ref_protected`, `repository_id`, `repository_owner_id`, `workflow_ref` and `job_workflow_sha`.

**What to notice:**

- This is the whole credential. A cloud checks (1) the signature against GitHub's public keys, (2) `iss`, (3) `aud`, then (4) your conditions on `sub` and other claims. We reproduced all four steps with no cloud account.
- A token for audience `sts.amazonaws.com` is **useless to anything else**: the wrong-audience test is why you cannot replay it elsewhere.
- Five minutes of validity is the entire window if one leaks into a log.

> 📝 **Full implementation:** See [Appendix A.1](#a1-evaluate-a-trust-policy-against-real-claims)

## 8. The `sub` Claim, Four Ways

The `sub` is what trust policies usually key on. Same repository, four tokens:

| Where the job ran | Environment? | `sub` (after `repo:Friend09@7501015/practice_git_intro_to_github_actions@1405684500:`) |
| --- | --- | --- |
| `main` | `staging` | `environment:staging` |
| `demo/ch13` | `staging` | `environment:staging` |
| `main` | none | `ref:refs/heads/main` |
| `demo/ch13` | none | `ref:refs/heads/demo/ch13` |

Two facts fall out of the table:

1. **With an environment, the `sub` names the environment and ignores the branch.** The `staging` token from `main` and from `demo/ch13` have an **identical** `sub`; only the separate `ref` claim differs (`refs/heads/main` versus `refs/heads/demo/ch13`). A trust policy that says "environment `production`" therefore trusts **any branch that is allowed to deploy to `production`**. The environment's branch rule (Section 4) is what keeps feature branches out. The two controls work together.
2. **Without an environment, the `sub` names the ref.** A policy on `ref:refs/heads/main` then pins the branch directly.

**The new format.** The prefix `repo:OWNER@OWNER_ID/REPO@REPO_ID` includes the numeric IDs (`7501015`, `1405684500`). Docs (verified 2026-10): repositories created after **2026-07-15** use "an immutable default subject format that includes owner and repository IDs". This repository was created on 2026-10-05 and shows exactly that. The older format was `repo:OWNER/REPO:...` with names only. IDs do not change if a repo is renamed or re-created under the same name, which closes a class of name-reuse attacks.

## 9. Evaluating a Trust Policy

A cloud's trust policy is a set of conditions on claims. Our teaching model (`intro_gha/oidc.py`, tested in `tests/test_oidc.py`) applies conditions the way an IAM `StringLike` does, with `*` as a wildcard. Against the real claims above:

| Policy (`sub` condition) | Token | Result | Why |
| --- | --- | --- | --- |
| `...:environment:production` | staging token | **denied** | subject does not match |
| `repo:Friend09/practice_git_intro_to_github_actions:environment:staging` (**legacy format**) | staging token | **denied** | the legacy name-only format never matches the new ID format |
| `...:ref:refs/heads/main` | no-environment token on `main` | allowed | exact match |
| `...:ref:refs/heads/main` | no-environment token on `demo/ch13` | denied | different ref |
| `repo:Friend09@7501015/practice_git_intro_to_github_actions@1405684500:*` | any token from this repo | allowed | the wildcard accepts every ref and environment |
| any `sub` | token with the wrong `aud` | denied | audience is checked first |

**What to notice:**

- **The legacy-format trap** is the practical danger. A trust policy copied from a 2024 tutorial uses `repo:OWNER/REPO:...`. On a repo created after 2026-07-15 it will **never match**. The deploy fails at the cloud with an authorization error that mentions nothing about format. (This table is our simulation; the provider's real error text is its own.)
- **A trailing `*` is a wide-open door.** It trusts every branch, tag and environment, including a throwaway feature branch.
- Check **both** `aud` and `sub`. A policy on `sub` alone accepts a token minted for a different audience.

## 10. Setting Up a Cloud Provider

> ⚠️ ADVANCED TOPIC: Skip on first read.

On the cloud side you (1) register GitHub's issuer (`https://token.actions.githubusercontent.com`) as a trusted identity provider, (2) create a role whose trust policy lists the `aud` and the `sub` patterns you want, and (3) give that role only the permissions the deploy needs. In the workflow, the provider's official action exchanges the token for short-lived credentials. Ours is `deploy_cloud_guarded`: `aws-actions/configure-aws-credentials` at v6.3.0 (`node24`), **pinned to its commit SHA** `e1253824e5c10ff9df46874f81ed3ec929e19cfd` (Chapter 04, Chapter 16). It needs an AWS account only you can create, so it is guarded:

```yaml
deploy_cloud_guarded:
  if: ${{ vars.GHA_ENABLE_AWS_OIDC == 'true' }}
  environment: production
  permissions: { contents: read, id-token: write }
```

In the real run it was **skipped**. To opt in: create the role, then `gh variable set GHA_ENABLE_AWS_OIDC --body true` and `gh variable set AWS_ROLE_ARN --body <arn>`. Never commit a role ARN's trust policy with a `*` wider than you intend.

## 11. Customizing Claims

> ⚠️ ADVANCED TOPIC: Skip on first read.

GitHub documents ways to customize the subject claim, and cloud providers can match on more than `sub`: for example `job_workflow_ref`, which names the exact workflow file and ref and so can pin trust to one reviewed workflow. We observed `job_workflow_ref` in the token but did not test customization or provider-side matching on it, so consult the docs for the syntax.

## 12. Reusable Workflows and `job_workflow_ref`

> ⚠️ ADVANCED TOPIC: Skip on first read.

The `job_workflow_ref` claim names the workflow file a job runs from. When a job runs through a reusable workflow (Chapter 20) it is documented to identify the **called** workflow, which would let a platform team say "only the approved deploy workflow may assume this role". We did not test the reusable-workflow case.

## 13. Case Study: The Policy That Worked Last Year

A platform team keeps a Terraform module that creates a deploy role with `sub = "repo:acme/webapp:environment:production"`. For years it worked. In October a new repository `acme/payments` is created, and its first production deploy fails with `Not authorized to perform sts:AssumeRoleWithWebIdentity`. The role, the permissions and the workflow are all correct; the **subject format** is not: the new repo's token says `repo:acme@<id>/payments@<id>:environment:production`. The module is updated to build the `sub` from the owner and repo **IDs**. The lesson: when a trust policy fails, **print the token's real `sub`** (as `oidc_with_environment` does) and compare it character by character. (This case is constructed from the format change we observed; the AWS error string is the provider's usual wording, which we did not reproduce.)

## 14. Comparison: Deploy Credentials

| Credential | Setup Effort | Control | Failure Visibility | Security Exposure | Maintenance Burden |
| --- | --- | --- | --- | --- | --- |
| Long-lived key as repository secret | Minimal - paste a key | Weak - works from any job | Weak - hard to see who used it | Very High - leakable, never expires | High - manual rotation |
| Key as environment secret | Low - per environment | Moderate - gated by environment rules | Moderate - deployments are logged | High - still long-lived | High - manual rotation |
| OIDC with environment `sub` | Moderate - cloud trust setup | Strong - per environment | Strong - cloud audit plus deployments | Low - 5-minute token, no stored secret | Low |
| OIDC pinned to `ref` or `job_workflow_ref` | Moderate-High - precise policy | Excellent - one workflow, one branch | Strong | Low | Low - until formats change |

## 15. Practical Tips

- Put branch rules and reviewers on the **environment**, never only in the YAML.
- Grant `id-token: write` to the single job that needs a token.
- Pin the cloud trust policy on **both** `aud` and `sub`; avoid a trailing `*`.
- When a trust policy fails, print the token's `sub` and compare it to the policy.
- Use IDs-format subjects for any repo created after 2026-07-15.
- Give every environment a URL; it shows up on the deployment and the run.
- Treat the deployments list as your audit trail; export it if compliance asks.

## 16. Demonstrated Failure Modes

**Failure 1: the wrong branch.** Run 37322900067: `Branch "demo/ch13" is not allowed to deploy to production due to environment protection rules.` Instant, with no approval request. This is the control **working**.

**Failure 2: no token without the permission.** `oidc_without_permission` saw `ACTIONS_ID_TOKEN_REQUEST_URL` as `absent`. Fix: `permissions: id-token: write` on that job.

**Failure 3: the trust policy that cannot match.** The legacy-format `sub` pattern is denied against the real token (Section 9). Fix: build the pattern from IDs, or copy the real `sub` from a decoded token.

**Failure 4: the environment `sub` that ignores the branch.** The staging token from `demo/ch13` is **identical in `sub`** to the one from `main` (Section 8). If `production` had no branch rule, a feature branch could mint a production token. Fix: the branch rule, or a ref- or `job_workflow_ref`-based condition.

**Failure 5: the wildcard.** `repo:...@1405684500:*` allows `demo/ch13`'s token. Fix: enumerate exact subjects.

## 17. Key Takeaways

- Every job with an `environment:` creates a deployment with a status history (`waiting`, `queued`, `in_progress`, `success` or `failure`).
- An environment branch rule rejects a deploy instantly, before any approval, and cannot be bypassed from the YAML.
- OIDC gives a job a signed, five-minute token; there is no stored credential to steal.
- A job gets a token only with `permissions: id-token: write`.
- Clouds verify the signature, `iss`, `aud`, then your conditions on `sub`.
- With an environment the `sub` names the environment, not the branch; without one it names the ref.
- Repos created after 2026-07-15 use an ID-based `sub`; legacy-format policies never match.
- Guard cloud-dependent jobs with a variable so they skip until you opt in.

## 18. Exercises

1. In Section 3's history, which state is the unbilled approval wait, and what moved the deployment out of it?
2. A feature branch runs `deploy_production` and the job fails immediately without a reviewer prompt. Which rule did it, and where is it configured?
3. A trust policy requires `sub = repo:Friend09@7501015/practice_git_intro_to_github_actions@1405684500:environment:production`. Does the `staging` token from `main` pass? Does a `production` token from a feature branch pass, assuming no branch rule?
4. Your policy was copied from an old guide: `repo:Friend09/practice_git_intro_to_github_actions:ref:refs/heads/main`. Will a no-environment token from `main` match? Why or why not?
5. (Hand arithmetic) The token's `iat` is 1000 and its lifetime is 300 s. A leaked token is found in a log at `t = 1400`. Is it still valid? What if it is found at `t = 1250`?

<details>
<summary>Answers</summary>

1. `waiting`. An approval by the reviewer moved it to `queued` (then `in_progress`).
2. The **deployment branch rule** on the `production` environment (Settings -> Environments -> production, or the deployment-branch-policies API). It is evaluated before the reviewer gate.
3. The staging token: no (`environment:staging` is not `environment:production`). The production token from a feature branch: **yes**, because the environment `sub` ignores the branch; only the environment's branch rule would stop it.
4. No. The new-format `sub` is `repo:Friend09@7501015/...@1405684500:ref:refs/heads/main`; the legacy pattern has no numeric IDs, so the strings differ.
5. At `t = 1400` it has expired (`exp` = 1300). At `t = 1250` it is still valid for 50 more seconds.

</details>

## 19. Additional Resources

All verified 2026-10.

- GitHub Docs: OpenID Connect in GitHub Actions (concepts and claims) - https://docs.github.com/en/actions/concepts/security/openid-connect
- GitHub Docs: Deployments and environments (protection rules) - https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments
- GitHub REST: Deployment statuses - https://docs.github.com/en/rest/deployments/statuses
- GitHub REST: Deployment branch policies - https://docs.github.com/en/rest/deployments/branch-policies
- OIDC issuer discovery document - https://token.actions.githubusercontent.com/.well-known/openid-configuration
- aws-actions/configure-aws-credentials - https://github.com/aws-actions/configure-aws-credentials
- RFC 7519: JSON Web Token (claims `iss`, `aud`, `sub`, `exp`, `iat`) - https://www.rfc-editor.org/rfc/rfc7519
- Live evidence: runs 37322740443, 37322900067, 37322974953 in this repo
- Laster, *Learning GitHub Actions* (O'Reilly), Chapters 6 and 9

## 20. Appendix A: Code Index

> 💻 Complete, runnable code for this chapter. Skip when reading for concepts.

### A.1 Evaluate a trust policy against real claims

```python
import json
from pathlib import Path

from intro_gha.oidc import immutable_sub, legacy_sub, trust_allows

d = json.loads(Path("fixtures/deploy_ch13_summary.json").read_text())["oidc"]
ISS, AUD = d["issuer"], "sts.amazonaws.com"
staging = {"iss": ISS, "aud": AUD, "sub": d["claims"]["with_environment_main"]["sub"]}

prod_policy = {"iss": ISS, "aud": AUD, "sub": immutable_sub(
    "Friend09", 7501015, "practice_git_intro_to_github_actions", 1405684500,
    "environment:production")}
assert trust_allows(staging, prod_policy) == (False, "subject does not match")

legacy = {"iss": ISS, "aud": AUD, "sub": legacy_sub(
    "Friend09", "practice_git_intro_to_github_actions", "environment:staging")}
assert not trust_allows(staging, legacy)[0]          # the legacy-format trap
assert not trust_allows({**staging, "aud": "sts.wrong"}, prod_policy)[0]
```

**Flow:** check `iss`, then `aud`, then any `sub` pattern (with `*` as a wildcard); all must match. Build subjects from IDs for repositories created after 2026-07-15.

### A.2 Decode and verify a token (runs inside the job)

```python
import json, os, urllib.request
import jwt  # pip install "pyjwt[crypto]"

aud = "sts.amazonaws.com"
url = os.environ["ACTIONS_ID_TOKEN_REQUEST_URL"] + "&audience=" + aud
req = urllib.request.Request(url, headers={
    "Authorization": "bearer " + os.environ["ACTIONS_ID_TOKEN_REQUEST_TOKEN"]})
token = json.load(urllib.request.urlopen(req))["value"]
key = jwt.PyJWKClient(
    "https://token.actions.githubusercontent.com/.well-known/jwks"
).get_signing_key_from_jwt(token).key
claims = jwt.decode(token, key, algorithms=["RS256"], audience=aud,
                    issuer="https://token.actions.githubusercontent.com")
print(claims["sub"])          # never print the token itself
```

**Flow:** request a token for an audience with the runner-provided URL and bearer value -> fetch the issuer's signing key by the token's key id -> verify signature, audience and issuer -> read the claims.
