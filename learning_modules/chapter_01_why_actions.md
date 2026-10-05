# Chapter 01: Why Actions? Cost vs Scripts and Jenkins

**Reading Time:** ~40 minutes
**Prerequisites:** Chapter 00 (YAML, refs, CI/CD vocabulary)
**Practice Notebook:** `notebooks/practice_01.ipynb`
**Reference Notebook:** `notebooks/lab_01_why_actions.ipynb`
**Script:** `labs/lab_01_why_actions.py`
**Book Reference:** Laster, Learning GitHub Actions Ch 1 / GitHub Docs: Billing for GitHub Actions
**Depth:** Core
**Default Runtime:** Offline fixtures

---

## Beginner's Guide

**Focus on first:** Sections 4 (what you stop owning), 5 (the billing arithmetic) and 8 (when Actions is the wrong tool).

**Skip on first read:** Sections 9-12 (self-hosted economics, lock-in, portability). They matter once you have a bill or a migration to plan.

**Key concepts in plain English:**

- **A CI server** is a machine that watches your repo and runs your tests when it changes. Someone has to run, patch and secure that machine.
- **Hosted runner:** a fresh virtual machine GitHub starts for each job and throws away afterwards.
- **Billed minute:** the unit you pay for. Each job's time is rounded **up** to whole minutes.
- **Overage:** minutes beyond your plan's monthly allowance.
- **Lock-in:** how expensive it is to leave later.

**If you have set up Jenkins, a cron job, or a pre-commit hook**, this chapter is the "why bother moving" argument with numbers attached.

> **🔬 Platform Engineer's Lens:** The first cost of CI is never the invoice. It is the engineer-hours spent keeping a build server alive. The second is the invoice, and it is dominated by one rounding rule: every job is billed in whole minutes, so a 15-second job costs the same as a 60-second one. Teams that split a pipeline into many tiny jobs for readability can triple their bill without noticing. Section 16 shows the exact arithmetic.

> **🚦 Native vs Marketplace vs Custom:** For "run tests on push", Actions is native: no server, no plugin, no webhook wiring. A self-managed CI server is the custom option, and it only wins when you need hardware, network placement or data residency that hosted runners cannot give you (Section 8).

## What You'll Learn

- Name what a self-run CI server makes you own, and what Actions takes off your hands
- Compute the billed minutes and dollar overage of a workflow run by hand
- Explain the per-job round-up rule and when splitting jobs costs more
- State the free allowance by plan and when public repos pay nothing
- Compare Actions with scripts, hooks and a CI server on five axes
- Decide when Actions is the wrong tool
- Reuse Tally's per-job timings in later chapters

## Table of Contents

