# Chapter 08: Variables, Secrets, Configuration and Environments

**Reading Time:** ~50 minutes
**Prerequisites:** Chapter 03 (`env`), Chapter 07 (contexts and expressions)
**Practice Notebook:** `notebooks/practice_08.ipynb`
**Reference Notebook:** `notebooks/lab_08_variables_secrets_environments.ipynb`
**Script:** `labs/lab_08_variables_secrets_environments.py`
**Book Reference:** Laster, Learning GitHub Actions Ch 6 / GitHub Docs: Variables, Secrets, Deployments and environments
**Depth:** Core
**Default Runtime:** Live repo

---

## Beginner's Guide

**Focus on first:** Sections 3 (three scopes of `env`), 7 (what masking does and does not do) and 9 (the approval gate).

**Skip on first read:** Sections 10-12 (deployment branch rules, OIDC preview, large secrets).

**Key concepts in plain English:**

- **Environment variable (`env`):** a named value inside the run, set in the workflow file. Visible to everyone who can read the file.
- **Variable (`vars`):** a named value stored in GitHub settings, not in the file. Not secret.
- **Secret (`secrets`):** a stored value that GitHub encrypts and hides (`***`) in logs.
- **Environment:** a named deployment target (`staging`, `production`) that can hold its own variables and secrets and can require an approval before a job runs.
- **Mask:** replacing a value with `***` wherever it would appear in a log.

**If you have used a `.env` file**, `vars` and `secrets` are the same idea moved out of the repo and into the platform.

> **🔬 Platform Engineer's Lens:** The failure that costs money here is not a hack. It is a secret that was masked in one form and printed in another. In the run below the secret printed directly as `***` and even as base64 as `***`, but **printed in full when reversed**. Masking is a convenience for accidents, not a security boundary, and a log is forever.

> **🚦 Native vs Marketplace vs Custom:** Native for all of this: variables, secrets, environments and approvals are platform features. Use them instead of committing config files, rolling your own approval bot, or pasting credentials into `env:`. Reach for an external secrets manager (Vault, a cloud store, OIDC; Chapter 13) when you need rotation, audit or short-lived credentials.

## What You'll Learn

- Predict which value an `env` variable has at workflow, job and step scope
- Explain why `GITHUB_ENV` is invisible to the step that writes it but visible to the next
- Read a repository variable and know what a missing one returns
- Show that an environment variable overrides a repository one of the same name
- Explain what secret masking covers and demonstrate a leak and its fix with `::add-mask::`
- Create environments, protect one with a required reviewer, and approve a waiting job
- Describe what is and is not available per plan, and to forked pull requests

## Table of Contents

<!-- toc-start -->

