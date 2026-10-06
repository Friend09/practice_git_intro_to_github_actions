# Chapter 02: How Actions Works: Event, Workflow, Job, Step, Runner

**Reading Time:** ~40 minutes
**Prerequisites:** Chapter 00 (YAML, refs), Chapter 01 (why Actions)
**Practice Notebook:** `notebooks/practice_02.ipynb`
**Reference Notebook:** `notebooks/lab_02_how_actions_works.ipynb`
**Script:** `labs/lab_02_how_actions_works.py`
**Book Reference:** Laster, Learning GitHub Actions Ch 2 / GitHub Docs: Understanding GitHub Actions
**Depth:** Core
**Default Runtime:** Live repo

---

## Beginner's Guide

**Focus on first:** Sections 3 (the five nouns), 5 (one real run, timestamp by timestamp) and 7 (the empty-workspace failure).

**Skip on first read:** Sections 9-12. They refine the model; you can build workflows without them.

**Key concepts in plain English:**

- **Event:** something happened in the repo (a push, a button click).
- **Workflow:** one YAML file; a recipe that says "when this event happens, do these jobs."
- **Job:** a group of steps that runs on one machine. Jobs run in parallel unless told otherwise.
- **Step:** one command (`run:`) or one reusable action (`uses:`), run in order inside a job.
- **Runner:** the machine that executes a job.

**If you have used a Makefile**, a job is like a target with a shell script body, and `needs` is its dependency list.

> **🔬 Platform Engineer's Lens:** Almost every confusing Actions behavior traces back to one fact: **each job gets its own fresh machine.** Files, installed tools and environment changes do not carry from one job to the next, and the machine starts with an empty workspace. When a teammate says "it works in the first job but the second can't find the file," this chapter is the explanation.

> **🚦 Native vs Marketplace vs Custom:** The event-to-runner pipeline is entirely native; you configure it but never build it. The only custom piece is the logic inside your steps.

## What You'll Learn

- Name the five nouns (event, workflow, job, step, runner) and how they nest
- Trace one real run from the event to each job's start and end time
- Predict which jobs run in parallel and which wait, from `needs`
- Explain why a job starts with an empty workspace and what `checkout` does about it
- Read a run's job timings with `gh run view --json`
- Calculate wall-clock time and billed minutes for a multi-job run
- Show, with a real run, what breaks when `checkout` is missing

## Table of Contents

<!-- toc-start -->

