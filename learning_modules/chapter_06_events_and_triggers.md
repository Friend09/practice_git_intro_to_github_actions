# Chapter 06: Events and Triggers in Depth

**Reading Time:** ~50 minutes
**Prerequisites:** Chapter 00 (refs), Chapter 02 (event to run), Chapter 03 (`on`, `paths`)
**Practice Notebook:** `notebooks/practice_06.ipynb`
**Reference Notebook:** `notebooks/lab_06_events_and_triggers.ipynb`
**Script:** `labs/lab_06_events_and_triggers.py`
**Book Reference:** Laster, Learning GitHub Actions Ch 4 / GitHub Docs: Events that trigger workflows
**Depth:** Core
**Default Runtime:** Live repo

---

## Beginner's Guide

**Focus on first:** Sections 4 (what `push` filters really do), 5 (pull request refs) and 16 (the three silent non-triggers).

**Skip on first read:** Sections 10-12 (activity types, the long tail of events, fork behavior).

**Key concepts in plain English:**

- **Trigger:** an entry under `on:` that says which events start the workflow.
- **Filter:** a narrowing rule on a trigger (`branches`, `tags`, `paths`, `types`).
- **Activity type:** the sub-kind of an event, such as a pull request being _opened_ versus _closed_.
- **Default branch:** the branch (usually `main`) that scheduled and `workflow_run` workflows run on.
- **`GITHUB_TOKEN`:** the automatic credential every run gets. Things done with it do not start new runs.

**If you have set up a webhook**, `on:` is the subscription list; the filters are the "only send me these" checkboxes.

> **🔬 Platform Engineer's Lens:** A trigger that does not fire raises no error, no warning and no red X. It just does not exist. Every failure in this chapter is of that kind, and every one was reproduced for real on this repo's runs. The cost is a pull request that merges with no checks, a release that never builds, or a nightly job that quietly stopped months ago.

> **🚦 Native vs Marketplace vs Custom:** Trigger logic is entirely native. The "custom" work is only to _predict_ it. This chapter ships a small executable model (`intro_gha/events.py`) that reproduces ten real outcomes, so you can check a filter before pushing it.

## What You'll Learn

- Read a workflow's `on:` block and say which events start it
- Predict `push` behavior for branches, tags and `paths`, including the case that surprises people
- Explain the pull request merge ref and why `github.sha` is not your commit
- Use `workflow_dispatch`, `repository_dispatch` and `schedule` correctly
- Explain why `workflow_run` runs on the default branch's latest commit
- Explain why a tag pushed with `GITHUB_TOKEN` starts nothing
- Evaluate a cron expression by hand and with code

## Table of Contents

<!-- toc-start -->