- [Chapter 08: Variables, Secrets, Configuration and Environments](#chapter-08-variables-secrets-configuration-and-environments)
  - [Beginner's Guide](#beginners-guide)
  - [What You'll Learn](#what-youll-learn)
  - [Table of Contents](#table-of-contents)
  - [1. Configuration Has Four Homes](#1-configuration-has-four-homes)
  - [2. Running Example: Config Under a Microscope](#2-running-example-config-under-a-microscope)
  - [3. Three Scopes of `env`](#3-three-scopes-of-env)
  - [4. `GITHUB_ENV`: Writing for the Next Step](#4-github_env-writing-for-the-next-step)
  - [5. Default Variables](#5-default-variables)
  - [6. Variables (`vars`) and Precedence](#6-variables-vars-and-precedence)
  - [7. Secrets and Masking](#7-secrets-and-masking)
    - [What is stored and who sees it](#what-is-stored-and-who-sees-it)
    - [Masking, measured](#masking-measured)
    - [Secrets cannot gate steps](#secrets-cannot-gate-steps)
  - [8. Scope: Repository Secrets vs Environment Secrets](#8-scope-repository-secrets-vs-environment-secrets)
  - [9. Environments and the Approval Gate](#9-environments-and-the-approval-gate)
  - [10. Wait Timers and Deployment Branches](#10-wait-timers-and-deployment-branches)
  - [11. A Preview of OIDC](#11-a-preview-of-oidc)
  - [12. Large and Structured Secrets](#12-large-and-structured-secrets)
  - [13. Case Study: The Base64 "Hiding Place"](#13-case-study-the-base64-hiding-place)
  - [14. Comparison: Where to Keep a Value](#14-comparison-where-to-keep-a-value)
  - [15. Practical Tips](#15-practical-tips)
  - [16. Demonstrated Failure Modes](#16-demonstrated-failure-modes)
  - [17. Key Takeaways](#17-key-takeaways)
  - [18. Exercises](#18-exercises)
  - [19. Additional Resources](#19-additional-resources)
  - [20. Appendix A: Code Index](#20-appendix-a-code-index)
    - [A.1 The environment and mask checks](#a1-the-environment-and-mask-checks)
    - [A.2 Resolve `env` scope](#a2-resolve-env-scope)

---

## 1. Configuration Has Four Homes

A value your workflow needs can live in four places, and the choice decides who can see it, who can change it and how safe it is. The four, from most visible to least:

| Home                                | Where it is set                | Visible in logs | Who can read it                      |
| ----------------------------------- | ------------------------------ | --------------- | ------------------------------------ |
| `env:` in the file                  | the YAML                       | yes             | anyone who can read the repo         |
| `vars`                              | Settings, or `gh variable set` | yes             | anyone who can run the workflow      |
| `secrets`                           | Settings, or `gh secret set`   | masked as `***` | the job that receives it             |
| Environment-scoped `vars`/`secrets` | the environment's settings     | as above        | only jobs that name that environment |

We test each against real runs, because the interesting behavior is in the exceptions.

## 2. Running Example: Config Under a Microscope

> 📌 **Running Example: two workflows and a handful of settings.** Settings we created on this repo: a **repository variable** `TALLY_COLOR=blue`; a **repository secret** `DEMO_SECRET` (a dummy 23-character value, since deleted); an environment **`staging`** with its own `TALLY_COLOR=green` and its own secret `STAGING_ONLY` (18 characters); and an environment **`production`** that requires me as a reviewer. Workflow `ch08-config.yml` (run **37317079828**) prints values at every scope. Workflow `ch08-environments.yml` (run **37317091672**) deploys to `staging` then `production`. Data: `fixtures/config_ch08_run.json`, `fixtures/environments_ch08_run.json`. We return to them in every section.

## 3. Three Scopes of `env`

`ch08-config.yml` sets `SCOPE` at the workflow level (`workflow`), again at the job level (`job`), and again on one step (`step`). What each place read:

| Where the `echo` ran                                        | `$SCOPE` printed |
| ----------------------------------------------------------- | ---------------- |
| a step in a job with its own `SCOPE: job`, no step override | `job`            |
| a step with `env: SCOPE: step` in that job                  | `step`           |
| a step in another job with **no** `SCOPE` of its own        | `workflow`       |

**What to notice:** the **closest** definition wins: step beats job beats workflow. The workflow-level value was still available (`workflow`) in the job that did not override it. Overriding is local: the step override did not change the value seen by later steps.

## 4. `GITHUB_ENV`: Writing for the Next Step

A step cannot set a shell variable for later steps just by `export`, because every step is a new shell. The supported way is to append `NAME=value` to the file whose path is in `$GITHUB_ENV`:

```bash
echo "FROM_FILE=written-by-previous-step" >> "$GITHUB_ENV"
```

Real results:

| Where                                                                | What it saw                |
| -------------------------------------------------------------------- | -------------------------- |
| The **same** step, reading `${FROM_FILE:-unset}` right after writing | `unset`                    |
| The **next** step, `$FROM_FILE` in the shell                         | `written-by-previous-step` |
| The next step, `${{ env.FROM_FILE }}` as an expression               | `written-by-previous-step` |

**What to notice:** the write takes effect **after** the step finishes. Within the writing step the shell variable does not exist yet. The `env` context is updated between steps too, so both forms see it in the next step.

## 5. Default Variables

Every run gets variables you did not set. Real values from the run:

| Variable            | Value                                                                                         |
| ------------------- | --------------------------------------------------------------------------------------------- |
| `CI`                | `true`                                                                                        |
| `GITHUB_ACTIONS`    | `true`                                                                                        |
| `GITHUB_REPOSITORY` | `Friend09/practice_git_intro_to_github_actions`                                               |
| `GITHUB_EVENT_NAME` | `workflow_dispatch`                                                                           |
| `RUNNER_OS`         | `Linux`                                                                                       |
| `GITHUB_WORKSPACE`  | `/home/runner/work/practice_git_intro_to_github_actions/practice_git_intro_to_github_actions` |

Use `CI=true` and `GITHUB_ACTIONS=true` to make scripts behave differently in CI than on a laptop.

## 6. Variables (`vars`) and Precedence

**Set and read.** `gh variable set TALLY_COLOR --body blue` creates a repository variable. The workflow reads it as `${{ vars.TALLY_COLOR }}`. Results:

| Expression                                              | Value printed           |
| ------------------------------------------------------- | ----------------------- |
| `vars.TALLY_COLOR` (repo, in a job with no environment) | `blue`                  |
| `vars.DOES_NOT_EXIST`                                   | empty (printed as `[]`) |
| `vars.TALLY_COLOR` in a job with `environment: staging` | `green`                 |

Docs (verified 2026-10): an unset variable returns an empty string, which our run confirmed.

**Precedence, observed.** The same name `TALLY_COLOR` exists at two levels: repository (`blue`) and environment `staging` (`green`). The job that declared `environment: staging` read `green`; the job without an environment read `blue`. **The environment value overrides the repository value** for jobs that use that environment. (We did not test organization-level variables, and the docs' variables page does not state a precedence rule for all three levels, so do not assume one.)

**Setting an environment variable from the CLI:**

```bash
gh variable set TALLY_COLOR --body green --env staging
```

## 7. Secrets and Masking

### What is stored and who sees it

`gh secret set DEMO_SECRET --body "..."` stores an encrypted secret. A workflow gets it only if the step or job asks for it: `env: DEMO_SECRET: ${{ secrets.DEMO_SECRET }}`. Docs (verified 2026-10): with the exception of `GITHUB_TOKEN`, **secrets are not passed to the runner when a workflow is triggered from a forked repository**.

### Masking, measured

The dummy secret was `tally-demo-s3cret-VALUE` (23 characters). The real log lines:

| What the step printed                                  | What the log showed                        |
| ------------------------------------------------------ | ------------------------------------------ |
| `echo "$DEMO_SECRET"`                                  | `***`                                      |
| `${#DEMO_SECRET}` (the length)                         | `23`                                       |
| the secret **base64-encoded**                          | `***`                                      |
| the secret **reversed** (`rev`)                        | `EULAV-terc3s-omed-yllat` (**plain text**) |
| the reversed value after `echo "::add-mask::$derived"` | `***`                                      |

**What to notice:**

- The runner masks the secret itself, and, as we observed, at least its base64 form. It does **not** know about arbitrary transformations: the reversed secret printed in full.
- The leak and the fix are the same value. `derived_before_mask` printed `EULAV-terc3s-omed-yllat`; after `::add-mask::EULAV-terc3s-omed-yllat` the identical `echo` printed `***`. Docs (verified 2026-10): mask derived values with `::add-mask::VALUE`.
- Even the length printed. Masking hides the value, not facts about it.

> 📝 **Full implementation:** See [Appendix A.1](#a1-the-environment-and-mask-checks)

### Secrets cannot gate steps

`actionlint` rejects `if: secrets.DEMO_SECRET != ''`:

```
context "secrets" is not allowed here. available contexts are "env", "github",
"inputs", "job", "matrix", "needs", "runner", "steps", "strategy", "vars".
```

Docs (verified 2026-10): "consider setting secrets as job-level environment variables, then referencing the environment variables to conditionally run steps." That is exactly the pattern in our workflow (`env: DEMO_SECRET: ${{ secrets.DEMO_SECRET }}`), after which `if: env.DEMO_SECRET != ''` is allowed.

## 8. Scope: Repository Secrets vs Environment Secrets

| Job                             | `DEMO_SECRET` (repo) length | `STAGING_ONLY` (staging env) length |
| ------------------------------- | --------------------------- | ----------------------------------- |
| job **without** an environment  | 23                          | **0** (not available)               |
| job with `environment: staging` | 23                          | 18                                  |

**What to notice:** an environment secret is invisible to a job that does not name the environment (length 0, an empty string). A job that does name it gets both its environment secrets **and** the repository secrets. This is the mechanism behind "only deploy jobs can read the production key".

## 9. Environments and the Approval Gate

An **environment** is a named target. Create it in Settings, or through the API:

```bash
echo '{"wait_timer":0}' | gh api -X PUT repos/OWNER/REPO/environments/staging --input -
```

(Our first attempt used `-f wait_timer=0` and failed with `Invalid property /wait_timer: "0" is not of type integer`: `gh api -f` sends **strings**; pass a JSON body with `--input`.)

`production` was created with one protection rule: a **required reviewer** (me). The run **37317091672**:

| Job        | Environment             | Started      | Completed | State                  |
| ---------- | ----------------------- | ------------ | --------- | ---------------------- |
| staging    | `staging` (no rules)    | 13:28:44     | 13:28:46  | success                |
| production | `production` (reviewer) | **13:29:37** | 13:29:40  | success after approval |

The run's status sat at **`waiting`** between 13:28:46 and the approval. `gh api repos/OWNER/REPO/actions/runs/37317091672/pending_deployments` returned:

```json
{
  "environment": "production",
  "current_user_can_approve": true,
  "wait_timer": 0,
  "reviewers": ["User:Friend09"]
}
```

I approved with a POST to the same endpoint and the job started 51 seconds after staging finished.

**What to notice:**

- Waiting for approval is **not billed**: no runner is assigned until the gate opens. (Docs: a wait timer, if set, does not consume billable time either.)
- The job's secrets and variables for `production` are only released **after** approval.
- Docs (verified 2026-10): up to **6** required reviewers; **one** approval is enough; **prevent self-review** blocks the person who started the run from approving it (we left it off, so I could approve my own run).

**Availability (docs, verified 2026-10):**

| Feature                           | Public repos    | Private repos     |
| --------------------------------- | --------------- | ----------------- |
| Required reviewers, wait timer    | Free, Pro, Team | Enterprise only   |
| Deployment branch/tag rules       | all plans       | Pro / Team and up |
| Environment secrets and variables | all plans       | Pro / Team and up |

So an environment on a **private repo on the Free plan** cannot hold secrets or rules. Plan your design around the plan you have.

## 10. Wait Timers and Deployment Branches

> ⚠️ ADVANCED TOPIC: Skip on first read.

A **wait timer** delays the job by a number of minutes: from **1 to 43,200 (30 days)** (docs). **Deployment branch and tag rules** restrict which refs may deploy: no restriction, protected branches only, or selected name patterns (matched against `GITHUB_REF` with Ruby `File.fnmatch`; wildcards do not match `/`). Combined with a required reviewer they make `production` reachable only from `main` and only with a human yes.

## 11. A Preview of OIDC

> ⚠️ ADVANCED TOPIC: Skip on first read.

The safest secret is one that does not exist. With **OpenID Connect** a job proves its identity to a cloud provider and receives a short-lived credential, so nothing long-lived is stored. It needs a cloud account you create, so Chapter 13 teaches it offline and guarded.

## 12. Large and Structured Secrets

> ⚠️ ADVANCED TOPIC: Skip on first read.

Secrets have a size limit, and the docs describe encrypting larger files (for example with GPG) and decrypting them in the job. The docs warn that a value produced this way is **not** masked automatically, which is the same lesson as Section 7: anything derived from a secret needs its own `::add-mask::`.

## 13. Case Study: The Base64 "Hiding Place"

A team stores an API key and, to be safe in logs, prints only its base64 form during debugging. Today the runner masks that form, so nothing leaks, and the habit survives. A year later a different encoding (a hex dump, a reversed string, a URL-encoded fragment, one character per line) is printed during an outage and the key appears in the log in plain text. The log is readable by everyone with repo access, and by anyone at all in a public repo. **The rule:** never print a secret or anything derived from it, however encoded. Where you must, register the exact derived string with `::add-mask::` first.

## 14. Comparison: Where to Keep a Value

| Home                         | Setup Effort                      | Control                          | Failure Visibility                    | Security Exposure                          | Maintenance Burden          |
| ---------------------------- | --------------------------------- | -------------------------------- | ------------------------------------- | ------------------------------------------ | --------------------------- |
| `env:` in the YAML           | Minimal - type it                 | Moderate - changes need a commit | Excellent - in the diff               | High - public if repo is public            | Low                         |
| Repository `vars`            | Low - one CLI call                | Strong - change without a commit | Fair - changes are not in git history | Moderate - visible in logs                 | Low                         |
| Repository `secrets`         | Low - one CLI call                | Strong - write-only              | Weak - masked, hard to inspect        | Moderate - any job in the repo can read it | Moderate - rotation by hand |
| Environment `vars`/`secrets` | Moderate - create the environment | Excellent - gated by rules       | Strong - approvals are logged         | Low - only named jobs, after approval      | Moderate                    |
| OIDC (no stored secret)      | High - cloud trust setup          | Excellent - short-lived          | Strong - cloud audit trail            | Low - nothing to steal                     | Moderate                    |

## 15. Practical Tips

- Put non-sensitive tunables in `vars`, so changing a threshold does not need a commit.
- Pass secrets to steps through `env:`, never inline in a script, and never print them.
- If a log line must contain something derived from a secret, `::add-mask::` it first.
- Use environments for anything that deploys; add a required reviewer on `production`.
- Remember secrets are absent in runs from forks; design for it (Chapter 16).
- Delete a secret you created for a demo when you are done (`gh secret delete NAME`).
- Check what exists: `gh variable list`, `gh secret list`, `gh secret list --env staging` (values are never shown).

## 16. Demonstrated Failure Modes

**Failure 1: the leak in another form.** Evidence (run 37317079828): the reversed secret printed as `EULAV-terc3s-omed-yllat` in plain text, while the direct and base64 forms printed `***`. Fix: never print derived values; if you must, `::add-mask::` the derived value first (`derived_after_mask = ***`).

**Failure 2: the variable that was not there.** `vars.DOES_NOT_EXIST` printed as empty, silently. A typo in a variable name yields an empty string, not an error. Fix: assert required values early (`test -n "$TALLY_COLOR" || exit 1`).

**Failure 3: the environment secret in the wrong job.** `STAGING_ONLY` had length **0** in the job without `environment: staging`. A deploy step that forgot the environment line runs with an empty credential and fails far from the cause. Fix: put `environment:` on the job and check for non-empty values.

**Failure 4: the secret in an `if:`.** `actionlint`: `context "secrets" is not allowed here.` Fix: map it to `env` first.

**Failure 5: the integer sent as a string.** `gh api -f wait_timer=0` fails with HTTP 422. Fix: send JSON with `--input`.

## 17. Key Takeaways

- `env` precedence is step over job over workflow.
- `GITHUB_ENV` takes effect in the next step, not the writing step.
- A missing variable is an empty string, never an error.
- An environment variable overrides a repository variable of the same name for jobs using that environment.
- Masking covers the secret (we saw base64 too) but not arbitrary derived values; `::add-mask::` fixes a specific value.
- Secrets cannot be used in `if:`; map to `env` first. Forks do not receive secrets.
- A required reviewer pauses a job (`waiting`, unbilled) until approved.
- Required reviewers and wait timers need a public repo on Free/Pro/Team, or Enterprise.

## 18. Exercises

1. A workflow sets `X: w`; job `a` sets `X: j`; a step in job `a` sets `X: s`. What does a step in job `b` (no overrides) print, and what does a step in job `a` with no override print?
2. A step runs `echo "N=5" >> "$GITHUB_ENV"; echo "$N"`. What does it print? What does the next step print?
3. Repo variable `V=1`; environment `prod` variable `V=2`. What does `vars.V` evaluate to in a job with `environment: prod`? In a job with none?
4. You print `echo "$SECRET" | tr a-z A-Z` and the log shows the uppercased secret in clear. Why, and what do you add?
5. (Hand arithmetic) The run waited from 13:28:46 (staging done) to 13:29:37 (production started). How many seconds, and what was billed for that wait?

<details>
<summary>Answers</summary>

1. Job `b`: `w`. Step in `a` without override: `j`.
2. First prints an empty line (the variable is not set yet in that shell). The next step prints `5`.
3. `2` with `environment: prod`; `1` with no environment.
4. The runner masks the secret and some encodings but not uppercasing; mask the derived value first with `echo "::add-mask::$(echo "$SECRET" | tr a-z A-Z)"`.
5. 51 seconds; nothing: no runner was assigned during the wait.

</details>

## 19. Additional Resources

All verified 2026-10.

- GitHub Docs: Using secrets in GitHub Actions - https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets
- GitHub Docs: Store information in variables - https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-variables
- GitHub Docs: Deployments and environments (protection rules, availability) - https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments
- GitHub Docs: Workflow commands (`::add-mask::`, `GITHUB_ENV`) - https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands
- GitHub REST: Create or update an environment - https://docs.github.com/en/rest/deployments/environments#create-or-update-an-environment
- Live evidence: runs 37317079828 (config) and 37317091672 (environments) in this repo
- Laster, _Learning GitHub Actions_ (O'Reilly), Chapter 6

## 20. Appendix A: Code Index

> 💻 Complete, runnable code for this chapter. Skip when reading for concepts.

### A.1 The environment and mask checks

```python
import json
from datetime import datetime
from pathlib import Path

cfg = json.loads(Path("fixtures/config_ch08_run.json").read_text())["reports"]
vs = cfg["vars_and_secrets"]
assert vs["secret_direct"] == "***" and vs["secret_base64"] == "***"
assert vs["derived_before_mask"] == "EULAV-terc3s-omed-yllat"   # leaked
assert vs["derived_after_mask"] == "***"                         # fixed by add-mask
assert vs["repo_color"] == "blue" and vs["missing_var"] == "[]"

envr = json.loads(Path("fixtures/environments_ch08_run.json").read_text())
assert envr["reports"]["staging"]["staging_color"] == "green"    # env beats repo
```

**Flow:** load the saved reports -> assert the masked and leaked forms -> assert variable precedence between repo and environment.

### A.2 Resolve `env` scope

```python
def resolve(name: str, workflow: dict, job: dict, step: dict) -> str | None:
    """Innermost definition wins: step, then job, then workflow."""
    for scope in (step, job, workflow):
        if name in scope:
            return scope[name]
    return None
```

**Flow:** look in the step's env, then the job's, then the workflow's, and return the first hit.
