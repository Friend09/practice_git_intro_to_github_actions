# Chapter 18: Cost, Performance and Limits

**Reading Time:** ~55 minutes
**Prerequisites:** Chapter 01 (billing arithmetic), Chapter 09 (caching), Chapter 10 (matrix, concurrency, timeouts), Chapter 17 (run history)
**Practice Notebook:** `notebooks/practice_18.ipynb`
**Reference Notebook:** `notebooks/lab_18_cost_performance_limits.ipynb`
**Script:** `labs/lab_18_cost_performance_limits.py`
**Book Reference:** Laster, Learning GitHub Actions Ch 5, 10 / GitHub Docs: Actions limits, Billing for GitHub Actions
**Depth:** Core
**Default Runtime:** Offline fixtures

---

## Beginner's Guide

**Focus on first:** Sections 4 (what this course would have cost, from real data), 5 (the single biggest saving) and 7 (a performance experiment that surprised us).

**Skip on first read:** Sections 10-12 (self-hosted economics, schedules, spending controls).

**Key concepts in plain English:**

- **Billed minute:** each job's time rounded **up** to a whole minute, times the OS rate (Chapter 01).
- **Wall-clock time:** how long you wait. It can drop while the bill rises, or the reverse.
- **Queue latency:** the gap between "run created" and "job started".
- **Limit:** a ceiling the platform enforces (job length, matrix size, concurrency, storage).
- **Overhead:** time spent on things that are not your work (setup, restoring a cache, saving one).

**If you have ever tuned a database query**, this chapter is the same discipline: measure first, change one thing, measure again, and distrust your intuition.

> **🔬 Platform Engineer's Lens:** Cost and speed are different budgets and they trade against each other. We have data for both from **this repository's own 178 runs and 353 jobs**, plus three controlled experiments. The headline findings are uncomfortable for common advice: **94% of jobs finished in 30 seconds or less yet were billed a full minute each (3.68 times the time used)**, and a cache **made a job slower** because restoring and saving it cost more than it saved.

> **🚦 Native vs Marketplace vs Custom:** All the levers here are native settings (job structure, `timeout-minutes`, `concurrency`, filters, runner choice, caching). The only custom piece is a small script over the API that turns your run history into a bill and a latency report. Reach for a larger runner or a faster installer before building anything.

## What You'll Learn

- Compute a workflow's billed minutes and cost from real job timestamps
- Explain why billed minutes can be several times the time actually used
- Estimate the saving from merging jobs, using your own history
- Read queue latency and know what is, and is not, under your control
- Decide whether to cache by measuring install, restore and save time
- State the platform limits that matter, with their verified values
- Rank cost levers by evidence and spot outlier jobs

## Table of Contents

