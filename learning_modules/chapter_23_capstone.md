# Chapter 23: Capstone: The Full Tally Pipeline

**Reading Time:** ~60 minutes
**Prerequisites:** Chapters 00-20 (Chapters 21 and 22 are optional)
**Practice Notebook:** `notebooks/practice_23.ipynb`
**Reference Notebook:** `notebooks/lab_23_capstone.ipynb`
**Script:** `labs/lab_23_capstone.py`
**Book Reference:** Laster, Learning GitHub Actions, all chapters
**Depth:** Core
**Default Runtime:** Live repo

---

## Beginner's Guide

> This chapter adds almost no new syntax. It assembles what Chapters 03-20 taught into one pipeline, runs it green and red, reviews it against a checklist, and prices it. If a section feels familiar, that is the point: follow the Chapter pointers to revisit the mechanism.

**Focus on first:** Section 2 (the pipeline), Section 6 (the green run) and Section 16 (the red run).

**Skip on first read:** Sections 11 and 12.

**Key concepts in plain English:**

- **Pipeline:** CI (does it work?), then build (make the artifact), then verify (is it the artifact we built?), then deploy (put it somewhere), as one workflow where each stage `needs` the one before.
- **Gate:** a stage that stops everything after it when it fails.
- **Final job:** a job that runs whatever happened, to report the result.
- **Review checklist:** a short list of properties every workflow must have, checked by code, not by memory.

**If you have run CI before**, the new part is the discipline: every job has a timeout and the least permissions it needs, every third-party action is pinned, and the red path is tested as carefully as the green one.

> **🔬 Platform Engineer's Lens:** A pipeline's cost is not the green run. It is the red run nobody tested, the token with more scope than needed, and the eight billed minutes per push nobody counted. The capstone shows all three on one workflow with real numbers.

> **🚦 Native vs Marketplace vs Custom:** Every stage here is **native** (`needs`, `environment`, `concurrency`, `gh attestation verify`) or a first-party action (`checkout`, `setup-python`, artifact actions, `attest-build-provenance`), all pinned by SHA. No custom action or third-party Marketplace action was needed. That is a result worth noticing.

## What You'll Learn

- Assemble CI, build, verify and deploy stages into one pipeline with `needs`
- Predict the pipeline's waves and which jobs a failure skips
- Give each job only the permissions it needs, and see why only `build` can mint tokens
- Guard a production stage so it skips instead of failing without credentials
- Run a review checklist as code and watch it catch a bad copy
- Price a run from measured job durations and compare it with one merged job

## Table of Contents

