# Chapter 19: Custom Actions: Composite, JavaScript, Docker

**Reading Time:** ~55 minutes
**Prerequisites:** Chapter 04 (`uses:`, `action.yml`), Chapter 07 (expressions), Chapter 09 (outputs), Chapter 12 (containers)
**Practice Notebook:** `notebooks/practice_19.ipynb`
**Reference Notebook:** `notebooks/lab_19_custom_actions.ipynb`
**Script:** `labs/lab_19_custom_actions.py`
**Book Reference:** Laster, Learning GitHub Actions Ch 11 / GitHub Docs: Metadata syntax for GitHub Actions
**Depth:** Core
**Default Runtime:** Live repo

---

## Beginner's Guide

**Focus on first:** Sections 3 (`action.yml`), 4 (a composite action, tested) and 6 (a JavaScript action, including the `post` step).

**Skip on first read:** Sections 10-12 (publishing, `pre`/`post` rules in depth, limits).

**Key concepts in plain English:**

- **Custom action:** a folder with an `action.yml` that other workflows can `uses:`. It packages steps so you write them once.
- **Composite action:** an action made of ordinary steps (the easiest kind).
- **JavaScript action:** an action whose code is a Node.js file the runner executes directly.
- **Docker action:** an action that runs inside a container image.
- **`pre` / `post`:** extra code that runs before and after the main step (cleanup, for example).

**If you have written a shell function you reuse everywhere**, a composite action is that function, with named inputs and outputs, callable from any repository.

> **🔬 Platform Engineer's Lens:** A custom action is shared infrastructure: every workflow that uses it inherits its bugs and its trust. So write it like a library: validate inputs, test it three ways, pin it by SHA when others consume it, and keep it small. In this chapter's run, the first bug we found was not in our code but in our tooling: `actionlint` passed an action that GitHub rejected.

> **🚦 Native vs Marketplace vs Custom:** This chapter *is* the custom path. Before you write an action, ask the three questions of Chapter 04: can a one-line `run:` do it; does a first-party action already; does a well-maintained third-party one. Write a composite action when you are copying the same three steps between workflows, and only reach for JavaScript or Docker when a shell script is not enough.

## What You'll Learn

- Write an `action.yml` with inputs, outputs and a runtime
- Build a composite action with a bundled script and call it locally and by path from another repository
- Build a dependency-free JavaScript action with `main` and `post` steps, and unit-test it
- Build Docker actions both ways (a Dockerfile and a prebuilt image) and compare their cost
- Explain exactly how inputs reach each kind of action (including hyphenated names)
- Choose between the three types
- Test an action at three layers and know what `actionlint` misses

## Table of Contents

