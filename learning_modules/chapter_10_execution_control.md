# Chapter 10: Execution Control: needs, Matrix, Concurrency, Timeouts

**Reading Time:** ~55 minutes
**Prerequisites:** Chapter 02 (jobs, `needs`), Chapter 07 (status functions), Chapter 09 (outputs)
**Practice Notebook:** `notebooks/practice_10.ipynb`
**Reference Notebook:** `notebooks/lab_10_execution_control.ipynb`
**Script:** `labs/lab_10_execution_control.py`
**Book Reference:** Laster, Learning GitHub Actions Ch 8 / GitHub Docs: Running variations of jobs, Control the concurrency of workflows
**Depth:** Core
**Default Runtime:** Live repo

---

## Beginner's Guide

**Focus on first:** Sections 3 (`needs` when something fails), 5 (`fail-fast`, with a real before and after) and 7 (concurrency groups).

**Skip on first read:** Sections 10-12 (dynamic matrices, runner limits, `queue: max`).

**Key concepts in plain English:**

- **`needs`:** "run this job only after those jobs, and only if they went well."
- **Matrix:** one job definition expanded into many jobs, one per combination of values.
- **`fail-fast`:** when one matrix job fails, stop the others that have not finished.
- **Concurrency group:** a name; only one run holding that name may execute at a time.
- **Timeout:** a ceiling on how long a job or step may run.

**If you have used a build tool with a dependency graph** (make, a task runner), `needs` is that graph, and the matrix is a parameterized loop.

> **🔬 Platform Engineer's Lens:** This chapter controls blast radius and cost. A matrix multiplies your bill by its size, a concurrency group decides whether a deploy can overlap itself, and a timeout is the only thing between a hung step and a very long job. Every number in this chapter comes from a real run, including two that surprised us: cancellation and timeouts are **not instantaneous**.

> **🚦 Native vs Marketplace vs Custom:** All native: do not write a scheduler or a locking script. Reach for a concurrency group instead of "check if another deploy is running" scripts, and for a matrix instead of copy-pasted jobs.

## What You'll Learn

- Predict which downstream jobs run when an upstream job fails, with and without `if:`
- Expand a matrix by hand, including `exclude` and `include`
- Show what `fail-fast` does to queued, running and finished legs
- Limit parallelism with `max-parallel` and measure the effect
- Use a concurrency group and say which run is kept, queued or cancelled
- Set job and step timeouts and know how late they actually fire
- Estimate what a matrix costs

## Table of Contents

<!-- toc-start -->

