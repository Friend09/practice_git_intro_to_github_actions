# Chapter 00: Essentials: YAML, Git Refs, CI/CD Vocabulary

**Reading Time:** ~40 minutes
**Prerequisites:** None
**Practice Notebook:** `notebooks/practice_00.ipynb`
**Reference Notebook:** `notebooks/lab_00_essentials_yaml_git_cicd.ipynb`
**Script:** `labs/lab_00_essentials_yaml_git_cicd.py`
**Book Reference:** Laster, Learning GitHub Actions Ch 1 / GitHub Docs: Understanding GitHub Actions
**Depth:** Core
**Default Runtime:** Offline fixtures

---

## Beginner's Guide

**Focus on first:** Sections 3 (YAML), 4 (the two YAML traps), 5 (Git refs) and 7 (CI vs CD vs delivery). Everything later in the course is a workflow file, and a workflow file is YAML that reacts to Git events.

**Skip on first read:** Sections 10-12 (YAML anchors, multi-document files, Git plumbing). Come back when something in a later chapter references them.

**Key concepts in plain English:**

- **YAML** is a way to write nested lists and key/value pairs using indentation instead of braces.
- **A ref** is a human-readable name (`main`, `v1.0.0`) that points at one exact commit.
- **A commit SHA** is the 40-character fingerprint of one exact snapshot of your repo.
- **CI (continuous integration)** means every change is automatically built and tested, shortly after it is pushed.
- **A pipeline** is just a sequence of automated stages that a change passes through.

**If you have written a shell script or a Makefile**, you already know the hard part: "run these commands in this order and stop if one fails." Actions is that, triggered by Git events.

> **🔬 Platform Engineer's Lens:** The two failure modes in this chapter (a YAML version parsed as a float, and the `on` key parsed as a boolean) never produce a syntax error. They produce a workflow that runs the wrong thing or never runs at all. In production that costs hours of staring at a green-looking repo. Learn the traps once, here, in 5 minutes, instead of at 11 pm.

> **🚦 Native vs Marketplace vs Custom:** There is nothing to build in this chapter. YAML parsing, ref resolution and event delivery are all native to GitHub. The only "custom" thing you will ever do with YAML is validate it, and `actionlint` (Chapter 17) already does that.

## What You'll Learn

- Read and write the YAML subset used by workflow files (maps, lists, scalars, block strings)
- Predict how a YAML parser types a value: string, int, float, bool or null
- Spot the two classic traps (`3.10` and `on`) before they bite
- Distinguish a branch, a tag, a SHA and `HEAD`, and say which one a workflow sees
- Explain CI, continuous delivery and continuous deployment without blurring them
- Describe the stages of a pipeline and what an artifact is
- Meet **Tally**, the running example used by every chapter

## Table of Contents

<!-- TOC -->
<!-- /TOC -->

---

## 1. Why This Chapter Exists

Every later chapter shows a workflow file and asks you to predict what GitHub does with it. To predict, you need three vocabularies: YAML (the file format), Git (the events and the names), and CI/CD (the goal). This chapter is those three vocabularies, with just enough depth to read a workflow without guessing.

It is deliberately short on GitHub features. No workflow runs in this chapter. The only thing that runs is a Python script that parses YAML, because the cheapest way to learn how a YAML parser thinks is to ask one.

## 2. Meet Tally: The Running Example

> 📌 **Running Example: Tally.** Tally is a tiny Python library. It has one function, `add(a, b)`, in `sandbox/tally/tally/add.py`, and two tests in `sandbox/tally/tests/test_add.py`. Across the course it grows a workflow one step at a time: one green check (Chapter 03), a test matrix (Chapter 10), a container (Chapter 12), a release (Chapter 14) and a full pipeline (Chapter 23). In this chapter we only need its first workflow file, shown in Section 3, and a Git history of three commits, shown in Section 5.

The app is small on purpose. When a chapter says "9 jobs" or "41 seconds", you can check the number by hand, because there is nothing hidden in the code.

```python
# sandbox/tally/tally/add.py
def add(a: int, b: int) -> int:
    return a + b
```