<!-- TOC -->
- [1. The Question](#1-the-question)
- [2. Running Example: Tally's Pipeline Timings](#2-running-example-tallys-pipeline-timings)
- [3. What a Self-Run CI Server Makes You Own](#3-what-a-self-run-ci-server-makes-you-own)
- [4. What Actions Takes Off Your Hands](#4-what-actions-takes-off-your-hands)
- [5. The Billing Arithmetic](#5-the-billing-arithmetic)
- [6. The Monthly Picture](#6-the-monthly-picture)
- [7. Where Hosted Runners Stop](#7-where-hosted-runners-stop)
- [8. When Actions Is the Wrong Tool](#8-when-actions-is-the-wrong-tool)
- [9. Self-Hosted Runner Economics](#9-self-hosted-runner-economics)
- [10. Lock-In](#10-lock-in)
- [11. Third-Party Dependencies](#11-third-party-dependencies)
- [12. Why Per-Job Isolation Matters](#12-why-per-job-isolation-matters)
- [13. Case Study: Tally Grows Up](#13-case-study-tally-grows-up)
- [14. Comparison: Options for "Run the Tests on Every Change"](#14-comparison-options-for-run-the-tests-on-every-change)
- [15. Practical Tips](#15-practical-tips)
- [16. Demonstrated Failure Mode: The Rounding Penalty](#16-demonstrated-failure-mode-the-rounding-penalty)
- [17. Key Takeaways](#17-key-takeaways)
- [18. Exercises](#18-exercises)
- [19. Additional Resources](#19-additional-resources)
- [20. Appendix A: Code Index](#20-appendix-a-code-index)
   - [A.1 The cost helpers](#a1-the-cost-helpers)
   - [A.2 Reproduce the rounding penalty](#a2-reproduce-the-rounding-penalty)
<!-- /TOC -->

---

## 1. The Question

Chapter 00 ended with a workflow file. Before writing more of them, ask the question a team lead will ask you: why this, and what does it cost? "It's built into GitHub" is the short answer. The long answer has three parts: what you stop operating, what you pay, and what you give up.

## 2. Running Example: Tally's Pipeline Timings

> 📌 **Running Example: Tally's CI bill.** Tally's CI has three stages. On a Linux runner they take: **lint 15 seconds, test 20 seconds, build 25 seconds**. Run as one job they take 60 seconds in total (setup time is ignored for the arithmetic). Run as three jobs they bill separately. Tally lives in a **private** repo on the **Free** plan (2,000 included minutes per month), and is pushed to **200 times a month**. We return to these numbers in Sections 5, 13 and 16.

| Stage | Seconds | Billed minutes if its own job |
| --- | --- | --- |
| lint | 15 | 1 |
| test | 20 | 1 |
| build | 25 | 1 |
| **All three, one job** | **60** | **1** |

## 3. What a Self-Run CI Server Makes You Own

Before hosted CI, "CI" meant a machine you ran. A typical Jenkins-style setup has these parts:

```
webhook from Git host -> controller (UI, scheduler, plugins)
                          -> agent machines (run the builds)
                          -> credentials store, plugin updates, OS patches, backups
```

| You own | Typical work |
| --- | --- |
| The controller | Upgrades, plugin compatibility, backups, availability |
| The agents | OS patches, tool versions, disk cleanup, capacity |
| The webhook | Network access from the Git host to your server |
| Credentials | Rotation, least privilege, audit |
| Capacity | Queues when 10 PRs arrive at once |

None of these is hard in isolation. Together they are a part-time job, and the work shows up exactly when you are busy with something else.

## 4. What Actions Takes Off Your Hands

Per GitHub's documentation, a standard hosted runner is a new virtual machine started for each job and discarded after it (verified 2026-10). That one design choice removes most of Section 3:

| Section 3 burden | Under Actions |
| --- | --- |
| Controller | GitHub runs it |
| Agent patching and cleanup | Fresh VM per job; nothing to clean |
| Webhook wiring | Native: events are delivered inside GitHub |
| Credentials | Built-in `GITHUB_TOKEN`, secrets store (Chapters 08, 15) |
| Capacity | Hosted pool; you pay per minute instead of owning machines |

**State before / after:** before, "run tests on push" required a server, a webhook and a plugin. After, it requires one file, `.github/workflows/ci.yml`, versioned in the same commit as the code it tests.

> **Analogy: renting a car vs owning one.** Owning a CI server is owning a car: cheaper per trip if you drive constantly, but you do the maintenance. Hosted runners are a rental: you pay per use and never change the oil. The analogy breaks when you need a vehicle the rental fleet doesn't stock (special hardware), which is Section 8.

## 5. The Billing Arithmetic

Three rules, all verified against GitHub Docs (2026-10):

1. Each job's time is **rounded up to a whole minute**.
2. Standard hosted runners are **free on public repos**. On private repos each plan includes minutes: **Free 2,000, Pro 3,000, Team 3,000, Enterprise Cloud 50,000 per month**.
3. Beyond the allowance you pay per minute (standard 2-core runners): **Linux $0.006, Windows $0.010, macOS $0.062**.

In plain English:

$$\text{cost} = \sum_{\text{jobs}} \lceil \text{seconds} / 60 \rceil \times \text{rate}_{\text{OS}}$$

The sum runs over every job in the run. The ceiling brackets mean "round up". The rate depends on the runner's operating system.

**Substitution on Tally (three separate Linux jobs):**

| Job | Seconds | Ceiling | Rate (mills) | Cost (mills) |
| --- | --- | --- | --- | --- |
| lint | 15 | 1 | 6 | 6 |
| test | 20 | 1 | 6 | 6 |
| build | 25 | 1 | 6 | 6 |
| **Run total** | | **3 min** | | **18 mills = $0.018** |

(A mill is $0.001. We use integers in code to avoid float error.)

**Same work as one job:** 60 seconds, ceiling 1, cost 6 mills = $0.006. Three times cheaper, for identical work.

**What to notice:**

- The 3x difference comes entirely from the round-up rule, not from compute time.
- On a **public** repo both versions cost $0: the rule only bites on private repos past the allowance.
- Parallelism is the reason to split anyway: three jobs finish in 25 seconds wall-clock; one job takes 60. You are buying time with minutes.

> 📝 **Full implementation:** See [Appendix A.1](#a1-the-cost-helpers)

## 6. The Monthly Picture

Using Tally's 200 pushes a month:

| Layout | Minutes per run | Runs | Minutes per month | vs 2,000 allowance | Overage |
| --- | --- | --- | --- | --- | --- |
| 3 jobs | 3 | 200 | 600 | under | $0 |
| 1 job | 1 | 200 | 200 | under | $0 |

Now the team grows and pushes **1,000 times a month**:

| Layout | Minutes per month | Overage minutes | Overage cost |
| --- | --- | --- | --- |
| 3 jobs | 3,000 | 1,000 | 1,000 x $0.006 = **$6.00** |
| 1 job | 1,000 | 0 | **$0** |

**What to notice:** the allowance hides the problem at small scale. At 1,000 pushes the split layout crosses the free line and starts costing money; the single-job layout is still free.

## 7. Where Hosted Runners Stop

Per the limits page (verified 2026-10): a job may run at most **6 hours** on a hosted runner, a workflow run at most **35 days**, a matrix may expand to at most **256 jobs**, and the Free plan allows **20 concurrent jobs**. These are generous for ordinary CI. They matter for long data jobs, giant matrices and bursty teams (Chapter 18).

## 8. When Actions Is the Wrong Tool

| Situation | Why Actions struggles | Better fit |
| --- | --- | --- |
| Needs a GPU or special hardware | Standard runners are CPU VMs | Self-hosted runner on your hardware (Chapter 05) |
| Builds must reach a private network | Hosted runners sit on GitHub's network | Self-hosted runner inside the network |
| Data cannot leave your premises | Code is processed on GitHub infrastructure | Self-hosted runner or on-prem CI |
| Single job over 6 hours | Hard job limit | Batch system or self-hosted |
| Not hosted on GitHub at all | Events come from GitHub only | The CI native to your host |

Note the pattern: the fix is usually **still Actions with a self-hosted runner**, not abandoning Actions. The control plane (events, YAML, UI) stays; only the machine changes.

## 9. Self-Hosted Runner Economics

> ⚠️ ADVANCED TOPIC: Skip on first read.

A self-hosted runner removes the per-minute charge but adds back Section 3: patching, capacity, security. Rule of thumb: self-hosting pays off when (a) you need hardware hosted runners lack, or (b) minutes consumed are high and steady enough that owned machines are cheaper than $0.006 per minute. At 100,000 Linux minutes a month the hosted bill is $600; compare that to the loaded cost of one engineer-day a month of maintenance before deciding. Chapter 05 and Chapter 18 return to this.

## 10. Lock-In

> ⚠️ ADVANCED TOPIC: Skip on first read.

Your workflow YAML is GitHub-specific: `on:`, `uses:`, contexts and the Marketplace do not exist elsewhere. Lock-in is the cost of rewriting them. Keep it low by putting real logic in scripts (`./scripts/test.sh`) that the workflow merely calls, so only a thin YAML layer is GitHub-shaped. Chapter 22 covers migration both into and out of Actions.

## 11. Third-Party Dependencies

> ⚠️ ADVANCED TOPIC: Skip on first read.

Every `uses: owner/action@ref` is code you did not write running in your pipeline. Convenience trades against supply-chain risk. Chapter 04 introduces the mechanics, Chapter 16 the defences.

## 12. Why Per-Job Isolation Matters

> ⚠️ ADVANCED TOPIC: Skip on first read.

Because each job gets a fresh VM, a job cannot see the previous job's files. That is safer and more reproducible, but it means data must be passed deliberately (outputs, artifacts, cache; Chapter 09). It is also why split jobs repeat setup work (checkout, install), which is the hidden cost of splitting.

## 13. Case Study: Tally Grows Up

Tally starts as one developer, 200 pushes a month, three jobs, 600 minutes: free. A second developer joins and a nightly job is added; pushes hit 1,000 a month. The bill arrives: $6.00. Nobody changed any code. Two fixes exist:

1. **Merge lint and test into one job** (35 s, 1 minute): 2 jobs per run, 2,000 minutes a month, $0 overage.
2. **Cache the install** (Chapter 09) so each job spends fewer seconds.

The lesson: measure billed minutes per run (`gh run view <id> --json jobs`) before and after any pipeline refactor.

## 14. Comparison: Options for "Run the Tests on Every Change"

| Approach | Setup Effort | Control | Failure Visibility | Security Exposure | Maintenance Burden |
| --- | --- | --- | --- | --- | --- |
| Manual script | Minimal - one file | Strong - local | Weak - only you | Minimal - local | Low - until forgotten |
| Pre-commit hook | Low - per clone | Moderate - skippable | Weak - local only | Minimal - local | Moderate - drifts |
| Self-run CI server | High - server, agents, webhook | Excellent - total | Strong - own UI | High - you secure it | Very High - you patch it |
| GitHub Actions (hosted) | Low - one YAML file | Strong - per workflow | Excellent - on the PR | Moderate - shared infra | Low - GitHub operates it |
| Actions + self-hosted runner | Moderate - register machine | Excellent - own hardware | Excellent - on the PR | High - your machine runs PR code | High - you patch the runner |

## 15. Practical Tips

- Check cost with real data: `gh run view <run-id> --json jobs` lists each job's start and end time.
- Before splitting a job, ask: do I need the parallelism or the clearer failure label? If neither, keep it one job.
- Public repo? Standard runners cost nothing; still keep runs fast, because waiting costs developer time.
- Put logic in scripts the workflow calls; keep YAML thin (cheaper lock-in, easier local testing).
- Set a budget alert in billing settings once the repo is private and busy.

## 16. Demonstrated Failure Mode: The Rounding Penalty

**Setup:** Tally's three stages as three jobs (Section 5).

| Step | State |
| --- | --- |
| Measure compute | 15 + 20 + 25 = 60 seconds of actual work |
| Bill as 3 jobs | 1 + 1 + 1 = **3 billed minutes** |
| Bill as 1 job | ceil(60/60) = **1 billed minute** |
| Monthly at 1,000 pushes | 3,000 vs 1,000 minutes |
| Overage at $0.006 | **$6.00** vs **$0** |

**Symptom:** the bill rose 3x with no change in what the pipeline does. **Cause:** per-job round-up to whole minutes. **Fix:** consolidate jobs whose parallelism you don't need; otherwise accept the cost knowingly. The lab asserts every figure above.

**Second failure: macOS surprise.** A 61-second macOS job bills 2 minutes at $0.062 = $0.124, twenty times Linux's $0.006 for the same wall-clock second. Use macOS only for steps that require it.

## 17. Key Takeaways

- A self-run CI server makes you own the controller, agents, webhook, credentials and capacity.
- Hosted Actions runners are fresh VMs per job; you own none of that.
- Cost is the sum over jobs of whole-minute round-ups times the OS rate.
- Public repos run standard runners free; private repos get 2,000 (Free) to 50,000 (Enterprise Cloud) minutes.
- Splitting jobs buys parallelism and costs rounded-up minutes.
- When hardware or network demands it, keep Actions and swap in a self-hosted runner.
- Keep logic in scripts so your lock-in stays in a thin YAML layer.

## 18. Exercises

1. A job runs 61 seconds on Linux. How many billed minutes and what cost in mills?
2. Tally on Windows runs lint 15 s, test 20 s, build 25 s as three jobs. Cost per run in mills? Single-job cost?
3. 1,500 pushes a month, three Linux jobs each, private repo on the Team plan (3,000 included minutes). Overage minutes and dollars?
4. Name two situations where Actions' hosted runners are the wrong choice, and what you would keep from Actions anyway.
5. (Hand arithmetic) A matrix of 3 OS (linux, windows, macos) each run a 45-second job. Cost per run in mills.

<details>
<summary>Answers</summary>

1. ceil(61/60) = 2 minutes; 2 x 6 = 12 mills ($0.012).
2. 3 jobs x 1 min x 10 mills = 30 mills per run; single job 60 s = 1 min x 10 = 10 mills.
3. 1,500 x 3 = 4,500 minutes; 4,500 - 3,000 = 1,500 overage; 1,500 x $0.006 = $9.00.
4. GPU/special hardware, or builds that must reach a private network. You keep the YAML, events and UI; only the runner is self-hosted.
5. Each job is 1 minute: linux 6 + windows 10 + macos 62 = 78 mills ($0.078).

</details>

## 19. Additional Resources

All verified 2026-10.

- GitHub Docs: GitHub Actions billing - https://docs.github.com/en/billing/concepts/product-billing/github-actions
- GitHub Docs: Actions limits - https://docs.github.com/en/actions/reference/limits
- GitHub Docs: GitHub-hosted runners reference - https://docs.github.com/en/actions/reference/runners/github-hosted-runners
- GitHub Docs: Understanding GitHub Actions - https://docs.github.com/en/actions/get-started/understand-github-actions
- GitHub Docs: About self-hosted runners - https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners/about-self-hosted-runners
- Laster, *Learning GitHub Actions* (O'Reilly), Chapter 1

## 20. Appendix A: Code Index

> 💻 Complete, runnable code for this chapter. Skip when reading for concepts.

### A.1 The cost helpers

```python
import math

RATE_MILLS_PER_MIN = {"linux": 6, "windows": 10, "macos": 62}


def billed_minutes(seconds: float) -> int:
    """Whole billed minutes for one job: ceil(seconds / 60), minimum 1."""
    return max(1, math.ceil(seconds / 60))


def job_cost_mills(seconds: float, os_name: str = "linux") -> int:
    """Overage cost of one job in mills (1 mill = $0.001)."""
    return billed_minutes(seconds) * RATE_MILLS_PER_MIN[os_name]


def run_cost_mills(jobs: list[tuple[float, str]]) -> int:
    """Total overage cost in mills for (seconds, os) jobs in one run."""
    return sum(job_cost_mills(s, o) for s, o in jobs)
```

**Flow:** seconds -> divide by 60 -> round up (minimum 1) -> multiply by the OS rate -> sum over jobs.

### A.2 Reproduce the rounding penalty

```python
from intro_gha.cost import run_cost_mills, run_minutes

split = [(15, "linux"), (20, "linux"), (25, "linux")]
merged = [(60, "linux")]
assert run_minutes(split) == 3 and run_minutes(merged) == 1
assert run_cost_mills(split) == 18 and run_cost_mills(merged) == 6
monthly_overage_minutes = 1000 * run_minutes(split) - 2000
assert monthly_overage_minutes * 6 == 6000  # 6000 mills = $6.00
print("split costs 3x for identical work")
```