<!-- TOC -->
- [1. Why Write an Action](#1-why-write-an-action)
- [2. Running Example: Five Actions](#2-running-example-five-actions)
- [3. Anatomy of `action.yml`](#3-anatomy-of-actionyml)
- [4. Composite Actions](#4-composite-actions)
- [5. Using an Action From Another Repository](#5-using-an-action-from-another-repository)
- [6. JavaScript Actions](#6-javascript-actions)
- [7. Docker Actions](#7-docker-actions)
- [8. Choosing a Type](#8-choosing-a-type)
- [9. Testing an Action at Three Layers](#9-testing-an-action-at-three-layers)
- [10. Publishing and Versioning](#10-publishing-and-versioning)
- [11. `pre`, `post` and Their Conditions](#11-pre-post-and-their-conditions)
- [12. Limits of Custom Actions](#12-limits-of-custom-actions)
- [13. Case Study: The Action That Followed `main`](#13-case-study-the-action-that-followed-main)
- [14. Comparison: Types of Custom Action](#14-comparison-types-of-custom-action)
- [15. Practical Tips](#15-practical-tips)
- [16. Demonstrated Failure Modes](#16-demonstrated-failure-modes)
- [17. Key Takeaways](#17-key-takeaways)
- [18. Exercises](#18-exercises)
- [19. Additional Resources](#19-additional-resources)
- [20. Appendix A: Code Index](#20-appendix-a-code-index)
   - [A.1 Run the composite script and compare with the SemVer parser](#a1-run-the-composite-script-and-compare-with-the-semver-parser)
<!-- /TOC -->

---

## 1. Why Write an Action

Chapter 04 used other people's actions. When you copy the same steps between workflows, you create a maintenance problem. An action solves it: one folder, one `action.yml`, versioned with the code it serves. Ours live in `.github/actions/` of this repository, which is the conventional place for actions private to a repo (anything referenced by a relative path, `./.github/actions/<name>`).

## 2. Running Example: Five Actions

> 📌 **Running Example: five custom actions and one workflow.** `tally-version` (composite, with a bundled shell script), `tally-js` (JavaScript, `main` and `post`), `tally-docker` (Docker, built from a Dockerfile), `tally-docker-prebuilt` (Docker, a prebuilt image) and `tally-noshell` (a composite action that is **invalid on purpose**). `ch19-custom-actions.yml` runs the first four (run **37332265631**); `ch19-bad-action.yml` runs the fifth (run **37332464081**). The actions were published at commit **`c41ee3a9fba818d86e0faeae6631bc1c08f5fcf5`**. The code has **15 Python tests** and a **Node test suite**. Data: `fixtures/actions_ch19_summary.json`, `fixtures/actions_ch19_run.json`. We return to them throughout.

## 3. Anatomy of `action.yml`

```yaml
name: Tally version
description: Validate a semantic version and split it into parts.
inputs:
  version:
    description: Version without a leading v
    required: true
outputs:
  major:
    description: Major number
    value: ${{ steps.parse.outputs.major }}     # composite only
runs:
  using: composite          # or node24, or docker
  steps: [...]
```

| Key | Rule (docs, verified 2026-10) |
| --- | --- |
| `name`, `description` | required |
| `inputs.<id>` | `description` required; `required`, `default` optional |
| `outputs.<id>` | `description` required; composite outputs also need `value` mapping to a step output |
| `runs.using` | `composite`, `docker`, `node20` or `node24` |
| `branding` | optional Marketplace icon and colour |

Outputs are **strings**, as everywhere (Chapter 09). The docs state a maximum of 1 MB of outputs per job and 50 MB per workflow run (our Chapter 09 measurement of the per-job limit: about 524,288 ASCII characters).

## 4. Composite Actions

A composite action is a list of steps. `tally-version` validates a version and splits it, and keeps its logic in a **bundled script**, called through `${{ github.action_path }}`, the path to the action's own folder:

```yaml
runs:
  using: composite
  steps:
    - id: parse
      shell: bash
      env:
        VERSION: ${{ inputs.version }}
      run: ${{ github.action_path }}/parse.sh
```

Three rules to notice:

1. **`shell` is required** on every `run:` step (docs). Section 9 shows what happens without it.
2. Inputs are read from the **`inputs` context**, not from environment variables, in a composite action (docs). We pass the version through `env:` into the script, the injection-safe pattern from Chapter 16.
3. A step can `uses:` other actions, so composites can compose.

Real run, `ch19-custom-actions.yml` job `composite`:

| Call | Input | Result |
| --- | --- | --- |
| first | `1.2.3-rc.1` | `normalized=1.2.3-rc.1`, `major.minor.patch=1.2.3`, `is-prerelease=true` |
| second (`continue-on-error`) | `1.2` | outcome **`failure`**; outputs empty (`bad_normalized=[]`) |

The failure's annotation: title **`Not a semantic version`**, message `'1.2' is not MAJOR.MINOR.PATCH`. That is the script's own `::error` (Chapter 17), so the failure explains itself.

**The script is tested without GitHub.** `tests/test_actions_metadata.py` runs `parse.sh` under bash with `VERSION` and a temporary `GITHUB_OUTPUT` file, and checks it against our Python SemVer parser (Chapter 14) on valid (`0.1.0`, `1.2.3-rc.1`, `10.20.30`, `2.0.0-beta`) and invalid (`1.2`, `v1.2.3`, `01.2.3`, `1.2.3.4`, empty) inputs. The shell regex and the Python parser **agree on all nine**.

> 📝 **Full implementation:** See [Appendix A.1](#a1-run-the-composite-script-and-compare-with-the-semver-parser)

## 5. Using an Action From Another Repository

Local actions are referenced with `./path`. Another repository references yours as `owner/repo/path/to/action@ref`. We tested it in the same repository without a checkout, the way a different repo would:

```yaml
- uses: Friend09/practice_git_intro_to_github_actions/.github/actions/tally-version@c41ee3a9fba818d86e0faeae6631bc1c08f5fcf5
  with:
    version: 3.4.5
```

The job `remote_reference` had **no checkout step**, yet the log showed the runner fetching the repo at that commit:

```
Download action repository 'Friend09/practice_git_intro_to_github_actions@c41ee3a9...' (SHA:c41ee3a9...)
```

and the action ran, returning `remote_ref_parts=3.4.5`. The bundled `parse.sh` worked because `${{ github.action_path }}` points inside the downloaded copy.

**What to notice:**

- A **subpath** reference (`owner/repo/path@ref`) lets one repository host many actions; the ref can be a tag, branch or SHA (Chapter 04). For a repo that other teams consume, tag releases (`v1`, `v1.2.0`) and tell consumers to **pin by SHA** (Chapter 16).
- The whole repository is downloaded, not just the folder. Keep action repos small, or put actions in a dedicated repository.

## 6. JavaScript Actions

A JavaScript action is a Node.js file the runner runs directly, with no container to build or pull (we did not time its startup separately). `tally-js` declares:

```yaml
runs:
  using: node24
  main: main.js
  post: post.js
```

**Dependency-free on purpose.** The official toolkit package `@actions/core` (version 3.0.1 on npm today) wraps the plumbing, but using it means committing `node_modules` or bundling with a tool like `ncc`. Our action uses only Node built-ins: it reads `INPUT_*` variables and appends to the files named by `GITHUB_OUTPUT` and `GITHUB_STATE`. That is about 20 lines and nothing to audit or update. Reach for the toolkit when you need its extras (annotations helpers, caching, the REST client).

Real run, job `javascript`, with `who-to-greet: Tally` and `shout: 'true'`:

| Observation | Value |
| --- | --- |
| Greeting output | `HELLO, TALLY` |
| Node version on the runner | **`v24.19.0`** |
| `INPUT_` variables the runner provided | **`INPUT_SHOUT,INPUT_WHO-TO-GREET`** |
| `post` step ran | **yes**, and read the `started` value saved by `main` (`state_started_present=yes`) |

**What to notice:**

- **Hyphens are kept.** The input `who-to-greet` became the variable `INPUT_WHO-TO-GREET`: uppercase, hyphen intact (docs: "converts input names to uppercase letters and replaces spaces with `_`"). A hyphenated name is not a valid shell identifier, so in JavaScript you read it as `process.env['INPUT_WHO-TO-GREET']`, and a shell script cannot reference it directly. If shell scripts will consume your inputs, choose names with underscores.
- **Defaults appear as inputs too.** `shout` was passed, but an input with a `default` is always present.
- **State passes from `main` to `post`** through the `GITHUB_STATE` file (variables named `STATE_<name>`), which is how a post step knows what to clean up.

**`post` runs even when the job fails.** Job `javascript_post_after_failure` ran the action and then a step that does `exit 1`:

| Step | Conclusion |
| --- | --- |
| Run `./.github/actions/tally-js` | success |
| Fail on purpose after the action ran | **failure** |
| **Post Run `./.github/actions/tally-js`** | **success** (and printed `js_post_ran=yes`) |

Docs (verified 2026-10): `post` and `pre` default to `always()`. That is why cleanup in a `post` step is reliable, and why it should be written to tolerate a half-finished job.

**Unit tests.** The pure functions (`greet`, `getInput`) are exported and tested with Node's built-in runner (`node --test`): 2 tests, both pass, and the workflow runs them too.

## 7. Docker Actions

A container action runs in an image. Two ways, both measured (run 37332265631):

| Action | `runs.image` | What happens each run | Step time |
| --- | --- | --- | --- |
| `tally-docker` | `Dockerfile` | the runner **builds the image from the Dockerfile** | **8 s** |
| `tally-docker-prebuilt` | `docker://alpine:3.20` | the runner **pulls** a prebuilt public image | **2 s** |

The built action's entrypoint reported `os=alpine uid=0` (it ran as root inside an Alpine container, which is *not* the runner's Ubuntu) and wrote `result=ok` to `GITHUB_OUTPUT`.

**What to notice:**

- **Building from a Dockerfile is paid on every run.** 8 seconds against 2: a quarter of the time is the build. If the action is used often, **publish the image** to a registry (Chapter 12) and reference it with `image: docker://ghcr.io/OWNER/NAME@sha256:...` (a digest, Chapter 12).
- Container actions have an image to build or pull on every run (8 s and 2 s here). Use them when you need a specific OS, language runtime or tool that the runner lacks, and remember they run only on Linux runners.
- **Tool quirk:** `actionlint` reported `/bin/echo does not exist` for an `entrypoint:` on a `docker://` image, as though it were a file in the action folder. It is a false positive for this form (the path is inside the container), so we passed the command as `args` instead (with no ENTRYPOINT in the image, args become the container's command).

## 8. Choosing a Type

| Need | Choose | Why |
| --- | --- | --- |
| Reuse a few steps, mostly shell and other actions | **Composite** | no build, no runtime choice, easiest to write and read |
| Logic that is awkward in shell; fast startup; use the toolkit | **JavaScript** | runs directly on the runner's Node |
| A specific OS, language or system tool | **Docker** | the image is the environment |
| Must also run on Windows or macOS runners | Composite or JavaScript | they run directly on the runner |

Docs (verified 2026-10): **Docker container actions can only execute on runners with a Linux operating system** (self-hosted ones also need Docker installed), whereas JavaScript actions work on all GitHub-hosted runner platforms and composite actions on Linux, macOS and Windows. Our runs used Linux only.

## 9. Testing an Action at Three Layers

| Layer | What it catches | Our tool |
| --- | --- | --- |
| **Unit tests** | the logic, without GitHub | `node --test`, and bash + Python for `parse.sh` |
| **Metadata tests** | a malformed `action.yml` | `tests/test_actions_metadata.py` (checks each action against the docs' rules) |
| **Workflow tests** | the action inside the real runner | `ch19-custom-actions.yml` |

The third layer found the one thing the others missed. We wrote a composite action whose `run:` step has **no `shell`** (`tally-noshell`) and tried each layer:

| Tool | Result on `tally-noshell` |
| --- | --- |
| `actionlint` | **passed** (exit 0, no message) |
| Our metadata test | **fails** (it asserts every composite `run:` step has `shell`), so the action is exempted by name |
| GitHub (run 37332464081) | the job's step **fails** with: `Failed to load .../tally-noshell/action.yml` ... `TemplateValidationException: The template is not valid. ... (Line: 6, Col: 7): Required property is missing: shell` |

**What to notice:** the failure is at the **step** that uses the action, not at "Set up job", so the earlier steps (checkout) had already run. And **`actionlint` is not a complete validator of action metadata**: it did catch two other mistakes (below), but not this one. Two more scratch tests:

| Mistake | `actionlint` said |
| --- | --- |
| `runs.main: does-not-exist.js` | `file "does-not-exist.js" does not exist in ... it is specified at "main" key in "runs" section` |
| `runs.using: node12` | `invalid runner name "node12" ... valid runners are "composite", "docker", "node20", and "node24"` |

(`actionlint` found these only when the checked project had a `.git` root; in a bare folder it reported nothing.) The lesson: validate action metadata yourself, as we do, and run the action for real.

## 10. Publishing and Versioning

> ⚠️ ADVANCED TOPIC: Skip on first read.

To share an action beyond one repository: put it at the repository root (or in a subfolder), push it, and **tag releases**. Convention is an exact tag (`v1.2.0`) and a floating major tag (`v1`) that you move forward, and a `README` with inputs and outputs. To list it on the Marketplace, add `branding` and publish a release from the repository settings. We did not publish to the Marketplace (it needs a dedicated public repository); the path reference of Section 5 is the mechanism consumers use either way. Chapter 04's cautions apply to *your* consumers: a floating tag of yours is a trust you ask them to extend, so document the SHA.

## 11. `pre`, `post` and Their Conditions

> ⚠️ ADVANCED TOPIC: Skip on first read.

`pre` runs at job start before any step; `main` at its place in the job; `post` at job end in **reverse order** of the actions (Chapter 04 saw this). `pre-if` and `post-if` default to `always()` (docs); a `post-if: success()` would skip cleanup on failure, which is rarely what you want. Docker actions have the equivalents `pre-entrypoint` and `post-entrypoint`.

## 12. Limits of Custom Actions

> ⚠️ ADVANCED TOPIC: Skip on first read.

An action sees what the caller gives it: inputs, the standard contexts and the job's environment; a secret reaches it only if the workflow passes it (as an input or `env:`). We did not test that boundary directly. It shares the job's runner, token permissions (Chapter 15) and filesystem, so an action you call can read the workspace and use the token: another reason to pin and to grant least privilege. An action cannot add jobs or change the workflow's triggers; for that, use a reusable workflow (Chapter 20).

## 13. Case Study: The Action That Followed `main`

A platform team publishes `acme/setup-tools` and tells everyone to use `@main` "so you always get fixes". A refactor to `main` renames an input. Forty repositories fail on the next push, with `Unexpected input(s)` warnings that look like typos. The fix has two halves: the action author tags releases and never breaks a major version's inputs; the consumers pin a SHA and let Dependabot (Chapter 16) propose bumps. (This scenario is constructed to apply Sections 5 and 10; we did not reproduce it.)

## 14. Comparison: Types of Custom Action

| Type | Setup Effort | Control | Failure Visibility | Security Exposure | Maintenance Burden |
| --- | --- | --- | --- | --- | --- |
| Composite | Minimal - YAML and a script | Moderate - steps only | Strong - each step visible in the log | Low - runs on the runner | Low |
| JavaScript (no dependencies) | Low - a few files | Strong - full language | Strong - own annotations | Low - nothing bundled | Low |
| JavaScript (with toolkit) | Moderate - bundling | Strong | Strong | Moderate - dependency tree | Moderate - rebuild bundle |
| Docker (Dockerfile) | Moderate - image to build | Excellent - own OS | Fair - build and run logs | Moderate - base image | Moderate - rebuilt every run |
| Docker (prebuilt image) | High - publish and pin an image | Excellent | Fair | Moderate - pin by digest | Moderate |

## 15. Practical Tips

- Start with a composite action; move to JavaScript or Docker only when you must.
- Put logic in a **script file** inside the action and unit-test that script.
- Pass inputs to scripts through `env:`, never inline into `run:` (Chapter 16).
- Name inputs with underscores if shell scripts will read them; hyphens are legal but awkward.
- Test at three layers: unit, metadata, and a real workflow run.
- Pin your own consumers by SHA and tag your releases.
- Publish Docker actions as prebuilt images referenced by digest.
- Do not trust `actionlint` alone to validate `action.yml`.

## 16. Demonstrated Failure Modes

**Failure 1: the invalid input.** `tally-version` with `1.2` exited non-zero with the annotation `Not a semantic version`; outputs were empty. Fix: callers should check `steps.<id>.outcome`.

**Failure 2: the missing `shell`.** `Required property is missing: shell` at the step; `actionlint` silent. Fix: our metadata test and a real run.

**Failure 3: the missing `main` and the old runtime.** Caught by `actionlint` only inside a project root.

**Failure 4: the hyphenated input.** `INPUT_WHO-TO-GREET` is unusable as a shell variable. Fix: underscore names, or read it in JavaScript.

**Failure 5: the per-run build.** 8 seconds against 2: a Dockerfile action rebuilds every run.

**Failure 6: the tool false positive.** `actionlint` flagged `/bin/echo` for a `docker://` entrypoint. Fix: `args`.

## 17. Key Takeaways

- An action is a folder with `action.yml`; reference it as `./path` locally or `owner/repo/path@ref` remotely.
- Composite: steps (each `run` needs `shell`), bundled scripts via `github.action_path`, composite outputs need `value`.
- JavaScript on `node24` (ours ran `v24.19.0`); inputs arrive as `INPUT_<UPPERCASED>` with hyphens kept; `post` runs even after a failure.
- A Dockerfile action rebuilds on every run (8 s vs 2 s prebuilt).
- Unit-test the logic, metadata-test the YAML, workflow-test the integration.
- `actionlint` missed a missing `shell`; GitHub rejected it at the step.
- Consumers should pin your action by SHA; you should tag releases.

## 18. Exercises

1. A composite step has `run: ./script.sh` but no `shell`. What happens, and which of `actionlint`, our metadata test and GitHub catch it?
2. An input is named `max-retries`. In JavaScript, how do you read it? In a bash `run:` inside a *JavaScript* action's job, can you write `$INPUT_MAX-RETRIES`?
3. A job runs `tally-js`, then a step that fails. Does the `post` step run? What setting controls it, and what is its default?
4. Your Docker action's Dockerfile build takes 40 s and the action is used 200 times a day. How much build time per day, and how do you remove it?
5. (Hand arithmetic) The shell script's regex accepted 4 of 4 valid and rejected 5 of 5 invalid versions, matching the Python parser. If you add 3 more valid and 2 more invalid cases, how many cases must agree in total?

<details>
<summary>Answers</summary>

1. GitHub fails the step with `Required property is missing: shell`. Our metadata test catches it. `actionlint` did **not** in our test.
2. JavaScript: `process.env['INPUT_MAX-RETRIES']`. No: `$INPUT_MAX-RETRIES` is not valid shell (a hyphen ends the name); use an underscore name or `printenv 'INPUT_MAX-RETRIES'`.
3. Yes. `post-if` controls it; the default is `always()`.
4. 40 x 200 = 8,000 seconds (about 2.2 hours) a day. Publish the image to a registry and use `image: docker://ghcr.io/OWNER/NAME@sha256:...`.
5. (4 + 3) valid + (5 + 2) invalid = **14** cases.

</details>

## 19. Additional Resources

All verified 2026-10.

- GitHub Docs: Metadata syntax for GitHub Actions - https://docs.github.com/en/actions/reference/workflows-and-actions/metadata-syntax
- GitHub Docs: About custom actions (runner support per type) - https://docs.github.com/en/actions/concepts/workflows-and-actions/custom-actions
- GitHub Actions Toolkit (`@actions/core`) - https://github.com/actions/toolkit
- Node.js test runner (`node --test`) - https://nodejs.org/api/test.html
- actionlint - https://github.com/rhysd/actionlint
- Live evidence: runs 37332265631 and 37332464081; actions at commit `c41ee3a9fba818d86e0faeae6631bc1c08f5fcf5`
- Laster, *Learning GitHub Actions* (O'Reilly), Chapter 11

## 20. Appendix A: Code Index

> 💻 Complete, runnable code for this chapter. Skip when reading for concepts.

### A.1 Run the composite script and compare with the SemVer parser

```python
import subprocess
import tempfile
from pathlib import Path

from intro_gha import REPO_ROOT
from intro_gha.semver import parse

SCRIPT = REPO_ROOT / ".github" / "actions" / "tally-version" / "parse.sh"


def run(version: str) -> tuple[int, dict[str, str]]:
    """Run parse.sh with VERSION set and a temp GITHUB_OUTPUT; return (code, outputs)."""
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "out.txt"
        out.write_text("")
        res = subprocess.run(["bash", str(SCRIPT)], capture_output=True, text=True,
                             env={"VERSION": version, "GITHUB_OUTPUT": str(out),
                                  "PATH": "/usr/bin:/bin"})
        pairs = [ln.split("=", 1) for ln in out.read_text().splitlines() if "=" in ln]
        return res.returncode, dict(pairs)


code, outputs = run("1.2.3-rc.1")
assert code == 0 and outputs["is_prerelease"] == "true" and outputs["major"] == "1"
assert run("1.2")[0] != 0 and run("1.2")[1] == {}
assert parse("1.2.3-rc.1").pre == "rc.1"
```

**Flow:** run the script as the runner would (a `VERSION` variable and an output file); read the `name=value` lines back; compare with the Python parser on the same input.
