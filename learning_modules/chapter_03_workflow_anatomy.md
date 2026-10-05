# Chapter 03: Workflow YAML Anatomy and Your First Green Check

**Reading Time:** ~45 minutes
**Prerequisites:** Chapter 00 (YAML), Chapter 02 (event, job, step, runner)
**Practice Notebook:** `notebooks/practice_03.ipynb`
**Reference Notebook:** `notebooks/lab_03_workflow_anatomy.ipynb`
**Script:** `labs/lab_03_workflow_anatomy.py`
**Book Reference:** Laster, Learning GitHub Actions Ch 4 / GitHub Docs: Workflow syntax
**Depth:** Core
**Default Runtime:** Live repo

---

## Beginner's Guide

**Focus on first:** Sections 3 (the file, key by key), 8 (reading a green run) and 9 (reading a red run).

**Skip on first read:** Sections 11-12 (`continue-on-error`, step ids). You will meet them again in Chapters 09 and 10.

**Key concepts in plain English:**

- **A workflow file** is a YAML recipe with four main parts: a name, triggers (`on`), settings (`permissions`, `env`), and `jobs`.
- **A step's `if:`** is a gate: false means the step is skipped, not failed.
- **A green check** means every job finished with no failed step. **A red X** means at least one step failed.
- **`working-directory`** says which folder a `run:` command executes in.

**If you have written a Makefile or a shell script**, a step is a line of it, and `if:` is the `[ ... ] &&` guard in front.

> **🔬 Platform Engineer's Lens:** A first workflow is where bad habits start. A workflow with no `permissions:` block inherits whatever the repository default is, and a workflow with no `timeout-minutes` can run for up to 6 hours if something hangs. This chapter's workflow sets both from the first line. The cost of a one-line default is zero; the cost of a hung job on a private repo is a 6-hour bill.

> **🚦 Native vs Marketplace vs Custom:** Everything here is native YAML except two Marketplace actions, `actions/checkout` and `actions/setup-python`. We use the official, first-party ones; Chapter 04 explains how to judge any other.

## What You'll Learn

- Name every top-level key of a workflow and what it controls
- Write a workflow that checks out code, sets up Python and runs tests
- Gate a step with `if:` and read "skipped" correctly
- Read a run's step list and spot the failing step
- Use `workflow_dispatch` inputs to trigger a deliberate failure
- Scope a `push` trigger with `paths:` and predict when it fires
- Explain what a green check and a red X actually mean

## Table of Contents

