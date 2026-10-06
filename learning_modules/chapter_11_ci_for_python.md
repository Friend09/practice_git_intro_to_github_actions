# Chapter 11: CI for Python: Lint, Test, Coverage Matrix

**Reading Time:** ~55 minutes
**Prerequisites:** Chapter 03 (first workflow), Chapter 09 (cache), Chapter 10 (matrix, `needs`)
**Practice Notebook:** `notebooks/practice_11.ipynb`
**Reference Notebook:** `notebooks/lab_11_ci_for_python.ipynb`
**Script:** `labs/lab_11_ci_for_python.py`
**Book Reference:** Laster, Learning GitHub Actions Ch 4, 7 / GitHub Docs: Building and testing Python
**Depth:** Core
**Default Runtime:** Live repo

---

## Beginner's Guide

**Focus on first:** Sections 3 (the shape of a CI workflow), 6 (the coverage gate with real numbers) and 7 (the one required check).

**Skip on first read:** Sections 10-12 (concurrency per branch, speed tuning, alternatives to pip).

**Key concepts in plain English:**

- **Lint:** an automatic style and mistake checker that does not run your code.
- **Coverage:** the percentage of your code's lines that the tests actually executed.
- **Gate:** a rule that fails the build when a number is too low (here, coverage below 80%).
- **Summary job:** one job that waits for all the others and gives a single pass/fail answer.
- **Annotation:** a message the runner pins to a line of code in the pull request.

**If you have run `pytest` and `ruff` on your laptop**, this chapter is that, run for every push on four Python versions, with a verdict that cannot be skipped.

> **🔬 Platform Engineer's Lens:** CI is only worth its cost if a red result is **believable** and a green one is **meaningful**. Two real bugs in this chapter's own workflow, both caught by running it, attack exactly those: a lint job governed by a configuration file we did not know it was reading, and a gate job that could never report because its working directory did not exist. Both are in Section 16.

> **🚦 Native vs Marketplace vs Custom:** `actions/setup-python` (first-party) installs Python and can cache `pip`. Lint and test are your own commands (`ruff`, `pytest`), not actions: a one-line `run:` beats a Marketplace wrapper. The coverage gate is a flag on `pytest`, so no coverage-service account is needed.

## What You'll Learn

- Build a CI workflow with lint, a multi-version test matrix and a gate job
- Install four Python versions and read exactly which ones you got
- Cache `pip` with `setup-python` and read the real cache key and when it is saved
- Measure whether caching helped, and bill the run
- Enforce a coverage threshold and read the failure
- Turn lint findings into annotations on the code
- Use one summary job as the single required check

## Table of Contents

<!-- toc-start -->

