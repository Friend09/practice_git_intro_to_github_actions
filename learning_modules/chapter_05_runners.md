# Chapter 05: Runners: Hosted, Larger, Self-Hosted, ARC

**Reading Time:** ~45 minutes
**Prerequisites:** Chapter 01 (billing), Chapter 02 (jobs and runners), Chapter 03 (`runs-on`)
**Practice Notebook:** `notebooks/practice_05.ipynb`
**Reference Notebook:** `notebooks/lab_05_runners.ipynb`
**Script:** `labs/lab_05_runners.py`
**Book Reference:** Laster, Learning GitHub Actions Ch 5 / GitHub Docs: GitHub-hosted runners, Self-hosted runners
**Depth:** Core
**Default Runtime:** Live repo (guarded)

---

## Beginner's Guide

**Focus on first:** Sections 3 (what a hosted runner really is, measured), 4 (`runs-on` forms) and 16 (the job that waits forever).

**Skip on first read:** Sections 10-12 (ARC internals, scale sets, runner groups).

**Key concepts in plain English:**

- **Runner:** the machine that executes one job.
- **GitHub-hosted runner:** a VM GitHub starts for you and discards after the job.
- **Label:** a name in `runs-on` that selects which runner may take the job.
- **Self-hosted runner:** a machine **you** register; GitHub sends it jobs.
- **ARC:** a Kubernetes add-on that starts and stops self-hosted runners automatically.

**If you have ever SSHed into a build server**, a self-hosted runner is that server, with an agent that asks GitHub "any work for me?"

> **🔬 Platform Engineer's Lens:** A self-hosted runner executes the code in pull requests on a machine **you own and must defend**. GitHub's own security guidance says self-hosted runners "should almost never be used for public repositories", because anyone can open a pull request and run code on your hardware. The cost of getting this wrong is not a bill; it is a compromised build machine inside your network.

> **🚦 Native vs Marketplace vs Custom:** Hosted runners are native and the default. Self-hosted runners are the answer only to a hardware, network or data-residency requirement (Chapter 01, Section 8). ARC is the native-ecosystem way to run self-hosted runners at scale; writing your own autoscaler is the custom path and rarely worth it.

## What You'll Learn

- Read real CPU, memory and OS figures for each hosted label from a live run
- Write `runs-on` as a string, a label list, a matrix value and an expression
- Compute the cost of a multi-OS matrix run on a private repo
- Explain what "ephemeral" means for hosted, ephemeral and persistent runners
- Say when a self-hosted runner is justified and what it exposes
- Describe what ARC and runner scale sets do
- Guard a self-hosted job so it skips instead of hanging, and diagnose a job stuck in the queue

## Table of Contents

<!-- toc-start -->

