# Chapter 20: Reusable Workflows and Workflow Templates

**Reading Time:** ~55 minutes
**Prerequisites:** Chapter 07 (contexts), Chapter 08 (secrets, `vars`), Chapter 13 (OIDC claims), Chapter 15 (permissions), Chapter 19 (custom actions)
**Practice Notebook:** `notebooks/practice_20.ipynb`
**Reference Notebook:** `notebooks/lab_20_reusable_workflows.ipynb`
**Script:** `labs/lab_20_reusable_workflows.py`
**Book Reference:** Laster, Learning GitHub Actions Ch 12 / GitHub Docs: Reusing workflows, Creating workflow templates
**Depth:** Core
**Default Runtime:** Live repo

---

## Beginner's Guide

**Focus on first:** Sections 4 (calling a workflow and what the jobs are named), 7 (what crosses the boundary and what does not) and 9 (the permission ceiling).

**Skip on first read:** Sections 10-12 (nesting, templates, versioning).

**Key concepts in plain English:**

- **Reusable workflow:** a whole workflow (with its own jobs and runners) that another workflow can _call_ like a function, using the trigger `workflow_call`.
- **Caller / called:** the workflow that makes the call, and the one being called.
- **Input / secret / output:** the arguments, protected arguments and return values of the call.
- **Workflow template:** a starting-point file an _organization_ offers in its "new workflow" screen.

**If you wrote a composite action in Chapter 19**, a reusable workflow is the next size up: an action reuses **steps** inside one job; a reusable workflow reuses **jobs**, with their own runners, permissions and matrix.

> **🔬 Platform Engineer's Lens:** A reusable workflow is how a platform team turns "40 copies of CI" into one reviewed file. The price is a boundary that behaves differently from copy-paste: some things cross it (inputs, `vars`, the caller's identity), some silently do not (`env`, secrets unless you pass them), and misconfigurations surface only as a `startup_failure` with no message. We tested each, because the docs do not state several of them.

> **🚦 Native vs Marketplace vs Custom:** Reusable workflows are native and the right tool when the unit of reuse is a **job** (build, test, deploy). Composite actions are the right tool for a few **steps**. Workflow templates are for **starting** a new workflow, not for keeping one in sync: they copy, they do not link.

## What You'll Learn

- Write a workflow with `on: workflow_call`, with typed inputs, secrets and outputs
- Call it locally and by `owner/repo/path@ref`, and read the jobs' names
- Explain what propagates into a called workflow (inputs, `vars`) and what does not (`env`, secrets)
- Pass secrets three ways and show the difference
- Run a matrix of calls and chain outputs back to the caller
- State why a called workflow cannot elevate permissions, and how that failure looks
- See which workflow an OIDC token's claims name, caller or called
- Describe workflow templates, which only organizations can use

## Table of Contents

<!-- toc-start -->

