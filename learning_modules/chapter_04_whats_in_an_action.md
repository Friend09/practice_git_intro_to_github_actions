# Chapter 04: What's in an Action: uses, Marketplace, Versioning

**Reading Time:** ~45 minutes
**Prerequisites:** Chapter 02 (steps, runners), Chapter 03 (workflow anatomy)
**Practice Notebook:** `notebooks/practice_04.ipynb`
**Reference Notebook:** `notebooks/lab_04_whats_in_an_action.ipynb`
**Script:** `labs/lab_04_whats_in_an_action.py`
**Book Reference:** Laster, Learning GitHub Actions Ch 3 / GitHub Docs: Workflow syntax (`jobs.<job_id>.steps[*].uses`)
**Depth:** Core
**Default Runtime:** Live repo

---

## Beginner's Guide

**Focus on first:** Sections 3 (the five `uses:` forms), 6 (how `@v7` becomes a commit) and 16 (the reference that does not exist).

**Skip on first read:** Sections 11-12 (action metadata edge cases, internals of pre/post steps).

**Key concepts in plain English:**

- **An action** is a reusable unit of automation that a step can call with `uses:`. It is not magic: it is a folder in a Git repo with a file called `action.yml`.
- **A reference** like `actions/checkout@v7` means "the repo `actions/checkout`, at the Git ref `v7`."
- **A tag** (`v7`) can be moved to a different commit. **A SHA** (`3d3c42e...`) cannot.
- **Runtime:** what executes the action: Node.js, a shell (composite), or a Docker container.

**If you have used a package manager** (pip, npm), `uses: owner/repo@ref` is a dependency declaration, and the ref is the version pin. The big difference: there is no lockfile unless you write the SHA yourself.

> **🔬 Platform Engineer's Lens:** An action is third-party code that runs inside your pipeline with access to your repo checkout and, depending on permissions, your token. The tag you write is a **promise by the action's maintainer**, not a guarantee. Two real events from preparing this chapter, both in Section 16: a floating major tag that simply does not exist, and a pair of widely copied versions (`checkout@v4`, `setup-python@v5`) that declare a Node runtime GitHub has since retired.

> **🚦 Native vs Marketplace vs Custom:** For checkout and language setup, use the first-party `actions/*` repos (native in spirit, maintained by GitHub). For anything else, ask in order: is there a shell one-liner? (use `run:`); is there a first-party action? (use it); is there a well-maintained third-party action? (pin it, Chapter 16); otherwise write your own (Chapter 19).

## What You'll Learn

- Read any `uses:` reference and say exactly what it points at
- Name the five reference forms: tag, branch, SHA, local path, Docker image
- Open an `action.yml` and identify inputs, outputs and the runtime
- Tell a JavaScript, composite and Docker action apart
- Prove from a run log that a tag resolved to a specific commit
- Explain why a SHA is immutable and a tag is not
- Diagnose `Unable to resolve action` and a stale runtime declaration

## Table of Contents

<!-- toc-start -->