**Tally's three commits** (we use these SHAs throughout, shortened to 7 characters as GitHub does):

| Commit | Message | Parent |
| --- | --- | --- |
| `a1b2c3d` | Add add() | none |
| `e4f5a6b` | Add tests | `a1b2c3d` |
| `9c8d7e6` | Add first workflow | `e4f5a6b` |

## 3. YAML in Ten Minutes

A workflow file is a YAML document. YAML has three building blocks.

**Maps** are `key: value` pairs. Indentation (spaces, never tabs) nests them.

**Lists** are lines starting with `- `.

**Scalars** are single values: strings, numbers, booleans, null.

Here is Tally's first workflow, which we will parse in this chapter:

```yaml
name: CI
on: push
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: python -m pytest
```

**How to read it, line by line:**

| Line | YAML meaning | Parsed Python value |
| --- | --- | --- |
| `name: CI` | map entry, string value | `"name": "CI"` |
| `on: push` | map entry (see Section 4!) | `True: "push"` |
| `jobs:` | map whose value is a nested map | `"jobs": {...}` |
| `steps:` | key whose value is a list | `[{...}, {...}]` |
| `- uses: ...` | one list item that is itself a map | `{"uses": "actions/checkout@v4"}` |
| `- run: ...` | the second list item | `{"run": "python -m pytest"}` |

**Worked trace: parse it.** Before: the text above, as a string. Command: `yaml.safe_load(text)`. After:

```python
{True: 'push',
 'name': 'CI',
 'jobs': {'test': {'runs-on': 'ubuntu-latest',
                   'steps': [{'uses': 'actions/checkout@v4'},
                             {'run': 'python -m pytest'}]}}}
```

**What to notice:**

- The key `on` has become the Python boolean `True`. Section 4 explains why.
- `steps` is a list of two maps; order is preserved, and order is execution order.
- Everything you can see in the file is in the dict. YAML has no hidden state.

### Block strings: `|` and `>`

Multi-line shell commands use a block scalar:

```yaml
- run: |
    pip install -e .
    python -m pytest
```

`|` keeps newlines (each line is a separate shell line). `>` folds newlines into spaces. In a `run:` step you almost always want `|`.

## 4. The Two Traps

Both traps are silent: the YAML is valid, the parse succeeds, and the result is not what you meant.

### Trap 1: `3.10` is the float 3.1

> 📌 **Running Example: the version matrix.** Tally supports Python 3.9, 3.10 and 3.11. Its workflow lists them as `python-version: [3.9, 3.10, 3.11]`.

State the parse results before you run anything:

| YAML text | Parsed type | Parsed value | What `setup-python` receives |
| --- | --- | --- | --- |
| `3.9` | float | `3.9` | `3.9` (works by luck) |
| `3.10` | float | `3.1` | `3.1`: **wrong version** |
| `3.11` | float | `3.11` | `3.11` (works) |
| `'3.10'` | string | `'3.10'` | `3.10` (correct) |

**What to notice:** the number `3.10` and the number `3.1` are the same float. The trailing zero is gone before GitHub ever sees the file. Your matrix silently tests 3.1 (which does not exist, so the job fails with "version not found", or worse, resolves to something you did not intend).

**The fix:** always quote versions. `python-version: ['3.9', '3.10', '3.11']`.

### Trap 2: `on` is a boolean

In YAML 1.1 (the version PyYAML implements) the bare words `on`, `off`, `yes`, `no`, `y` and `n` are booleans. So the key `on:` parses as `True`. GitHub's own parser handles it correctly, so your workflow works. But **any tool you write in Python** will see `True` instead of `"on"` and look up the wrong key.

| Source | Key you see |
| --- | --- |
| GitHub's runner | `on` (understood correctly) |
| `yaml.safe_load` in Python | `True` |
| `intro_gha.workflow.load_workflow` | `"on"` (we normalize it) |

**The fix in tooling:** normalize `True` back to `"on"` right after loading. We do this once, in `src/intro_gha/workflow.py`, and every chapter reuses it.