- [Chapter 20: Reusable Workflows and Workflow Templates](#chapter-20-reusable-workflows-and-workflow-templates)
  - [Beginner's Guide](#beginners-guide)
  - [What You'll Learn](#what-youll-learn)
  - [Table of Contents](#table-of-contents)
  - [1. From Steps to Jobs](#1-from-steps-to-jobs)
  - [2. Running Example: One Workflow, Many Calls](#2-running-example-one-workflow-many-calls)
  - [3. Anatomy of a Reusable Workflow](#3-anatomy-of-a-reusable-workflow)
  - [4. Calling It](#4-calling-it)
  - [5. Inputs, Defaults and Required Inputs](#5-inputs-defaults-and-required-inputs)
  - [6. Outputs Come Back](#6-outputs-come-back)
  - [7. What Crosses the Boundary](#7-what-crosses-the-boundary)
  - [8. Secrets, Three Ways](#8-secrets-three-ways)
  - [9. The Permission Ceiling, and Whose Token Is It](#9-the-permission-ceiling-and-whose-token-is-it)
  - [10. Nesting, Limits and Matrices](#10-nesting-limits-and-matrices)
  - [11. Workflow Templates (Organizations Only)](#11-workflow-templates-organizations-only)
  - [12. Versioning a Reusable Workflow](#12-versioning-a-reusable-workflow)
  - [13. Case Study: Forty Copies of CI](#13-case-study-forty-copies-of-ci)
  - [14. Comparison: Ways to Share Pipeline Logic](#14-comparison-ways-to-share-pipeline-logic)
  - [15. Practical Tips](#15-practical-tips)
  - [16. Demonstrated Failure Modes](#16-demonstrated-failure-modes)
  - [17. Key Takeaways](#17-key-takeaways)
  - [18. Exercises](#18-exercises)
  - [19. Additional Resources](#19-additional-resources)
  - [20. Appendix A: Code Index](#20-appendix-a-code-index)
    - [A.1 Read the reusable-workflow run](#a1-read-the-reusable-workflow-run)

---

## 1. From Steps to Jobs

Chapter 19's composite action reuses a _sequence of steps_ inside the caller's own job. A **reusable workflow** reuses _jobs_: when you call it, GitHub starts **its own jobs on its own runners**, in the caller's run. That makes it the right granularity for "our standard CI pipeline" or "our deploy procedure".

## 2. Running Example: One Workflow, Many Calls

> 📌 **Running Example: `ch20-reusable.yml` and its callers.** The called workflow takes three inputs (`who`: required string; `python-version`: string, default `3.12`; `run-tests`: boolean, default `true`), one optional secret (`demo_secret`), and returns one output (`summary`). Its job prints what it sees (including `secret_len`, the length of the secret) and optionally runs Tally's tests. The caller, `ch20-caller.yml` (run **37333020006**), makes **six calls**: a local call, a two-leg matrix, a call by `owner/repo/path@sha`, a call with `secrets: inherit`, a call with an explicit secret mapping, and a consumer of the output; plus one call to a second reusable workflow, `ch20-reusable-oidc.yml`, which decodes its OIDC token. Two more callers are broken on purpose: `ch20-caller-denied.yml` (run **37333146229**) and `ch20-caller-bad-input.yml` (run **37333193334**). The called workflows were published at commit **`58e6665c76701fbc2f31ef401c54bd6a79b94992`**. Data: `fixtures/reusable_ch20_summary.json`, `fixtures/reusable_ch20_run.json`. We return to them throughout.

## 3. Anatomy of a Reusable Workflow

```yaml
on:
  workflow_call:
    inputs:
      who: { type: string, required: true }
      python-version: { type: string, default: "3.12" }
      run-tests: { type: boolean, default: true }
    secrets:
      demo_secret: { required: false }
    outputs:
      summary:
        value: ${{ jobs.build.outputs.summary }}
permissions:
  contents: read
jobs:
  build: ...
```

Rules (docs, verified 2026-10): the trigger must include `workflow_call`; the file must sit in `.github/workflows/` (subdirectories are not supported); input types are `boolean`, `number` or `string`; **outputs map in two hops**: a step output becomes a _job_ output, which becomes a _workflow_ output through `on.workflow_call.outputs`, and the caller reads it as `needs.<call job id>.outputs.<name>`.

## 4. Calling It

```yaml
jobs:
  call_local:
    uses: ./.github/workflows/ch20-reusable.yml # same repository
    with:
      who: Tally
  call_remote_path:
    uses: Friend09/practice_git_intro_to_github_actions/.github/workflows/ch20-reusable.yml@58e6665c76701fbc2f31ef401c54bd6a79b94992
    with: { who: remote, run-tests: false }
```

Syntax for another repository: `{owner}/{repo}/.github/workflows/{file}@{ref}`, where `ref` can be a SHA, tag or branch (docs). Pin it by SHA (Chapter 16): the call is a trust relationship, and a moved branch changes your pipeline.

The call is a **job**, not a step, so it has no `steps:` and no `runs-on:` of its own; those belong to the called workflow. In the run, the jobs were named by joining the caller's job id and the called job id:

```
call_local / build
call_matrix (3.11) / build
call_matrix (3.12) / build
call_remote_path / build
call_inherit / build
call_explicit_secret / build
oidc_in_called_workflow / claims
consume_output                      (a normal job in the caller)
```

All succeeded. **What to notice:** each called job is a **real job on its own runner**, billed on its own (Chapter 01). A caller with three calls to a four-job workflow starts twelve jobs, and each rounds up to a minute (Chapter 18). A composite action would have run inside one job.

> 📝 **Full implementation:** See [Appendix A.1](#a1-read-the-reusable-workflow-run)

## 5. Inputs, Defaults and Required Inputs

What the called workflow reported (`called who=... python=... run_tests=...`):

| Call                 | `who`    | `python-version` | `run-tests` | Where each value came from       |
| -------------------- | -------- | ---------------- | ----------- | -------------------------------- |
| `call_local`         | `Tally`  | **`3.12`**       | **`true`**  | default, default                 |
| `call_matrix (3.11)` | `matrix` | `3.11`           | `false`     | `${{ matrix.python }}`, explicit |
| `call_matrix (3.12)` | `matrix` | `3.12`           | `false`     |                                  |
| `call_remote_path`   | `remote` | `3.12` (default) | `false`     |                                  |

Defaults fill in what the caller omits. A **required** input that the caller omits fails the run. We built `ch20-caller-bad-input.yml` to omit `who`:

| Layer                         | Result                                                                                                                                                                                                                                                          |
| ----------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `actionlint` (before pushing) | **caught it**: `input "who" is required by "./.github/workflows/ch20-reusable.yml" reusable workflow [workflow-call]`                                                                                                                                           |
| GitHub (run 37333193334)      | **`startup_failure`**, **0 jobs**, and `gh run view` says only `This run likely failed because of a workflow file issue.`; no message through the API (to push this probe at all we suppressed that one finding for that one file in `.github/actionlint.yaml`) |

Chapter 05, 16 and now 20 share this shape: **a call-time configuration error is a `startup_failure`**, and lint is your only early warning.

## 6. Outputs Come Back

The called workflow's `summary` output is `hello $WHO on python $PYV`. The caller's job `consume_output` declared `needs: [call_local]` and read `needs.call_local.outputs.summary` through an environment variable. Its log:

```
REPORT consumed_output=[hello Tally on python 3.12]
```

Same rules as Chapter 09: outputs are strings, and a failed or skipped call yields empty outputs. A matrix of calls produces one called workflow per leg, so a single `needs.<id>.outputs.<name>` cannot carry every leg's value (we did not test which leg it returns); if you need per-leg results, write them to artifacts (Chapter 09).

## 7. What Crosses the Boundary

The docs say little about this, so the called workflow printed everything it could see. Results from run 37333020006:

| What the called workflow saw                                 | Value                                                   | Crosses?                  |
| ------------------------------------------------------------ | ------------------------------------------------------- | ------------------------- |
| `github.workflow`                                            | **`ch20 caller`** (the **caller's** name)               | the caller's identity     |
| `github.event_name`                                          | `workflow_dispatch` (the caller's event)                | yes                       |
| `github.workflow_ref`                                        | `.../.github/workflows/ch20-caller.yml@refs/heads/main` | yes: names the **caller** |
| `env.CALLER_ENV` (set in the caller's workflow-level `env:`) | **empty**                                               | **no**                    |
| `vars.TALLY_COLOR` (a repository variable)                   | `blue`                                                  | **yes**                   |
| `inputs.*`                                                   | as passed                                               | yes (that is the purpose) |
| `secrets.demo_secret` (not passed)                           | length **0**                                            | **no**                    |

**What to notice:**

- **`env` does not propagate.** The caller set `CALLER_ENV: from-the-caller` at workflow level; the called workflow saw an empty string. Pass values you need as **inputs**.
- **Repository variables do** reach the called workflow (`vars` are looked up in the repository, not carried in the call).
- Inside the called workflow, `github.workflow` and `github.event_name` describe the **caller's** run, so a reusable workflow cannot tell by those which workflow it _is_. If it needs its own identity, use `github.workflow_ref` knowing it names the caller, or the OIDC claim in Section 9.

## 8. Secrets, Three Ways

We created a dummy 23-character repository secret and called the workflow three ways (we deleted the secret afterwards). The called workflow reported `secret_len`:

| Call                   | How the secret was passed                              | `secret_len` |
| ---------------------- | ------------------------------------------------------ | ------------ |
| `call_local`           | not passed                                             | **0**        |
| `call_inherit`         | `secrets: inherit`                                     | **23**       |
| `call_explicit_secret` | `secrets: { demo_secret: ${{ secrets.DEMO_SECRET }} }` | **23**       |

**What to notice:**

- **Secrets do not cross automatically.** Without passing, the called workflow got nothing.
- `secrets: inherit` hands over **all** the caller's secrets; an explicit mapping hands over exactly the ones you name. **Prefer explicit**: it documents what the called workflow can see and limits the damage of a compromised one (Chapter 16). Docs (verified 2026-10): `secrets: inherit` is described as available within the same organization or enterprise; it worked here in a single-repository setup.
- **Environment secrets cannot be passed**: docs say `on.workflow_call` does not support the `environment` keyword, so environment-scoped secrets are not available through a call. (We did not test this; it is the documented limitation.)

## 9. The Permission Ceiling, and Whose Token Is It

Docs (verified 2026-10): "Permissions can only be maintained or reduced—not elevated—throughout the chain." A called workflow can never have more permission than its caller grants.

**The failure.** `ch20-reusable-oidc.yml` declares `permissions: contents: read, id-token: write` (it needs a token to ask for OIDC). `ch20-caller-denied.yml` has `permissions: contents: read` and calls it with no job-level grant. Run 37333146229:

| Layer        | Result                                                    |
| ------------ | --------------------------------------------------------- |
| `actionlint` | **passed** (exit 0), no warning                           |
| GitHub       | **`startup_failure`**, **0 jobs**, no message via the API |

The successful caller instead granted the permission **on the calling job**:

```yaml
oidc_in_called_workflow:
  permissions:
    contents: read
    id-token: write
  uses: ./.github/workflows/ch20-reusable-oidc.yml
```

and the call worked. The grant belongs on the **call job**, because that is the job the platform checks.

**Whose identity is the token?** Inside that called workflow we decoded the OIDC token (Chapter 13), and finally tested the claim we only observed there:

| Claim              | Value                                                                                       |
| ------------------ | ------------------------------------------------------------------------------------------- |
| `job_workflow_ref` | `.../.github/workflows/ch20-reusable-oidc.yml@refs/heads/main` (the **called** workflow)    |
| `workflow_ref`     | `.../.github/workflows/ch20-caller.yml@refs/heads/main` (the **caller**)                    |
| `workflow`         | `ch20 caller`                                                                               |
| `sub`              | `repo:Friend09@7501015/practice_git_intro_to_github_actions@1405684500:ref:refs/heads/main` |

**What to notice:** the token carries **both**: `workflow_ref` names the caller and **`job_workflow_ref` names the called workflow**. A cloud trust policy can therefore say "only tokens whose `job_workflow_ref` is `org/platform/.github/workflows/deploy.yml@<sha>` may assume this role", which pins trust to **one reviewed deploy workflow** regardless of which repository calls it. Chapter 13 described that as documented behavior; here it is measured. (The `sub` is ref-based because this job has no `environment`; Chapter 13 explained why.)

## 10. Nesting, Limits and Matrices

> ⚠️ ADVANCED TOPIC: Skip on first read.

Docs (verified 2026-10): workflows can be nested to **ten levels** (the top caller plus up to nine reusable workflows), and loops are not allowed. A reusable workflow supports a `strategy.matrix` like any job, and a call job can be matrixed too, as we did: `call_matrix (3.11)` and `call_matrix (3.12)` ran as two separate calls, in parallel. We did not test the nesting limit.

## 11. Workflow Templates (Organizations Only)

> ⚠️ ADVANCED TOPIC: Skip on first read.

A **workflow template** (formerly "starter workflow") is a file an organization offers when someone clicks **New workflow**. Docs (verified 2026-10): templates live in a **`.github` repository at the organization level**, in a `workflow-templates` directory; each needs a same-named `.properties.json` with `name` and `description` (optional `iconName`, `categories`, `filePatterns`); and `$default-branch` in the template is replaced with the new repository's actual default branch. The docs describe them as an **organization** feature, so a personal account like this one cannot use them, and we could not demonstrate one live.

We include an example under `examples/workflow-templates/` and a test (`tests/test_workflow_templates.py`) that checks its properties file and placeholder. Note what a template **is**: a **copy**. Once a repository creates a workflow from it, the copy lives and drifts on its own. The sensible pattern is the one in our example: the template is a few lines that **call** a shared reusable workflow (`uses: ORG/.github/.github/workflows/python-ci.yml@main`), so the logic stays in one place.

## 12. Versioning a Reusable Workflow

> ⚠️ ADVANCED TOPIC: Skip on first read.

A reusable workflow in another repository is consumed at a ref. Treat it like a library: keep inputs backward compatible within a major version, tag releases (`v1`, `v1.2.0`), document inputs and secrets, and tell consumers to pin by SHA with Dependabot proposing bumps (Chapter 16). Changing an input name or making an optional input required is a breaking change that fails every caller at startup, with no message through the API.

## 13. Case Study: Forty Copies of CI

A company has 40 repositories, each with a hand-copied 80-line `ci.yml`. A security fix (pin an action, add `permissions: contents: read`) needs 40 pull requests, and three are forgotten. They write `org/.github/.github/workflows/python-ci.yml` with `workflow_call` inputs for the Python version and test command, and replace each repository's file with a 10-line caller pinned by SHA. The next security fix is **one** pull request to one file, then a Dependabot bump in each caller. The trade-off they accept: each call is its own set of jobs (more, shorter jobs: Chapter 18's rounding), and a mistake in the shared file breaks forty pipelines, so changes to it are reviewed like production code. (This scenario applies Sections 4 and 12; we did not reproduce it.)

## 14. Comparison: Ways to Share Pipeline Logic

| Approach                        | Setup Effort                     | Control                          | Failure Visibility                          | Security Exposure                      | Maintenance Burden                            |
| ------------------------------- | -------------------------------- | -------------------------------- | ------------------------------------------- | -------------------------------------- | --------------------------------------------- |
| Copy and paste                  | Minimal                          | Weak - drifts per repo           | Fair - each copy independent                | Moderate - fixes are missed            | Very High - N copies                          |
| Composite action (Chapter 19)   | Low                              | Moderate - steps only            | Strong - steps in the caller's job          | Low - runs in the caller's job         | Low                                           |
| Reusable workflow               | Moderate - define inputs/secrets | Strong - whole jobs, own runners | Moderate - `startup_failure` has no message | Moderate - boundary rules, pin the ref | Low                                           |
| Workflow template               | Low - org repo                   | Weak - a copy that drifts        | Weak                                        | Moderate                               | High unless it only calls a reusable workflow |
| Platform-wide required workflow | High - org policy                | Excellent                        | Strong                                      | Low                                    | Moderate                                      |

(Required workflows are an organization feature we did not test.)

## 15. Practical Tips

- Reuse **jobs** with reusable workflows and **steps** with composite actions.
- Pass what the called workflow needs as **inputs**; do not rely on `env`.
- Pass **named** secrets, not `secrets: inherit`.
- Grant permissions on the **call job**, minimally.
- Pin remote calls by SHA; tag and version your shared workflow.
- Lint with `actionlint` (it caught the missing input) and expect a `startup_failure` with no message for the rest.
- Use `job_workflow_ref` in cloud trust policies to pin trust to one reviewed workflow.
- Let a workflow template be a thin caller, not a copy of the logic.

## 16. Demonstrated Failure Modes

**Failure 1: the missing required input.** `startup_failure`, 0 jobs, no message. `actionlint` caught it first. Fix: lint, and give inputs defaults where sensible.

**Failure 2: the permission elevation.** The called workflow asked for `id-token: write` the caller had not granted: `startup_failure`; `actionlint` silent. Fix: grant it on the call job.

**Failure 3: the vanishing `env`.** The caller's `CALLER_ENV` was empty in the called workflow. Fix: pass an input.

**Failure 4: the missing secret.** `secret_len=0` with no pass-through. Fix: map the secret explicitly.

**Failure 5: the wrong identity.** `github.workflow` named the **caller**. Fix: use `job_workflow_ref` when you need the called workflow's identity.

**Failure 6: two lint surprises while writing it.** `actionlint` rejected `env.*` in a **job-level** `env:` (available contexts there are `github`, `inputs`, `matrix`, `needs`, `secrets`, `strategy`, `vars`) and did not know a `github.job_workflow_ref` property. Fix: read `env` in a **step**; take the called-workflow identity from the OIDC claim.

## 17. Key Takeaways

- A reusable workflow reuses **jobs**; every called job is a real, separately billed job named `caller / called`.
- Inputs (typed, defaulted), `vars` and the caller's identity cross the boundary; **`env` and secrets do not**.
- Pass secrets explicitly (`secrets: { name: ... }`) rather than `inherit`.
- Outputs travel step -> job -> workflow -> caller (`needs.<call>.outputs.<name>`).
- A called workflow cannot elevate permissions; grant them on the calling job.
- Configuration errors at call time are `startup_failure` with no jobs and no API message.
- The OIDC token names the caller in `workflow_ref` and the called workflow in `job_workflow_ref`.
- Workflow templates are an organization feature and are copies; make them thin callers.

## 18. Exercises

1. A caller sets `env: REGION: us-east-1` at workflow level and calls a reusable workflow that reads `${{ env.REGION }}`. What does it see, and what is the fix?
2. A reusable workflow declares `permissions: contents: write`. The caller's workflow is `permissions: contents: read`. What happens?
3. In which claim would a trust policy look to require "only the approved deploy workflow", and does it name the caller or the called workflow?
4. A caller calls a 4-job reusable workflow 3 times. How many jobs start, and how many billed minutes if every job is under a minute on Linux (private repo)?
5. (Hand arithmetic) Our caller run started `call_local`, `call_matrix` x2, `call_remote_path`, `call_inherit`, `call_explicit_secret`, `oidc_in_called_workflow` and `consume_output`. How many jobs ran, and what is the mills cost on a private repo if each ran under a minute on Linux?

<details>
<summary>Answers</summary>

1. An empty string: `env` does not propagate into a called workflow. Pass it as an **input** (`with: { region: us-east-1 }`) and read `inputs.region`.
2. The run fails at startup (`startup_failure`, no jobs): permissions cannot be elevated. Grant `contents: write` on the calling job (and in the caller's allowed set).
3. **`job_workflow_ref`**, which names the **called** workflow (the caller is in `workflow_ref`).
4. 4 x 3 = **12** jobs; 12 billed minutes (12 x 6 = 72 mills).
5. 8 jobs (`call_local`, 2 matrix legs, `call_remote_path`, `call_inherit`, `call_explicit_secret`, `oidc_in_called_workflow`, `consume_output`), i.e. **8 billed minutes = 48 mills**.

</details>

## 19. Additional Resources

All verified 2026-10.

- GitHub Docs: Reuse workflows - https://docs.github.com/en/actions/how-tos/reuse-automations/reuse-workflows
- GitHub Docs: Create workflow templates - https://docs.github.com/en/actions/how-tos/reuse-automations/create-workflow-templates
- GitHub Docs: Workflow syntax (`on.workflow_call`) - https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax
- GitHub Docs: OpenID Connect (claims, including `job_workflow_ref`) - https://docs.github.com/en/actions/concepts/security/openid-connect
- actionlint (reusable-workflow checks) - https://github.com/rhysd/actionlint
- Live evidence: runs 37333020006, 37333146229, 37333193334; called workflows at commit `58e6665c76701fbc2f31ef401c54bd6a79b94992`
- Laster, _Learning GitHub Actions_ (O'Reilly), Chapter 12

## 20. Appendix A: Code Index

> 💻 Complete, runnable code for this chapter. Skip when reading for concepts.

### A.1 Read the reusable-workflow run

```python
import json
from pathlib import Path

s = json.loads(Path("fixtures/reusable_ch20_summary.json").read_text())
seen = s["called_sees"]
assert seen["github_workflow"] == "ch20 caller"            # the caller's name
assert seen["caller_env_visible"] is False                 # env does not propagate
assert seen["repo_vars_visible"] is True                   # vars do
sec = s["secrets"]
assert (sec["not_passed_len"], sec["inherit_len"], sec["explicit_len"]) == (0, 23, 23)
oidc = s["oidc"]
assert oidc["job_workflow_ref"].endswith("ch20-reusable-oidc.yml@refs/heads/main")
assert oidc["workflow_ref"].endswith("ch20-caller.yml@refs/heads/main")
assert s["failures"]["permission_elevation"]["conclusion"] == "startup_failure"
```

**Flow:** load the saved facts from the real run; assert what crosses the boundary (name, `vars`, inputs), what does not (`env`, secrets), and which workflow each OIDC claim names.