- [Chapter 10: Execution Control: needs, Matrix, Concurrency, Timeouts](#chapter-10-execution-control-needs-matrix-concurrency-timeouts)
  - [Beginner's Guide](#beginners-guide)
  - [What You'll Learn](#what-youll-learn)
  - [Table of Contents](#table-of-contents)
  - [1. Four Controls](#1-four-controls)
  - [2. Running Example: Five Real Experiments](#2-running-example-five-real-experiments)
  - [3. `needs` and Failure](#3-needs-and-failure)
  - [4. The Matrix](#4-the-matrix)
  - [5. `fail-fast`: Before and After](#5-fail-fast-before-and-after)
  - [6. `max-parallel`](#6-max-parallel)
  - [7. Concurrency Groups](#7-concurrency-groups)
  - [8. Timeouts](#8-timeouts)
  - [9. Forgiving a Leg](#9-forgiving-a-leg)
  - [10. Dynamic Matrices](#10-dynamic-matrices)
  - [11. Runner Concurrency Limits](#11-runner-concurrency-limits)
  - [12. Matrix Naming and Required Checks](#12-matrix-naming-and-required-checks)
  - [13. Case Study: The 256-Leg Surprise](#13-case-study-the-256-leg-surprise)
  - [14. Comparison: Controlling a Pipeline](#14-comparison-controlling-a-pipeline)
  - [15. Practical Tips](#15-practical-tips)
  - [16. Demonstrated Failure Modes](#16-demonstrated-failure-modes)
  - [17. Key Takeaways](#17-key-takeaways)
  - [18. Exercises](#18-exercises)
  - [19. Additional Resources](#19-additional-resources)
  - [20. Appendix A: Code Index](#20-appendix-a-code-index)
    - [A.1 `needs` skip propagation and matrix expansion](#a1-needs-skip-propagation-and-matrix-expansion)

---

## 1. Four Controls

| Control           | Question it answers                            |
| ----------------- | ---------------------------------------------- |
| `needs`           | In what order, and what if a dependency fails? |
| `strategy.matrix` | How many variations of this job?               |
| `concurrency`     | May two runs overlap?                          |
| `timeout-minutes` | How long is too long?                          |

## 2. Running Example: Five Real Experiments

> 📌 **Running Example: four `ch10-*.yml` workflows.** `ch10-needs.yml` (run **37318821322**) has jobs `a` (fails on purpose), `b` (needs a), `c` (needs b) and three report jobs. `ch10-matrix.yml` has a 6-leg matrix with `max-parallel: 2`, run twice: **37319094292** (`fail-fast: true`) and **37319194753** (`fail-fast: false`). `ch10-concurrency.yml` has `concurrency: group: ch10-demo` and a 40-second job; we dispatched it three times in a row with `cancel-in-progress: false` (runs **37319409690**, **37319423478**, **37319437491**) and three times with `true` (**37319632048**, **37319663031**, **37319694303**). `ch10-timeouts.yml` (run **37318827012**) has a job and a step with a 1-minute timeout around a 120-second `sleep`. All data: `fixtures/exec_ch10_all.json`. We return to them in every section.

## 3. `needs` and Failure

`needs` waits for the listed jobs **and requires them to have succeeded**. The graph in `ch10-needs.yml`:

```
a (fails) ──▶ b ──▶ c
a, b, c ──▶ report_always   (if: always())
a, b, c ──▶ report_on_failure (if: failure())
a       ──▶ report_default  (no if)
```

Real result (run 37318821322, overall `failure`):

| Job                 | Conclusion  | Why                                                         |
| ------------------- | ----------- | ----------------------------------------------------------- |
| `a`                 | **failure** | `exit 1`                                                    |
| `b`                 | skipped     | its need `a` failed                                         |
| `c`                 | skipped     | its need `b` was **skipped** (not even a failure)           |
| `report_default`    | skipped     | no `if`, so the implicit `success()` applies and `a` failed |
| `report_always`     | **success** | `if: always()` runs whatever happened                       |
| `report_on_failure` | **success** | `if: failure()`: a needed job failed                        |

And what the always-job saw: `needs.a.result = failure`, `needs.b.result = skipped`, `needs.c.result = skipped`.

**What to notice:**

- **Skips propagate.** `c` needs only `b`, yet it was skipped because `b` was skipped. The default condition is "all needs succeeded", and "skipped" is not "succeeded".
- The four values of `needs.<job>.result` are `success`, `failure`, `cancelled` and `skipped`. They are strings; compare them explicitly (`needs.a.result == 'failure'`).
- To run a job **despite** upstream trouble (cleanup, notifications, a report), give it `if: ${{ always() }}`, or `failure()` to run only on trouble.
- `always()` also runs after a **cancelled** run. If a step must not run on cancel, use `if: ${{ !cancelled() }}`.

> 📝 **Full implementation:** See [Appendix A.1](#a1-needs-skip-propagation-and-matrix-expansion)

## 4. The Matrix

A matrix expands one job into one job per combination. Ours:

```yaml
strategy:
  fail-fast: ${{ inputs.fail_fast }}
  max-parallel: 2
  matrix:
    os: [ubuntu-latest, ubuntu-22.04]
    py: ["3.11", "3.12", "3.13"]
    exclude:
      - { os: ubuntu-22.04, py: "3.11" }
    include:
      - { os: ubuntu-latest, py: "3.14", experimental: true }
```

**Expansion by hand.**

| Step                      | Combinations                                                                                                                                        | Count |
| ------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- | ----- |
| Cross product of the axes | 2 `os` x 3 `py`                                                                                                                                     | **6** |
| Remove `exclude` matches  | minus `(ubuntu-22.04, 3.11)`                                                                                                                        | **5** |
| Apply `include`           | `(ubuntu-latest, 3.14)` matches **no** existing combination (3.14 is not an axis value), so it becomes a **new job**, carrying `experimental: true` | **6** |

The real run listed exactly six legs: `(ubuntu-latest, 3.11)`, `(ubuntu-latest, 3.12)`, `(ubuntu-latest, 3.13)`, `(ubuntu-22.04, 3.12)`, `(ubuntu-22.04, 3.13)` and `(ubuntu-latest, 3.14)`. Docs (verified 2026-10): include entries that match existing combinations add properties to them; entries that do not match create new jobs; and a matrix may produce at most 256 jobs (Chapter 01).

**What to notice:** `include` is for **adding** legs and **decorating** existing ones; it is the only way to add a combination that is not in the cross product. Order matters: `exclude` is applied first, then `include`.

## 5. `fail-fast`: Before and After

`fail-fast: true` means that when any leg fails, legs that are queued or running are cancelled (docs, verified 2026-10). One leg, `(ubuntu-22.04, 3.12)`, fails on purpose after 3 seconds; every other leg works for 15 seconds. Same matrix, both settings:

| Leg                     | `fail-fast: true` (run 37319094292) | `fail-fast: false` (run 37319194753) |
| ----------------------- | ----------------------------------- | ------------------------------------ |
| `(ubuntu-latest, 3.11)` | success                             | success                              |
| `(ubuntu-latest, 3.12)` | success                             | success                              |
| `(ubuntu-22.04, 3.12)`  | **failure**                         | **failure**                          |
| `(ubuntu-latest, 3.13)` | **cancelled** (steps had finished)  | success                              |
| `(ubuntu-22.04, 3.13)`  | **cancelled** (never got a runner)  | success                              |
| `(ubuntu-latest, 3.14)` | **cancelled** (never got a runner)  | success                              |
| Legs that got a runner  | **4**                               | **6**                                |

The two "never got a runner" legs have **no steps and an empty runner name** in the API. The run's conclusion is `failure` either way.

**What to notice:**

- With `max-parallel: 2` only two legs run at a time, so four legs were still waiting when the failure arrived. `fail-fast: true` cancelled those two before they ever ran: that is the saving.
- `(ubuntu-latest, 3.13)` shows a subtlety: all three of its steps are `success`, yet the job is `cancelled`. The cancel landed as it finished. A leg marked cancelled may have done its work; do not treat `cancelled` as "did nothing".
- **Billing** (private repo, Chapter 01): 4 legs x 1 minute = 4 minutes versus 6 x 1 = 6. `fail-fast: true` saved a third of the cost, because legs that never got a runner have no runner time to bill.
- The price is information. With `fail-fast: true` you learned that 3.12 on 22.04 fails but **not** whether 3.13 and 3.14 would have passed. For a bug hunt, use `fail-fast: false`.
- We passed `fail-fast` explicitly in both runs (as an expression from an input). We did not test the behavior when the key is omitted.

## 6. `max-parallel`

`max-parallel: 2` caps simultaneous legs. From the `fail-fast: false` run's timestamps:

| Leg                     | Started  | Completed |
| ----------------------- | -------- | --------- |
| `(ubuntu-latest, 3.11)` | 13:44:58 | 13:45:16  |
| `(ubuntu-latest, 3.12)` | 13:44:58 | 13:45:16  |
| `(ubuntu-latest, 3.13)` | 13:45:18 | 13:45:36  |
| `(ubuntu-22.04, 3.12)`  | 13:45:19 | 13:45:25  |
| `(ubuntu-22.04, 3.13)`  | 13:45:27 | 13:45:45  |
| `(ubuntu-latest, 3.14)` | 13:45:39 | 13:45:56  |

The most legs ever overlapping is **2**. The whole run took 58 seconds (13:44:58 to 13:45:56); with no cap, six 15-second legs would overlap and finish in roughly the time of one (about 18 seconds each including setup). The cap trades **wall-clock time** for **runner pressure**. Billing is unchanged: 6 legs, 6 billed minutes. Use it to be polite to a shared service (a database, a rate-limited API), not to save money.

## 7. Concurrency Groups

```yaml
concurrency:
  group: ch10-demo
  cancel-in-progress: ${{ inputs.cancel }}
```

Docs (verified 2026-10): at most **one running** run per group; by default only **one pending** run, and a new arrival **replaces** any existing pending one; `cancel-in-progress: true` cancels the running one when a new one arrives; group names are case-insensitive and may use `github`, `inputs`, `vars`, `needs`, `strategy` and `matrix` contexts. We dispatched three runs 4 seconds apart each time (labels `x1 x2 x3`, then `y1 y2 y3`).

**With `cancel-in-progress: false`** (runs started 13:46:30, :37, :44):

| Run | Final         | What happened                                                                |
| --- | ------------- | ---------------------------------------------------------------------------- |
| x1  | **success**   | started immediately, ran to completion                                       |
| x2  | **cancelled** | went **pending** behind x1, then was **replaced** by x3 without ever running |
| x3  | **success**   | pending until x1 finished, then ran                                          |

**With `cancel-in-progress: true`** (runs created 13:48:16, :30, :44):

| Run | Final         | What happened                                                                        |
| --- | ------------- | ------------------------------------------------------------------------------------ |
| y1  | **cancelled** | annotation: `Canceling since a higher priority waiting request for ch10-demo exists` |
| y2  | **cancelled** | never ran: replaced by y3                                                            |
| y3  | **success**   | ran last                                                                             |

**What to notice:**

- **x2 vanished.** Nobody told you; it simply shows as cancelled. In a "deploy on every push" workflow the middle pushes are skipped on purpose and the **latest** one always wins. That is usually what you want for deploys, and a surprise for anything that must process every event.
- **Cancellation is not instantaneous.** y1's job record is `cancelled`, but its single step ran 13:48:22 to 13:49:03, a full **41 seconds**, all steps `success`. The platform marked the job cancelled while the command still ran to its natural end. Do not rely on `cancel-in-progress` to stop side effects mid-step; design steps to be safe to interrupt or to finish. We did not determine why this run was slow to stop, so we report only the observation.
- Docs (verified 2026-10) also describe `queue: max`, which lets up to 100 runs queue instead of one. It cannot be combined with `cancel-in-progress: true`. We did not test it.

## 8. Timeouts

`timeout-minutes` limits a job or a step. Both set to **1 minute** around `sleep 120`. Real results (run 37318827012):

| Scope                                    | Limit | Actual                                                 | Conclusion                                                               |
| ---------------------------------------- | ----- | ------------------------------------------------------ | ------------------------------------------------------------------------ |
| Job `job_timeout`                        | 60 s  | job ran **90 s** (13:42:08 to 13:43:38), its step 88 s | job **cancelled**                                                        |
| Step `Slow step` (in job `step_timeout`) | 60 s  | step ran **73 s** (13:42:08 to 13:43:21)               | step **failure**, forgiven by `continue-on-error` (conclusion `success`) |

The job's annotations: `The job has exceeded the maximum execution time of 1m0s` and `The operation was canceled.`

**What to notice:**

- **A timeout is enforced late.** A 60-second limit let the job run 88-90 seconds and the step 73. Budget a margin of tens of seconds.
- A job that times out ends **`cancelled`**, not `failure`. If a downstream check treats only `failure()` as bad, a timed-out job can slip past it; use `!success()` or test `needs.<job>.result != 'success'`.
- A step timeout makes that **step** fail; the job continues only if you forgive it (`continue-on-error`), which also made the next step run and report `slow_outcome=failure`.
- Always set a timeout. Without one a hung hosted job runs up to the platform maximum of **6 hours** (limits page, verified 2026-10); on a private repo that is hundreds of billed minutes for one stuck command.

## 9. Forgiving a Leg

`continue-on-error: ${{ matrix.experimental || false }}` makes a leg's failure non-fatal. Our experimental `(ubuntu-latest, 3.14)` leg passed, so we did not exercise the forgiveness; the docs' example shows it prevents `fail-fast` cancellation. The `|| false` default matters: legs without the `experimental` property would otherwise evaluate to an empty string.

## 10. Dynamic Matrices

> ⚠️ ADVANCED TOPIC: Skip on first read.

The matrix can be computed by an earlier job and passed as JSON: `matrix: ${{ fromJSON(needs.plan.outputs.matrix) }}` (docs, verified 2026-10). The producer job decides, for example, to test only the packages that changed. Chapter 21 builds one.

## 11. Runner Concurrency Limits

> ⚠️ ADVANCED TOPIC: Skip on first read.

A matrix is also bounded by your plan's concurrent-job limit: **20** total on Free, with at most **5** macOS jobs (Chapter 05, limits page). A 100-leg matrix on a Free account runs 20 at a time regardless of `max-parallel`.

## 12. Matrix Naming and Required Checks

> ⚠️ ADVANCED TOPIC: Skip on first read.

Each leg's name is the job name plus its values, here `leg (ubuntu-latest, 3.11)`. Branch protection's required checks refer to those **names**, so changing the matrix changes the names and can silently un-require a check (we did not test branch protection here). Keep a single stable summary job that `needs` the matrix and require **that** one.

## 13. Case Study: The 256-Leg Surprise

A library tests 4 interpreters x 8 dependency versions x 8 plugin versions = **256** legs, the platform maximum, on every push. Each leg takes 40 seconds and bills 1 minute on Linux. One run bills 256 minutes, or 256 x 6 = **1,536 mills ($1.536)**. At 200 pushes a month that is 51,200 minutes; with a 2,000-minute allowance the overage is 49,200 minutes = **$295.20 a month**, and `fail-fast: true` would cut a failing run's cost only by what had not yet started. Fixes: test the full matrix nightly and a small one per push; use `include` to add only the odd combinations; split an axis into a scheduled workflow.

## 14. Comparison: Controlling a Pipeline

| Control                    | Setup Effort           | Control                             | Failure Visibility                     | Security Exposure | Maintenance Burden     |
| -------------------------- | ---------------------- | ----------------------------------- | -------------------------------------- | ----------------- | ---------------------- |
| `needs` + `if`             | Low - declare and gate | Strong - exact ordering             | Strong - skipped jobs are visible      | Low               | Low                    |
| Matrix, `fail-fast: true`  | Low - one block        | Moderate - fast but partial results | Fair - cancelled legs hide information | Low               | Low                    |
| Matrix, `fail-fast: false` | Low - one block        | Strong - full results               | Excellent - every leg reports          | Low               | Moderate - higher cost |
| Concurrency group          | Minimal - two lines    | Moderate - only the latest wins     | Weak - dropped runs show as cancelled  | Low               | Low                    |
| Timeouts                   | Minimal - one line     | Moderate - enforced late            | Fair - ends as cancelled               | Low               | Low                    |

## 15. Practical Tips

- Give reporting and cleanup jobs `if: ${{ always() }}`; give pure-notification jobs `failure()`.
- Test the matrix expansion by hand before pushing; count legs and multiply by the rate.
- Use `fail-fast: false` when diagnosing, `true` when you just need a quick red.
- Put deploys in a concurrency group with `cancel-in-progress: false` so a deploy is never cut off mid-way.
- Set `timeout-minutes` on **every** job, with a margin of at least 30 seconds over the real duration.
- Keep a single summary job as the required check, not each matrix leg.

## 16. Demonstrated Failure Modes

**Failure 1: the transitive skip.** Run 37318821322: `c` needs only `b`, yet is skipped because `b` was skipped. Fix: add `if: ${{ !cancelled() }}` where a job should run despite skipped upstream jobs, or restructure.

**Failure 2: the lost verdict.** Run 37319094292 (`fail-fast: true`): two legs never ran, so you cannot tell whether 3.13 on 22.04 passes. Fix: `fail-fast: false` for diagnosis.

**Failure 3: the vanished run.** Run 37319423478 (x2): cancelled while pending, never executed. Fix: choose a design where dropping intermediate runs is acceptable, or use `queue: max`.

**Failure 4: the cancel that did not stop work.** Run 37319632048 (y1): marked `cancelled`, step ran 41 s to completion. Fix: make steps idempotent and safe to finish.

**Failure 5: the late timeout.** Run 37318827012: a 60-second limit fired at 88 seconds. Fix: budget a margin, and never use a timeout as a precise deadline.

**Failure 6: the cancelled that was not a failure.** A timed-out job has conclusion `cancelled`; a `failure()` gate does not fire. Fix: test `needs.<job>.result != 'success'`.

## 17. Key Takeaways

- A job runs only if all its `needs` succeeded; a skipped need skips its dependents.
- `if: always()` runs a job regardless; `failure()` only when something failed; `needs.<job>.result` tells you which.
- Matrix: cross product, minus `exclude`, plus `include`. Ours gave 6 -> 5 -> 6.
- `fail-fast: true` cancelled two never-started legs and saved a third of the cost, at the price of knowledge.
- `max-parallel` caps overlap (we measured 2) and costs wall-clock time, not money.
- A concurrency group keeps one running and one pending run; newer pending replaces older. Cancellation is not instantaneous.
- Timeouts are enforced late (88 s for a 60 s limit) and a timed-out job is `cancelled`.

## 18. Exercises

1. Expand `os: [a, b, c]`, `v: [1, 2]`, `exclude: [{os: b, v: 2}]`, `include: [{os: d, v: 9}]`. How many legs?
2. A job `deploy` has `needs: [test]` and `if: always()`. `test` fails. Does `deploy` run, and is that what you want?
3. Why did the `fail-fast: true` run bill fewer minutes than the `false` run? Give the numbers.
4. You push three commits in quick succession to a workflow with `concurrency: {group: deploy, cancel-in-progress: false}`. Which runs execute?
5. (Hand arithmetic) A matrix has 3 OS legs (linux 50 s, windows 50 s, macos 50 s) with `max-parallel: 1`. Wall-clock time (ignoring setup), and cost in mills.

<details>
<summary>Answers</summary>

1. 3 x 2 = 6, minus 1 exclude = 5, plus 1 new include = **6** legs.
2. It runs (`always()` overrides the default). Usually **not** what you want: a deploy after failed tests. Use `if: ${{ success() }}` or omit the `if`.
3. `true`: 4 legs got runners (4 x 1 min = 4 billed minutes); `false`: 6 legs (6 billed minutes). Two legs never got a runner under `true`.
4. The first (running) and the **last** (pending then run). The middle one is replaced while pending and cancelled.
5. Sequential: 3 x 50 = **150 s** wall-clock. Cost: 6 + 10 + 62 = **78 mills** (each leg bills 1 minute at its rate).

</details>

## 19. Additional Resources

All verified 2026-10.

- GitHub Docs: Running variations of jobs in a workflow (matrix) - https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/run-job-variations
- GitHub Docs: Control the concurrency of workflows and jobs - https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency
- GitHub Docs: Workflow syntax (`needs`, `timeout-minutes`, `strategy`) - https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax
- GitHub Docs: Actions limits - https://docs.github.com/en/actions/reference/limits
- Live evidence: runs 37318821322, 37319094292, 37319194753, 37319409690, 37319423478, 37319437491, 37319632048, 37319663031, 37319694303, 37318827012 in this repo
- Laster, _Learning GitHub Actions_ (O'Reilly), Chapter 8

## 20. Appendix A: Code Index

> 💻 Complete, runnable code for this chapter. Skip when reading for concepts.

### A.1 `needs` skip propagation and matrix expansion

```python
from intro_gha.matrix import expand_matrix

legs = expand_matrix({
    "os": ["ubuntu-latest", "ubuntu-22.04"],
    "py": ["3.11", "3.12", "3.13"],
    "exclude": [{"os": "ubuntu-22.04", "py": "3.11"}],
    "include": [{"os": "ubuntu-latest", "py": "3.14", "experimental": True}],
})
assert len(legs) == 6
assert {"os": "ubuntu-latest", "py": "3.14", "experimental": True} in legs


def results(graph: dict[str, list[str]], failed: set[str]) -> dict[str, str]:
    """Job conclusions under the default `needs` rule: needs must have succeeded."""
    out: dict[str, str] = {}
    for job in graph:  # graph is in topological order
        if job in failed:
            out[job] = "failure"
        elif any(out[n] != "success" for n in graph[job]):
            out[job] = "skipped"
        else:
            out[job] = "success"
    return out


assert results({"a": [], "b": ["a"], "c": ["b"]}, {"a"}) == {
    "a": "failure", "b": "skipped", "c": "skipped"}
```

**Flow:** expand the cross product -> drop `exclude` matches -> add `include` entries; for `needs`, walk the graph in order: a failed job fails, a job with any non-successful need is skipped, otherwise it succeeds.