> 📝 **Full implementation:** See [Appendix A.1](#a1-load_workflow-and-the-on-fix)

## 5. Git Refs: The Names Your Workflows See

Git stores snapshots called **commits**. Each commit has a **SHA**, a 40-hex-character hash of its contents. Humans use **refs**: names that point at a commit.

**State before:** Tally's three commits from Section 2, linear history, `main` pointing at `9c8d7e6`.

```
a1b2c3d <- e4f5a6b <- 9c8d7e6
                       ^
                      main (refs/heads/main), HEAD
```

| Thing | Full name | Moves? | Example value |
| --- | --- | --- | --- |
| Branch | `refs/heads/main` | Yes, on every commit | `9c8d7e6...` |
| Tag | `refs/tags/v0.1.0` | No (by convention) | `9c8d7e6...` |
| SHA | (the commit itself) | Never | `9c8d7e6...` |
| `HEAD` | (local only) | Yes | whatever you checked out |

**Command and after-state.** Tally's owner makes a fourth commit `1d2e3f4` and tags the old one:

```bash
git tag v0.1.0 9c8d7e6
git commit -m "Add subtract"
```

```
a1b2c3d <- e4f5a6b <- 9c8d7e6 <- 1d2e3f4
                       ^           ^
                    v0.1.0        main
```

**What to notice:**

- The branch moved forward by one; the tag stayed put. That is the difference a workflow cares about.
- A workflow triggered by a push sees `github.ref = refs/heads/main` and `github.sha = 1d2e3f4...`. Chapter 07 covers these in depth.
- `HEAD` is not visible to a workflow. Runners check out a specific SHA, not "whatever HEAD is".

**Why workflows care:** a trigger filter such as `branches: [main]` matches against `refs/heads/...`, and `tags: ['v*']` matches against `refs/tags/...`. A tag push and a branch push are different events.

## 6. The Event That Starts Everything

GitHub emits an event when something happens in a repository: a push, a pull request opened, an issue commented. A workflow subscribes to events with `on:`. When one arrives, GitHub starts a **run** of every matching workflow.

```
you: git push  ->  GitHub receives push event  ->  looks in .github/workflows/*.yml
                                                    for `on: push`  ->  starts a run
```

Chapter 02 builds the full model (event, workflow, job, step, runner). For now remember one fact: **the workflow file that runs is the one in the commit that triggered the event.** Push a broken workflow file and the broken one runs.

## 7. CI, Continuous Delivery, Continuous Deployment

These three terms are used loosely. Use them precisely:

| Term | What is automated | Human step remaining |
| --- | --- | --- |
| Continuous integration (CI) | Build + test every change | Decide to merge |
| Continuous delivery | CI + produce a releasable artifact every time | Decide to release |
| Continuous deployment | CI + release + deploy to production | None |

> **Analogy: the kitchen pass.** CI is the cook tasting every dish before it leaves the kitchen. Delivery is plating every dish so it is ready to serve. Deployment is a robot waiter carrying it to the table without asking. The analogy breaks at rollback: a dish cannot be un-served, but a deployment can be reverted.

**Tally across the course:** Chapters 03-11 are CI. Chapter 14 adds delivery (a GitHub Release with a built wheel). Chapter 13 adds deployment (to a protected environment).

## 8. Pipelines, Stages and Artifacts

A **pipeline** is the ordered set of automated stages a change passes through. A typical one:

```
commit -> lint -> test -> build -> publish artifact -> deploy to staging -> deploy to prod
```

An **artifact** is a file produced by one stage and consumed by a later one (a wheel, a coverage report, a container image). In GitHub Actions the word has a second, specific meaning (a stored file attached to a run, Chapter 09); in the wider industry it means any build output.

**A stage fails closed:** if lint fails, test never starts. The ordering is how a pipeline saves time and money, because the cheapest check runs first.

## 9. Where Workflow Files Live

Per GitHub Docs, workflow files must be stored in `.github/workflows/` in the repository and have a `.yml` or `.yaml` extension. A file anywhere else is ignored without warning.

| Location | Result |
| --- | --- |
| `.github/workflows/ci.yml` | Loaded |
| `.github/workflows/ci.yaml` | Loaded |
| `.github/workflow/ci.yml` (typo) | **Silently ignored** |
| `workflows/ci.yml` | **Silently ignored** |

This is the first "why didn't it fire" cause you will meet; Chapter 17 collects the rest.

## 10. YAML Anchors and Aliases

> ⚠️ ADVANCED TOPIC: Skip on first read.

YAML lets you name a block with `&name` and reuse it with `*name`:

```yaml
defaults: &py
  python-version: '3.12'
a: *py
```

**Important:** GitHub Actions did not support anchors and aliases for a long time and rejected them. Check the current docs before relying on them; where they are unsupported, use reusable workflows or composite actions (Chapter 19, 20) instead.

## 11. Multi-Document Files and Comments

> ⚠️ ADVANCED TOPIC: Skip on first read.

A YAML file can contain several documents separated by `---`. A workflow file must contain exactly one. Comments start with `#` and are legal anywhere; they are your documentation, because workflow YAML has no other place for it.

## 12. Git Plumbing You Can Ignore for Now

> ⚠️ ADVANCED TOPIC: Skip on first read.

Under the hood a ref is a file: `.git/refs/heads/main` contains the 40-character SHA. `git rev-parse main` prints it. `git for-each-ref` lists all refs. Pull requests add a special ref, `refs/pull/<n>/merge`, which GitHub creates to test the merge result. Chapter 06 shows why that matters.

## 13. Case Study: A Typo That Looked Fine

A teammate renames `.github/workflows/` to `.github/workflow/` while tidying. Nothing errors. Pushes still succeed. CI stops running. Because no run is created, there is no red X. The first sign is a pull request merging with no checks at all.

**Detection:** `gh workflow list` shows nothing, and the Actions tab shows no runs after the date of the rename. **Prevention:** a repo-level test that asserts `.github/workflows/*.yml` exists. This repo has one: `tests/test_workflow_yaml.py`.

## 14. Comparison: Three Ways to Automate "Run the Tests"

| Approach | Setup Effort | Control | Failure Visibility | Security Exposure | Maintenance Burden |
| --- | --- | --- | --- | --- | --- |
| A shell script you run by hand | Minimal - one file | Strong - full local control | Weak - only you see it | Minimal - runs locally | Low - until you forget |
| A Git pre-commit hook | Low - per-clone setup | Moderate - skippable with `--no-verify` | Weak - local only | Minimal - local | Moderate - drifts per clone |
| GitHub Actions workflow | Low - one YAML file | Strong - runs on every push | Excellent - shown on the PR | Moderate - runs on shared infra | Low - versioned with the code |

Chapter 01 expands this comparison to include Jenkins and other servers.

## 15. Practical Tips

- Quote anything that looks like a number but is a version: `'3.10'`, `'20'`.
- Use two spaces per indent level and an editor that shows whitespace; one tab is a syntax error.
- Quote strings containing `: ` or starting with `*`, `&`, `!`, `%`, `@` or a backtick.
- Run `actionlint .github/workflows/*.yml` after every edit (Chapter 17).
- Pin to a commit SHA when you need a reproducible reference; a branch or tag can move.

## 16. Demonstrated Failure Modes

**Failure 1: the 3.10 matrix.** Tally's workflow lists `[3.9, 3.10, 3.11]` unquoted.

| Step | State |
| --- | --- |
| Parse | matrix values: `[3.9, 3.1, 3.11]` |
| Expand | 3 jobs named `test (3.9)`, `test (3.1)`, `test (3.11)` |
| Run job 2 | `setup-python` is asked for `3.1`: fails "version not found" |

**Symptom:** a red job labelled `3.1`, a version you never wrote. **Cause:** YAML floats drop trailing zeros. **Fix:** quote.

**Failure 2: the `on` boolean in your own tool.** A script reads `workflow["on"]` and gets `KeyError`, because the key is `True`. **Symptom:** works on hand-written dicts, fails on real files. **Fix:** normalize with `load_workflow`.

Both failures are re-created, with assertions, in `labs/lab_00_essentials_yaml_git_cicd.py`.

## 17. Key Takeaways

- A workflow is YAML; learn maps, lists and scalars and you can read any of them.
- Quote versions. `3.10` parses to the float `3.1`.
- `on` is a boolean to a YAML 1.1 parser; normalize it in your own tooling.
- A branch moves, a tag (by convention) does not, a SHA never changes.
- A workflow file must be in `.github/workflows/` or it is silently ignored.
- CI tests every change; delivery makes a release ready; deployment ships it.
- Tally is the running example: `add(a, b)`, three commits, one workflow.

## 18. Exercises

1. What Python value does `yaml.safe_load("v: 3.10")["v"]` return, and what type is it?
2. Given Tally's history in Section 5 after the fourth commit, which refs point at `9c8d7e6` and which at `1d2e3f4`?
3. A matrix is written `os: [ubuntu-latest, windows-latest]` and `python: [3.10, 3.11]`. How many jobs, and what versions do they request?
4. Classify each as CI, delivery or deployment: (a) tests run on every PR; (b) a wheel is attached to every tag; (c) merging to `main` updates the live site.
5. You rename `.github/workflows/ci.yml` to `.github/workflows/ci.txt`. What happens on the next push, and how would you detect it?

<details>
<summary>Answers</summary>

1. The float `3.1` (type `float`). The trailing zero is lost.
2. `v0.1.0` points at `9c8d7e6`. `main` (and `HEAD` if checked out) points at `1d2e3f4`.
3. 2 x 2 = 4 jobs, requesting Python `3.1` (twice, once per OS) and `3.11`. Quote the versions to get `3.10`.
4. (a) CI. (b) Continuous delivery. (c) Continuous deployment.
5. The file is no longer loaded (wrong extension), so no run is created and nothing is red. Detect it with `gh workflow list` or a test that asserts the workflow file exists.

</details>

## 19. Additional Resources

All verified 2026-10.

- GitHub Docs: Understanding GitHub Actions - https://docs.github.com/en/actions/get-started/understand-github-actions
- GitHub Docs: Workflow syntax reference (file location, extensions) - https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax
- GitHub Docs: Actions limits (6 hours per job, 256 matrix jobs) - https://docs.github.com/en/actions/reference/limits
- YAML 1.1 specification, boolean type (why `on` is `True`) - https://yaml.org/type/bool.html
- YAML 1.2 specification (what newer parsers fix) - https://yaml.org/spec/1.2.2/
- Pro Git, "Git Internals: Git References" - https://git-scm.com/book/en/v2/Git-Internals-Git-References
- Laster, *Learning GitHub Actions* (O'Reilly), Chapter 1

## 20. Appendix A: Code Index

> 💻 Complete, runnable code for this chapter. Skip when reading for concepts.

### A.1 load_workflow and the `on` fix

```python
from pathlib import Path
from typing import Any

import yaml


def load_workflow(path: Path) -> dict[str, Any]:
    """Parse a workflow file, mapping the YAML-1.1 boolean key True to "on"."""
    data = yaml.safe_load(path.read_text())
    if True in data:
        data["on"] = data.pop(True)
    return data
```

**Flow:** read text -> `safe_load` -> if the key `True` exists, rename it to `"on"` -> return.

### A.2 Reproduce both traps

```python
import yaml

TALLY = """
name: CI
on: push
jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: [3.9, 3.10, 3.11]
"""

doc = yaml.safe_load(TALLY)
assert True in doc and "on" not in doc                    # trap 2
versions = doc["jobs"]["test"]["strategy"]["matrix"]["python-version"]
assert versions == [3.9, 3.1, 3.11]                       # trap 1
fixed = yaml.safe_load("python-version: ['3.9', '3.10', '3.11']")
assert fixed["python-version"] == ["3.9", "3.10", "3.11"]
print("both traps reproduced; quoting fixes the first")
```