- [Chapter 11: CI for Python: Lint, Test, Coverage Matrix](#chapter-11-ci-for-python-lint-test-coverage-matrix)
  - [Beginner's Guide](#beginners-guide)
  - [What You'll Learn](#what-youll-learn)
  - [Table of Contents](#table-of-contents)
  - [1. What CI for Python Must Do](#1-what-ci-for-python-must-do)
  - [2. Running Example: Tally Gets a Real Pipeline](#2-running-example-tally-gets-a-real-pipeline)
  - [3. The Shape of the Workflow](#3-the-shape-of-the-workflow)
  - [4. Installing Python, Four Times](#4-installing-python-four-times)
  - [5. Caching pip, Honestly Measured](#5-caching-pip-honestly-measured)
  - [6. The Coverage Gate](#6-the-coverage-gate)
  - [7. The Gate Job: One Required Check](#7-the-gate-job-one-required-check)
  - [8. Lint Annotations](#8-lint-annotations)
  - [9. Per-Leg Coverage Artifacts](#9-per-leg-coverage-artifacts)
  - [10. Concurrency per Branch](#10-concurrency-per-branch)
  - [11. Making It Faster](#11-making-it-faster)
  - [12. Alternatives to pip](#12-alternatives-to-pip)
  - [13. Case Study: The Gate That Never Reported](#13-case-study-the-gate-that-never-reported)
  - [14. Comparison: Where to Run Checks](#14-comparison-where-to-run-checks)
  - [15. Practical Tips](#15-practical-tips)
  - [16. Demonstrated Failure Modes](#16-demonstrated-failure-modes)
  - [17. Key Takeaways](#17-key-takeaways)
  - [18. Exercises](#18-exercises)
  - [19. Additional Resources](#19-additional-resources)
  - [20. Appendix A: Code Index](#20-appendix-a-code-index)
    - [A.1 The gate rule and coverage arithmetic](#a1-the-gate-rule-and-coverage-arithmetic)
    - [A.2 Detect the working-directory trap](#a2-detect-the-working-directory-trap)

---

## 1. What CI for Python Must Do

For every push and pull request: install the dependencies, check style and obvious mistakes, run the tests on the Python versions you support, measure coverage, and produce one answer. Each of those is a few lines of YAML. The skill is in what goes **wrong**, and this chapter's workflow went wrong three different ways while we built it, which is why the numbers below are all from real runs.

## 2. Running Example: Tally Gets a Real Pipeline

> 📌 **Running Example: `ch11-python-ci.yml`.** Tally now has `tally/stats.py` with `mean`, `median` and `clamp` (17 statements in the package in total) and a `requirements-dev.txt` (`pytest`, `pytest-cov`, `ruff`). The workflow has three kinds of job: **lint** (`ruff check --output-format=github`), **test** (a 4-leg matrix: Python 3.11, 3.12, 3.13, 3.14, each running `pytest --cov=tally --cov-fail-under=80`), and **ci-ok**, a gate that `needs` both and uses `if: always()`. We ran it five times as we fixed it: **37321016076** (coverage too low), **37321165485** (lint failure), **37321351215** (gate job broken), **37321500402** (all green) and **37321582147** (lint failure injected on purpose). Data: `fixtures/ci_ch11_*.json`. We return to them throughout.

## 3. The Shape of the Workflow

```yaml
jobs:
  lint:
    steps: [checkout, setup-python (cache: pip), pip install, ruff check]
  test:
    strategy:
      { fail-fast: false, matrix: { python: ["3.11", "3.12", "3.13", "3.14"] } }
    steps:
      [
        checkout,
        setup-python (cache: pip),
        pip install,
        pytest --cov ...,
        upload coverage,
      ]
  ci-ok:
    needs: [lint, test]
    if: ${{ always() }}
    steps: [fail unless both results are 'success']
```

Lint and test run **in parallel** (Chapter 02: no `needs` between them); `ci-ok` waits for both. `fail-fast: false` on the matrix means every Python version reports even when one fails, which is what you want from CI (Chapter 10). The whole file is under 90 lines; the full text is `.github/workflows/ch11-python-ci.yml`.

Triggers: `push` and `pull_request` filtered to `sandbox/**` plus the workflow file, and `workflow_dispatch` with two test inputs (`min_cov`, `lint_bad`). A concurrency group `ch11-${{ github.ref }}` with `cancel-in-progress: true` means a newer push to the same branch cancels the older run, which is usually right for CI (not for deploys; Chapter 10).

## 4. Installing Python, Four Times

`actions/setup-python@v7` installs the version you ask for. The real `python -V` printed by each matrix leg:

| Requested | Got                |
| --------- | ------------------ |
| `'3.11'`  | Python **3.11.16** |
| `'3.12'`  | Python **3.12.14** |
| `'3.13'`  | Python **3.13.15** |
| `'3.14'`  | Python **3.14.7**  |

**What to notice:** you ask for a minor version and receive the **latest patch** available that day. Two runs a month apart can run different patch versions. And every version here was **quoted** (Chapter 00: an unquoted `3.10` would have been the float `3.1`).

## 5. Caching pip, Honestly Measured

`setup-python` caches pip with one input: `cache: pip`, plus `cache-dependency-path` to say which file's hash goes in the key. The real key from the logs:

```
setup-python-Linux-x64-24.04-Ubuntu-python-3.12.14-pip-08e32bcf59ada40dd5876e64938bc6a2398938dee0dc2131c86c33ffc0a43c66
```

Read it left to right: tool, OS, architecture, **runner image version** (`24.04-Ubuntu`), **exact Python version**, `pip`, then the hash of `requirements-dev.txt`. Any change to those changes the key and forces a miss. That includes a new Python patch release, and (Chapter 05) a new runner image.

What happened across three runs (`Cache saved` / `Cache hit` lines from the logs):

| Run                  | lint      | 3.11      | 3.12    | 3.13      | 3.14      |
| -------------------- | --------- | --------- | ------- | --------- | --------- |
| 37321016076 (first)  | **saved** | no save   | no save | no save   | no save   |
| 37321165485 (second) | hit       | **saved** | hit     | **saved** | **saved** |
| 37321351215 (third)  | hit       | hit       | hit     | hit       | hit       |

**What to notice:**

- In the first run **no test leg saved a cache**. Those legs failed (the coverage gate), and a cache is saved by the **post step only when the job succeeds** (Chapter 09, docs). A failing job leaves no cache behind, so you can be cold for as long as your tests are red.
- The 3.12 test leg **hit** the cache the lint job saved, because both use Python 3.12.14 and the same dependency file: same key. The other legs each have their own key (the Python version is in it).
- By the third run every job hit. Now: did it help?

| Python | pip install, cold | pip install, warm |
| ------ | ----------------- | ----------------- |
| 3.11   | 4 s               | 3 s               |
| 3.12   | 4 s               | 4 s               |
| 3.13   | 3 s               | 3 s               |
| 3.14   | 4 s               | 4 s               |

**It barely did.** Three small packages install in 3-4 seconds from PyPI, so a warm cache saves at most a second. Whole-job time was no better (cold 9-14 s, warm 11-17 s: noise dominates). With every job under a minute, the bill is identical (below). Caching pays when installs are long (hundreds of megabytes, compiled wheels) and, as in Chapter 09, **only moves the bill when it crosses a minute boundary**. Measure before you add cache complexity.

> 📝 **Full implementation:** See [Appendix A.1](#a1-the-gate-rule-and-coverage-arithmetic)

## 6. The Coverage Gate

`pytest --cov=tally --cov-fail-under=80` runs the tests, measures which lines ran, and fails if the total is under 80%. Our first real run:

```
TOTAL                  17      8    53%
ERROR: Coverage failure: total of 53 is less than fail-under=80
FAIL Required test coverage of 80% not reached. Total coverage: 52.94%
```

17 statements, 8 missed. The missed ones were `median`'s seven lines (we wrote no test for it) plus the `raise` in `mean` (no empty-list test). In plain English:

$$\text{coverage} = 100 \times \frac{\text{statements} - \text{missed}}{\text{statements}} = 100 \times \frac{17 - 8}{17} = 52.94\%$$

The numerator counts statements that ran at least once. With 9 of 17 executed the result is 52.94%, which `coverage report --format=total` rounds to `53`. The gate compared against 80 and failed **all four** legs. After adding `test_mean_empty`, `test_median_odd_and_even` and `test_median_empty`, all four legs reported `coverage_total=100`.

**What to notice:**

- The fix to a failing gate is **tests**, not lowering the threshold. A gate that is quietly lowered each time it fails stops being a gate.
- Coverage counts **lines executed**, not lines _verified_: a test that calls `median` and asserts nothing would also reach 100%.
- The gate is a `pytest` flag, so every leg enforces it. We pass the threshold through an environment variable (`MIN_COV`) so the dispatch input is not pasted into the shell.

## 7. The Gate Job: One Required Check

A matrix creates several checks (`test (py3.11)`, `test (py3.12)`, ...). If branch protection required each by name, adding or removing a Python version would change what is required. So we add **one** job whose name never changes:

```yaml
ci-ok:
  needs: [lint, test]
  if: ${{ always() }}
  env:
    LINT: ${{ needs.lint.result }}
    TEST: ${{ needs.test.result }}
  steps:
    - run: |
        echo "REPORT lint=$LINT test=$TEST"
        [ "$LINT" = "success" ] && [ "$TEST" = "success" ]
```

`needs.test.result` is **one value for the whole matrix**: `success` only if every leg succeeded. `if: always()` is essential: without it, a failing `lint` would make `ci-ok` **skipped** (Chapter 10), and a skipped job is commonly reported as passing to branch protection (a behavior we did not test here). Real verdict when we injected a lint error (run 37321582147): the report line read `lint=failure test=success` and `ci-ok` failed. Tests were green; the gate still said no.

(Making this job a _required status check_ is a ruleset setting; Chapter 16 Section 5 tested it on throwaway branches: a red `ci-ok` blocks the merge, and so does a `ci-ok` that never reports. We still did not test a _skipped_ required job.)

## 8. Lint Annotations

`ruff check --output-format=github .` prints findings in the workflow-command format that GitHub turns into **annotations** on the exact file and line. The real annotations from run 37321582147, where we appended `import os` to `add.py`:

| Annotation | File and line                  | Rule                                                 |
| ---------- | ------------------------------ | ---------------------------------------------------- |
| failure    | `sandbox/tally/tally/add.py:7` | `ruff (F401)` `os` imported but unused               |
| failure    | `sandbox/tally/tally/add.py:7` | `ruff (E402)` module level import not at top of file |

and from run 37321165485: `tests/test_stats.py:3` `ruff (I001)` import block is un-sorted. They appear in the run summary and on the pull request's changed lines, which is far faster to act on than reading a log.

## 9. Per-Leg Coverage Artifacts

Each test leg uploads its `coverage.xml` as `coverage-3.11`, `coverage-3.12` and so on, with `retention-days: 1`. Artifact names must be unique within a run (Chapter 09), so the Python version goes in the name. Without that suffix the second leg would fail with a `409 Conflict`.

## 10. Concurrency per Branch

> ⚠️ ADVANCED TOPIC: Skip on first read.

`group: ch11-${{ github.ref }}` gives each branch its own group, so a new push to `feature-x` cancels only the older `feature-x` run. Cancelling superseded CI runs saves minutes; cancelling a **deploy** is dangerous (Chapter 10). Remember that cancellation is not instantaneous, so a cancelled run may still finish its current step.

## 11. Making It Faster

> ⚠️ ADVANCED TOPIC: Skip on first read.

Order of impact: (1) run lint and tests in parallel (done); (2) drop matrix legs you do not need on every push; (3) cache only if the install is long (Section 5); (4) run slow tests on a schedule; (5) split the suite across jobs only when one job exceeds a few minutes, because each job pays setup and rounds up to a billed minute (Chapter 01).

## 12. Alternatives to pip

> ⚠️ ADVANCED TOPIC: Skip on first read.

This repository's own `ci.yml` uses `uv` (`astral-sh/setup-uv`, `uv sync`, `uv run pytest`), which is typically much faster at resolving and installing, and caches itself. For a project with a lockfile, `uv` is usually the better default; the structure of the workflow (lint, matrix, gate) is the same.

## 13. Case Study: The Gate That Never Reported

Our own workflow. After lint and tests were green the pipeline still said `failure`. Everything inside passed; only `ci-ok` failed, with:

```
An error occurred trying to start process '/usr/bin/bash' with working directory
'/home/runner/work/.../sandbox/tally'. No such file or directory
```

The cause was one line at the top of the file: `defaults: run: working-directory: sandbox/tally`. **Workflow-level defaults apply to every job**, including `ci-ok`, which never ran `actions/checkout`. Its workspace was empty (Chapter 02), so the directory did not exist and the runner could not even start a shell. Worse, this had been true from the very first run, so `ci-ok` had been failing for a reason unrelated to the gate's logic and **masking** its real verdict. We found it only when every other job was green and the pipeline was still red.

**The fix** moves `working-directory` into the two jobs that check out the repo. `intro_gha.workflow.jobs_missing_checkout_with_workflow_workdir` now detects the shape statically, and `tests/test_workflow_yaml.py` runs it against every workflow in this repo.

## 14. Comparison: Where to Run Checks

| Approach                      | Setup Effort                         | Control                       | Failure Visibility                | Security Exposure               | Maintenance Burden          |
| ----------------------------- | ------------------------------------ | ----------------------------- | --------------------------------- | ------------------------------- | --------------------------- |
| Pre-commit hooks              | Low - install per clone              | Moderate - skippable          | Weak - local only                 | Minimal                         | Moderate - drifts per clone |
| CI lint + test (this chapter) | Low - one file                       | Strong - runs for everyone    | Excellent - annotations on the PR | Moderate - runs on shared infra | Low                         |
| CI with one required gate job | Moderate - plus a protection setting | Excellent - cannot be skipped | Excellent - one clear verdict     | Moderate                        | Low - stable name           |
| Third-party coverage service  | Moderate - account and token         | Moderate - trends and diffs   | Strong - dashboards               | High - external token           | Moderate                    |

## 15. Practical Tips

- Quote Python versions; remember you get the latest patch, not a pinned one.
- Put the Python version in every per-leg artifact name.
- Give the gate job `if: always()` and compare **each** result to `'success'` explicitly.
- Set `working-directory` per job, never at workflow level, unless every job checks out.
- Pass dispatch inputs to the shell through `env:`, not inline.
- Add a cache only after measuring a slow install; remember the key includes the runner image and the exact Python.
- Raise the coverage gate gradually; never lower it to make a red run green.

## 16. Demonstrated Failure Modes

**Failure 1: coverage below the gate.** Run 37321016076: 52.94% against 80 fails all four legs with `FAIL Required test coverage of 80% not reached`. A side effect: no leg saved a pip cache (Section 5). Fix: write the missing tests.

**Failure 2: lint governed by an unexpected config.** Run 37321165485: the lint job in `sandbox/tally` flagged `I001` (import sorting), a rule our workflow never asked for. `ruff` **discovers its configuration by looking in parent directories**, found this repository's root `pyproject.toml` (which selects the `I` rules) and applied it to the sandbox. Symptom: lint results differ from a laptop run in another folder. Fix: put a `pyproject.toml` (or `ruff.toml`) in the project you are linting so it is self-contained, or pass `--config`. We fixed the import with `ruff --fix`.

**Failure 3: the unreachable working directory.** Run 37321351215: `ci-ok` failed with `No such file or directory` while every other job passed (Section 13). Fix: job-level `defaults`.

**Failure 4: a gate that does its job.** Run 37321582147: lint failed (`F401`, `E402`), tests passed, and `ci-ok` reported `lint=failure test=success` and failed. This is the system working: the verdict is "no", for the right reason.

## 17. Key Takeaways

- A CI workflow is lint and a test matrix in parallel, plus a gate that waits for both.
- `setup-python` gives you the latest patch of the minor version you request.
- The pip cache key includes OS, runner image, exact Python and the dependency-file hash; a failing job saves no cache.
- Caching a 3-4 second install saved about a second: measure first.
- Coverage is statements run divided by statements total (9 of 17 = 52.94%); the cure for a red gate is tests.
- Ruff reads the nearest enclosing config, which may not be the one you expect.
- The gate job needs `if: always()` and explicit `== 'success'` checks.
- Workflow-level `defaults.run.working-directory` hits every job, including those without checkout.

## 18. Exercises

1. 20 statements, 3 missed: coverage? Does it pass an 85% gate?
2. In which of the three Section 5 runs would `test (py3.12)` have used a cache from a **different job**, and why?
3. `ci-ok` is missing `if: always()`. Lint fails. What is `ci-ok`'s conclusion, and why is that dangerous?
4. Your matrix adds `'3.15'`. Which required-check configuration breaks: requiring `ci-ok`, or requiring each `test (py...)` name?
5. (Hand arithmetic) The warm run has 6 jobs (lint, 4 tests, ci-ok), each under a minute on Linux. Billed minutes and mills per run, and per 1,000 pushes?

<details>
<summary>Answers</summary>

1. 100 x 17/20 = **85%**. It passes an 85% gate (the check is "not less than"); it would fail an 86% gate.
2. The second run (37321165485): the 3.12 test leg hit the cache the **lint** job saved, because they share Python 3.12.14 and the same dependency file, hence the same key.
3. `skipped`, because a failed need skips the job by default (Chapter 10). A skipped job is commonly treated as satisfied by branch protection (we did not test this), so a lint failure could merge.
4. Requiring each `test (py...)` name: the new leg is a new check that is not required, and a removed leg would be required forever and never report. `ci-ok` is stable.
5. 6 jobs x 1 min = **6 billed minutes**, 6 x 6 = **36 mills**; per 1,000 pushes 6,000 minutes and 36,000 mills ($36.00) before any free allowance.

</details>

## 19. Additional Resources

All verified 2026-10.

- GitHub Docs: Building and testing Python - https://docs.github.com/en/actions/tutorials/build-and-test-code/python
- actions/setup-python (caching, `cache-dependency-path`) - https://github.com/actions/setup-python
- Ruff: configuration discovery and output formats - https://docs.astral.sh/ruff/configuration/
- pytest-cov documentation (`--cov-fail-under`) - https://pytest-cov.readthedocs.io/
- GitHub Docs: Workflow syntax (`defaults.run`, `jobs.<id>.defaults`) - https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax
- Live evidence: runs 37321016076, 37321165485, 37321351215, 37321500402, 37321582147 in this repo
- Laster, _Learning GitHub Actions_ (O'Reilly), Chapters 4 and 7

## 20. Appendix A: Code Index

> 💻 Complete, runnable code for this chapter. Skip when reading for concepts.

### A.1 The gate rule and coverage arithmetic

```python
def coverage_percent(statements: int, missed: int) -> float:
    """Coverage as pytest-cov computes it: executed statements over total."""
    return 100 * (statements - missed) / statements


def gate(lint: str, test: str) -> bool:
    """The ci-ok rule: pass only if every upstream result is exactly 'success'."""
    return lint == "success" and test == "success"


assert round(coverage_percent(17, 8), 2) == 52.94
assert coverage_percent(17, 8) < 80 <= coverage_percent(20, 3)
assert gate("success", "success") and not gate("failure", "success")
assert not gate("skipped", "success")          # a skipped lint must not pass
```

**Flow:** coverage = (statements - missed) / statements x 100; the gate compares each upstream result to the literal `success`, so `failure`, `skipped` and `cancelled` all block.

### A.2 Detect the working-directory trap

```python
from intro_gha import WORKFLOWS_DIR
from intro_gha.workflow import jobs_missing_checkout_with_workflow_workdir, load_workflow

wf = load_workflow(WORKFLOWS_DIR / "ch11-python-ci.yml")
assert jobs_missing_checkout_with_workflow_workdir(wf) == []
buggy = {
    "defaults": {"run": {"working-directory": "sandbox/tally"}},
    "jobs": {"ci-ok": {"steps": [{"run": "true"}]}},
}
assert jobs_missing_checkout_with_workflow_workdir(buggy) == ["ci-ok"]
```

**Flow:** if a workflow-level `working-directory` exists, flag every job that runs commands, has no job-level override and has no `actions/checkout` step.
