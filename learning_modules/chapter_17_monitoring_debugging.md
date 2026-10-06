# Chapter 17: Monitoring, Logging and Debugging

**Reading Time:** ~55 minutes
**Prerequisites:** Chapter 05 (invalid workflows, `startup_failure`), Chapter 06 (why a workflow did not fire), Chapter 10 (re-runs, cancellation)
**Practice Notebook:** `notebooks/practice_17.ipynb`
**Reference Notebook:** `notebooks/lab_17_monitoring_debugging.ipynb`
**Script:** `labs/lab_17_monitoring_debugging.py`
**Book Reference:** Laster, Learning GitHub Actions Ch 10 / GitHub Docs: Workflow commands, Monitoring and troubleshooting workflows
**Depth:** Core
**Default Runtime:** Live repo

---

## Beginner's Guide

**Focus on first:** Sections 3 (making a log readable), 5 (debug logging, with the engine's own trace) and 8 (the "why didn't it fire" checklist).

**Skip on first read:** Sections 10-12 (local runners, retention, billing endpoints).

**Key concepts in plain English:**

- **Log:** the text output of every step. It is the evidence.
- **Annotation:** a message the runner attaches to a run, a file or a line (`::error::`, `::warning::`, `::notice::`).
- **Job summary:** a Markdown page a job writes for humans, shown on the run page.
- **Debug logging:** extra detail the runner prints when asked, including how every expression was evaluated.
- **Re-run:** running the same run again; it gets a new **attempt** number.

**If you debug with `print` statements**, this chapter is how to turn the runner's own `print`s on, and how to read what your whole repository's CI history says about you.

> **🔬 Platform Engineer's Lens:** Every chapter so far produced a failure we then diagnosed. This one tallies them: **178 runs, 25 failures, and 11 failed CI runs that were all our own mistakes** (8 lint errors committed without running the linter, 2 chapters committed ahead of their notebooks, 1 broken YAML file). The cost of weak observability is not one bad outage; it is a slow drip of small ones. The cure was a 6-line pre-commit hook.

> **🚦 Native vs Marketplace vs Custom:** Everything here is native or first-party tooling: workflow commands, job summaries, debug logging, `gh run`, and the API are GitHub's; `actionlint` and `act` are the two well-known open-source local tools. We wrote only a small metrics script over the API.

## What You'll Learn

- Emit annotations, groups, masks and job summaries with workflow commands
- State the real annotation limit (measured) and whether it is per step or per job
- Turn on debug logging for a re-run and read the expression trace
- Re-run only the failed jobs and know what is and is not repeated
- Work through a checklist for "my workflow did not run"
- Use `actionlint` and `act` locally, and know the danger of `act`'s host mode
- Compute success rate and duration by workflow from the API, and read log-retention settings

## Table of Contents

<!-- toc-start -->

- [Chapter 17: Monitoring, Logging and Debugging](#chapter-17-monitoring-logging-and-debugging)
  - [Beginner's Guide](#beginners-guide)
  - [What You'll Learn](#what-youll-learn)
  - [Table of Contents](#table-of-contents)
  - [1. Three Kinds of Question](#1-three-kinds-of-question)
  - [2. Running Example: A Run Built to Be Debugged](#2-running-example-a-run-built-to-be-debugged)
  - [3. Making a Log Readable: Workflow Commands](#3-making-a-log-readable-workflow-commands)
  - [4. How Many Annotations Can You Emit?](#4-how-many-annotations-can-you-emit)
  - [5. Debug Logging](#5-debug-logging)
  - [6. Re-runs and Attempts](#6-re-runs-and-attempts)
  - [7. Reading Logs from the Terminal](#7-reading-logs-from-the-terminal)
  - [8. "Why Didn't It Run?": A Checklist](#8-why-didnt-it-run-a-checklist)
  - [9. `actionlint`: The Linter That Knows Workflows](#9-actionlint-the-linter-that-knows-workflows)
  - [10. `act`: Running Workflows Locally](#10-act-running-workflows-locally)
  - [11. A Pre-commit Gate](#11-a-pre-commit-gate)
  - [12. Monitoring Your Own History](#12-monitoring-your-own-history)
  - [13. Case Study: The Red Build Nobody Looked At](#13-case-study-the-red-build-nobody-looked-at)
  - [14. Comparison: Ways to Find the Cause](#14-comparison-ways-to-find-the-cause)
  - [15. Practical Tips](#15-practical-tips)
  - [16. Demonstrated Failure Modes](#16-demonstrated-failure-modes)
  - [17. Key Takeaways](#17-key-takeaways)
  - [18. Exercises](#18-exercises)
  - [19. Additional Resources](#19-additional-resources)
  - [20. Appendix A: Code Index](#20-appendix-a-code-index)
    - [A.1 Metrics from the run history and the stage comparison](#a1-metrics-from-the-run-history-and-the-stage-comparison)

---

## 1. Three Kinds of Question

| Question                       | Where the answer is                              |
| ------------------------------ | ------------------------------------------------ |
| "Why did **this run** fail?"   | the log, annotations, debug re-run               |
| "Why did **nothing run**?"     | the trigger rules, workflow state, file validity |
| "How is CI doing **overall**?" | run history and its metrics                      |

We have answered the first two by hand all course; this chapter makes the methods systematic and ends with the third.

## 2. Running Example: A Run Built to Be Debugged

> 📌 **Running Example: `ch17-observability.yml` and this repository's history.** One workflow with four jobs. **commands** emits 15 `notice`, 15 `warning` and 15 `error` annotations, a collapsed log group, a `::debug::` message and a job summary, then runs a step whose `if:` is an expression. **flaky** fails on attempt 1 (when asked) and passes on attempt 2. **stable** just prints its attempt number. **annotation_scope** has two steps emitting 8 errors each. Real runs: **37329174822** (dispatched with the flake on, then re-run **twice**: `--failed` made attempt 2, `--debug` made attempt 3) and **37329444667** (annotation scope). For monitoring we use a snapshot of this repository's 178 runs. Data: `fixtures/observability_ch17_summary.json`, `fixtures/runs_ch17_snapshot.json`, `fixtures/ci_failures_ch17.json`. We return to them throughout.

## 3. Making a Log Readable: Workflow Commands

A step can talk to the runner by printing special lines (docs, verified 2026-10):

| Command                                   | Effect                                                                                 |
| ----------------------------------------- | -------------------------------------------------------------------------------------- |
| `::notice file=F,line=L,title=T::message` | a notice annotation (file and line optional)                                           |
| `::warning ...::message`                  | a warning annotation                                                                   |
| `::error ...::message`                    | an error annotation (it does **not** fail the step by itself; only the exit code does) |
| `::group::Title` ... `::endgroup::`       | a collapsible section in the log                                                       |
| `::add-mask::value`                       | replace `value` with `***` from now on (Chapter 08)                                    |
| `::debug::message`                        | shown **only** when debug logging is on (Section 5)                                    |
| `echo "..." >> "$GITHUB_STEP_SUMMARY"`    | append Markdown to the run's summary page                                              |

Annotations with a `file` and `line` appear **on the code** in the pull request's Files tab, which is why the lint output in Chapter 11 (`ruff --output-format=github`) was so useful.

**Job summaries.** Our job wrote a small table and the step reported `summary_bytes=` the size of what it wrote. Docs: each step's summary is limited to **1 MiB**, and up to **20** summaries are displayed per job. A summary is for humans; do not use it to pass data (Chapter 09).

## 4. How Many Annotations Can You Emit?

The docs do not give a number, so we measured. The `commands` job emitted **15 of each level** in one step. Asked via the API (`GET /check-runs/<id>/annotations`) how many exist:

| Level   | Emitted | Surfaced                                |
| ------- | ------- | --------------------------------------- |
| error   | 15      | **10**                                  |
| warning | 15      | **10**                                  |
| notice  | 15      | **11** (10 ours + 1 the platform added) |

The platform's own notice is the `ubuntu-latest` migration warning we met in Chapter 05 (`... will migrate to Ubuntu 26 beginning October 19, 2026`); every job carries it. So the cap is **10 per level**. Is it per step or per job? Run 37329444667 had one job with **two** steps of 8 errors each:

|                 | Step one | Step two | Job total surfaced |
| --------------- | -------- | -------- | ------------------ |
| errors emitted  | 8        | 8        | 16                 |
| errors surfaced | 8        | 8        | **16**             |

16 surfaced, more than 10, so the cap is **per step**: ten errors, ten warnings and ten notices **per step**. Anything beyond is dropped from the annotations (it is still in the raw log). **Design consequence:** a linter that finds 200 problems will show 10; put the first ten that matter first, and rely on the log or the summary for the rest.

> 📝 **Full implementation:** See [Appendix A.1](#a1-metrics-from-the-run-history-and-the-stage-comparison)

## 5. Debug Logging

Normal logs show what ran. **Debug logging** shows how the runner decided. Two ways to turn it on (docs, verified 2026-10): a repository secret or variable `ACTIONS_STEP_DEBUG` set to `true`, or **re-running with debug logging**. We used the second (`gh run rerun <id> --debug`) on run 37329174822. The same run, two attempts:

| Attempt | How it started         | Total log lines | `##[debug]` lines |
| ------- | ---------------------- | --------------- | ----------------- |
| 1       | the original dispatch  | 187             | **0**             |
| 3       | `gh run rerun --debug` | 333             | **140**           |

Most of the 140 lines are the runner narrating itself (`Evaluating job-level environment variables`, `Evaluating job container`, ...). The valuable ones are the **expression traces**. For our conditional step, `if: ${{ github.event_name == 'workflow_dispatch' && success() }}`:

```
##[debug]Evaluating condition for step: 'A conditional step (its expression is traced in debug mode)'
##[debug]Evaluating: ((github.event_name == 'workflow_dispatch') && success())
##[debug]..Evaluating Equal:
##[debug]....=> 'workflow_dispatch'
##[debug]....=> 'workflow_dispatch'
##[debug]Expanded: (('workflow_dispatch' == 'workflow_dispatch') && true)
```

**What to notice:**

- `Expanded:` shows the expression with **every value substituted**. This is how you find `'false'` being truthy (Chapter 07) or an empty context: it is the engine's own `${{ }}` evaluator, printed.
- Our `echo "::debug::this message appears only when debug logging is on"` printed its message **only** in attempt 3. (In attempt 1 the text appears once, as the script's source line; in attempt 3 it appears twice: the source line and the debug output.)
- Debug logs are large and can include more than normal logs. Do not leave `ACTIONS_STEP_DEBUG` on in a repository; use a re-run with `--debug` when you need it. (Docs: setting a secret or variable `ACTIONS_RUNNER_DEBUG` to `true` additionally adds two diagnostic files to the log archive, the runner process log and the worker process log; we did not try it.)

## 6. Re-runs and Attempts

Run 37329174822 was dispatched with `fail_first_attempt=true`: `flaky` failed (`::error title=Simulated flake::attempt 1 fails on purpose`, exit 1) while `commands` and `stable` succeeded. Then `gh run rerun 37329174822 --failed`:

| Job        | Attempt 1                  | Attempt 2                                  | What it printed in attempt 2 |
| ---------- | -------------------------- | ------------------------------------------ | ---------------------------- |
| `flaky`    | **failure**                | **success** (started 15:00:09)             | `flaky_attempt=2`            |
| `commands` | success (started 14:59:30) | success, **carried over** (still 14:59:30) | its attempt-1 output         |
| `stable`   | success (started 14:59:30) | success, **carried over** (still 14:59:30) | **`stable_attempt=1`**       |

**What to notice:**

- `--failed` re-ran **only** `flaky`. The proof is `stable_attempt=1`: `stable` printed the attempt number it had in attempt 1, because its result was reused, not re-executed. The run's attempt counter went to 2, but only one job executed at attempt 2.
- Each attempt keeps its own job records (`GET /actions/runs/<id>/attempts/<n>/jobs`), so you can compare them: the "flaky" test passed on a retry. That is data about flakiness; do not just click Re-run and forget it.
- A re-run in our case used the **same commit** (the run record keeps one head SHA across attempts), so it cannot pick up a fix you pushed afterwards. To test a fix, push it and run again.
- We did not test how re-runs are billed; the jobs it executes are real jobs, so assume Chapter 01's rules apply and check your own usage.

## 7. Reading Logs from the Terminal

The `gh` CLI turns the run page into scriptable commands we have used all course:

| Need                              | Command                                                           |
| --------------------------------- | ----------------------------------------------------------------- |
| Which runs exist for a commit?    | `gh run list --commit <sha> --json workflowName,event,conclusion` |
| What failed, and why?             | `gh run view <id> --log-failed`                                   |
| Everything, filtered              | `gh run view <id> --log \| grep REPORT`                           |
| One attempt                       | `gh run view <id> --attempt 2 --log`                              |
| Jobs and timings                  | `gh api repos/OWNER/REPO/actions/runs/<id>/jobs`                  |
| Annotations of a job              | `gh api repos/OWNER/REPO/check-runs/<job id>/annotations`         |
| Re-run only failures / with debug | `gh run rerun <id> --failed` / `--debug`                          |

Every table of numbers in this course came from these commands. The habit worth building: when a run fails, read `--log-failed` **first** and the annotations second; the first red step is the cause and later failures are usually consequences.

## 8. "Why Didn't It Run?": A Checklist

A workflow that never starts raises no error (Chapter 06). Work down this list; each item has a real example from this course:

| #   | Check                                                      | How                                        | Real example                                                                                                       |
| --- | ---------------------------------------------------------- | ------------------------------------------ | ------------------------------------------------------------------------------------------------------------------ |
| 1   | Is the workflow **disabled**?                              | `gh workflow list --all`                   | state `disabled_manually`; dispatch fails: `HTTP 422: Cannot trigger a 'workflow_dispatch' on a disabled workflow` |
| 2   | Is the file **valid**?                                     | `actionlint .github/workflows/*.yml`       | a run with `jobs: []`, titled by its path (Chapter 05)                                                             |
| 3   | Did it end in **`startup_failure`**?                       | `gh run view <id>`                         | an allow-list violation: zero jobs, no API message (Chapter 16)                                                    |
| 4   | Do the **filters** match?                                  | `intro_gha.events.would_fire` (Chapter 06) | `paths` ignored on tags; `branches`-only ignores tags                                                              |
| 5   | Was the event made with **`GITHUB_TOKEN`**?                | check who created the tag/PR               | a token-created tag started 0 runs (Chapters 06, 14)                                                               |
| 6   | Is the file on the **default branch** (dispatch/schedule)? | `gh workflow list`                         | docs (Chapter 06)                                                                                                  |
| 7   | Was a run **cancelled** by concurrency?                    | `gh run list --workflow <name>`            | pending run replaced (Chapter 10)                                                                                  |
| 8   | Is it **waiting** for approval?                            | `gh run view <id>`                         | `waiting`, unbilled (Chapters 08, 13)                                                                              |
| 9   | Did the **commit** hit a path filter?                      | `gh run list --commit <sha>`               | a docs-only push: no run (Chapter 03)                                                                              |

Most causes are 1, 2, 4 and 5. Check them in that order.

## 9. `actionlint`: The Linter That Knows Workflows

`actionlint` parses the workflow, understands expressions and contexts, and runs `shellcheck` on `run:` scripts. Every finding below is something it **really reported** in this course, before the bug reached GitHub:

| Chapter | `actionlint` said                                                         | What it prevented                                            |
| ------- | ------------------------------------------------------------------------- | ------------------------------------------------------------ |
| 02      | `SC2012`: use `find` instead of `ls`                                      | a fragile file count in a script                             |
| 05      | `could not parse as YAML: mapping values are not allowed in this context` | an invalid workflow (an unquoted `: `)                       |
| 05      | `label "tally-gpu" is unknown`                                            | a typo'd runner label (fixed with `.github/actionlint.yaml`) |
| 07      | `got unexpected character '+' while lexing expression`                    | arithmetic that GitHub does not have                         |
| 07      | `"github.event.pull_request.title" is potentially untrusted`              | script injection (Chapter 16)                                |
| 07      | `string should not be empty` for `if: !cancelled()`                       | a leading `!` that YAML reads as a tag (needs `${{ }}`)      |
| 07      | `calling function "success" is not allowed here`                          | a status function in `run:`                                  |
| 07      | `context "env" is not allowed here` (in `runs-on`)                        | a runner label from `env`                                    |
| 08      | `context "secrets" is not allowed here` (in `if`)                         | gating a step on a secret                                    |
| 10      | `could not parse as YAML` (unquoted `: ` in a `run:`)                     | a second broken workflow                                     |

It is fast (milliseconds), runs in CI (`ci.yml` installs it) and in the pre-commit hook (Section 11). What it did **not** catch: `inputs.title` interpolated into a `run:` (Chapter 16), because that is a design flaw, not a syntax error.

## 10. `act`: Running Workflows Locally

> ⚠️ ADVANCED TOPIC: Skip on first read.

`act` (v0.2.89, installed with `brew install act`) runs workflows on your machine using Docker, or on the host. Two uses, both tried:

```
$ act -l -W .github/workflows/ch10-needs.yml
Stage  Job ID             ...
0      a
1      report_default
1      b
2      c
3      report_always
3      report_on_failure
```

The **stages** are the dependency waves, and they match `intro_gha.workflow.execution_waves` exactly (`[[a], [b, report_default], [c], [report_always, report_on_failure]]`). A local run of the same workflow reproduced GitHub's results: `a` failed, and the report job printed `REPORT a=failure b=skipped c=skipped`, exactly Chapter 10's table.

**A danger we hit.** We asked for `act -n` (a "dry run") with `-P ubuntu-latest=-self-hosted`, which means **host mode**: the `run:` steps executed on our laptop, and they appeared to run despite the dry-run flag (we saw `exit 1` and `echo` output). Our workflow was harmless. **Never use host mode on a workflow you did not write**, because it runs its shell commands with your user's privileges. Use the default Docker mode, and remember that `act` is an approximation: not every action, context or permission behaves as on GitHub.

## 11. A Pre-commit Gate

Section 12's data shows what to automate. `.githooks/pre-commit` runs three checks before every commit:

```bash
uv run ruff check .
actionlint .github/workflows/*.yml
uv run pytest -q -x
```

Enable it with `make hooks` (`git config core.hooksPath .githooks`). Hooks are local and skippable with `--no-verify`, so CI remains the real gate; the hook just keeps you from pushing the avoidable ones.

## 12. Monitoring Your Own History

> ⚠️ ADVANCED TOPIC: Skip on first read.

The REST API lists every run. A snapshot of this repository (taken during this chapter) has **178 runs across 40 workflows**:

| Conclusion      | Runs | Share |
| --------------- | ---- | ----- |
| success         | 146  | 82.0% |
| failure         | 25   | 14.0% |
| cancelled       | 6    | 3.4%  |
| startup_failure | 1    | 0.6%  |

`ci.yml`, the only workflow that must always be green, ran **57** times with **46** successes (80.7%). The 11 failures are the interesting part. We read each failing run's log and classified it:

| Cause                                                 | Runs  | Prevented by                         |
| ----------------------------------------------------- | ----- | ------------------------------------ |
| `ruff` lint error committed without running it        | **8** | the pre-commit hook                  |
| A chapter committed before its notebooks/labs existed | 2     | the hook (`pytest` checks structure) |
| Invalid workflow YAML                                 | 1     | `actionlint` in the hook             |

**What to notice:** **every one of the 11 was preventable locally in seconds.** Many failures in our other workflows were deliberate (the red-gate demo, the missing-checkout probe); the 25 non-success runs are mostly the experiments of Chapters 02 to 16 working as designed. Counting failures without classifying them would have been misleading.

Other facts we read from the platform:

- **Retention.** `GET /repos/OWNER/REPO/actions/permissions/artifact-and-log-retention` returned `{"days":90,"maximum_allowed_days":90}`: logs and artifacts are kept 90 days, and 90 is the maximum.
- **Usage.** `GET /actions/runs/<id>/timing` returned `billable ... total_ms: 0` for a run on this **public** repository (standard runners are free here, Chapter 01) alongside the run's duration. On a private repo the same endpoint is where you check billed time.

## 13. Case Study: The Red Build Nobody Looked At

A repository's `main` has been red for three days. Each developer assumes someone else is fixing it, because the failure is a flaky integration test that "just needs a re-run". Section 6 shows why that is not enough: a re-run (`--failed`) executes only the failed job on the same commit, so it passes by chance and the red returns on the next push. The fix is observational: classify the failures (Section 12), find that one test fails on attempt 1 in 30% of runs, and quarantine or fix it. (This scenario is constructed to apply Sections 6 and 12; the percentages are illustrative.)

## 14. Comparison: Ways to Find the Cause

| Approach                     | Setup Effort                  | Control                          | Failure Visibility                   | Security Exposure               | Maintenance Burden |
| ---------------------------- | ----------------------------- | -------------------------------- | ------------------------------------ | ------------------------------- | ------------------ |
| Read the log                 | Minimal - open the run        | Weak - you search by eye         | Fair - raw text                      | Low                             | Low                |
| Annotations and summaries    | Low - print workflow commands | Moderate - 10 per level per step | Excellent - on the code and run page | Low                             | Low                |
| Debug re-run                 | Minimal - `--debug`           | Strong - engine trace            | Excellent - expression expansion     | Moderate - may expose more data | Low                |
| Local `actionlint`           | Minimal - one binary          | Strong - catches before pushing  | Strong - precise messages            | Minimal                         | Minimal            |
| Local `act`                  | Moderate - Docker, images     | Moderate - approximates GitHub   | Fair - differs from the real engine  | High in host mode               | Moderate           |
| API metrics over run history | Moderate - a script           | Strong - trends and causes       | Strong - answers "how are we doing"  | Low                             | Moderate           |

## 15. Practical Tips

- Put the **first** ten important findings in annotations; the cap is ten per level per step.
- Re-run with `--debug`, not by leaving `ACTIONS_STEP_DEBUG` on.
- Remember `--failed` re-runs only the failed jobs on the same commit.
- Add `actionlint` and `ruff` to a pre-commit hook and to CI.
- Classify failures by reading logs before deciding they are "flaky".
- Never run `act` in host mode on a workflow you did not write.
- Work down the "didn't run" checklist in order: disabled, invalid, filters, token-made events.

## 16. Demonstrated Failure Modes

**Failure 1: the annotations that disappeared.** 15 emitted, 10 shown. Fix: prioritize, and put the rest in the summary or log.

**Failure 2: the re-run that proved nothing.** `rerun --failed` re-ran one job on the same commit; `stable_attempt=1` shows the other jobs were not re-executed. Fix: record flaky failures, push fixes, and run again.

**Failure 3: the disabled workflow.** `HTTP 422: Cannot trigger a 'workflow_dispatch' on a disabled workflow`; state `disabled_manually`. Fix: `gh workflow enable`.

**Failure 4: the dry run that was not.** `act -n` in host mode executed `run:` steps on the laptop. Fix: use Docker mode and never run untrusted workflows.

**Failure 5: the preventable drip.** 11 failed CI runs, all preventable locally. Fix: the pre-commit hook.

## 17. Key Takeaways

- Workflow commands make logs and pull requests readable; errors do not fail a step by themselves.
- Annotations are capped at **10 per level per step** (measured); the platform adds one notice of its own.
- Debug re-runs add the engine's expression traces (`Expanded: ...`): 0 debug lines became 140 on our run.
- `gh run rerun --failed` re-runs only failed jobs on the same commit; others are carried over.
- A workflow that did not run is usually disabled, invalid, filtered out, or created by `GITHUB_TOKEN`.
- `actionlint` caught ten distinct bugs in this course before GitHub saw them.
- `act` matches GitHub's wave structure but host mode is dangerous.
- Our own CI history: 8 of 11 failures were lint errors; a hook prevents them.
- Logs and artifacts are kept 90 days (max 90).

## 18. Exercises

1. A step emits 25 `::warning::` lines. How many appear as annotations? If the same job has a second step emitting 25 more, how many in total?
2. Run attempt 1: jobs A (ok), B (failed), C (needs B, skipped). You run `gh run rerun --failed`. Which jobs execute at attempt 2? What does C do?
3. In debug output you see `Expanded: (('false' == 'true') && true)`. What is the value of the expression and why is that useful?
4. Your workflow has `on: workflow_dispatch` and the button is missing. List two checks from Section 8.
5. (Hand arithmetic) `ci.yml` ran 57 times, 46 succeeded, and 8 of the failures were lint errors. What fraction of **all** its failures were lint errors, and what would the success rate have been without them?

<details>
<summary>Answers</summary>

1. 10 for the first step (cap per level per step); 10 + 10 = **20** with the second step.
2. Only **B** executes at attempt 2 (A's success is carried over). If B now succeeds, C (whose need is now satisfied) runs too; if B fails again, C stays skipped.
3. `('false' == 'true')` is false, so the whole expression is `false`. The expanded form shows the **actual values** that were compared, exposing wrong or empty contexts.
4. (1) Is the workflow disabled (`gh workflow list --all`)? (2) Is the file on the default branch? Also: is it valid YAML (`actionlint`)?
5. 11 failures in total, 8 were lint: 8 / 11 = **72.7%**. Without them: (46 + 8) / 57 = 54 / 57 = **94.7%** success (counting the 8 lint failures as successes).

</details>

## 19. Additional Resources

All verified 2026-10.

- GitHub Docs: Workflow commands for GitHub Actions - https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands
- GitHub Docs: Enabling debug logging - https://docs.github.com/en/actions/how-tos/monitoring-and-troubleshooting-workflows/troubleshooting-workflows/enabling-debug-logging
- GitHub CLI manual: `gh run` - https://cli.github.com/manual/gh_run
- GitHub REST: Workflow runs and jobs - https://docs.github.com/en/rest/actions/workflow-runs
- actionlint - https://github.com/rhysd/actionlint
- act - https://github.com/nektos/act
- Live evidence: runs 37329174822 and 37329444667, plus this repository's run history (178 runs)
- Laster, _Learning GitHub Actions_ (O'Reilly), Chapter 10

## 20. Appendix A: Code Index

> 💻 Complete, runnable code for this chapter. Skip when reading for concepts.

### A.1 Metrics from the run history and the stage comparison

```python
import collections
import json
from pathlib import Path

from intro_gha.workflow import execution_waves

snap = json.loads(Path("fixtures/runs_ch17_snapshot.json").read_text())
runs = snap["runs"]
c = collections.Counter(r["conclusion"] for r in runs)
assert snap["count"] == len(runs) == 178 and c["success"] == 146
ci = [r for r in runs if r["workflow"] == "ci.yml"]
assert len(ci) == 57 and sum(r["conclusion"] == "success" for r in ci) == 46

graph = {"a": [], "b": ["a"], "c": ["b"], "report_always": ["a", "b", "c"],
         "report_on_failure": ["a", "b", "c"], "report_default": ["a"]}
assert execution_waves(graph) == [["a"], ["b", "report_default"], ["c"],
                                  ["report_always", "report_on_failure"]]
```

**Flow:** count conclusions over the snapshot, group by workflow file, compute success rate; derive dependency waves from `needs` and compare them with the stages `act -l` printed.