- [Chapter 05: Runners: Hosted, Larger, Self-Hosted, ARC](#chapter-05-runners-hosted-larger-self-hosted-arc)
  - [Beginner's Guide](#beginners-guide)
  - [What You'll Learn](#what-youll-learn)
  - [Table of Contents](#table-of-contents)
  - [1. What a Runner Is](#1-what-a-runner-is)
  - [2. Running Example: One Job, Four Machines](#2-running-example-one-job-four-machines)
  - [3. What a Hosted Runner Is, Measured](#3-what-a-hosted-runner-is-measured)
  - [4. The Forms of `runs-on`](#4-the-forms-of-runs-on)
  - [5. Worked Trace: Price the Matrix](#5-worked-trace-price-the-matrix)
  - [6. Ephemeral by Design](#6-ephemeral-by-design)
  - [7. The `runner` Context](#7-the-runner-context)
  - [8. Larger Runners](#8-larger-runners)
  - [9. Self-Hosted Runners](#9-self-hosted-runners)
  - [10. Actions Runner Controller (ARC)](#10-actions-runner-controller-arc)
  - [11. The Guard Pattern: Skip Instead of Hang](#11-the-guard-pattern-skip-instead-of-hang)
  - [12. Runner Groups and Labels](#12-runner-groups-and-labels)
  - [13. Case Study: The Build That Got Slower After Going Private](#13-case-study-the-build-that-got-slower-after-going-private)
  - [14. Comparison: Where to Run a Job](#14-comparison-where-to-run-a-job)
  - [15. Practical Tips](#15-practical-tips)
  - [16. Demonstrated Failure Mode: The Job That Waits Forever](#16-demonstrated-failure-mode-the-job-that-waits-forever)
  - [17. Key Takeaways](#17-key-takeaways)
  - [18. Exercises](#18-exercises)
  - [19. Additional Resources](#19-additional-resources)
  - [20. Appendix A: Code Index](#20-appendix-a-code-index)
    - [A.1 Compare measured runners to the docs and price the run](#a1-compare-measured-runners-to-the-docs-and-price-the-run)

---

## 1. What a Runner Is

Chapter 02 said a runner is "the machine that runs a job." This chapter measures that machine. We ask a real runner how many CPUs and how much memory it has, compare it with GitHub's published table, work out what each costs, and then look at the two ways jobs go wrong: no matching runner, and a runner you should not have.

## 2. Running Example: One Job, Four Machines

> 📌 **Running Example: `ch05-runners.yml`.** One job definition expanded by a matrix into **four** runners: `ubuntu-latest`, `ubuntu-22.04`, `windows-latest`, `macos-latest`. Each prints one `REPORT` line with its OS, architecture, environment, CPU count and memory. A fifth job, `self-hosted-guarded`, is gated by `if: vars.GHA_ENABLE_SELFHOSTED == 'true'`. Real run **37312789542** on this **public** repo. Data in `fixtures/run_ch05_runners.json`. We return to it in Sections 3, 5, 9 and 11.

```yaml
hosted:
  runs-on: ${{ matrix.label }}
  strategy:
    fail-fast: false
    matrix:
      label: [ubuntu-latest, ubuntu-22.04, windows-latest, macos-latest]
```

## 3. What a Hosted Runner Is, Measured

The `REPORT` lines from run 37312789542:

```
REPORT label=ubuntu-22.04    os=Linux   arch=X64   env=github-hosted cpu=4 mem_mb=15988
REPORT label=windows-latest  os=Windows arch=X64   env=github-hosted cpu=4 mem_mb=16379
REPORT label=ubuntu-latest   os=Linux   arch=X64   env=github-hosted cpu=4 mem_mb=15989
REPORT label=macos-latest    os=macOS   arch=ARM64 env=github-hosted cpu=3 mem_mb=7168
```

Compare with GitHub's published specification (verified 2026-10):

| Label            | Measured here (public repo) | Docs, public repo        | Docs, **private** repo |
| ---------------- | --------------------------- | ------------------------ | ---------------------- |
| `ubuntu-latest`  | 4 CPU, ~16 GB, Linux X64    | 4 vCPU, 16 GB            | **2 vCPU, 8 GB**       |
| `windows-latest` | 4 CPU, ~16 GB, Windows X64  | 4 vCPU, 16 GB            | **2 vCPU, 8 GB**       |
| `macos-latest`   | 3 CPU, 7 GB, macOS ARM64    | 3 vCPU (M1), 7 GB, arm64 | same: 3 vCPU, 7 GB     |

**What to notice:**

- Our measurement matches the docs for a **public** repo. The same label gives **half** the CPU and memory on a **private** repo. A build that takes 4 minutes on a public repo can take noticeably longer when you move it private. We measured public only, so the private column is the docs' claim, not ours.
- `env=github-hosted` comes from the `RUNNER_ENVIRONMENT` variable. A self-hosted runner reports `self-hosted` here; scripts can branch on it.
- `ubuntu-latest` and `ubuntu-22.04` report the same CPU and memory (15,989 vs 15,988 MB) but are different images: per the docs `ubuntu-latest` currently maps to Ubuntu 24.04, and the alias is one GitHub moves over time (Section 6). We caught it moving: the runner itself later annotated our Chapter 10 runs with `The ubuntu-latest label will migrate to Ubuntu 26 beginning October 19, 2026.` (see `fixtures/exec_ch10_all.json`), so a workflow using `ubuntu-latest` can change operating system with no edit to the file.

> 📝 **Full implementation:** See [Appendix A.1](#a1-compare-measured-runners-to-the-docs-and-price-the-run)

## 4. The Forms of `runs-on`

| Form         | Example                                                     | Meaning                                  |
| ------------ | ----------------------------------------------------------- | ---------------------------------------- | ----------------- | ------------------ |
| String       | `runs-on: ubuntu-latest`                                    | One label                                |
| List         | `runs-on: [self-hosted, linux]`                             | A runner must have **all** listed labels |
| Matrix value | `runs-on: ${{ matrix.label }}`                              | One job per label (our example)          |
| Expression   | `runs-on: ${{ github.repository == 'a/b' && 'ubuntu-latest' |                                          | 'self-hosted' }}` | Chosen at run time |

The list form is "and", not "or": `[self-hosted, tally-gpu]` needs a runner that is self-hosted **and** labelled `tally-gpu`. If you want "either of these", use a matrix.

Other hosted labels exist beyond the four we ran. `actionlint` 1.7.12 recognizes, among others, `ubuntu-24.04`, `ubuntu-24.04-arm`, `ubuntu-slim`, `windows-11-arm`, `macos-26`, `macos-15` and the larger sizes `ubuntu-latest-4-cores`, `ubuntu-latest-8-cores`, `macos-latest-xlarge`. (This list is **actionlint's** knowledge, taken from its own error message, not a GitHub guarantee; check the runners docs for what your plan can use.)

## 5. Worked Trace: Price the Matrix

Durations from the run's timestamps (Chapter 02's method):

| Label            | Started  | Completed | Seconds | Billed minutes | Rate (mills/min) | Cost (mills)          |
| ---------------- | -------- | --------- | ------- | -------------- | ---------------- | --------------------- |
| `ubuntu-latest`  | 12:54:29 | 12:54:32  | 3       | 1              | 6                | 6                     |
| `ubuntu-22.04`   | 12:54:29 | 12:54:37  | 8       | 1              | 6                | 6                     |
| `windows-latest` | 12:54:29 | 12:54:32  | 3       | 1              | 10               | 10                    |
| `macos-latest`   | 12:54:35 | 12:54:40  | 5       | 1              | 62               | 62                    |
| **Total**        |          |           |         | **4 min**      |                  | **84 mills = $0.084** |

**What to notice:**

- This repo is **public**, so the real bill is $0 (Chapter 01). The $0.084 is what the same run **would** cost on a private repo past its free minutes.
- The macOS job ran only 5 seconds yet costs **62 of the 84 mills**, 74% of the total. One macOS job dominates a mixed-OS bill.
- The wall-clock was 11 seconds (12:54:29 to 12:54:40), but the macOS job started 6 seconds after the others: macOS runner pools start more slowly. Do not assume matrix jobs begin together.

## 6. Ephemeral by Design

Per GitHub's docs (Chapter 01), a hosted runner is a **new VM for each job**, discarded afterwards. Practical consequences:

| Question                                       | Answer                                                          |
| ---------------------------------------------- | --------------------------------------------------------------- |
| Does the second job see the first job's files? | No (Chapter 02)                                                 |
| Can `ubuntu-latest` change under you?          | Yes: it is an alias GitHub re-points to a newer image over time |
| How do I pin the OS?                           | Use the exact label, e.g. `ubuntu-24.04`                        |
| Is state ever shared?                          | Only via outputs, artifacts and caches (Chapter 09)             |

## 7. The `runner` Context

Inside a job, the `runner` context describes the machine: `runner.os` (`Linux`, `Windows`, `macOS`), `runner.arch` (`X64`, `ARM64`), and the `RUNNER_ENVIRONMENT` variable. Our workflow uses `if: runner.os == 'Linux'` to choose which report step runs, and the three OS-specific steps use different shells (`bash`, `pwsh`). Chapter 07 covers contexts in full.

## 8. Larger Runners

GitHub-hosted **larger runners** (more cores, more memory, optional static IPs) are billed per minute and are, per the billing docs, **not free for public repositories**. They are the middle path when standard runners are too small but you do not want to operate machines yourself. Concurrency for larger runners is a separate limit: Team and Enterprise plans allow up to 1,000 concurrent larger-runner jobs, and the macOS maximum (5 on Free/Pro/Team, 50 on Enterprise) is shared with standard runners (limits page, verified 2026-10).

## 9. Self-Hosted Runners

A self-hosted runner is a machine you register to a repo, organization or enterprise. It polls GitHub for jobs matching its labels.

| Aspect                        | Hosted                                | Self-hosted                                 |
| ----------------------------- | ------------------------------------- | ------------------------------------------- |
| Who owns the machine          | GitHub                                | You                                         |
| Per-minute charge             | Yes (private repos, beyond allowance) | None from GitHub; you pay for the machines  |
| Clean state each job          | Yes                                   | Only if you make it ephemeral               |
| Hardware                      | Fixed menu                            | Anything (GPU, ARM boards, on-prem network) |
| Max job time                  | 6 hours                               | 5 days (limits page)                        |
| Queue wait before auto-cancel | n/a (pool)                            | 24 hours                                    |

**Security, from the docs (verified 2026-10):**

- "Self-hosted runners should almost never be used for public repositories on GitHub, because any user can open pull requests against the repository and compromise the environment."
- An **ephemeral** (or just-in-time) runner "performs at most one job before being automatically removed", which limits what a compromised job can leave behind. Reusing the same hardware for several such runners still risks cross-job exposure, so automation must ensure each starts clean.

**Rule for this course:** this repo is public, so we **never** register a self-hosted runner for it. The self-hosted job in our workflow exists to show the guard pattern (Section 11), and it never runs.

## 10. Actions Runner Controller (ARC)

> ⚠️ ADVANCED TOPIC: Skip on first read.

Per the docs, ARC is "a Kubernetes operator that orchestrates and scales self-hosted runners for GitHub Actions." In outline: you install ARC on a Kubernetes cluster; a **runner scale set** represents a pool; a **listener** pod holds a connection to GitHub and is told when jobs are waiting; ARC starts **ephemeral runner pods**, one per job, and deletes each when its job completes. The result is self-hosted hardware with hosted-style hygiene. Setup needs a cluster and credentials only you can create, so this course teaches it but cannot demonstrate it in the sandbox.

## 11. The Guard Pattern: Skip Instead of Hang

In run 37312789542 the `self-hosted-guarded` job's `if:` was false (the repository variable `GHA_ENABLE_SELFHOSTED` is not set), and the result was:

| Field               | Value                           |
| ------------------- | ------------------------------- |
| conclusion          | **skipped**                     |
| started - completed | 12:54:26 - 12:54:26 (0 seconds) |
| runner assigned     | none                            |

**What to notice:** a job-level `if:` is evaluated **before** a runner is requested, so a guarded job costs nothing and never waits. This is how every credential- or hardware-dependent demo in this course is written: it skips until you opt in by setting the variable. Opt in with `gh variable set GHA_ENABLE_SELFHOSTED --body true`, and only after registering a runner you control.

## 12. Runner Groups and Labels

> ⚠️ ADVANCED TOPIC: Skip on first read.

Organizations can place runners in **groups** and restrict which repos may use each group (see the docs on managing access to self-hosted runners; we did not re-verify the details here); labels then select within the group. By convention a self-hosted runner carries `self-hosted` plus labels for its OS and architecture, and `actionlint` recognizes `self-hosted`, `linux`, `macos`, `windows`, `x64`, `arm` and `arm64` as known labels. Custom labels (our `tally-gpu`) must be added to `.github/actionlint.yaml` or `actionlint` reports `label "tally-gpu" is unknown`.

## 13. Case Study: The Build That Got Slower After Going Private

A team moves an open-source library into a private repo. Same workflow, same `ubuntu-latest`. Build time rises from about 4 minutes to about 7. Nothing changed in the code. The cause is Section 3's table: the label now maps to a **2 vCPU, 8 GB** machine instead of **4 vCPU, 16 GB**, and a parallel test suite is CPU-bound. Fixes, cheapest first: reduce parallelism to match, cache dependencies (Chapter 09), or pay for a larger runner (Section 8).

## 14. Comparison: Where to Run a Job

| Option                  | Setup Effort                | Control                       | Failure Visibility           | Security Exposure                        | Maintenance Burden          |
| ----------------------- | --------------------------- | ----------------------------- | ---------------------------- | ---------------------------------------- | --------------------------- |
| Standard hosted         | Minimal - one label         | Weak - fixed menu             | Excellent - UI and logs      | Low - fresh VM per job                   | Minimal - GitHub runs it    |
| Larger hosted           | Low - create in settings    | Moderate - choose size        | Excellent - UI and logs      | Low - fresh VM per job                   | Minimal - GitHub runs it    |
| Self-hosted, persistent | Moderate - install agent    | Excellent - any hardware      | Strong - logs plus host logs | Very High - state persists, runs PR code | High - patch and clean it   |
| Self-hosted, ephemeral  | High - needs automation     | Excellent - any hardware      | Strong - logs plus host logs | Moderate - one job per runner            | High - build the automation |
| ARC on Kubernetes       | High - cluster and operator | Excellent - pod spec is yours | Strong - cluster tooling     | Moderate - one pod per job               | High - operate the cluster  |

## 15. Practical Tips

- Pin the OS for reproducibility (`ubuntu-24.04`) once builds matter; accept `-latest` for throwaway work.
- On a mixed-OS matrix, put macOS jobs last in your mind: they dominate the bill and start later.
- Branch on `RUNNER_ENVIRONMENT` in scripts that must behave differently on self-hosted machines.
- Never attach a self-hosted runner to a public repo; for private repos, prefer ephemeral.
- Always guard hardware-dependent jobs with a variable so a missing runner cannot hang a workflow.
- Register custom labels in `.github/actionlint.yaml` so the linter stays useful.

## 16. Demonstrated Failure Mode: The Job That Waits Forever

**Setup:** `ch05-no-runner.yml` asks for `runs-on: [self-hosted, tally-gpu]`. No runner has that label.

Real run **37313375076**, observed 55 seconds after dispatch:

| Field              | Value                       |
| ------------------ | --------------------------- |
| run status         | `queued`                    |
| job `stuck` status | `queued`                    |
| job `runnerName`   | `null` (no runner assigned) |
| steps run          | 0                           |

No error appears. The run simply sits there. Per the limits page, a self-hosted job "can be in the queue for 24 hours before it is automatically cancelled". We ran `gh run cancel 37313375076` and the run ended `cancelled`.

**Symptom:** a yellow "queued" dot that never turns green or red. **Cause:** no registered runner satisfies **all** the labels (a typo, a runner offline, or a label that was never created). **Fix:** compare the label to `gh api repos/<o>/<r>/actions/runners`, bring a runner online, or fix the typo. **Prevention:** `timeout-minutes` does **not** help here (it limits execution, not queue time), so use the guard pattern from Section 11 and monitor queue age.

**Second failure: a YAML slip.** While writing this demo we first wrote `run: echo "this never prints: no runner..."`. The unquoted `: ` made the file invalid YAML. GitHub created a run (**37313041440**) with conclusion `failure`, **zero jobs**, and a title equal to the file **path**, not the workflow's `name:`; `gh run view` printed `This run likely failed because of a workflow file issue.` `actionlint` had flagged it locally (`mapping values are not allowed in this context`) but our command chain pushed anyway. This repo's own CI then failed on that commit (run 37313042900), because `tests/test_workflow_yaml.py` parses every workflow file: a second safety net. Lesson: lint **before** committing (Chapter 17 automates this).

## 17. Key Takeaways

- Standard hosted runners: Linux and Windows 4 vCPU/16 GB on public repos, 2 vCPU/8 GB on private; macOS 3 vCPU/7 GB.
- `runs-on` as a list means "all labels"; use a matrix for "any of".
- Billing is per job, rounded up, at the OS rate; macOS dominates mixed matrices.
- Self-hosted runners: you secure them; GitHub says almost never for public repos.
- Ephemeral runners (including ARC pods) do at most one job each.
- Guard optional runner jobs with `if: vars.X == 'true'` so they skip.
- A job with no matching runner sits `queued` silently for up to 24 hours.

## 18. Exercises

1. Which label in run 37312789542 reports a different CPU architecture, and what is it?
2. What would the Section 5 run cost on a private repo if the macOS leg were removed?
3. A job says `runs-on: [self-hosted, linux, gpu]`. Runner A has `self-hosted, linux`; runner B has `self-hosted, linux, gpu`. Which can take it?
4. Why does a job-level `if: ${{ vars.GHA_ENABLE_SELFHOSTED == 'true' }}` prevent a hang, and why would `timeout-minutes: 5` not?
5. (Hand arithmetic) A matrix runs 3 Linux jobs at 70 seconds and 1 Windows job at 20 seconds. Billed minutes, and cost in mills?

<details>
<summary>Answers</summary>

1. `macos-latest`: ARM64 (the others are X64).
2. 6 + 6 + 10 = 22 mills ($0.022).
3. Only runner B: the list means the runner must have all three labels.
4. The `if` is evaluated before a runner is requested, so the job is skipped. `timeout-minutes` limits job **execution** time; a job that never starts is not executing.
5. Each Linux job: ceil(70/60) = 2 min x 6 = 12 mills, so three jobs = 36 mills and 6 minutes. The Windows job: 1 min x 10 = 10 mills. Total: **7 billed minutes, 46 mills**.

</details>

## 19. Additional Resources

All verified 2026-10.

- GitHub Docs: GitHub-hosted runners reference - https://docs.github.com/en/actions/reference/runners/github-hosted-runners
- GitHub Docs: Self-hosted runners reference - https://docs.github.com/en/actions/reference/runners/self-hosted-runners
- GitHub Docs: Actions Runner Controller - https://docs.github.com/en/actions/concepts/runners/actions-runner-controller
- GitHub Docs: Secure use reference (self-hosted runners and public repos) - https://docs.github.com/en/actions/reference/security/secure-use
- GitHub Docs: Actions limits (queue time, concurrency) - https://docs.github.com/en/actions/reference/limits
- Live evidence: runs 37312789542 (four runners), 37313375076 (stuck job), 37313041440 (invalid workflow file)
- Laster, _Learning GitHub Actions_ (O'Reilly), Chapter 5

## 20. Appendix A: Code Index

> 💻 Complete, runnable code for this chapter. Skip when reading for concepts.

### A.1 Compare measured runners to the docs and price the run

```python
import json
from datetime import datetime
from pathlib import Path

from intro_gha.cost import run_cost_mills

data = json.loads(Path("fixtures/run_ch05_runners.json").read_text())
fmt = "%Y-%m-%dT%H:%M:%SZ"


def seconds(job: dict) -> int:
    """Duration of one job from its fixture timestamps."""
    return int((datetime.strptime(job["completed_at"], fmt)
                - datetime.strptime(job["started_at"], fmt)).total_seconds())


by_label = {j["label"]: j for j in data["jobs"]}
assert by_label["macos-latest"]["arch"] == "ARM64"
assert by_label["ubuntu-latest"]["cpu"] == data["docs_public_specs"]["ubuntu-latest"][0]
os_key = {"Linux": "linux", "Windows": "windows", "macOS": "macos"}
price = run_cost_mills([(seconds(j), os_key[j["os"]]) for j in data["jobs"]])
assert price == 84
```

**Flow:** load fixture -> compare measured CPU to the docs' public spec -> convert each job's timestamps to seconds -> price each at its OS rate -> total 84 mills.