<!-- TOC -->
- [1. The Goal](#1-the-goal)
- [2. Running Example: Tally's First CI](#2-running-example-tallys-first-ci)
- [3. The File, Key by Key](#3-the-file-key-by-key)
- [4. Triggers: `on`](#4-triggers-on)
- [5. `permissions` and `env`](#5-permissions-and-env)
- [6. The Job](#6-the-job)
- [7. The Steps](#7-the-steps)
- [8. Reading a Green Run](#8-reading-a-green-run)
- [9. Reading a Red Run](#9-reading-a-red-run)
- [10. Run Names and Titles](#10-run-names-and-titles)
- [11. Gating and `continue-on-error`](#11-gating-and-continue-on-error)
- [12. Step IDs and Outputs Preview](#12-step-ids-and-outputs-preview)
- [13. Case Study: The Workflow Nobody Ran](#13-case-study-the-workflow-nobody-ran)
- [14. Comparison: `run:` vs `uses:`](#14-comparison-run-vs-uses)
- [15. Practical Tips](#15-practical-tips)
- [16. Demonstrated Failure Mode: A Regression Caught](#16-demonstrated-failure-mode-a-regression-caught)
- [17. Key Takeaways](#17-key-takeaways)
- [18. Exercises](#18-exercises)
- [19. Additional Resources](#19-additional-resources)
- [20. Appendix A: Code Index](#20-appendix-a-code-index)
   - [A.1 Parse the workflow and test the paths filter](#a1-parse-the-workflow-and-test-the-paths-filter)
<!-- /TOC -->

---

## 1. The Goal

Chapter 02 showed a run built from `echo` commands. This chapter writes a workflow that does something real: it tests Tally. By the end you will have produced a green check and a red X on purpose, and read both.

## 2. Running Example: Tally's First CI

> 📌 **Running Example: `ch03-tally-ci.yml`.** One job, `test`, on `ubuntu-latest`, with five real steps. It runs Tally's two tests from `sandbox/tally/`. It triggers on `push` when files under `sandbox/` change, or manually via `workflow_dispatch` with a boolean input `fail`. We have two real runs of it: **run 37311496555** (green, `push`, commit `18514aeb631b...`, 14 seconds) and **run 37311583393** (red, `workflow_dispatch` with `fail=true`, 16 seconds). Both are saved in `fixtures/run_ch03_green.json` and `fixtures/run_ch03_red.json`. We return to them in Sections 8, 9 and 16.

The complete file (this is under 15 lines per block, so we show it in two parts):

```yaml
name: ch03 tally ci
run-name: Tally CI (fail=${{ inputs.fail || false }}) by ${{ github.actor }}
on:
  push:
    paths: ['sandbox/**', '.github/workflows/ch03-tally-ci.yml']
  workflow_dispatch:
    inputs:
      fail: { description: 'Break add() first', type: boolean, default: false }
permissions:
  contents: read
env:
  PYTHON_VERSION: '3.12'
```

```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    defaults: { run: { working-directory: sandbox/tally } }
    steps:
      - uses: actions/checkout@v7
      - uses: actions/setup-python@v7
        with: { python-version: '${{ env.PYTHON_VERSION }}' }
      - run: python -m pip install pytest
      - if: ${{ inputs.fail }}
        run: sed -i 's/return a + b/return a - b/' tally/add.py
      - run: python -m pytest -v
```

(The real file adds a `name:` to every step; they appear in the run logs below. The two runs below executed when the file used `checkout@v4` and `setup-python@v5`; Chapter 04 Section 8 explains why we later bumped both to `@v7`. The step results are identical.)

## 3. The File, Key by Key

| Key | Level | What it does | In Tally's file |
| --- | --- | --- | --- |
| `name` | workflow | Label in the Actions tab | `ch03 tally ci` |
| `run-name` | workflow | Label of each run (can use expressions) | `Tally CI (fail=...) by Friend09` |
| `on` | workflow | Events that start the workflow | `push`, `workflow_dispatch` |
| `permissions` | workflow or job | Scopes of the run's `GITHUB_TOKEN` | `contents: read` |
| `env` | workflow, job or step | Environment variables | `PYTHON_VERSION` |
| `jobs` | workflow | The jobs, keyed by id | `test` |
| `runs-on` | job | Runner label | `ubuntu-latest` |
| `timeout-minutes` | job | Kill the job after N minutes | `5` |
| `defaults.run` | job | Defaults for every `run:` step | `working-directory: sandbox/tally` |
| `steps` | job | Ordered list of steps | five |
| `uses` / `run` | step | An action, or a shell command | both |
| `with` | step | Inputs passed to an action | `python-version` |
| `if` | step or job | Gate: run only when true | `inputs.fail` |

**What to notice:**

- Three levels exist: workflow, job, step. `env` and `permissions` can sit at any of them, and the closest one wins.
- A step has exactly one of `uses` or `run`, never both.
- `timeout-minutes: 5` is a ceiling a hung job cannot exceed; without it the limit is far higher (a hosted job may run up to 6 hours per the limits page).

## 4. Triggers: `on`

Two triggers are set.

**`push` with `paths`.** The workflow fires on a push only if **at least one changed file** matches a path pattern. `sandbox/**` matches any file under `sandbox/`, at any depth.

| Files changed in the push | Fires? | Why |
| --- | --- | --- |
| `sandbox/tally/tally/add.py` | Yes | matches `sandbox/**` |
| `README.md` | No | matches nothing |
| `README.md` and `sandbox/tally/tests/test_add.py` | Yes | **any** match is enough |
| `.github/workflows/ch03-tally-ci.yml` | Yes | listed explicitly |

This is why the repo's curriculum edits never trigger the demo: a push touching only `learning_modules/` matches none of the paths. The matcher behind this table is `intro_gha.triggers.paths_trigger`; Chapter 06 covers its edge cases.

**`workflow_dispatch` with an input.** This adds a **Run workflow** button and a CLI path:

```bash
gh workflow run ch03-tally-ci.yml -f fail=true
```

The input is typed (`boolean`), has a description for the form, and a default. Inside the workflow it is read as `inputs.fail`.

> 📝 **Full implementation:** See [Appendix A.1](#a1-parse-the-workflow-and-test-the-paths-filter)

## 5. `permissions` and `env`

`permissions: contents: read` gives the run's built-in token read access to the repo and nothing else. Chapter 15 explains why this is the right default; for now, copy it into every workflow.

`env` at the workflow level defines `PYTHON_VERSION` once. A step reads it as `${{ env.PYTHON_VERSION }}`. Note the quoted `'3.12'`: this is Chapter 00's float trap in practice (an unquoted `3.10` would become `3.1`).

## 6. The Job

```yaml
test:
  runs-on: ubuntu-latest
  timeout-minutes: 5
  defaults: { run: { working-directory: sandbox/tally } }
```

`defaults.run.working-directory` applies to every `run:` step in the job, so each command runs inside `sandbox/tally` without repeating it. It does **not** apply to `uses:` steps; `actions/checkout` still checks out the repo root. This matters: remember Chapter 02's empty workspace and that checkout happens first.

## 7. The Steps

| # | Step | Kind | Purpose |
| --- | --- | --- | --- |
| 2 | Check out repository | `uses` | Fill the empty workspace with the repo |
| 3 | Set up Python | `uses` + `with` | Install Python 3.12 |
| 4 | Install pytest | `run` | `python -m pip install pytest` |
| 5 | Break add() on purpose | `run` + `if` | Only when `inputs.fail` is true |
| 6 | Run tests | `run` | `python -m pytest -v` |

(Numbers start at 2 in the log because GitHub numbers its own **Set up job** as step 1.)

## 8. Reading a Green Run

Run **37311496555**, triggered by a push. State dump from the fixture:

| Step | Conclusion |
| --- | --- |
| 1 Set up job | success |
| 2 Check out repository | success |
| 3 Set up Python | success |
| 4 Install pytest | success |
| 5 Break add() on purpose | **skipped** |
| 6 Run tests | success |
| 11 Post Set up Python | success |
| 12 Post Check out repository | success |
| 13 Complete job | success |

**What to notice:**

- Step 5 is **skipped**, not failed: `inputs.fail` is empty on a push event, so its `if:` is false. A skipped step does not turn the run red.
- The run title read `Tally CI (fail=false) by Friend09`. The expression `inputs.fail || false` turned the push's missing input into `false`. Without `|| false` the title would show an empty value.
- The step numbers jump from 6 to 11. GitHub reserves numbers for hidden pre- and post-steps (actions can register cleanup steps). Do not rely on the numbers; rely on names.

The overall result is a **green check**. On a private repo this 14-second run bills one minute (Chapter 01).

## 9. Reading a Red Run

Run **37311583393**, triggered with `gh workflow run ch03-tally-ci.yml -f fail=true`:

| Step | Conclusion |
| --- | --- |
| 1 Set up job | success |
| 2 Check out repository | success |
| 3 Set up Python | success |
| 4 Install pytest | success |
| 5 Break add() on purpose | success (it ran: `if` was true) |
| 6 Run tests | **failure** |
| 11 Post Set up Python | skipped |
| 12 Post Check out repository | success |
| 13 Complete job | success |

The failing step's log, trimmed to the lines that matter:

```
E       assert -1 == 5
E        +  where -1 = add(2, 3)
E       assert 5 == -1
E        +  where 5 = add(2, -3)
FAILED tests/test_add.py::test_add_small_numbers - assert -1 == 5
FAILED tests/test_add.py::test_add_negative - assert 5 == -1
============================== 2 failed in 0.03s ===============================
```

**What to notice:**

- The `sed` step changed `return a + b` into `return a - b`. Tally's own tests caught it: `add(2, 3)` returned `-1` instead of `5`.
- One failed step makes the job and the run `failure`. The remaining steps either still ran (cleanup posts) or were skipped; later *work* steps would have been skipped by default.
- The log shows **why**: the assertion text is right there. A red X is the summary; the step log is the evidence.

## 10. Run Names and Titles

`run-name` sets the title of each run in the Actions list. Expressions work inside it. Our two titles (`fail=false`, `fail=true`) let you tell runs apart at a glance, which matters when a workflow has many runs a day.

## 11. Gating and `continue-on-error`

> ⚠️ ADVANCED TOPIC: Skip on first read.

`if:` decides whether a step runs; `continue-on-error: true` decides whether its **failure** counts. A step with `continue-on-error: true` that fails shows as failed in the UI but does not fail the job. Use it sparingly, for genuinely optional checks (a coverage upload, say); a test step with `continue-on-error` is a test that cannot fail your build.

## 12. Step IDs and Outputs Preview

> ⚠️ ADVANCED TOPIC: Skip on first read.

A step with `id: tests` can be referenced later as `steps.tests.outcome` and `steps.tests.conclusion`. Chapter 07 covers contexts and Chapter 09 covers passing step results onward.

## 13. Case Study: The Workflow Nobody Ran

A new contributor adds a workflow with `on: push: paths: ['src/**']`. The project's code lives in `lib/`. Every push is green, because **no run exists**: the filter never matches. The pull request shows no checks at all, which looks like success. Detect it by checking that a deliberate change under `lib/` produces a run (our `make pr` flow does this for `sandbox/`). Chapter 06 and Chapter 17 treat "why didn't it fire" systematically.

## 14. Comparison: `run:` vs `uses:`

| Approach | Setup Effort | Control | Failure Visibility | Security Exposure | Maintenance Burden |
| --- | --- | --- | --- | --- | --- |
| `run:` shell command | Minimal - one line | Excellent - exact command | Strong - raw output in log | Low - your own code | Low - nothing to update |
| `uses:` first-party action | Minimal - one line | Moderate - set by inputs | Fair - grouped log | Low - GitHub-maintained | Low - bump version |
| `uses:` third-party action | Minimal - one line | Moderate - set by inputs | Fair - grouped log | High - code you did not write | Moderate - track updates |

## 15. Practical Tips

- Start every job with `actions/checkout`; set `permissions` and `timeout-minutes` on every workflow.
- Name every step. Names are what you read in a failed log, and what required status checks refer to.
- Quote versions (`'3.12'`), always.
- Read the first red step, not the last: later failures are often consequences.
- Use `gh run view <id> --log-failed` to see only the failing step's output.

## 16. Demonstrated Failure Mode: A Regression Caught

**Setup:** Section 2's workflow, run with `fail=true`.

| Step | State |
| --- | --- |
| Before | `add(a, b)` returns `a + b`; tests pass |
| Change | `sed` rewrites it to `a - b` |
| Run tests | `add(2, 3)` returns `-1`; `add(2, -3)` returns `5` |
| Result | 2 failed in 0.03 s; job `failure`; run red |

**Symptom:** red X, `FAILED tests/test_add.py::...`. **Cause:** a real behavior change, detected by tests. **Fix:** revert the change. This is the system working: the red X is the point of CI.

**Second failure: the path filter that hides.** Change only `README.md` and push: **no run is created at all**. Compare run lists: the push to `sandbox/` made run `37311496555`; a push to `README.md` makes nothing. The absence is silent, which is why Chapter 17 is devoted to it.

## 17. Key Takeaways

- A workflow has three levels: workflow, job, step; `env` and `permissions` can sit at each.
- Set `permissions` and `timeout-minutes` from your first workflow.
- `if:` false means **skipped**, which is not a failure.
- A step's failure fails its job; the log of the first failed step explains why.
- `paths:` fires on **any** matching changed file; no match means no run at all.
- `workflow_dispatch` plus an input is the safest way to exercise a failure path.
- Never trust step numbers; trust step names.

## 18. Exercises

1. Given the Section 4 table, would a push changing only `learning_modules/chapter_03_workflow_anatomy.md` fire the workflow? Why?
2. In the green run, what is the conclusion of the `Break add()` step, and why isn't the run red?
3. Write the `gh` command to trigger a **green** manual run of this workflow.
4. If you moved the `Run tests` step above the checkout, what would happen, referring to Chapter 02?
5. (Hand arithmetic) The red run took 16 seconds and the green 14. On a private Linux repo, how many billed minutes and what cost in mills for each?

<details>
<summary>Answers</summary>

1. No. It matches neither `sandbox/**` nor the workflow file path, so no run is created.
2. `skipped`; `inputs.fail` is empty on a push so the `if` is false. Skipped steps don't fail the job.
3. `gh workflow run ch03-tally-ci.yml` (the input defaults to false) or `gh workflow run ch03-tally-ci.yml -f fail=false`.
4. The workspace would be empty, so the tests would not be found and the step would fail (no tests collected / file not found).
5. Each rounds up to 1 minute: 6 mills each ($0.006).

</details>

## 19. Additional Resources

All verified 2026-10.

- GitHub Docs: Workflow syntax reference - https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax
- GitHub Docs: Events that trigger workflows (`push`, `workflow_dispatch`) - https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows
- GitHub Docs: Actions limits - https://docs.github.com/en/actions/reference/limits
- actions/checkout - https://github.com/actions/checkout
- actions/setup-python - https://github.com/actions/setup-python
- Live evidence: runs 37311496555 (green) and 37311583393 (red) in this repo
- Laster, *Learning GitHub Actions* (O'Reilly), Chapter 4

## 20. Appendix A: Code Index

> 💻 Complete, runnable code for this chapter. Skip when reading for concepts.

### A.1 Parse the workflow and test the paths filter

```python
from intro_gha import WORKFLOWS_DIR
from intro_gha.triggers import paths_trigger
from intro_gha.workflow import load_workflow, triggers

wf = load_workflow(WORKFLOWS_DIR / "ch03-tally-ci.yml")
trig = triggers(wf)
assert set(trig) == {"push", "workflow_dispatch"}
paths = trig["push"]["paths"]
assert paths_trigger(["sandbox/tally/tally/add.py"], paths)
assert not paths_trigger(["README.md"], paths)
assert paths_trigger(["README.md", "sandbox/tally/tests/test_add.py"], paths)
steps = wf["jobs"]["test"]["steps"]
assert len(steps) == 5 and steps[3]["if"] == "${{ inputs.fail }}"
```

**Flow:** load (normalizing `on`) -> read triggers -> feed the `paths` list to the matcher with sample change sets -> assert the step list and the `if` gate.