- [Chapter 04: What's in an Action: uses, Marketplace, Versioning](#chapter-04-whats-in-an-action-uses-marketplace-versioning)
  - [Beginner's Guide](#beginners-guide)
  - [What You'll Learn](#what-youll-learn)
  - [Table of Contents](#table-of-contents)
  - [1. What `uses:` Does](#1-what-uses-does)
  - [2. Running Example: Five Forms in One Job](#2-running-example-five-forms-in-one-job)
  - [3. The Five Forms of `uses:`](#3-the-five-forms-of-uses)
  - [4. What Is Inside an Action](#4-what-is-inside-an-action)
  - [5. The Three Action Types](#5-the-three-action-types)
  - [6. Worked Trace: How a Tag Becomes a Commit](#6-worked-trace-how-a-tag-becomes-a-commit)
  - [7. Versions: Tags, Floating Majors and SHAs](#7-versions-tags-floating-majors-and-shas)
  - [8. Runtimes Expire: The Node 20 Story](#8-runtimes-expire-the-node-20-story)
  - [9. Judging an Action from the Marketplace](#9-judging-an-action-from-the-marketplace)
  - [10. Pre, Main and Post Steps](#10-pre-main-and-post-steps)
  - [11. Inputs, Defaults and the `INPUT_` Convention](#11-inputs-defaults-and-the-input_-convention)
  - [12. `action.yml` Versus `action.yaml` and Subpaths](#12-actionyml-versus-actionyaml-and-subpaths)
  - [13. Case Study: The Copy-Paste Pin](#13-case-study-the-copy-paste-pin)
  - [14. Comparison: Reference Styles](#14-comparison-reference-styles)
  - [15. Practical Tips](#15-practical-tips)
  - [16. Demonstrated Failure Modes](#16-demonstrated-failure-modes)
  - [17. Key Takeaways](#17-key-takeaways)
  - [18. Exercises](#18-exercises)
  - [19. Additional Resources](#19-additional-resources)
  - [20. Appendix A: Code Index](#20-appendix-a-code-index)
    - [A.1 Audit which commit each action ran](#a1-audit-which-commit-each-action-ran)
    - [A.2 Classify a reference](#a2-classify-a-reference)

---

## 1. What `uses:` Does

Chapter 03 used `uses: actions/checkout@v7` without explanation. This chapter opens the box. When the runner reaches a `uses:` step it (1) resolves the reference to a commit, (2) downloads that repo, (3) reads its `action.yml`, and (4) runs whatever the metadata says to run.

## 2. Running Example: Five Forms in One Job

> 📌 **Running Example: `ch04-uses-forms.yml`.** One job, five steps, each using a different form of `uses:`. Real run **37312325910** (success, `workflow_dispatch`). The steps: (1) `actions/checkout@v7`, (2) `actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1`, (3) a **local composite action** `./.github/actions/tally-greet`, (4) a **Docker image** `docker://alpine:3.20`, and (5) a plain `run:` that reads the composite's output. Data is saved in `fixtures/run_ch04_forms.json`. We return to it in Sections 3, 6 and 10.

```yaml
steps:
  - uses: actions/checkout@v7
  - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
  - uses: ./.github/actions/tally-greet
    with: { who: Tally }
  - uses: docker://alpine:3.20
    with: { entrypoint: /bin/echo, args: hello from a container step }
```

## 3. The Five Forms of `uses:`

| Form       | Example                         | Points at                                      | Mutable?                    |
| ---------- | ------------------------------- | ---------------------------------------------- | --------------------------- |
| Tag        | `actions/checkout@v7`           | A tag in the action's repo                     | Yes: maintainer can move it |
| Branch     | `actions/checkout@main`         | A branch tip                                   | Yes: changes every commit   |
| SHA        | `actions/checkout@3d3c42e...`   | One exact commit                               | **No**                      |
| Local path | `./.github/actions/tally-greet` | A folder in **your** repo, at the run's commit | Moves with your commits     |
| Docker     | `docker://alpine:3.20`          | A container image                              | By tag, yes                 |

The general shape for a remote action is `owner/repo[/subpath]@ref`. A `subpath` lets one repo hold many actions (`owner/repo/path/to/action@ref`).

**What to notice:** only the SHA form is immutable. The others depend on someone's discipline. Chapter 16 turns that into policy.

## 4. What Is Inside an Action

An action is a repo (or a folder) containing `action.yml`. Ours:

```yaml
name: Tally greet
inputs:
  who: { description: Name to greet, required: false, default: world }
outputs:
  message:
    {
      description: The greeting produced,
      value: "${{ steps.say.outputs.message }}",
    }
runs:
  using: composite
  steps:
    - id: say
      shell: bash
      env: { WHO: "${{ inputs.who }}" }
      run: echo "message=hello, $WHO" >> "$GITHUB_OUTPUT"
```

| Metadata key           | Meaning                             | In `tally-greet`       |
| ---------------------- | ----------------------------------- | ---------------------- |
| `name` / `description` | Human labels                        | `Tally greet`          |
| `inputs`               | Values the caller sets with `with:` | `who`, default `world` |
| `outputs`              | Values later steps can read         | `message`              |
| `runs.using`           | The runtime                         | `composite`            |

**State before / after the call.** Before: the caller passes `with: { who: Tally }`. During: the composite step receives `WHO=Tally` and writes `message=hello, Tally` to the special file `$GITHUB_OUTPUT`. After: step 5 reads `steps.greet.outputs.message` and prints `composite said hello, Tally`.

Note that the input is passed through an environment variable (`WHO`) instead of being pasted into the shell command. That is a security habit; Chapter 16 explains why.

## 5. The Three Action Types

| Type       | `runs.using`           | Runs as                                  | Example here                    |
| ---------- | ---------------------- | ---------------------------------------- | ------------------------------- |
| JavaScript | `node24` (or `node20`) | Node.js on the runner                    | `actions/checkout@v7`           |
| Composite  | `composite`            | A list of steps, like a mini-workflow    | `./.github/actions/tally-greet` |
| Docker     | `docker`               | A container built or pulled for the step | `docker://alpine:3.20`          |

We verified the JavaScript runtime declarations by reading each version's `action.yml` (fixture `action_tags_2026_10.json`): `checkout@v4` declares `node20`; `checkout@v6` and `@v7` declare `node24`; `setup-python@v5` declares `node20`, `@v7` declares `node24`.

In the real run the Docker step shows the runner doing the work: it **pulled** `alpine:3.20` as step 2 (before your first step), then ran `/usr/bin/docker run ... --entrypoint "/bin/echo" ... alpine:3.20 hello from a container step`. Docker steps are slower than shell steps because of the image pull.

## 6. Worked Trace: How a Tag Becomes a Commit

**State before:** the workflow text says `actions/checkout@v7` and `actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1`. **Command:** run the workflow. **State after:** the runner's own log, from the **Set up job** step of run 37312325910:

```
Download action repository 'actions/checkout@v7' (SHA:3d3c42e5aac5ba805825da76410c181273ba90b1)
Download action repository 'actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1' (SHA:3d3c42e5aac5ba805825da76410c181273ba90b1)
```

**What to notice:**

- The runner **resolved the tag** `v7` to a full commit SHA and prints it in parentheses. That resolution happens **every run**, at run time.
- Both references landed on the **same commit**. Today the tag and the SHA agree. If the maintainer moved `v7` tomorrow, the first line would show a different SHA and the second would not change.
- This log line is the cheapest audit tool you have: `gh run view <id> --log | grep "Download action repository"` lists exactly which commit of every action actually executed.

> 📝 **Full implementation:** See [Appendix A.1](#a1-audit-which-commit-each-action-ran)

## 7. Versions: Tags, Floating Majors and SHAs

Maintainers usually publish an exact version tag (`v7.0.1`) **and** move a floating major tag (`v7`) to follow the latest release. Real data for `actions/checkout`, verified 2026-10-05:

| Tag      | Resolves to commit | Note                                                    |
| -------- | ------------------ | ------------------------------------------------------- |
| `v4`     | `11d5960a3267`     | declares `node20`                                       |
| `v5`     | `fbc6f3992d24`     |                                                         |
| `v6`     | `d23441a48e51`     | same as release `v6.1.0`                                |
| `v7`     | `3d3c42e5aac5`     | same as release `v7.0.1` (latest)                       |
| `v7.0.0` | `9c091bb21b7c`     | an older point release; **not** what `v7` points to now |

**What to notice:**

- The floating `v7` moved from `v7.0.0`'s commit to `v7.0.1`'s commit. Anyone pinned to `@v7` got the new code automatically; anyone pinned to `@v7.0.0` did not.
- That is the trade: **a floating major** gets fixes without you doing anything and also gets whatever the maintainer ships. **An exact version or SHA** changes only when you decide.
- Nothing forces a maintainer to publish a floating tag at all (Section 16).

## 8. Runtimes Expire: The Node 20 Story

JavaScript actions run on a Node.js version the runner provides. GitHub's changelog (verified 2026-10) states the plan: runners began using **Node 24 by default on 2026-06-16**, and **Node 20 is removed on 2026-09-23**. Opt-outs exist only until then (`ACTIONS_ALLOW_USE_UNSECURE_NODE_VERSION`), and opting in early used `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24`.

Today's date is after both. Yet our Chapter 03 runs, which used `checkout@v4` and `setup-python@v5` (both declaring `node20`), succeeded. The runner now runs node20-declared JavaScript actions on Node 24. We see indirect evidence in the Chapter 03 log: the `Set up Python` step printed `DeprecationWarning: The 'punycode' module is deprecated` (code `DEP0040`), a Node message from a Node version newer than 20. We infer, rather than read, that the runner executed the action on its default Node.

**The lesson:** a stale major keeps working until it doesn't, and the warning you ignore today is the outage later. This repository's workflows were bumped to `checkout@v7` and `setup-python@v7` (both `node24`) when we wrote this chapter, and `ci.yml` to `astral-sh/setup-uv@v10.2.0` (`node24`).

## 9. Judging an Action from the Marketplace

The Marketplace is a search page over public actions. A listing is not a vetting. Before you adopt one, check:

| Check                   | Where                     | Healthy sign                                             |
| ----------------------- | ------------------------- | -------------------------------------------------------- |
| Who maintains it        | The repo owner            | A first-party org, or a maintainer you can name          |
| Last release            | Releases page             | Recent, with a changelog                                 |
| Runtime                 | `action.yml` `runs.using` | `node24` today, not `node20` or older                    |
| Permissions it needs    | README                    | Needs nothing your job does not already have             |
| Reference style offered | README                    | Documents exact versions or SHAs                         |
| Could `run:` do it?     | You                       | If a one-line command does the same job, skip the action |

## 10. Pre, Main and Post Steps

Some actions register cleanup. In run 37312325910 the step list ends:

| Step | Name                                   |
| ---- | -------------------------------------- |
| 13   | Post 2. Full-SHA reference (immutable) |
| 14   | Post 1. Tag reference (movable major)  |
| 15   | Complete job                           |

**What to notice:** the **post** steps run in **reverse order** of the main steps (2 before 1), like stack unwinding. The numbers jump (7 to 13) because GitHub reserves slots for each action's pre/post hooks; do not depend on step numbers, depend on names.

## 11. Inputs, Defaults and the `INPUT_` Convention

> ⚠️ ADVANCED TOPIC: Skip on first read.

`with:` values reach an action as environment variables named `INPUT_<UPPERCASED NAME>`. You can see this in the Docker step's command line: `-e "INPUT_ENTRYPOINT" -e "INPUT_ARGS"`. A missing optional input falls back to its `default` in `action.yml`; a missing `required: true` input is an error.

## 12. `action.yml` Versus `action.yaml` and Subpaths

> ⚠️ ADVANCED TOPIC: Skip on first read.

The metadata file can be named `action.yml` or `action.yaml`. An action in a subfolder is referenced as `owner/repo/subfolder@ref`; for a local action the path in `uses:` must point at the **folder** containing the metadata file, not the file itself.

## 13. Case Study: The Copy-Paste Pin

A tutorial from 2023 shows `actions/checkout@v3`. A team copies it into 40 repos. Three years on, every repo runs a version declaring a retired runtime. Nothing fails loudly until the runtime is finally removed. The fix is mechanical (bump the major in 40 files), but **finding** the 40 files is the cost. One query does it: `gh search code "actions/checkout@v3" --owner <org>`. Better: let a bot (Dependabot, Chapter 16) open the bump PRs.

## 14. Comparison: Reference Styles

| Style                     | Setup Effort            | Control                         | Failure Visibility          | Security Exposure            | Maintenance Burden      |
| ------------------------- | ----------------------- | ------------------------------- | --------------------------- | ---------------------------- | ----------------------- |
| Floating major (`@v7`)    | Minimal - copy one line | Weak - maintainer moves it      | Fair - log shows SHA        | Moderate - trusts maintainer | Low - fixes arrive free |
| Exact version (`@v7.0.1`) | Minimal - one line      | Moderate - fixed until you bump | Fair - tag could still move | Moderate - tag is mutable    | Moderate - manual bumps |
| Full SHA                  | Low - look up the SHA   | Excellent - immutable           | Strong - exact commit named | Low - cannot be swapped      | Moderate - needs a bot  |
| Branch (`@main`)          | Minimal - one line      | Weak - changes every push       | Weak - unpredictable        | High - any commit runs       | Low - but surprising    |

## 15. Practical Tips

- Prefer first-party actions; read the `action.yml` of anything else.
- Record the version in a trailing comment next to a SHA: `uses: owner/repo@<sha> # v7.0.1`.
- Run `gh run view <id> --log | grep "Download action repository"` to audit what actually ran.
- Check a Node action's runtime: `curl -s https://raw.githubusercontent.com/<owner>/<repo>/<ref>/action.yml | grep using`.
- Never use a branch as a reference in anything that touches secrets.
- Search your own repos for old majors on a schedule.

## 16. Demonstrated Failure Modes

**Failure 1: the tag that does not exist.** We referenced `astral-sh/setup-uv@v10` (the repo's latest release is `v10.2.0`). Real run **37312465693**:

| Step             | Result      |
| ---------------- | ----------- |
| 1 Set up job     | **failure** |
| every later step | never ran   |

```
##[error]Unable to resolve action `astral-sh/setup-uv@v10`, unable to find version `v10`
```

**Symptom:** the run dies in **Set up job**, before any of your steps, with `Unable to resolve action`. **Cause:** that repo has floating major tags such as `v5` and `v7` but no `v10` (we checked each with the API: `v10` returns 404). Writing the pattern you expect from other actions is not enough. **Fix:** use the exact tag `v10.2.0`, or its SHA; this repo's `ci.yml` now uses `astral-sh/setup-uv@v10.2.0`.

**Failure 2: the stale runtime (Section 8).** `checkout@v4` and `setup-python@v5` declare `node20`, which GitHub scheduled for removal on 2026-09-23. Symptom today: the workflow still passes (the runner substitutes its default Node), plus runtime deprecation noise in the log. Symptom eventually: a hard failure when substitution ends. **Fix:** bump to a version that declares `node24`.

## 17. Key Takeaways

- `owner/repo@ref` means: that repo, at that tag, branch or commit, run according to its `action.yml`.
- Only a full SHA is immutable; tags and branches can move.
- The runner resolves the reference every run and logs the SHA: `Download action repository '...' (SHA:...)`.
- Actions are JavaScript (`node24` today), composite, or Docker.
- A floating major tag may not exist; read the repo's tags before assuming.
- Runtimes expire: Node 20 was scheduled for removal on 2026-09-23.
- Post steps run in reverse order.

## 18. Exercises

1. In Section 6's log, why are there two `Download action repository` lines with the same SHA?
2. Using the Section 7 table, which tag would have silently changed behavior for a user pinned to `@v7` when `v7.0.1` shipped, and which would not have?
3. What does `uses: ./.github/actions/tally-greet` need to exist at that path?
4. You see `Unable to resolve action` in step 1. List two causes and how to check each.
5. (Hand check) `tally-greet` is called with `who: Tally`. What exact line does it write to `$GITHUB_OUTPUT`, and what does step 5 print?

<details>
<summary>Answers</summary>

1. Two steps referenced the same action, once by tag and once by SHA; the tag resolved to the same commit as the explicit SHA.
2. `@v7` changed (it moved from `v7.0.0`'s commit to `v7.0.1`'s); `@v7.0.0` (exact tag) did not.
3. A folder containing `action.yml` (or `action.yaml`), present in the repo at the run's commit, with the repo already checked out so the path exists.
4. (a) The tag/branch does not exist: list the repo's tags (`gh api repos/<o>/<r>/git/ref/tags/<tag>`). (b) The repo is private/missing: open it while logged out, or check the name.
5. `message=hello, Tally`; step 5 prints `composite said hello, Tally`.

</details>

## 19. Additional Resources

All verified 2026-10.

- GitHub Docs: Workflow syntax, `jobs.<job_id>.steps[*].uses` - https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax
- GitHub Docs: Metadata syntax for GitHub Actions (`action.yml`) - https://docs.github.com/en/actions/reference/workflows-and-actions/metadata-syntax
- GitHub changelog: Deprecation of Node 20 on GitHub Actions runners - https://github.blog/changelog/2025-09-19-deprecation-of-node-20-on-github-actions-runners/
- actions/checkout releases - https://github.com/actions/checkout/releases
- Live evidence: runs 37312325910 (five forms) and 37312465693 (unresolvable tag) in this repo
- Laster, _Learning GitHub Actions_ (O'Reilly), Chapter 3

## 20. Appendix A: Code Index

> 💻 Complete, runnable code for this chapter. Skip when reading for concepts.

### A.1 Audit which commit each action ran

```python
import re

LINE = re.compile(r"Download action repository '([^']+)' \(SHA:([0-9a-f]{40})\)")


def audit(log_lines: list[str]) -> dict[str, str]:
    """Map each ``owner/repo@ref`` reference to the commit SHA the runner used."""
    resolved = {}
    for line in log_lines:
        m = LINE.search(line)
        if m:
            resolved[m.group(1)] = m.group(2)
    return resolved
```

**Flow:** scan log lines -> regex-match the runner's download message -> record reference-to-SHA -> a tag and its SHA form should map to the same value.

### A.2 Classify a reference

```python
def classify(ref: str) -> str:
    """Return the form of a ``uses:`` reference: local, docker, sha, or tag/branch."""
    if ref.startswith("./"):
        return "local"
    if ref.startswith("docker://"):
        return "docker"
    _, _, version = ref.partition("@")
    if len(version) == 40 and all(c in "0123456789abcdef" for c in version):
        return "sha"
    return "tag-or-branch"
```
