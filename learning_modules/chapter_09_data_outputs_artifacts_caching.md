# Chapter 09: Data Between Steps and Jobs: Outputs, Artifacts, Caching

**Reading Time:** ~55 minutes
**Prerequisites:** Chapter 02 (jobs are isolated), Chapter 07 (contexts), Chapter 08 (`GITHUB_ENV`, secrets)
**Practice Notebook:** `notebooks/practice_09.ipynb`
**Reference Notebook:** `notebooks/lab_09_data_outputs_artifacts_caching.ipynb`
**Script:** `labs/lab_09_data_outputs_artifacts_caching.py`
**Book Reference:** Laster, Learning GitHub Actions Ch 7 / GitHub Docs: Workflow commands, Dependency caching
**Depth:** Core
**Default Runtime:** Live repo

---

## Beginner's Guide

**Focus on first:** Sections 3 (outputs), 6 (artifacts) and 7 (the cache, with real timings).

**Skip on first read:** Sections 10-12 (cache scope and eviction rules, summaries).

**Key concepts in plain English:**

- **Output:** a small text value one step or job hands to later steps or jobs.
- **Artifact:** a file or folder saved at the end of a job, so another job or a person can download it.
- **Cache:** files saved under a key so a *future run* can skip re-creating them (typically installed dependencies).
- **Key:** the name a cache is stored under. Same key means same cache.
- **Hit / miss:** the key was found, or it was not.

**If you have passed files between pipeline stages before**, artifacts are that. A cache is different: it is for speed across *runs*, not for passing results within one.

> **🔬 Platform Engineer's Lens:** These three features look interchangeable and are not. An **output** is capped at about a megabyte and, as we measured, a large one can cost minutes of billed runner time in a job that did no work. An **artifact** is the right way to move build results and is immutable. A **cache** is a performance hint that may vanish at any time, so your workflow must be correct without it.

> **🚦 Native vs Marketplace vs Custom:** All three are native. Use `actions/upload-artifact`, `actions/download-artifact` and `actions/cache` (first-party, all on `node24` today). Language setup actions such as `setup-python` can cache for you with one input; reach for `actions/cache` directly when you cache something they do not.

## What You'll Learn

- Write and read step outputs and job outputs, including multi-line values
- State what outputs are (strings) and how large they can be
- Upload, download and verify an artifact between jobs
- Predict what happens with an empty upload and with a duplicate artifact name
- Read cache hit and miss from a run and compute what caching saved
- Design a cache key with `hashFiles` and know what changes it
- Choose between an output, an artifact and a cache

## Table of Contents