<!-- TOC -->
- [1. What a Pipeline Is For](#1-what-a-pipeline-is-for)
- [2. Running Example: The Tally Pipeline](#2-running-example-the-tally-pipeline)
- [3. The Map Back to the Course](#3-the-map-back-to-the-course)
- [4. The Shape: Waves](#4-the-shape-waves)
- [5. Least Privilege, Job by Job](#5-least-privilege-job-by-job)
- [6. The Green Run](#6-the-green-run)
- [7. Variants on the Same Pipeline](#7-variants-on-the-same-pipeline)
- [8. Concurrency](#8-concurrency)
- [9. Failure Reporting with a Final Job](#9-failure-reporting-with-a-final-job)
- [10. The Review Checklist, as Code](#10-the-review-checklist-as-code)
- [11. Observability](#11-observability)
- [12. Cost](#12-cost)
- [13. Case Study: The Token That Did Too Much](#13-case-study-the-token-that-did-too-much)
- [14. Comparison: Pipeline Designs](#14-comparison-pipeline-designs)
- [15. Practical Tips](#15-practical-tips)
- [16. Demonstrated Failure Modes](#16-demonstrated-failure-modes)
- [17. Key Takeaways](#17-key-takeaways)
- [18. Exercises](#18-exercises)
- [19. Additional Resources](#19-additional-resources)
- [20. Appendix A: Code Index](#20-appendix-a-code-index)
   - [A.1 The review checklist](#a1-the-review-checklist)
   - [A.2 Waves and cost of the pipeline](#a2-waves-and-cost-of-the-pipeline)
<!-- /TOC -->

## 1. What a Pipeline Is For

A push should answer four questions in order: does the code work, can we build it, is the thing we built the thing we tested, and can we put it somewhere safe. Each question is a stage; each stage is a gate for the next. The workflow's job is to make the order, and the failure behavior, explicit.

## 2. Running Example: The Tally Pipeline

> 📌 **Running Example: Tally, CI to staging.** The file is `.github/workflows/ch23-pipeline.yml`, started by `workflow_dispatch` with two boolean inputs: `break_tests` (fails the Python 3.13 test leg on purpose) and `to_production`. Its seven job ids and what each does:
>
> | Job | What it does | Needs | Permissions beyond `contents: read` |
> | --- | --- | --- | --- |
> | `lint` | `ruff check .` in `sandbox/tally`, Python 3.12, pip cache | none | none |
> | `test` | matrix of Python 3.11, 3.12, 3.13; pytest with `--cov-fail-under=80`; `fail-fast: false` | none | none |
> | `build` | builds the wheel, records its SHA-256, attests provenance, uploads the artifact | `lint`, `test` | `id-token: write`, `attestations: write` |
> | `verify` | downloads the wheel, re-checks the digest, runs `gh attestation verify` | `build` | `attestations: read` |
> | `deploy_staging` | `environment: staging`; prints the commit | `verify` | none |
> | `deploy_production` | `environment: production`; guarded by `inputs.to_production && vars.GHA_ENABLE_PROD == 'true'` | `deploy_staging` | none |
> | `summary` | `if: always()`; writes a results table to the run summary | all of the above | none |
>
> Every job has `timeout-minutes`; the workflow has a `concurrency` group on the ref with `cancel-in-progress: false`. We return to it throughout.

## 3. The Map Back to the Course

| Feature in the pipeline | Chapter |
| --- | --- |
| `workflow_dispatch` inputs, `on:` | 03, 06 |
| Matrix, `fail-fast: false`, `needs`, `concurrency`, `timeout-minutes` | 10 |
| `defaults.run.working-directory` on jobs, not the workflow | 11 |
| pip cache through `setup-python` | 09, 18 |
| Wheel as an artifact between jobs | 09 |
| `environment: staging` / `production` | 08, 13 |
| Top-level `permissions: contents: read`, per-job grants | 15 |
| SHA-pinned actions, attestation, `gh attestation verify` | 16 |
| `if: always()` summary job | 22 |
| `vars.GHA_ENABLE_PROD` guard (skip, not fail, without credentials) | 13 |
| Billing arithmetic | 18 |

## 4. The Shape: Waves

From the `needs` graph (`execution_waves`, Chapter 10), the seven job ids run in six waves:

| Wave | Jobs |
| --- | --- |
| 1 | `lint`, `test` (three legs in parallel) |
| 2 | `build` |
| 3 | `verify` |
| 4 | `deploy_staging` |
| 5 | `deploy_production` |
| 6 | `summary` |

**What to notice:** `lint` and `test` start together; nothing after them starts until both finish. Seven job ids give nine job runs: the matrix adds two legs, and a skipped job still appears in the run.

## 5. Least Privilege, Job by Job

The workflow-level grant is `contents: read`. Only `build` adds `id-token: write` and `attestations: write`, because only it creates an attestation (Chapter 16). `verify` adds only `attestations: read`. A compromised `lint` or `test` step cannot mint an OIDC token or write an attestation, and the lab asserts that the only job holding `id-token` is `build`.

## 6. The Green Run

Run 37338733951, dispatched with `to_production=true`, **success**:

| Job | Seconds (API timestamps) | Result |
| --- | --- | --- |
| `lint` | 12 | success |
| `test (3.11)` | 9 | success |
| `test (3.12)` | 11 | success |
| `test (3.13)` | 15 | success |
| `build` | 21 | success |
| `verify` | 45 | success; digest matched; attestation verified |
| `deploy_staging` | 5 | success; sha `74d7cdb` |
| `deploy_production` | 0 | **skipped** |
| `summary` | 3 | success; reported `production=skipped` |

The wheel's digest was `sha256:2bb486690c2aa144d880598731ce3985150a0f431430edeefae2ca178f3a1360`, recorded by `build`, re-computed by `verify`, and verified against the attestation.

**What to notice:**

- Production was **skipped even though we asked for it**, because `vars.GHA_ENABLE_PROD` is unset. The guard turns a missing credential into a skip, as designed (Chapter 13).
- `verify` took the longest (45 s): `gh attestation verify` does the network work. A cheap-looking safety stage can dominate wall-clock time.
- Eight jobs consumed runner time; the ninth was skipped.

## 7. Variants on the Same Pipeline

| Change | Effect | Where taught |
| --- | --- | --- |
| `break_tests=true` | `test (3.13)` fails; `build` onward skipped | Section 16 |
| `to_production=true` and set `vars.GHA_ENABLE_PROD` to `true` | `deploy_production` would run (not done here) | Chapter 13 |
| Add a leg to the matrix | one more parallel job in wave 1 | Chapter 10 |
| Merge `lint` into `test` | fewer jobs, less parallelism, fewer billed minutes | Section 12 |

We did not set `GHA_ENABLE_PROD` or run the production job in this chapter.

## 8. Concurrency

The `concurrency` group `ch23-${{ github.ref }}` with `cancel-in-progress: false` queues a second run on the same ref instead of cancelling the first. For a pipeline that deploys, cancelling mid-deploy is the riskier default (Chapter 10 measured both behaviors).

## 9. Failure Reporting with a Final Job

The `summary` job has `needs` on every other job and `if: ${{ always() }}`. It reads each `needs.<job>.result` and writes a table to `$GITHUB_STEP_SUMMARY`. It is Chapter 22's replacement for a Jenkins `post` block, and it is the only job that runs after the red run's failure.

## 10. The Review Checklist, as Code

> ⚠️ ADVANCED TOPIC: Skip on first read.

`review(workflow)` in the lab returns findings for: no top-level `permissions`, any job without `timeout-minutes`, any unpinned remote action (Chapter 16), and any untrusted expression inside a `run` script (Chapter 16). On `ch23-pipeline.yml` it returns `[]`. On a copy with the permissions block and the `lint` timeout deleted it returns exactly `["no top-level permissions", "lint: no timeout-minutes"]`, which shows the checklist can fail.

A checklist you run is better than one you remember. The repository's own test suite applies the permissions and pinning checks to every workflow on every commit.

## 11. Observability

> ⚠️ ADVANCED TOPIC: Skip on first read.

The run summary table is the first thing a reader sees. Job names (`test (3.13)`) identify the failing leg without opening a log (Chapter 10, Chapter 21's leg names). `REPORT` lines in the logs (`verify digest_match=yes attestation=verified`) make a stage's outcome greppable (Chapter 17).

## 12. Cost

> ⚠️ ADVANCED TOPIC: Skip on first read.

Each job rounds up to a whole minute (Chapter 18). From the measured durations in Section 6 (private repository, Linux at $0.006 per minute):

| Run | Jobs with runner time | Billed minutes | Cost |
| --- | --- | --- | --- |
| Green (`37338733951`) | 8 | 8 | **$0.048** |
| Red (`37338751943`) | 5 | 5 | **$0.030** |
| Green as **one job** (121 s total) | 1 | 3 | $0.018 |

The seconds are the API's `started_at` to `completed_at` per job, so GitHub's own bill could differ by a few seconds. **What to notice:** splitting into jobs bought parallelism and clear gates and cost 8 minutes against 3. That is a fair price for a pipeline that wants gates; it is a poor price for one that does not. On a public repository, standard runners are free.

## 13. Case Study: The Token That Did Too Much

A pipeline like this one is copied into five repositories. In one copy, someone sets `permissions: write-all` at the top "to make a step work". Months later a dependency in the `test` job runs a malicious script; with `write-all` it can push to the repository and mint an OIDC token. In our pipeline the same script would find `contents: read` and no `id-token`. The review checklist in Section 10 would flag a missing `permissions` block, and a stricter version would flag `write-all`. (The scenario is constructed; the per-job permissions are observed in the workflow file and asserted in the lab.)

## 14. Comparison: Pipeline Designs

| Design | Setup Effort | Control | Failure Visibility | Security Exposure | Maintenance Burden |
| --- | --- | --- | --- | --- | --- |
| One job, many steps | Minimal | Low - no parallelism, no gates | Fair - one log | Higher - all steps share one token | Low |
| One job per stage (this chapter) | Moderate | High - gates and per-job permissions | Excellent - per-stage results | Low - least privilege per job | Moderate |
| Reusable workflow per stage (Chapter 20) | Higher | High - shared, versioned | Good - names include the caller | Low if inputs are validated | Lower across repos |
| Matrix everything | Moderate | High | Fair - many legs to read | Low | Moderate - cost grows with legs |

## 15. Practical Tips

- Start from the red path: break something on purpose and watch what is skipped.
- Put the report in a final `if: always()` job.
- Give every job `timeout-minutes`.
- Grant a permission to the one job that needs it, never the workflow.
- Guard credential-dependent stages with a variable so they skip, not fail.
- Count billed minutes before splitting into many small jobs.
- Run the checklist in CI so it cannot rot.

## 16. Demonstrated Failure Modes

**Failure 1: the broken leg (observed).** Run 37338751943 with `break_tests=true`:

| Job | Result |
| --- | --- |
| `lint`, `test (3.11)`, `test (3.12)` | success |
| `test (3.13)` | **failure** |
| `build`, `verify`, `deploy_staging`, `deploy_production` | **skipped** |
| `summary` | success; reported `test=failure build=skipped verify=skipped staging=skipped production=skipped` |

`fail-fast: false` let the other legs finish, so the report shows exactly which leg broke. The run's overall conclusion is **failure** even though the `summary` job succeeded: the run is as red as its worst required job.

**Failure 2: the checklist catches a bad copy (observed in the lab).** Deleting the `permissions` block and a timeout gives the two findings listed in Section 10.

**Failure 3: the over-broad token (constructed).** Section 13.

## 17. Key Takeaways

- A pipeline is stages joined by `needs`; each stage is a gate.
- Six waves, seven job ids, nine job runs: count them from the graph.
- Only the job that needs a token gets one.
- A guarded production stage skips instead of failing when its credential is absent.
- A final `always()` job reports the red path; the run still ends red.
- Per-job billing makes eight small jobs cost 8 minutes against 3 for one merged job.
- Run the checklist as code.

## 18. Exercises

1. Write the waves if `verify` is removed and `deploy_staging` `needs: [build]`.
2. In the red run, why was `deploy_production` skipped, and is that the same reason as in the green run?
3. The `summary` job succeeded in the red run. Why is the run still red?
4. Add a fourth Python version to the matrix. How many billed minutes does the green run now use if the new leg takes 14 seconds?
5. (Hand arithmetic) The green run takes 8 billed minutes. A private repository on the Free plan has 2,000 included minutes. How many such runs fit in a month, and what is the overage cost of the 251st run at $0.006 per minute?

<details>
<summary>Answers</summary>

1. `[[lint, test], [build], [deploy_staging], [deploy_production], [summary]]`, provided `summary` no longer lists `verify` in its `needs` (a `needs` entry naming a missing job is an error).
2. In the red run it was skipped because its `needs` chain failed (`deploy_staging` was skipped). In the green run it was skipped because its `if:` was false (`vars.GHA_ENABLE_PROD` unset). Same label, different reasons; `needs.<job>.result` is `skipped` in both.
3. A run's conclusion is determined by the jobs that failed; the `test (3.13)` failure makes it `failure`. `if: always()` only controls whether `summary` runs, not the run's color.
4. A new leg of 14 seconds rounds up to 1 minute: 9 billed minutes (a 9th job ran). Cost $0.054.
5. 2,000 / 8 = **250** runs. The 251st run uses 8 minutes of overage: 8 x $0.006 = **$0.048**.

</details>

## 19. Additional Resources

All verified 2026-10.

- GitHub Docs, [Workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax) (`needs`, `strategy`, `concurrency`, `environment`, `timeout-minutes`)
- GitHub Docs, [Controlling permissions for GITHUB_TOKEN](https://docs.github.com/en/actions/security-for-github-actions/security-guides/automatic-token-authentication)
- GitHub Docs, [Using artifact attestations](https://docs.github.com/en/actions/security-for-github-actions/using-artifact-attestations/using-artifact-attestations-to-establish-provenance-for-builds)
- GitHub Docs, [Actions billing](https://docs.github.com/en/billing/managing-billing-for-your-products/managing-billing-for-github-actions/about-billing-for-github-actions)
- GitHub Docs, [Expressions: status check functions](https://docs.github.com/en/actions/reference/workflows-and-actions/expressions)
- Laster, *Learning GitHub Actions* (O'Reilly), the whole book

## 20. Appendix A: Code Index

> 💻 Complete, runnable code for this chapter. Skip when reading for concepts.

### A.1 The review checklist

```python
from intro_gha import WORKFLOWS_DIR
from intro_gha.injection import injection_sites
from intro_gha.pinning import unpinned
from intro_gha.workflow import load_workflow


def review(workflow: dict) -> list[str]:
    """Return findings from the capstone review checklist (empty means clean)."""
    findings: list[str] = []
    if "permissions" not in workflow:
        findings.append("no top-level permissions")
    for job_id, job in workflow["jobs"].items():
        if "timeout-minutes" not in job:
            findings.append(f"{job_id}: no timeout-minutes")
    findings += [f"unpinned: {ref}" for ref in unpinned(workflow)]
    findings += [f"injection: {site}" for site in injection_sites(workflow)]
    return findings


wf = load_workflow(WORKFLOWS_DIR / "ch23-pipeline.yml")
assert review(wf) == []
```

**Flow:** load the workflow; check permissions, timeouts, pins and injection sinks; an empty list is clean.

### A.2 Waves and cost of the pipeline

```python
from intro_gha.cost import run_cost_mills, run_minutes
from intro_gha.workflow import execution_waves, job_graph

assert execution_waves(job_graph(wf))[0] == ["lint", "test"]
green = [(s, "linux") for s in (12, 9, 11, 15, 21, 45, 5, 3)]
assert (run_minutes(green), run_cost_mills(green)) == (8, 48)
assert run_minutes([(121, "linux")]) == 3          # the same work as one job
```

**Flow:** compute the first wave from `needs`; price the eight jobs that ran, each rounded up; compare with one merged job.