- [Chapter 02: How Actions Works: Event, Workflow, Job, Step, Runner](#chapter-02-how-actions-works-event-workflow-job-step-runner)
  - [Beginner's Guide](#beginners-guide)
  - [What You'll Learn](#what-youll-learn)
  - [Table of Contents](#table-of-contents)
  - [1. The Model in One Picture](#1-the-model-in-one-picture)
  - [2. Running Example: A Real Three-Job Run](#2-running-example-a-real-three-job-run)
  - [3. The Five Nouns](#3-the-five-nouns)
  - [4. From Event to Run](#4-from-event-to-run)
  - [5. Scheduling: One Run, Timestamp by Timestamp](#5-scheduling-one-run-timestamp-by-timestamp)
  - [6. Steps: Sequential, Same Machine](#6-steps-sequential-same-machine)
  - [7. The Empty Workspace: What Checkout Does](#7-the-empty-workspace-what-checkout-does)
  - [8. Jobs Are Isolated](#8-jobs-are-isolated)
  - [9. Why a Fresh VM](#9-why-a-fresh-vm)
  - [10. Where Contexts Come From](#10-where-contexts-come-from)
  - [11. Workflow vs Run vs Job Naming](#11-workflow-vs-run-vs-job-naming)
  - [12. Where This Model Bends](#12-where-this-model-bends)
  - [13. Case Study: "It Passed in lint but Failed in test"](#13-case-study-it-passed-in-lint-but-failed-in-test)
  - [14. Comparison: One Job vs Several](#14-comparison-one-job-vs-several)
  - [15. Practical Tips](#15-practical-tips)
  - [16. Demonstrated Failure Mode: The Missing Checkout](#16-demonstrated-failure-mode-the-missing-checkout)
  - [17. Key Takeaways](#17-key-takeaways)
  - [18. Exercises](#18-exercises)
  - [19. Additional Resources](#19-additional-resources)
  - [20. Appendix A: Code Index](#20-appendix-a-code-index)
    - [A.1 Compute waves and wall-clock from a run](#a1-compute-waves-and-wall-clock-from-a-run)

---

## 1. The Model in One Picture

```
event ──▶ workflow(s) matching it ──▶ run
                                       ├── job A ──▶ runner VM 1 ──▶ step, step, step
                                       ├── job B ──▶ runner VM 2 ──▶ step, step
                                       └── job C (needs A, B) ──▶ runner VM 3 ──▶ step
```

Read it left to right. An event selects workflows; each workflow becomes a **run**; each run schedules **jobs**; each job occupies one **runner** and runs its **steps** in order.

## 2. Running Example: A Real Three-Job Run

> 📌 **Running Example: run 37311041878.** This is a real run of `.github/workflows/ch02-run-anatomy.yml` in this repo, triggered by `workflow_dispatch` on commit `4dafa17c04c85fffb056191c38846d931ea566de`. It has three jobs: **lint** and **test** (independent) and **build** (`needs: [lint, test]`). Every step is a one-line `echo`, so all the time you see is platform overhead, not work. The raw data is saved in `fixtures/run_ch02_anatomy.json`. We return to it in Sections 4-6 and 8.

```yaml
jobs:
  lint: { runs-on: ubuntu-latest, steps: [{ run: echo lint }] }
  test: { runs-on: ubuntu-latest, steps: [{ run: echo test }] }
  build:
    {
      needs: [lint, test],
      runs-on: ubuntu-latest,
      steps: [{ run: echo build }],
    }
```

## 3. The Five Nouns

Definitions, per GitHub Docs (verified 2026-10):

| Noun     | Docs definition (condensed)                                                                     | In Tally's run            |
| -------- | ----------------------------------------------------------------------------------------------- | ------------------------- |
| Event    | A specific activity in a repository that triggers a workflow run                                | `workflow_dispatch`       |
| Workflow | A configurable automated process that runs one or more jobs; a YAML file in `.github/workflows` | `ch02-run-anatomy.yml`    |
| Job      | A set of steps executed on the same runner                                                      | `lint`, `test`, `build`   |
| Step     | A shell script or an action, run sequentially within a job                                      | each `echo`               |
| Runner   | A server that runs your workflows when triggered                                                | three `ubuntu-latest` VMs |

Also from the docs: **by default jobs run in parallel, each on its own runner; a job with `needs` waits for its dependencies.** Those two sentences predict the rest of this chapter.

## 4. From Event to Run

**State before:** nothing running. **Event:** you click "Run workflow" (or `gh workflow run ch02-run-anatomy.yml`). **State after:** GitHub creates one **run** with its own id (`37311041878`), records the event name (`workflow_dispatch`) and the commit it ran against (`4dafa17...`), and schedules the jobs.

| Field      | Value               | Where it comes from                        |
| ---------- | ------------------- | ------------------------------------------ |
| run id     | 37311041878         | assigned by GitHub                         |
| event      | `workflow_dispatch` | the trigger                                |
| head SHA   | `4dafa17c04c8...`   | the commit the workflow file was read from |
| conclusion | `success`           | after all jobs finish                      |

**Command that reads this back:**

```bash
gh run view 37311041878 --json event,headSha,conclusion,jobs
```

**What to notice:**

- The run is pinned to one commit. Later pushes do not change what this run executes.
- The workflow file used is the one **in that commit**. If you push a broken workflow file, the broken one runs.

## 5. Scheduling: One Run, Timestamp by Timestamp

Here is the real timeline from the fixture (all times 2026-10-05 UTC):

| Job   | `needs`    | Started  | Completed | Duration |
| ----- | ---------- | -------- | --------- | -------- |
| lint  | none       | 12:39:27 | 12:39:29  | 2 s      |
| test  | none       | 12:39:28 | 12:39:32  | 4 s      |
| build | lint, test | 12:39:34 | 12:39:37  | 3 s      |

**State dump over time:**

| Time | lint    | test    | build    |
| ---- | ------- | ------- | -------- |
| :27  | running | queued  | waiting  |
| :28  | running | running | waiting  |
| :29  | done    | running | waiting  |
| :32  | done    | done    | eligible |
| :34  | done    | done    | running  |
| :37  | done    | done    | done     |

**What to notice:**

- lint and test **overlapped** (27-29 and 28-32): no `needs` means parallel, exactly as the docs say.
- build started at :34, **after** test finished at :32, not after lint at :29. A `needs` list waits for **all** of its dependencies, so the slowest one sets the start time.
- The two-second gap between :32 and :34 is scheduling latency: finding a runner and starting a VM. It is not your code; you cannot remove it, only avoid paying it repeatedly by using fewer jobs.

**Wall-clock vs billed.** Wall-clock is from :27 to :37, 10 seconds. If this repo were private, each job rounds up to 1 minute, so the run bills **3 minutes** even though all work took 10 seconds. Chapter 01's rounding rule applies to every run you will ever see.

> 📝 **Full implementation:** See [Appendix A.1](#a1-compute-waves-and-wall-clock-from-a-run)

## 6. Steps: Sequential, Same Machine

Inside a job, steps run top to bottom on the **same runner**, sharing its filesystem and environment. If a step fails, later steps are skipped by default (a failed step stops the job). Each step is either:

- `run:` a shell command (bash by default on Linux and macOS, PowerShell on Windows per the docs), or
- `uses:` a packaged **action** (Chapter 04).

```yaml
steps:
  - uses: actions/checkout@v4 # an action: fetches your code
  - run: python -m pytest # a shell command
```

The contrast to hold on to: **steps share a machine; jobs do not.** A file written in step 1 is visible to step 2 of the same job. It is gone by the time another job starts.

## 7. The Empty Workspace: What Checkout Does

A runner starts with an **empty workspace**. Your repository is not on it. The `actions/checkout` action downloads your code into the workspace. We proved this with a real run (`37311217505`, workflow `ch02-no-checkout.yml`):

| Moment                   | Entries in workspace | `pyproject.toml` |
| ------------------------ | -------------------- | ---------------- |
| Before the checkout step | **0**                | MISSING          |
| After the checkout step  | **20**               | present          |

**What to notice:**

- The workspace is not "a bit empty"; it has exactly zero entries. A `run: pytest` placed before checkout fails to find any test file.
- The 20 entries are the repository's top-level files and folders (plus `.git`), at the commit the run was pinned to in Section 4.

## 8. Jobs Are Isolated

Because each job has its own VM, data moves between jobs only deliberately. Using the same run:

| Question                               | Answer                                             |
| -------------------------------------- | -------------------------------------------------- |
| Can `build` read a file `test` wrote?  | No: different VM                                   |
| Can `build` read `test`'s result?      | Yes, if `test` declares an **output** (Chapter 09) |
| Can `build` get `test`'s build output? | Yes, via an **artifact** or **cache** (Chapter 09) |
| Does `build` repeat `checkout`?        | Yes: it also starts empty                          |

**Variant on the same example:** put lint and test as two _steps of one job_ instead of two jobs. They now share a VM and filesystem, run sequentially (2 + 4 = 6 s instead of overlapping), and bill 1 minute instead of 2 on a private repo. Choose by whether you value parallelism or shared state.

## 9. Why a Fresh VM

> ⚠️ ADVANCED TOPIC: Skip on first read.

A fresh, disposable machine per job gives reproducibility (no leftover state) and isolation (one job cannot tamper with another's machine). The price is repeated setup (checkout, tool install) and the data-passing work from Section 8. Caching (Chapter 09) is the standard way to claw back setup time.

## 10. Where Contexts Come From

> ⚠️ ADVANCED TOPIC: Skip on first read.

Expressions like `${{ github.event_name }}` and `${{ github.sha }}` in the demo workflow are filled from the run's metadata (Section 4's table). Chapter 07 covers contexts fully; for now, note that `github.sha` printed in the log equals the head SHA from `gh run view`.

## 11. Workflow vs Run vs Job Naming

> ⚠️ ADVANCED TOPIC: Skip on first read.

A **workflow** is a file; a **run** is one execution of it; a **job** is a unit inside a run. In the UI and API these are different objects with different ids. Many "the workflow failed" messages really mean "this run's job `test` failed".

## 12. Where This Model Bends

> ⚠️ ADVANCED TOPIC: Skip on first read.

Reusable workflows (Chapter 20) let one job _call_ another workflow; matrices (Chapter 10) expand one job definition into many jobs; service containers (Chapter 12) add sidecar containers to a job. All three extend the model without breaking it: still events, runs, jobs on runners, steps in order.

## 13. Case Study: "It Passed in lint but Failed in test"

A team splits `lint` and `test`. `lint` installs dependencies; `test` does not, assuming "the install already happened". It fails with `ModuleNotFoundError`. The cause is Section 8: `test` ran on a different VM that never had the install. Fix options: repeat the install in `test`, restore it from cache, or merge the jobs. The same mistake appears in a missing `checkout` (Section 7), a missing tool setup, or a missing environment variable.

## 14. Comparison: One Job vs Several

| Layout                    | Setup Effort            | Control                    | Failure Visibility               | Security Exposure  | Maintenance Burden        |
| ------------------------- | ----------------------- | -------------------------- | -------------------------------- | ------------------ | ------------------------- |
| One job, many steps       | Minimal - one block     | Moderate - sequential only | Fair - which step failed         | Low - one VM       | Low - one place           |
| Several parallel jobs     | Low - repeat setup      | Strong - run in parallel   | Strong - one red job per problem | Low - isolated VMs | Moderate - repeated setup |
| Jobs chained with `needs` | Moderate - wire outputs | Strong - gated stages      | Strong - clear stage             | Low - isolated VMs | Moderate - passing data   |

## 15. Practical Tips

- First step of almost every job: `uses: actions/checkout@v4`.
- Name your jobs for what fails, not what they do: `lint`, `unit-tests`, `build-wheel`.
- Read timings with `gh run view <id> --json jobs`; the `startedAt`/`completedAt` fields are the ground truth.
- When something is "missing" in a later job, suspect the empty-VM rule before suspecting your code.
- Use `needs` only for true ordering; unnecessary `needs` serializes work and slows the run.

## 16. Demonstrated Failure Mode: The Missing Checkout

Run `37311217505`, live, step 1 (before checkout):

```
count=0
pyproject.toml: MISSING
```

and after the checkout step:

```
count=20
pyproject.toml: present
```

**Symptom:** commands that need your files fail with "No such file or directory" or "no tests ran". **Cause:** the runner's workspace starts empty (Section 7). **Fix:** add `uses: actions/checkout@v4` as the first step of **every job** that needs the code, because each job has its own workspace.

**Second failure: the phantom dependency.** If `build` is not given `needs: [lint, test]`, all three jobs start at :27 and `build` can finish before `test` even fails. The pipeline looks green for a moment and ships work that never passed its checks. The `needs` keyword is the only thing enforcing order.

## 17. Key Takeaways

- Event selects workflows; a workflow produces a run; a run schedules jobs; each job runs steps on one runner.
- Jobs run in parallel by default; `needs` waits for **all** listed jobs.
- Steps in a job share a machine; jobs do not.
- A fresh runner has an empty workspace: `checkout` is not optional.
- A run is pinned to one commit and uses the workflow file from that commit.
- Wall-clock is the longest chain; billing is the sum of rounded-up job minutes.

## 18. Exercises

1. From the Section 5 table, why did `build` start at :34 and not :29?
2. How many billed minutes would run `37311041878` use on a private Linux repo? On a public repo?
3. If `lint` and `test` were merged into one job with two steps, what would the sequential time be, using their durations?
4. A job runs `pytest` as its first step and says "no tests collected". Name the most likely cause and the fix.
5. (Hand arithmetic) Jobs A (30 s), B (45 s) are independent; C (20 s) needs both. Ignoring scheduling latency, what is the wall-clock time, and how many billed minutes on a private repo?

<details>
<summary>Answers</summary>

1. `build` needs both lint and test and waits for the slowest; test finished at :32, so build could start no earlier than that (:34 after scheduling latency).
2. 3 billed minutes (one per job); 0 on a public repo (standard runners free).
3. 2 s + 4 s = 6 s, billed as 1 minute.
4. The workspace is empty because there was no `actions/checkout` step; add it first.
5. A and B overlap, so 45 s; then C adds 20 s: 65 s. Billed: 1 + 1 + 1 = 3 minutes.

</details>

## 19. Additional Resources

All verified 2026-10.

- GitHub Docs: Understanding GitHub Actions - https://docs.github.com/en/actions/get-started/understand-github-actions
- GitHub Docs: Workflow syntax (jobs, needs, steps) - https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax
- GitHub Docs: GitHub-hosted runners - https://docs.github.com/en/actions/reference/runners/github-hosted-runners
- actions/checkout repository - https://github.com/actions/checkout
- `gh run view` manual - https://cli.github.com/manual/gh_run_view
- Live evidence: run 37311041878 (anatomy) and run 37311217505 (no-checkout) in this repo
- Laster, _Learning GitHub Actions_ (O'Reilly), Chapter 2

## 20. Appendix A: Code Index

> 💻 Complete, runnable code for this chapter. Skip when reading for concepts.

### A.1 Compute waves and wall-clock from a run

```python
import json
from datetime import datetime
from pathlib import Path

from intro_gha.workflow import execution_waves

run = json.loads(Path("fixtures/run_ch02_anatomy.json").read_text())
fmt = "%Y-%m-%dT%H:%M:%SZ"
t = {j["name"]: (datetime.strptime(j["started_at"], fmt),
                 datetime.strptime(j["completed_at"], fmt)) for j in run["jobs"]}
waves = execution_waves({"lint": [], "test": [], "build": ["lint", "test"]})
assert waves == [["lint", "test"], ["build"]]
assert t["build"][0] >= max(t["lint"][1], t["test"][1])   # needs honored
wall = max(e for _, e in t.values()) - min(s for s, _ in t.values())
assert wall.seconds == 10
```

**Flow:** load fixture -> parse timestamps -> derive waves from `needs` -> assert build started after both dependencies -> wall-clock = last end minus first start.