- [Chapter 06: Events and Triggers in Depth](#chapter-06-events-and-triggers-in-depth)
  - [Beginner's Guide](#beginners-guide)
  - [What You'll Learn](#what-youll-learn)
  - [Table of Contents](#table-of-contents)
  - [1. Events Are the Front Door](#1-events-are-the-front-door)
  - [2. Running Example: One Workflow, Many Doors](#2-running-example-one-workflow-many-doors)
  - [3. What an Event Looks Like Inside a Run](#3-what-an-event-looks-like-inside-a-run)
  - [4. `push`: Branches, Tags and Paths](#4-push-branches-tags-and-paths)
  - [5. `pull_request`: The Merge Ref](#5-pull_request-the-merge-ref)
  - [6. `workflow_dispatch` and `repository_dispatch`](#6-workflow_dispatch-and-repository_dispatch)
  - [7. `schedule`: Cron](#7-schedule-cron)
  - [8. `workflow_run` and the Token Rule](#8-workflow_run-and-the-token-rule)
    - [`workflow_run`: chaining](#workflow_run-chaining)
    - [The token rule](#the-token-rule)
  - [9. Filter Patterns](#9-filter-patterns)
  - [10. Activity Types](#10-activity-types)
  - [11. The Long Tail of Events](#11-the-long-tail-of-events)
  - [12. Forks and `pull_request_target`](#12-forks-and-pull_request_target)
  - [13. Case Study: The Tag That Ran the Wrong Tests](#13-case-study-the-tag-that-ran-the-wrong-tests)
  - [14. Comparison: Ways to Start a Workflow](#14-comparison-ways-to-start-a-workflow)
  - [15. Practical Tips](#15-practical-tips)
  - [16. Demonstrated Failure Modes](#16-demonstrated-failure-modes)
  - [17. Key Takeaways](#17-key-takeaways)
  - [18. Exercises](#18-exercises)
  - [19. Additional Resources](#19-additional-resources)
  - [20. Appendix A: Code Index](#20-appendix-a-code-index)
    - [A.1 The `would_fire` model](#a1-the-would_fire-model)
    - [A.2 Cron evaluation](#a2-cron-evaluation)

---

## 1. Events Are the Front Door

Chapter 02 said an event selects workflows. Chapter 03 used two triggers. This chapter covers the ones you will use in practice, and the rules that decide whether a given push, pull request or API call actually starts a run. We learn the rules by running experiments and reading what happened.

## 2. Running Example: One Workflow, Many Doors

> 📌 **Running Example: `ch06-events.yml` and its experiments.** One workflow subscribed to five triggers (`push`, `pull_request`, `workflow_dispatch`, `repository_dispatch`, `schedule`) whose only job prints a `REPORT` of what the event looked like. Around it we ran ten real experiments on this repo on 2026-10-05: a push to `main`, a tag push from a laptop, a tag push by `GITHUB_TOKEN`, a branch push, a pull request opened, the PR closed, and a tag deleted. For each we recorded **which workflows fired**: `ci.yml`, `ch03-tally-ci.yml` and `ch06-events.yml`, later joined by two probe workflows (Section 4). Data: `fixtures/events_ch06_observed.json`. We return to it in Sections 4, 5, 8 and 16.

```yaml
on:
  push:
    branches: ["main"]
    tags: ["demo-v*"]
    paths: ["sandbox/**", ".github/workflows/ch06-events.yml"]
  pull_request:
    branches: ["main"]
    paths: ["sandbox/**"]
  workflow_dispatch:
  repository_dispatch:
    types: [tally-ping]
  schedule:
    - cron: "23 4 1 1 *"
```

The other two workflows' triggers, for reference: `ci.yml` is `push: branches: [main]` plus `pull_request` (no filter); `ch03-tally-ci.yml` is `push: paths: [sandbox/**, its own file]` plus `workflow_dispatch`.

## 3. What an Event Looks Like Inside a Run

The workflow's `REPORT` lines, from real runs:

| Event                 | `ref`               | `ref_type` | `ref_name` | `sha`                         | other                                                        |
| --------------------- | ------------------- | ---------- | ---------- | ----------------------------- | ------------------------------------------------------------ |
| `push` (tag)          | `refs/tags/demo-v1` | `tag`      | `demo-v1`  | `4c4ee30f...` (tagged commit) |                                                              |
| `pull_request`        | `refs/pull/1/merge` | `branch`   | `1/merge`  | `b2459d83...`                 | head `de54f8aa...`, `head_ref=demo/ch06-pr`, `base_ref=main` |
| `repository_dispatch` | `refs/heads/main`   | `branch`   | `main`     | `4c4ee30f...`                 | `action=tally-ping`                                          |

**What to notice:**

- The same context names (`github.ref`, `github.sha`) mean different things per event. Never assume `github.sha` is "my latest commit".
- For `repository_dispatch`, the event type you sent (`tally-ping`) arrives as `github.event.action`.
- `github.head_ref` and `github.base_ref` are filled **only** on pull request events; they are empty strings elsewhere (our tag-push report printed `head_ref=` blank).

## 4. `push`: Branches, Tags and Paths

Here is the single most useful table in this chapter. Each row is a **real experiment**; the last three columns say whether that workflow created a run.

| #   | Experiment                                                  | `ci.yml` (branches: main) | `ch03` (paths only) | `ch06-events` (branches + tags + paths) |
| --- | ----------------------------------------------------------- | ------------------------- | ------------------- | --------------------------------------- |
| 1   | Push to `main`, changed only `.github/workflows/ch06-*.yml` | **fired**                 | no                  | **fired**                               |
| 2   | Push tag `demo-v1` from a laptop                            | no                        | **fired**           | **fired**                               |
| 3   | Push tag `demo-v-token` using `GITHUB_TOKEN`                | no                        | no                  | no                                      |
| 4   | Push branch `demo/ch06-pr`, changed `sandbox/...`           | no                        | **fired**           | no                                      |
| 5   | Delete tag `demo-v1`                                        | no                        | no                  | no                                      |

Three more experiments with two extra probe workflows, `ch06-tag-aware.yml` (`branches: ['**']`, `tags-ignore: ['**']`, `paths`) and `ch06-tags-only.yml` (`tags: ['demo-v*']` only):

| #   | Experiment                                       | `tag-aware` | `tags-only` |
| --- | ------------------------------------------------ | ----------- | ----------- |
| 6   | Push to `main`, changed the two probe files      | **fired**   | no          |
| 7   | Push branch `demo/ch06-b`, changed `sandbox/...` | **fired**   | no          |
| 8   | Push tag `demo-v2`                               | no          | **fired**   |

Rows 7 and 8 together confirm that a **tags-only trigger ignores branch pushes**, and row 8 that `tags-ignore` cleanly excludes tags once `branches` is also defined.

**Reading the table, rule by rule:**

1. **A trigger with only `branches` ignores tag pushes** (row 2, `ci.yml` stayed silent). **With only `tags`, it ignores branch pushes.** With neither, both fire (row 2 and 4, `ch03`).
2. **`paths` does not apply to tag pushes.** In row 2 `ch03` ran on a tag even though no file changed under `sandbox/`. Docs (verified 2026-10): paths filters are not evaluated for tag pushes.
3. **`branches` and `paths` are an AND** for branch pushes (row 4: `ch06-events` has `branches: [main]`, so a push to `demo/ch06-pr` did nothing even though the path matched; row 1 passed both).
4. **`paths` uses "any file matches"** (Chapter 03, Section 4). `paths-ignore` is the inverse: the workflow runs unless **every** changed file matches the ignore list. You cannot use `paths` and `paths-ignore` together.
5. **Deleting a ref starts nothing** (row 5).

**State before / after for row 2.** Before: `main` at `4c4ee30`, no tag. Command: `git tag demo-v1 && git push origin demo-v1`. After: two runs, `ch06 events` and `ch03 tally ci`, both with `headBranch=demo-v1` and the **tagged commit's** SHA.

> 📝 **Full implementation:** See [Appendix A.1](#a1-the-would_fire-model)

## 5. `pull_request`: The Merge Ref

When a pull request is opened, GitHub builds a **test merge** of the head branch into the base and exposes it as `refs/pull/<n>/merge`. A `pull_request` workflow runs against that merge, not against your branch tip. Real values from run 37314622219:

| Name                                 | Value               | Meaning                   |
| ------------------------------------ | ------------------- | ------------------------- |
| `github.ref`                         | `refs/pull/1/merge` | the synthetic merge ref   |
| `github.sha`                         | `b2459d83...`       | the **merge commit**      |
| `github.event.pull_request.head.sha` | `de54f8aa...`       | your branch's actual tip  |
| `github.head_ref`                    | `demo/ch06-pr`      | your branch name          |
| `github.base_ref`                    | `main`              | the target branch         |
| API `merge_commit_sha`               | `b2459d83...`       | identical to `github.sha` |

**What to notice:**

- `github.sha` equals the API's `merge_commit_sha`: the workflow tested the **result of merging**, which is what you actually care about.
- `github.sha` is not a commit you made. If a script prints it into a release name, it names a throwaway commit. For "my branch's commit", use `github.event.pull_request.head.sha`.
- Docs (verified 2026-10): `pull_request` defaults to the activity types `opened`, `synchronize` and `reopened`. We closed the PR and **no run started**, because `closed` is not a default type.
- The `branches` filter on `pull_request` matches the **base** branch (`main`), not your branch name. That is why `ch06-events` fired for PR #1 although its branch was `demo/ch06-pr`.

In the experiment table: PR opened with a `sandbox/` change fired `ci.yml` and `ch06-events` (both have a `pull_request` trigger) but **not** `ch03` (no `pull_request` trigger at all).

## 6. `workflow_dispatch` and `repository_dispatch`

Two ways to start a workflow on purpose.

**`workflow_dispatch`** adds a button and CLI entry. Docs (verified 2026-10): it only works if the workflow file exists **on the default branch**; up to 25 inputs, 65,535 characters of payload.

```bash
gh workflow run ch06-upstream.yml                    # on the default branch
gh workflow run ch06-upstream.yml --ref demo/ch06-pr # on another branch's version
```

**`repository_dispatch`** is for external systems. You POST a named event; `types:` filters by name:

```bash
gh api repos/OWNER/REPO/dispatches -f event_type=tally-ping -f 'client_payload[note]=hello'
```

Run 37314448134 received it: `event=repository_dispatch action=tally-ping ref=refs/heads/main`. It always runs on the **default branch**.

Both are the exceptions to the "tokens do not start runs" rule (Section 8): events created with `GITHUB_TOKEN` start nothing, except `workflow_dispatch` and `repository_dispatch`.

## 7. `schedule`: Cron

```yaml
schedule:
  - cron: "23 4 1 1 *" # minute hour day-of-month month day-of-week
```

Five fields, **UTC**. Docs (verified 2026-10): scheduled workflows run on the **last commit of the default branch**; the shortest interval is once every 5 minutes; load at the start of every hour can delay or drop runs; and in a **public** repo they are **disabled automatically after 60 days without repository activity**.

Our demo cron fires once a year, so we cannot watch it live. Instead we evaluate it with code (`next_cron_run`). Worked evaluation from `2026-10-05 12:00 UTC`:

| Expression                   | Meaning            | Next run         |
| ---------------------------- | ------------------ | ---------------- |
| `23 4 1 1 *`                 | 04:23 on 1 January | 2027-01-01 04:23 |
| `*/15 * * * *` (after 12:01) | every 15 minutes   | 2026-10-05 12:15 |
| `0 9 * * 1`                  | 09:00 every Monday | 2026-10-12 09:00 |

**What to notice:**

- `*/15` means "every 15th minute value": 0, 15, 30, 45.
- When **both** day-of-month and day-of-week are restricted, classic cron fires when **either** matches, a famous trap. We implement that.
- Two hours matter in real life: `0 * * * *` runs at the busiest minute of the hour. Pick an odd minute (`23`) to dodge the load the docs warn about.

> 📝 **Full implementation:** See [Appendix A.2](#a2-cron-evaluation)

## 8. `workflow_run` and the Token Rule

### `workflow_run`: chaining

`ch06-downstream.yml` triggers when the workflow named `ch06 upstream` completes. We dispatched the upstream **on a branch** (`demo/ch06-pr`) to see what the downstream sees. Real data:

| Value                   | Upstream run   | Downstream run                            |
| ----------------------- | -------------- | ----------------------------------------- |
| Ran on branch           | `demo/ch06-pr` | (default) `main`                          |
| `github.sha`            | `de54f8aa...`  | `4c4ee30f...` (**main's latest commit**)  |
| `workflow_run.head_sha` | `de54f8aa...`  | `de54f8aa...` (the **upstream's** commit) |
| `github.ref`            |                | `refs/heads/main`                         |

**What to notice:** the downstream workflow runs with `main`'s code and `main`'s `github.sha`, and carries the upstream's commit only inside `github.event.workflow_run.head_sha`. If the downstream needs to check out the code that was tested, it must check out `workflow_run.head_sha` **explicitly**. Docs (verified 2026-10): `workflow_run` runs on the last commit of the default branch and cannot chain more than three levels deep.

### The token rule

Docs (verified 2026-10): "With the exception of `workflow_dispatch` and `repository_dispatch`, other `GITHUB_TOKEN`-triggered events do not create workflow runs at all." We proved it:

| Step    | State                                                                                   |
| ------- | --------------------------------------------------------------------------------------- |
| Before  | no tag `demo-v-token`; `ch06-events` would match `demo-v*`                              |
| Action  | `ch06-token-tag.yml` ran `git tag` + `git push origin demo-v-token` with `GITHUB_TOKEN` |
| After   | tag **exists** on the remote; **0 workflow runs** have `headBranch=demo-v-token`        |
| Control | the same kind of push from a laptop (`demo-v1`) started 2 runs                          |

The design reason: it stops a workflow from endlessly triggering itself. The consequence: a release workflow that creates a tag with `GITHUB_TOKEN` will **not** trigger the `on: push: tags` workflow you wrote to build it (Chapter 14 shows the standard fixes).

## 9. Filter Patterns

Branch, tag and path filters use globs (the matcher is `intro_gha.triggers.matches_filter`):

| Pattern      | Matches                                      | Does not match                |
| ------------ | -------------------------------------------- | ----------------------------- |
| `main`       | `main`                                       | `main2`, `feature/main`       |
| `demo-v*`    | `demo-v1`, `demo-v-token`                    | `demo-v/x` (`*` stops at `/`) |
| `demo/**`    | `demo/ch06-pr`, `demo/a/b`                   | `demo` alone                  |
| `sandbox/**` | any file under `sandbox/`                    | `sandboxes/x.py`              |
| `**.md`      | any file ending `.md` at any depth           |                               |
| `!docs/**`   | negation: remove matches after a prior match |                               |

Rule: `*` does not cross `/`; `**` does. A `!` pattern excludes, and **order matters** (the last match wins); a list with only `!` patterns matches nothing.

## 10. Activity Types

> ⚠️ ADVANCED TOPIC: Skip on first read.

Many events have sub-kinds. For `pull_request` the full list includes `opened`, `synchronize`, `reopened`, `closed`, `labeled`, `ready_for_review` and more. Setting `types: [closed]` is how you react to merges (`github.event.pull_request.merged` is true when it merged). Setting `types:` **replaces** the default list, so `types: [labeled]` means PR pushes no longer trigger it.

## 11. The Long Tail of Events

> ⚠️ ADVANCED TOPIC: Skip on first read.

Beyond these, workflows can respond to `issues`, `issue_comment`, `release`, `create`, `delete`, `fork`, `watch`, `check_run`, `deployment`, `workflow_call` (Chapter 20) and many more. Each has its own context and its own default branch behavior. When in doubt, add `workflow_dispatch` and a `REPORT` step like ours to see the real payload before building on it.

## 12. Forks and `pull_request_target`

> ⚠️ ADVANCED TOPIC: Skip on first read.

A pull request from a **fork** runs with a read-only token and no secrets by default. `pull_request_target` runs with the **base** repo's context and secrets, which makes it powerful and dangerous. Chapter 16 covers when it is safe; until then, do not use it.

## 13. Case Study: The Tag That Ran the Wrong Tests

A team writes `on: push: paths: ['src/**']` believing "tests run only when source changes". Releasing means pushing tags. Every release tag **also runs the full test suite**, because `paths` is ignored for tags (our experiment, row 2: `ch03` fired on a tag with no changed files). Nobody noticed because the extra runs were green. The fix, if unwanted: make the trigger explicitly tag-aware with **both** `branches: ['**']` and `tags-ignore: ['**']`. (`tags-ignore` alone would also silence branch pushes, because defining only one ref type blocks the other; Section 16 shows the live proof.)

## 14. Comparison: Ways to Start a Workflow

| Trigger               | Setup Effort                   | Control                            | Failure Visibility                   | Security Exposure                             | Maintenance Burden        |
| --------------------- | ------------------------------ | ---------------------------------- | ------------------------------------ | --------------------------------------------- | ------------------------- |
| `push`                | Minimal - one key              | Moderate - branch/tag/path filters | Weak - a non-match is silent         | Low - your commits                            | Low                       |
| `pull_request`        | Minimal - one key              | Moderate - base branch filter      | Weak - silent if filtered            | Moderate - runs PR code (read-only for forks) | Low                       |
| `workflow_dispatch`   | Low - add inputs               | Strong - explicit human intent     | Excellent - you see the run you made | Low - needs write access                      | Low                       |
| `repository_dispatch` | Moderate - needs an API caller | Strong - external system decides   | Fair - payload is free-form          | Moderate - caller needs a token               | Moderate                  |
| `schedule`            | Minimal - one cron             | Weak - best-effort timing          | Weak - disabled after 60 idle days   | Low                                           | Moderate - silently stops |
| `workflow_run`        | Low - name the upstream        | Moderate - default-branch code     | Fair - chained across runs           | Moderate - upstream data is untrusted         | Moderate - 3-level cap    |

## 15. Practical Tips

- Add `workflow_dispatch` to every workflow: it is the cheapest way to test and to re-run.
- Use `REPORT`-style dump steps (our pattern) when you meet an unfamiliar event.
- Decide on purpose whether tags should trigger: add `tags-ignore` or `tags` explicitly.
- Never create a tag or push a commit with `GITHUB_TOKEN` and expect another workflow to react.
- Pick odd cron minutes; check scheduled workflows aren't silently disabled (`gh workflow list --all`).
- In `workflow_run` consumers, check out `workflow_run.head_sha`, not the default checkout.

## 16. Demonstrated Failure Modes

**Failure 1: the tag that starts nothing.** Symptom: you tag a release and the build never runs. Evidence: `demo-v-token` exists on the remote, matches `demo-v*`, and produced **0 runs**; the same pattern from a laptop produced 2. Cause: it was created with `GITHUB_TOKEN`. Fix: create the tag with a personal access token or app token, or call the build as a reusable workflow (Chapters 14 and 20).

**Failure 2: the `paths` filter that does not filter.** Symptom: "path-filtered" tests run on every release. Evidence: `ch03` fired on tag push `demo-v1` with an empty change list. Cause: paths are not applied to tags. Fix: use `branches: ['**']` together with `tags-ignore: ['**']`. We verified it live with `ch06-tag-aware.yml`: it fired on a branch push (run 37315330848) and on `main`, and did **not** fire when tag `demo-v2` was pushed (the same tag started `ch03`, `ch06 events` and `ch06 tags only`).

**Failure 3: the `branches` filter that blocks tags.** Symptom: CI is silent on tags. Evidence: `ci.yml` (`branches: [main]`) did not fire on `demo-v1`. Cause: with only `branches` defined, tag pushes never match. This is usually the _desired_ behavior, but it is silent when you meant otherwise.

**Failure 4: the downstream that tests the wrong code.** Symptom: a `workflow_run` workflow passes using stale code. Evidence: downstream `github.sha` was `main`'s commit `4c4ee30f`, not the upstream's `de54f8aa`. Fix: check out `github.event.workflow_run.head_sha`.

Every outcome above is asserted in `tests/test_events.py` by comparing the model against the real runs.

## 17. Key Takeaways

- A trigger that does not match raises no error; it just never starts a run.
- `branches`-only ignores tags; `tags`-only ignores branches; neither means both fire.
- `paths` is never applied to tag pushes.
- `pull_request` runs against `refs/pull/N/merge`; `github.sha` is the merge commit, `head.sha` is yours.
- `workflow_dispatch` needs the file on the default branch; `repository_dispatch` carries its type in `github.event.action`.
- `schedule` and `workflow_run` run on the default branch's latest commit.
- Anything done with `GITHUB_TOKEN` starts no runs, except the two dispatch events.
- Cron is UTC; schedules in idle public repos stop after 60 days.

## 18. Exercises

1. Using Section 4's rules, would `ci.yml` (push: branches [main]) fire when `v2.0` is pushed as a tag? Why?
2. A workflow has `on: pull_request: types: [closed]`. Does opening a PR trigger it? Does merging?
3. What is the next UTC run, after `2026-10-05 12:00`, of `30 6 * * 1-5`? Of `0 0 13 * 5`?
4. In the Section 5 table, which two values are equal and why does that matter?
5. (Hand arithmetic) A repo pushes a tag every release (12/year) and each tag runs a 3-job Linux workflow of 40 s per job, private repo. How many billed minutes and mills per year does the unintended tag run cost?

<details>
<summary>Answers</summary>

1. No. A trigger with only `branches` does not fire for tag pushes (experiment row 2: `ci.yml` stayed silent).
2. Opening: no (type `opened` is not in `[closed]`). Merging: yes (a merged PR is `closed`; `merged` is true in the payload).
3. `30 6 * * 1-5` is 06:30 on weekdays; 2026-10-05 is a Monday and 12:00 is past 06:30, so the next is Tue 2026-10-06 06:30. `0 0 13 * 5` has both day fields restricted, so it fires on the 13th **or** any Friday at 00:00: next is Fri 2026-10-09 00:00.
4. `github.sha` and the API's `merge_commit_sha` (both `b2459d83...`). It proves the run tested the merge result.
5. 3 jobs x ceil(40/60)=1 min = 3 min per tag; 12 tags = 36 min; 36 x 6 = 216 mills ($0.216) per year.

</details>

## 19. Additional Resources

All verified 2026-10.

- GitHub Docs: Events that trigger workflows - https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows
- GitHub Docs: Workflow syntax (`on`, filters, filter pattern cheat sheet) - https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax
- GitHub Docs: Actions limits - https://docs.github.com/en/actions/reference/limits
- GitHub REST: Create a repository dispatch event - https://docs.github.com/en/rest/repos/repos#create-a-repository-dispatch-event
- crontab.guru (cron expression checker) - https://crontab.guru
- Live evidence: runs 37314006999, 37314113036, 37314112978, 37314622219, 37314448134, 37314725398 in this repo
- Laster, _Learning GitHub Actions_ (O'Reilly), Chapter 4

## 20. Appendix A: Code Index

> 💻 Complete, runnable code for this chapter. Skip when reading for concepts.

### A.1 The `would_fire` model

```python
import json
from intro_gha import FIXTURES_DIR, WORKFLOWS_DIR
from intro_gha.events import would_fire
from intro_gha.workflow import load_workflow

obs = json.loads((FIXTURES_DIR / "events_ch06_observed.json").read_text())
wfs = {n: load_workflow(WORKFLOWS_DIR / n) for n in obs["workflows"]}
for o in obs["observations"]:
    predicted = sorted(n for n, wf in wfs.items() if would_fire(wf, o["event"]))
    assert predicted == sorted(o["fired"]), o["id"]
```

**Flow:** for each real experiment -> evaluate every workflow's trigger against the event (ref filters, then paths, then token rule) -> compare the set that fires with the set that really fired.

### A.2 Cron evaluation

```python
from datetime import datetime
from intro_gha.events import next_cron_run

assert next_cron_run("23 4 1 1 *", datetime(2026, 10, 5, 12, 0)) == datetime(2027, 1, 1, 4, 23)
assert next_cron_run("0 9 * * 1", datetime(2026, 10, 5, 12, 0)) == datetime(2026, 10, 12, 9, 0)
```

**Flow:** expand each of the five fields to a set of allowed values -> step forward day by day -> on a day whose month and day fields match, return the earliest allowed hour and minute after the start.