<!-- TOC -->
- [1. Three Budgets](#1-three-budgets)
- [2. Running Example: The Course's Own Bill](#2-running-example-the-courses-own-bill)
- [3. The Bill Model](#3-the-bill-model)
- [4. What the Course Would Have Cost](#4-what-the-course-would-have-cost)
- [5. The Biggest Lever: Fewer, Longer Jobs](#5-the-biggest-lever-fewer-longer-jobs)
- [6. Where Time Goes: Queue Latency](#6-where-time-goes-queue-latency)
- [7. A Performance Experiment That Surprised Us](#7-a-performance-experiment-that-surprised-us)
- [8. The Limits That Matter](#8-the-limits-that-matter)
- [9. Cost Levers, Ranked by Evidence](#9-cost-levers-ranked-by-evidence)
- [10. Larger Runners and Self-Hosting](#10-larger-runners-and-self-hosting)
- [11. Scheduled Workflows](#11-scheduled-workflows)
- [12. Spending Controls](#12-spending-controls)
- [13. Case Study: The Five-Minute Heartbeat](#13-case-study-the-five-minute-heartbeat)
- [14. Comparison: Ways to Spend Less](#14-comparison-ways-to-spend-less)
- [15. Practical Tips](#15-practical-tips)
- [16. Demonstrated Failure Modes](#16-demonstrated-failure-modes)
- [17. Key Takeaways](#17-key-takeaways)
- [18. Exercises](#18-exercises)
- [19. Additional Resources](#19-additional-resources)
- [20. Appendix A: Code Index](#20-appendix-a-code-index)
   - [A.1 Price a job history and the merge what-if](#a1-price-a-job-history-and-the-merge-what-if)
<!-- /TOC -->

---

## 1. Three Budgets

| Budget | Measured in | You pay with |
| --- | --- | --- |
| Money | billed minutes x rate | the invoice, past the free allowance |
| Time | wall-clock seconds | developer waiting |
| Limits | job length, matrix size, concurrency, storage | hard stops |

This chapter treats each as a number to measure.

## 2. Running Example: The Course's Own Bill

> 📌 **Running Example: this repository's history.** A snapshot of **178 runs** with their **353 jobs** (`fixtures/jobs_ch18_snapshot.json`, from the REST API: start, end and runner label for every job). Of the 353 jobs, **337 actually ran** on a runner, **15 were skipped** (no runner assigned) and 1 was not billable (a self-hosted job that never found a runner). We price the 337 as if the repository were **private**: Linux $0.006, Windows $0.010 and macOS $0.062 per whole minute, per job (Chapter 01; docs verified 2026-10). The repository is public, so the real bill was **$0**. Three controlled experiments (`ch18-cache-benefit.yml`, `ch18-uv-benefit.yml`) measure installs. Data: `fixtures/jobs_ch18_snapshot.json`, `fixtures/cache_benefit_ch18.json`. We return to them throughout.

## 3. The Bill Model

Chapter 01's rule, unchanged: **each job** is billed `ceil(seconds / 60)` whole minutes (minimum 1) times its OS rate, and standard runners are free on public repositories. Free-plan private repos include 2,000 minutes a month (Pro and Team 3,000, Enterprise Cloud 50,000; docs). Jobs that never receive a runner (skipped, or never scheduled) have no runner time to bill.

$$\text{cost} = \sum_{\text{jobs that ran}} \lceil \text{seconds} / 60 \rceil \times \text{rate}_{\text{OS}}$$

In plain English: for each job that actually ran, round its seconds up to whole minutes, multiply by that operating system's per-minute rate, and add them all.

> 📝 **Full implementation:** See [Appendix A.1](#a1-price-a-job-history-and-the-merge-what-if)

## 4. What the Course Would Have Cost

Pricing all 337 jobs that ran:

| Measure | Value |
| --- | --- |
| Jobs that ran | 337 |
| Time actually used | **6,357 seconds** (106 minutes) |
| Billed minutes | **390** |
| **Billed / used** | **3.68x** |
| Cost on a private repo | **2,400 mills = $2.40** |
| Share of the Free plan's 2,000 monthly minutes | 19.5% |

**What to notice:**

- **The round-up dominates.** 316 of the 337 jobs (**94%**) lasted **30 seconds or less**, and 324 (96%) lasted a minute or less. Each is billed a whole minute. We used 106 minutes and would be billed for 390.
- The total is tiny ($2.40) because the jobs are tiny. A team with the same structure and 100 times the runs would pay about $240 and waste the same 3.7x.
- Time and bill diverge: a workflow of many 5-second jobs is **fast and expensive**; one 55-second job is **slow-ish and cheap**.

Where the minutes went, by workflow (top rows):

| Workflow | Jobs | Billed minutes | Mills |
| --- | --- | --- | --- |
| `ch11-python-ci.yml` | 90 | 90 | 540 |
| `ci.yml` | 57 | 57 | 342 |
| `ch09-output-limits.yml` | 4 | **39** | **234** |
| `ch03-tally-ci.yml` | 18 | 18 | 108 |
| `ch07-expressions.yml` | 16 | 16 | 96 |

**Outliers.** `ch09-output-limits.yml` has only **4 jobs** yet billed **39 minutes (10% of the whole bill)** because of the slow-completing oversized-output probes of Chapter 09: its two failing jobs ran **787 and 784 seconds**. Four jobs out of 337 produced a tenth of the cost. And the only macOS job (5 seconds) cost **62 mills, 2.6% of the total on its own** (Chapter 05). Both are "look at the top of the list" findings, which is what Section 12 of Chapter 17's monitoring approach is for.

## 5. The Biggest Lever: Fewer, Longer Jobs

Chapter 01 showed the rounding penalty on one workflow. Now measure it on all of history. For every run, group its jobs by OS and bill the **sum of their seconds** once, as if each run's same-OS jobs were merged into one:

| Layout | Cost (mills) |
| --- | --- |
| As it ran (one bill per job) | **2,400** |
| Same-OS jobs of each run merged into one job | **1,500** |
| **Saving** | **900 mills, 38%** |

Only 52 of the 173 runs had more than one job, so the saving comes from a minority of runs, but it is large: **merging small jobs would have cut the bill by more than a third**.

**The trade-off you must not ignore.** Merging removes parallelism and clear per-job failure labels (Chapter 10). Lint and tests as separate jobs finish in the time of the slower; merged, they take the sum. It is worth merging when jobs are **shorter than a minute each** and parallelism does not buy you much. It is not worth merging two 50-second jobs (you'd be at 100 s and bill 2 minutes either way, but wait longer).

## 6. Where Time Goes: Queue Latency

For each job that ran we computed `started_at - created_at`, the time between the run being created and a runner starting the job:

| Statistic | Seconds |
| --- | --- |
| Median | **3** |
| 90th percentile | **4** |
| Maximum | **72** |
| Jobs measured | 337 |

**What to notice:** a typical job waits **3 seconds** to start, so for our tiny jobs the platform overhead (queue, "Set up job", "Complete job") is a large share of wall-clock time. The 72-second maximum is a reminder that queue time has a tail you cannot control (we did not investigate its cause). In our single macOS run (Chapter 05) the job began about 6 seconds after the Linux jobs of the same run, so expect other platforms to differ. **You cannot tune queue time; you can only avoid doing work that multiplies it** (more jobs means more waits).

## 7. A Performance Experiment That Surprised Us

Chapter 11 measured a pip cache on a 3-second install and found it saved a second. The skeptic's reply: "try a *heavy* install." We did. `sandbox/ch18/requirements.txt` is PyTorch (CPU), NumPy, pandas, scikit-learn and Matplotlib: **1,329 MB of site-packages, a 301 MB pip cache**.

**Experiment A: pip, with `setup-python` caching** (runs on `ubuntu-latest`, same job each time):

| Run | Cache | `pip install` | Notes |
| --- | --- | --- | --- |
| 37330675284 | none | **49 s** | job 54 s |
| 37330856258 | miss, saved 302 MiB | **44 s** | restored an unrelated **14 MB stale cache** via a restore key |
| 37331043640 | **exact hit**, 303 MB restored | **43 s** | job 50 s |

**It barely helped: 49 s to 43 s.** The cache restored 303 MB at about **230 MB/s (roughly 2 seconds)**, yet `pip install` still took 43 seconds. Downloading the wheels from PyPI was fast; the time is in **installing 1.3 GB of files** (unpacking and writing them). Caching the *download* did not touch that cost.

**A subtlety.** The "miss" run did not start cold: its log said `Cache hit for restore-key: setup-python-...-pip-08e32bcf...`. `setup-python` tries **prefix keys**, and found Chapter 11's cache (a different dependency file, 14 MB) and restored that. It is not an exact hit, so it saved nothing here, but be aware that a restore-key hit can load **stale, unrelated** content.

**Experiment B: `uv`, the same requirements file:**

| Run | uv cache | `uv pip install` | `Set up uv` | Post (save) | Job total |
| --- | --- | --- | --- | --- | --- |
| 37331343049 | off | **3 s** | 1 s | 0 s | **9 s** |
| 37331411088 | on, miss | 4 s | 1 s | **6 s** | 16 s |
| 37331557757 | on, **hit** (248 MB) | **1 s** | **5 s** | 0 s | 13 s |

**What to notice:**

- **`uv` installed the same dependency set in 3 seconds against pip's 43 to 49**: roughly **15 times faster**, with no cache at all. (We used the same requirements file but did not verify that both resolved identical versions, so treat the ratio as indicative.)
- **The uv cache made the job slower.** Cache off: 9 s total. Cache on, a miss: 16 s (6 s spent saving). Cache on, a hit: 13 s (5 s spent restoring to save 2 s of install). **Restoring and saving cost more than the work it avoided.**
- On the bill: every job here is under a minute, so **all six runs bill 1 minute**. The wins are wall-clock: from 54 s to 9 s per run is **45 seconds of developer waiting saved on every push**, for free.

**The lesson is the method:** the first intuition ("cache it") was wrong twice. The effective change was swapping the tool. Measure the install, the restore and the save separately (Chapter 09's step timings) before adding cache complexity.

## 8. The Limits That Matter

Verified against GitHub Docs on 2026-10-05 (the limits page and billing page), with the Chapter where each appears:

| Limit | Value | Chapter |
| --- | --- | --- |
| Job runtime on a hosted runner | **6 hours** | 01, 10 |
| Workflow run runtime | **35 days** | 01 |
| Jobs from one matrix | **256** | 01, 10 |
| Concurrent jobs, Free plan | **20** (Pro 40, Team 60, Enterprise 500) | 05 |
| Concurrent macOS jobs | **5** on Free, Pro, Team; 50 on Enterprise | 05 |
| Workflow runs queued | **500 per 10 seconds** | here |
| Self-hosted job queue time | **24 hours** before auto-cancel | 05 |
| Self-hosted job runtime | **5 days** | 05 |
| Cache storage | **10 GB per repository** (7 days without access evicts) | 09 |
| Artifact storage, Free plan | **500 MB** | 09 |
| Job outputs | **1,048,576 bytes** (measured ~524,288 ASCII chars) | 09 |
| Step summary | **1 MiB per step** | 17 |
| Annotations | **10 per level per step** (measured) | 17 |
| Free minutes, Free plan | **2,000 per month** (Pro/Team 3,000) | 01 |

**One number we could not reproduce.** The docs say `GITHUB_TOKEN` is limited to **1,000 requests per hour per repository**. In Chapter 15 a job made 1,150 calls with no failure and the response header reported **5,000**. Treat documented numbers as claims to check, especially ones that gate your automation.

## 9. Cost Levers, Ranked by Evidence

| Lever | Evidence from this repo | Effect |
| --- | --- | --- |
| Merge sub-minute jobs | History what-if: 2,400 to 1,500 mills | **-38% cost**, at the price of parallelism |
| Faster tool, not a cache | pip 43 to 49 s vs uv 3 s | **-45 s wall-clock** per run; bill unchanged here |
| Do not cache cheap installs | uv cache on: 13 to 16 s vs 9 s off | cache **added** 4 to 7 s |
| Stop outlier jobs early | 2 probe jobs = 28 billed minutes, 7% of the bill | `timeout-minutes` and an eye on the top-10 list |
| Keep tag pushes from running CI | 4 of 8 tag-push runs were `paths`-filtered workflows running anyway (Chapter 06) | removes avoidable runs |
| Use Linux unless you need another OS | one 5 s macOS job = 2.6% of cost | rate is 10x Linux's |
| Cancel superseded runs | `concurrency` + `cancel-in-progress` (Chapter 10) | not measured here |

## 10. Larger Runners and Self-Hosting

> ⚠️ ADVANCED TOPIC: Skip on first read.

A larger hosted runner costs more per minute and is not free for public repositories (Chapter 05). It pays off only when it cuts runtime by more than its price premium, **and** the saving crosses minute boundaries. For a 3-second install (Experiment B) it can never pay. Self-hosting removes the per-minute charge but adds maintenance and security cost (Chapter 05); it makes sense for sustained, high volume or special hardware, not to save a few dollars.

## 11. Scheduled Workflows

> ⚠️ ADVANCED TOPIC: Skip on first read.

A `schedule` run costs the same as any run, and the arithmetic is simple. A cron of `*/5 * * * *` (every five minutes, the shortest interval the docs allow) is **12 runs an hour x 24 x 30 = 8,640 runs a month**. At one billed Linux minute each that is **8,640 minutes, or $51.84, even if it does nothing**. At the Free plan's 2,000 included minutes, a single five-minute cron on a private repo exhausts the allowance in about 7 days. Pick the slowest cadence that meets the need.

## 12. Spending Controls

> ⚠️ ADVANCED TOPIC: Skip on first read.

The billing docs describe included minutes, per-minute rates and storage, but the pages we read did not detail budget alerts or hard spending limits, so we did not test them. Check your organization's billing settings for budgets and alerts before running anything large on a private repository, and use the API in Section 4's style (jobs and timings) to forecast.

## 13. Case Study: The Five-Minute Heartbeat

A team adds `on: schedule: - cron: '*/5 * * * *'` to ping a service, "just in case". On a private Team-plan repository (3,000 included minutes) the heartbeat alone consumes 8,640 minutes a month: 3,000 free, then **5,640 minutes at $0.006 = $33.84** of overage, for a job that runs 4 seconds. The invoice looks like a mystery until someone sorts the run history by workflow (Chapter 17) and sees 8,640 runs of one file. The fix is a slower cadence (every 30 minutes is 1,440 minutes, inside the allowance). (This scenario is arithmetic applied to our measured model, not an observed incident.)

## 14. Comparison: Ways to Spend Less

| Approach | Setup Effort | Control | Failure Visibility | Security Exposure | Maintenance Burden |
| --- | --- | --- | --- | --- | --- |
| Merge sub-minute jobs | Low - restructure YAML | Moderate - lose parallelism | Fair - fewer, coarser checks | Minimal | Low |
| Faster tooling (uv) | Low - swap one command | Strong | Strong | Low - another tool to pin | Low |
| Add dependency caching | Low - one input | Weak - may be slower | Fair - extra restore/save steps | Moderate - cache poisoning (Chapter 16) | Moderate - key design |
| Timeouts and outlier review | Minimal - one line | Strong - caps the damage | Strong - fails loudly | Minimal | Low |
| Larger runner | Low - choose a label | Moderate | Strong | Low | Low - higher price |
| Self-hosted runners | High | Excellent | Strong | High | High |

## 15. Practical Tips

- Price your own history before optimizing: a short script over the API (Appendix A) beats a guess.
- Treat the **top 5 jobs by billed minutes** as a standing report; outliers hide there.
- Merge jobs that are each under a minute and need no parallelism.
- Replace a slow tool before adding a cache; measure restore and save, not just install.
- Beware restore-key prefixes that load unrelated stale caches.
- Set `timeout-minutes` on every job; one hung job costs more than a hundred healthy ones.
- Choose the slowest schedule that meets the need.
- Re-check documented limits you depend on.

## 16. Demonstrated Failure Modes

**Failure 1: the rounding tax.** 106 minutes used, 390 billed (3.68x), because 94% of jobs were under 30 seconds.

**Failure 2: the outlier.** Four jobs in one workflow billed 39 minutes, 10% of the total.

**Failure 3: the cache that slows.** uv cache on: 13 and 16 seconds against 9 seconds off.

**Failure 4: the cache that barely helps.** A 303 MB exact hit (about 2 seconds to restore) still left a 43-second install against 49 without; the time was unpacking, not downloading.

**Failure 5: the stale restore.** A "miss" restored an unrelated 14 MB cache through a prefix key.

**Failure 6: the avoidable runs.** 4 of 8 tag-push runs were `paths`-filtered CI workflows running on tags (Chapter 06).

**Failure 7: the number that was not true.** A documented 1,000-requests-per-hour token limit that a job exceeded by 150 calls with the header reporting 5,000.

## 17. Key Takeaways

- Cost is the sum of per-job round-ups; for tiny jobs the bill is several times the time used (3.68x here).
- Merging each run's same-OS jobs would have cut this repository's bill 38%.
- Median queue latency is 3 seconds; you cannot tune it, only avoid multiplying it.
- A faster installer beat a cache by a wide margin (3 s vs 43 to 49 s), and a cache can make a job slower.
- Measure install, restore and save separately before caching.
- A handful of outlier jobs can dominate the bill; review the top of the list and set timeouts.
- Know the limits (6 h, 256, 20 concurrent, 10 GB, 1 MiB) and verify the ones you rely on.
- A five-minute cron is 8,640 runs a month.

## 18. Exercises

1. A job runs 25 seconds on Linux. Billed minutes and mills? Three such jobs in one run, merged into one 75-second job: billed minutes?
2. 200 pushes a month, each triggers 4 Linux jobs of 20 seconds. Monthly billed minutes as is, and if merged into one 80-second job per push? Overage on the Free plan (2,000 minutes) in each case?
3. Experiment B's cache-hit run: restore 5 s, install 1 s. Cache-off run: install 3 s. Is the cache worth it? Show the arithmetic.
4. A cron of `0 * * * *` (hourly) on a private repo, one 40-second Linux job. Billed minutes in a 30-day month?
5. (Hand arithmetic) Using the course numbers: 390 billed minutes against 106 used. What are the billed-to-used ratio and the wasted minutes?

<details>
<summary>Answers</summary>

1. 25 s: ceil(25/60) = 1 minute = 6 mills. Merged 75 s: ceil(75/60) = **2 minutes** (12 mills) instead of 3 minutes (18 mills): a saving of one third.
2. As is: 200 x 4 x 1 = **800** minutes (under 2,000, no overage). Merged: 200 x ceil(80/60) = 200 x 2 = **400** minutes. No overage either way; merging halves the usage.
3. No. With the cache: restore 5 + install 1 = 6 s. Without: install 3 s. The cache adds 3 seconds of net **cost**.
4. 24 x 30 = 720 runs x ceil(40/60) = 1 minute = **720 minutes**.
5. 390 / 106 = **3.68x**; wasted = 390 - 106 = **284 minutes** (billed but not used, almost all from per-job rounding).

</details>

## 19. Additional Resources

All verified 2026-10.

- GitHub Docs: Actions limits - https://docs.github.com/en/actions/reference/limits
- GitHub Docs: GitHub Actions billing - https://docs.github.com/en/billing/concepts/product-billing/github-actions
- GitHub Docs: Dependency caching reference - https://docs.github.com/en/actions/reference/workflows-and-actions/dependency-caching
- GitHub REST: Workflow jobs (timestamps and labels) - https://docs.github.com/en/rest/actions/workflow-jobs
- astral-sh/setup-uv (`enable-cache`) - https://github.com/astral-sh/setup-uv
- Live evidence: this repository's 178-run history, and runs 37330675284, 37330856258, 37331043640 (pip) and 37331343049, 37331411088, 37331557757 (uv)
- Laster, *Learning GitHub Actions* (O'Reilly), Chapters 5 and 10

## 20. Appendix A: Code Index

> 💻 Complete, runnable code for this chapter. Skip when reading for concepts.

### A.1 Price a job history and the merge what-if

```python
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from intro_gha.cost import RATE_MILLS_PER_MIN, billed_minutes

FMT = "%Y-%m-%dT%H:%M:%SZ"


def os_of(label: str) -> str:
    """Map a runner label to the billing OS."""
    return "macos" if label.startswith("macos") else "windows" if label.startswith("windows") else "linux"


jobs = json.loads(Path("fixtures/jobs_ch18_snapshot.json").read_text())["jobs"]
ran = []
for j in jobs:
    if j["conclusion"] == "skipped" or j["labels"][0] == "self-hosted":
        continue
    s, e = (datetime.strptime(j[k], FMT) for k in ("started_at", "completed_at"))
    if e >= s:
        ran.append({**j, "sec": int((e - s).total_seconds()), "os": os_of(j["labels"][0])})

cost = sum(billed_minutes(j["sec"]) * RATE_MILLS_PER_MIN[j["os"]] for j in ran)
groups = defaultdict(list)
for j in ran:
    groups[(j["run_id"], j["os"])].append(j["sec"])
merged = sum(billed_minutes(sum(v)) * RATE_MILLS_PER_MIN[k[1]] for k, v in groups.items())
assert (len(ran), cost, merged) == (337, 2400, 1500)
```

**Flow:** keep jobs that ran; compute seconds from timestamps; bill each job (round up, OS rate) and sum; then group by (run, OS), bill the **sum** of seconds once, and compare.