<!-- TOC -->
- [1. Three Ways to Pass Data](#1-three-ways-to-pass-data)
- [2. Running Example: Tally Builds and Packs](#2-running-example-tally-builds-and-packs)
- [3. Step Outputs](#3-step-outputs)
- [4. Job Outputs and `needs`](#4-job-outputs-and-needs)
- [5. How Big Can an Output Be?](#5-how-big-can-an-output-be)
- [6. Artifacts](#6-artifacts)
- [7. Caching, with Real Timings](#7-caching-with-real-timings)
- [8. Designing a Cache Key](#8-designing-a-cache-key)
- [9. Choosing the Mechanism](#9-choosing-the-mechanism)
- [10. Cache Scope Rules](#10-cache-scope-rules)
- [11. Limits and Eviction](#11-limits-and-eviction)
- [12. Job Summaries](#12-job-summaries)
- [13. Case Study: The Stale Dependency](#13-case-study-the-stale-dependency)
- [14. Comparison: Moving Data](#14-comparison-moving-data)
- [15. Practical Tips](#15-practical-tips)
- [16. Demonstrated Failure Modes](#16-demonstrated-failure-modes)
- [17. Key Takeaways](#17-key-takeaways)
- [18. Exercises](#18-exercises)
- [19. Additional Resources](#19-additional-resources)
- [20. Appendix A: Code Index](#20-appendix-a-code-index)
   - [A.1 Verify outputs, artifacts and cache from the saved runs](#a1-verify-outputs-artifacts-and-cache-from-the-saved-runs)
   - [A.2 Cache savings and billing](#a2-cache-savings-and-billing)
<!-- /TOC -->

---

## 1. Three Ways to Pass Data

Chapter 02 established that every job gets a fresh machine. Anything one job produces is gone unless you move it deliberately. The platform offers three mechanisms, for three different jobs:

| Mechanism | Carries | Lives for | Direction |
| --- | --- | --- | --- |
| Output | a short string | the workflow run | step to step, job to job |
| Artifact | files | days (retention period) | job to job, and out to humans |
| Cache | files | until evicted | run to **later runs** |

## 2. Running Example: Tally Builds and Packs

> 📌 **Running Example: `ch09-data.yml`.** Three jobs. **build** computes outputs (`version=0.1.<run number>`, a two-line `notes`, a content `digest`), builds a fake distribution `dist/` (a 12-byte text file plus 2,048 zero bytes) and uploads it as artifact `tally-dist` with `retention-days: 1`; it also tries three deliberately bad uploads. **consume** downloads the artifact **without checking out the repo** and verifies it. **cache** restores a 20 MB "dependency" folder under a key built from `hashFiles('pyproject.toml')`, installs it only on a miss (a 12-second `sleep` stands in for a slow install), and reports. We ran it three times: run **37318380786** (`salt=a`, miss), run **37318461776** (`salt=a`, hit), run **37318514549** (`salt=b`, new key, miss). Data: `fixtures/data_ch09_*.json`, `fixtures/artifacts_cache_ch09.json`. Two separate probes, `ch09-output-limits.yml` (run **37317645339**) and `ch09-output-bisect.yml` (run **37320026502**), measure output size limits (Section 5). We return to them throughout.

## 3. Step Outputs

A step publishes an output by appending `name=value` to the file named by `$GITHUB_OUTPUT`. Later steps read it as `steps.<id>.outputs.<name>`:

```bash
echo "version=0.1.${{ github.run_number }}" >> "$GITHUB_OUTPUT"   # step id: ver
```

For a value with newlines, use a delimiter (docs, verified 2026-10):

```bash
{ echo 'notes<<EOF'; echo 'line one'; echo 'line two'; echo EOF; } >> "$GITHUB_OUTPUT"
```

The delimiter (`EOF`) must not appear on a line of its own inside the value. Results in the real run:

| Output | Value in the three runs |
| --- | --- |
| `version` | `0.1.1`, `0.1.2`, `0.1.3` (the **run number** increments per workflow) |
| `notes` | two lines; first line `line one` |

**What to notice:** `github.run_number` counts runs of **this workflow** (1, 2, 3 across our three dispatches), which is why it is a convenient build number. It is not the run id (`37318380786`).

## 4. Job Outputs and `needs`

Step outputs are visible only inside their job. To hand one to another job, declare it under `jobs.<id>.outputs` and read it through `needs`:

```yaml
build:
  outputs:
    version: ${{ steps.ver.outputs.version }}
consume:
  needs: [build]
  env:
    VERSION: ${{ needs.build.outputs.version }}
```

In the `consume` job of run 37318380786 the log shows `REPORT version=0.1.1` and `notes_lines=2`: the string and the two-line value both crossed jobs.

**What to notice:**

- **Outputs are always strings.** A boolean output arrives as the text `'true'` (Chapter 07's truthiness trap applies).
- The value arrives through `needs.<job>.outputs.<name>`; it is only available to jobs that list the producer in `needs`.
- A job that was skipped or failed contributes **empty** outputs.

> 📝 **Full implementation:** See [Appendix A.1](#a1-verify-outputs-artifacts-and-cache-from-the-saved-runs)

## 5. How Big Can an Output Be?

The docs do not state a step or job output limit, so we measured. `ch09-output-limits.yml` and `ch09-output-bisect.yml` make producer jobs, each emitting one string of repeated `a`. Runs **37317645339** and **37320026502**:

| Producer | Characters | Job duration | Result |
| --- | --- | --- | --- |
| `p400k` | 400,000 | **128 s** | success |
| `p520k` | 520,000 | **215 s** | success |
| `p530k` | 530,000 | **226 s** | **failure** |
| `p1m` | 1,000,000 | **786 s** | **failure** |
| `p1_1m` | 1,100,000 | **781 s** | **failure** |

Every failing job's annotation: **`Job outputs exceed 1,048,576 bytes`**.

**What to notice:**

- The platform's limit is **1,048,576 bytes (1 MiB)** per job's outputs. But our 520,000-character output passed and our 530,000-character output failed. The boundary between them contains **524,288**, which is exactly 1,048,576 / 2. So the limit behaves as **2 bytes per character**, i.e. about **524,288 ASCII characters**, not a million. (Two bytes per character is our inference from the bracket; the platform message only states the byte limit.)
- The cost is not just failure. The step that wrote the output ran in **0 seconds**, yet the job took minutes: the time is spent in the **Complete job** step. Fitting the passing and borderline sizes to `time = 128 s x (chars / 400,000)^2` predicts 216 s at 520,000 and 225 s at 530,000, against measured 215 s and 226 s: the time grows about **with the square of the size**. For 1,000,000 characters the same curve predicts about 800 s and we measured 786 s; the 1,100,000-character job ended at 781 s instead of the predicted ~970 s, so something stops it near 13 minutes. (This is a curve fit to five points, not a documented rule.)
- On a private repo (Chapter 01), `p400k` would bill **3 minutes** (ceil(128 / 60)) for a job that did no work, and `p520k` 4 minutes (ceil(215 / 60)); the failing 1,000,000-character jobs 14 minutes each.
- Our consumer, which received the 400,000-character value as an environment variable, was still running 4 minutes after it started, so we cancelled the whole run after 18 minutes.

**Rule:** outputs are for identifiers, flags, versions and paths. Anything resembling data goes in an artifact.

## 6. Artifacts

An artifact is a named, zipped set of files stored with the run. Upload and download:

```yaml
- uses: actions/upload-artifact@v7
  with: { name: tally-dist, path: dist/, retention-days: 1 }
# in another job:
- uses: actions/download-artifact@v8
  with: { name: tally-dist, path: got/ }
```

(Versions verified 2026-10-05: `upload-artifact` latest `v7.0.1`, `download-artifact` `v8.0.1`, both `node24`.)

What the real run stored (API `repos/OWNER/REPO/actions/runs/<id>/artifacts`):

| Field | Value |
| --- | --- |
| name | `tally-dist` |
| size_in_bytes | **277** (from 2,060 raw bytes: it is zipped) |
| created_at | 2026-10-05T13:38:36Z |
| expires_at | 2026-10-06T13:38:36Z (**exactly +1 day**: `retention-days: 1`) |

And in the `consume` job, which never checked out the repo (`no_checkout_here=absent`):

| Check | Result |
| --- | --- |
| files downloaded | `got/payload.bin`, `got/tally.txt` |
| content digest equals the producer's output | **yes** (`digest_match=yes`) |

**What to notice:**

- The artifact is how the **bytes** crossed jobs, and the output `digest` is how the consumer **verified** them. Pairing a small output (a hash) with an artifact (the file) is a standard pattern.
- Retention is yours to set per upload (we set 1 day). The default comes from repository settings; we did not measure it, so check yours.
- Artifacts are immutable and uploading the same name twice is an error (Section 16).
- You can fetch one from a terminal: `gh run download 37318380786 -n tally-dist`.

## 7. Caching, with Real Timings

An artifact carries results *forward in a run*. A **cache** carries expensive-to-rebuild files *forward across runs*. Our cache job:

```yaml
- uses: actions/cache@v6
  id: cache
  with:
    path: ~/.cache/ch09-deps
    key: ch09-${{ inputs.salt }}-${{ hashFiles('pyproject.toml') }}
- name: Install dependencies (slow on a miss)
  if: ${{ steps.cache.outputs.cache-hit != 'true' }}
  run: sleep 12 && head -c 20000000 /dev/urandom > ~/.cache/ch09-deps/deps.bin
```

The same job, three runs. Step durations are real (from the jobs API):

| Run | Salt | `cache-hit` output | Restore | Install | Post (save) | Sum of steps |
| --- | --- | --- | --- | --- | --- | --- |
| 37318380786 | a | *empty* | 0 s | **13 s** | **2 s** | 17 s |
| 37318461776 | a | `true` | 2 s | **skipped** | 0 s | 4 s |
| 37318514549 | b | *empty* | 1 s | **12 s** | 1 s | 14 s |

**What to notice:**

- The key had two parts: our salt, and `hashFiles('pyproject.toml')` (`6e19a1b8...`). Changing the salt from `a` to `b` is a **different key**, hence a miss, even though nothing else changed. Changing `pyproject.toml` would do the same.
- **On a miss `cache-hit` is an empty string, not `false`.** Our guard `!= 'true'` handles both. A guard written `== 'false'` would never fire (Chapter 07).
- The **save** happens in the job's **post step** after the job succeeds ("Post Restore cache", 2 s), not at the restore step. Docs (verified 2026-10): the cache is created if the job completes successfully after a miss.
- The cache holds 20,003,186 bytes for 20,000,000 raw bytes. Random data does not compress; real dependency trees do.
- The repository's cache listing afterward showed four entries: our two plus two created by `setup-uv` in `ci.yml`. (The separate usage endpoint, which lags, reported 3 entries and 82,148,885 bytes at that moment.)

**Savings arithmetic.** A hit saved 13 s of install at the price of 2 s of restore: **11 s per run**. But look at billing (Chapter 01): the miss job's steps sum to 17 s and the hit job's to 4 s, and **both bill 1 minute**. Caching saves *time* always; it saves *money* only when it moves a job across a minute boundary (for example 70 s down to 55 s). For a repo with a 3-minute install, the same 11-second-ish ratio becomes decisive.

> 📝 **Full implementation:** See [Appendix A.2](#a2-cache-savings-and-billing)

## 8. Designing a Cache Key

A good key changes **exactly when the cached content would change**. The standard shape:

```
<purpose>-<runner os>-<hash of the lock file>
ch09-deps-Linux-${{ hashFiles('**/requirements.txt') }}
```

| Key design | Behavior |
| --- | --- |
| No hash (`ch09-deps`) | One cache forever: **stale** after a dependency change |
| Hash of the lock file | New cache whenever dependencies change |
| Includes OS (`runner.os`) | Prevents restoring Linux files on macOS |
| Includes a salt | Lets you force a miss on purpose (our `salt` input) |

`restore-keys` provide **fallback prefixes**: if the exact key misses, a cache whose key starts with a listed prefix can be restored (and `cache-hit` stays not-`true`, since it was not an exact match), so you start from a nearly-right cache instead of nothing. Docs (verified 2026-10): matching checks the exact key first, then partial matches, then each `restore-keys` entry in order, and a key may be at most **512 characters**.

## 9. Choosing the Mechanism

| Need | Use |
| --- | --- |
| Pass a version, flag or path to the next job | **Output** |
| Pass a built file to the next job, or let a person download it | **Artifact** |
| Avoid re-downloading dependencies on every run | **Cache** |
| Pass something secret | none of these: use a secret/OIDC (Chapter 08, 13) |
| Show a human a short report | job summary (`$GITHUB_STEP_SUMMARY`, 1 MiB per step per docs) |

## 10. Cache Scope Rules

> ⚠️ ADVANCED TOPIC: Skip on first read.

Docs (verified 2026-10): a run can restore caches created on its **own branch**, the **default branch**, and (for pull requests) the **base branch**. It cannot read caches from sibling or child branches or from other tags. So a cache first built on a feature branch is invisible to other feature branches until it exists on the default branch. Every cache entry records its `ref`; ours say `refs/heads/main`.

## 11. Limits and Eviction

> ⚠️ ADVANCED TOPIC: Skip on first read.

Docs (verified 2026-10): the default cache limit is **10 GB per repository**; an entry **not accessed for more than 7 days** is removed; when over the limit, entries are deleted oldest-last-access first. A cache is **immutable**: you cannot change an existing entry, only create a new key. Treat the cache as disposable.

## 12. Job Summaries

> ⚠️ ADVANCED TOPIC: Skip on first read.

Appending Markdown to `$GITHUB_STEP_SUMMARY` shows it on the run page. Docs (verified 2026-10): each step's summary is limited to 1 MiB. It is the right place for a human-readable report that does not belong in an output.

## 13. Case Study: The Stale Dependency

A team caches `~/.cache/pip` under the key `pip-cache` with no hash. Months later a transitive dependency is patched for a security issue, but CI keeps installing the cached old version because the key never changes. Tests pass against the vulnerable version. The fix is mechanical: key on `hashFiles('requirements*.txt')`. The lesson: a key is a **promise** that the content is current; if nothing in the key can change when the content should, the promise is false. (This is a design inference, not something we reproduced in a run.)

## 14. Comparison: Moving Data

| Mechanism | Setup Effort | Control | Failure Visibility | Security Exposure | Maintenance Burden |
| --- | --- | --- | --- | --- | --- |
| Step output | Minimal - one line | Moderate - strings only, size-capped | Fair - empty if mis-wired | Low - visible in logs, so no secrets | Low |
| Job output (`needs`) | Low - declare and wire | Moderate - same limits | Fair - skipped job gives empty | Low - same | Low |
| Artifact | Low - two actions | Strong - any files, retention set | Excellent - listed on the run page | Moderate - downloadable by anyone with access | Low |
| Cache | Low - one action | Weak - may be evicted any time | Fair - hit or miss in the log | Moderate - shared across runs, can be poisoned (Chapter 16) | Moderate - key design |

## 15. Practical Tips

- Put the **hash** of an artifact in an output so the consumer can verify it.
- Never put a secret or a large blob in an output.
- Set `retention-days` deliberately; the default may be much longer than you need.
- Always check `cache-hit != 'true'` rather than `== 'false'`.
- Make the workflow correct **without** the cache; treat a hit as a bonus.
- Use `if-no-files-found: error` when a missing upload would be a real bug.
- Use a unique artifact name per matrix leg (`tally-dist-${{ matrix.py }}`), because names must be unique in a run.

## 16. Demonstrated Failure Modes

All from run 37318380786 (`build` job).

**Failure 1: the empty upload.** `path: nothing-here/*.xyz`. Default behavior is a **warning** and a green step:

```
##[warning]No files were found with the provided path: nothing-here/*.xyz. No artifacts will be uploaded.
```

With `if-no-files-found: error` the same path is an **error** (the step's outcome was `failure`; we kept the job green with `continue-on-error`). Symptom of the default: a build that "uploaded" nothing and a consumer that later cannot find the file. Fix: set `error` for must-have artifacts.

**Failure 2: the duplicate name.** Uploading `tally-dist` a second time in the same run:

```
##[error]Failed to CreateArtifact: Received non-retryable error: Failed request: (409) Conflict: an artifact with this name already exists on the workflow run
```

Artifacts are immutable per name. Fix: unique names (matrix legs especially), or merge steps.

**Failure 3: the oversized output.** `Job outputs exceed 1,048,576 bytes`, discovered only after minutes of waiting (226 s at 530,000 characters, 786 s at 1,000,000; Section 5). Fix: use an artifact, and keep outputs far below about 500,000 characters.

**Failure 4: the guard that never fires.** `cache-hit` is empty on a miss. `if: steps.cache.outputs.cache-hit == 'false'` would **never** be true, so the install would never run on a miss. Use `!= 'true'`.

## 17. Key Takeaways

- Outputs are short strings; job outputs cross jobs through `needs`.
- A job's outputs may not exceed 1,048,576 bytes (about 524,288 ASCII characters in our measurements), and large outputs make the job slow before they make it fail.
- Artifacts carry files between jobs and to people; names must be unique and uploads are immutable.
- An empty upload is only a warning unless `if-no-files-found: error`.
- A cache is keyed, saved after a successful job on a miss, and may disappear.
- `cache-hit` is `true` only on an exact hit and empty on a miss.
- Caching saves time every run, but saves billed minutes only when it crosses a minute boundary.
- A cache key must change exactly when the cached content should.

## 18. Exercises

1. In the Section 7 table, what is the saving per run from a hit, and why might the bill not change?
2. You write `if: steps.cache.outputs.cache-hit == 'false'` to run an install on a miss. Does it run? Why?
3. Two matrix legs both upload an artifact named `results`. What happens, and what is the fix?
4. A job output holds the string `true`. In the consumer, `if: needs.build.outputs.flag` is checked. If the output were `false`, what would the `if` do?
5. (Hand arithmetic) A job installs dependencies in 95 s on a miss and restores a cache in 6 s on a hit; the rest of the job takes 20 s. Billed minutes for a miss and for a hit?

<details>
<summary>Answers</summary>

1. 13 s install minus 2 s restore = 11 s. Both jobs bill one minute (17 s and 4 s each round up to 1), so the bill is unchanged.
2. No. On a miss `cache-hit` is an empty string, not `'false'`, so the comparison is false and the install is skipped. Use `!= 'true'`.
3. The second upload fails with a 409 Conflict (name already exists). Give each leg a unique name such as `results-${{ matrix.py }}`.
4. It would **run**: the output is the string `'false'`, which is truthy. Compare explicitly: `== 'true'`.
5. Miss: 95 + 20 = 115 s, ceil(115/60) = 2 min. Hit: 6 + 20 = 26 s, 1 min. Here caching saves a billed minute.

</details>

## 19. Additional Resources

All verified 2026-10.

- GitHub Docs: Workflow commands (`GITHUB_OUTPUT`, multiline values, summaries) - https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands
- GitHub Docs: Dependency caching reference - https://docs.github.com/en/actions/reference/workflows-and-actions/dependency-caching
- GitHub Docs: Workflow artifacts - https://docs.github.com/en/actions/concepts/workflows-and-actions/workflow-artifacts
- actions/upload-artifact - https://github.com/actions/upload-artifact
- actions/download-artifact - https://github.com/actions/download-artifact
- actions/cache - https://github.com/actions/cache
- Live evidence: runs 37318380786, 37318461776, 37318514549 (data) and 37317645339 (output size) in this repo
- Laster, *Learning GitHub Actions* (O'Reilly), Chapter 7

## 20. Appendix A: Code Index

> 💻 Complete, runnable code for this chapter. Skip when reading for concepts.

### A.1 Verify outputs, artifacts and cache from the saved runs

```python
import json
from pathlib import Path

miss = json.loads(Path("fixtures/data_ch09_miss.json").read_text())
hit = json.loads(Path("fixtures/data_ch09_hit.json").read_text())
assert miss["reports"]["consume"]["version"] == "0.1.1"
assert hit["reports"]["consume"]["version"] == "0.1.2"      # run_number increments
assert miss["reports"]["consume"]["digest_match"] == "yes"
assert miss["reports"]["cache"]["cache_hit"] == "[]"         # empty on a miss
assert hit["reports"]["cache"]["cache_hit"] == "[true]"
assert miss["reports"]["build"]["strict_outcome"] == "failure"
assert miss["reports"]["build"]["duplicate_outcome"] == "failure"
```

**Flow:** load two saved runs -> assert the output values crossed jobs -> assert the digest matched across the artifact -> assert the `cache-hit` forms -> assert both bad uploads failed.

### A.2 Cache savings and billing

```python
from intro_gha.cost import billed_minutes

miss_steps, hit_steps = [1, 1, 0, 13, 0, 2, 0, 0], [1, 1, 2, 0, 0, 0, 0, 0]
assert sum(miss_steps) == 17 and sum(hit_steps) == 4
assert billed_minutes(sum(miss_steps)) == billed_minutes(sum(hit_steps)) == 1
assert billed_minutes(95 + 20) == 2 and billed_minutes(6 + 20) == 1   # exercise 5
```

**Flow:** sum each job's step seconds -> round each up to a billed minute -> compare: equal here, different when the install is long enough to cross a minute.
