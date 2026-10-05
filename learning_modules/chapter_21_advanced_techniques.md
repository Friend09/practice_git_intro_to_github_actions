# Chapter 21: Advanced Techniques: Dynamic Matrices, github-script, ChatOps

**Reading Time:** ~55 minutes
**Prerequisites:** Chapter 06 (events, the token rule), Chapter 07 (expressions), Chapter 10 (matrix), Chapter 15 (permissions), Chapter 16 (injection, pinning)
**Practice Notebook:** `notebooks/practice_21.ipynb`
**Reference Notebook:** `notebooks/lab_21_advanced_techniques.ipynb`
**Script:** `labs/lab_21_advanced_techniques.py`
**Book Reference:** Laster, Learning GitHub Actions Ch 13 / GitHub Docs: Running variations of jobs, github-script
**Depth:** Optional Deep-Dive
**Default Runtime:** Live repo

---

## Beginner's Guide

> ⭐ **Optional deep-dive.** Everything you need for a working pipeline was in Chapters 00-20. This chapter adds three techniques that make workflows *adaptive*. Skip it on a first pass and return when you need one.

**Focus on first:** Section 3 (a matrix computed at run time and what happens when the computation is wrong) and Section 5 (a bot that takes commands in comments).

**Skip on first read:** Sections 7-9.

**Key concepts in plain English:**

- **Dynamic matrix:** a matrix whose list of legs is **computed by an earlier job** instead of written in the YAML.
- **`github-script`:** a first-party action that runs a few lines of JavaScript with a ready-made GitHub API client, so you can call the API without writing `curl`.
- **ChatOps:** controlling automation by typing commands in comments (`/tally ping`).
- **Idempotent bot:** one that updates its own comment instead of posting a new one each time.

**If you have scripted the GitHub API with `curl` and `jq`**, `github-script` is that with the authentication, pagination and JSON handling done for you.

> **🔬 Platform Engineer's Lens:** Each technique trades a static, reviewable file for behavior decided at run time, and each failed in a way that was quiet: a malformed matrix produced a **green run that did nothing**, a script output vanished because it shared a name with the action's own, and every comment in the repository started a workflow run. The cost of cleverness is detection. For each, this chapter shows the quiet failure and the loud check that catches it.

> **🚦 Native vs Marketplace vs Custom:** All three are native building blocks (`fromJSON`, `issue_comment`, the REST API), and `actions/github-script` is the first-party glue. Reach for them when a plain static workflow cannot express the logic, and prefer a **small, tested script in the repo** to a long inline `script:` block.

## What You'll Learn

- Compute a matrix in one job and consume it with `fromJSON`
- Predict what happens with an empty or malformed matrix, with and without a guard
- Use `github-script` to read and write the GitHub API, and update a comment idempotently
- Avoid the `result` output collision and the `script:` injection sink
- Build a ChatOps command handler with an authorization check
- Explain why a bot's own comments do not retrigger the workflow
- Count what ChatOps costs in runs

## Table of Contents

<!-- TOC -->
- [1. Why Adaptive Workflows](#1-why-adaptive-workflows)
- [2. Running Example: Three Small Workflows](#2-running-example-three-small-workflows)
- [3. Dynamic Matrices](#3-dynamic-matrices)
- [4. `github-script`](#4-github-script)
- [5. ChatOps: Commands in Comments](#5-chatops-commands-in-comments)
- [6. Reacting and Replying Safely](#6-reacting-and-replying-safely)
- [7. Choosing Inputs: `choice`, `boolean`, `string`](#7-choosing-inputs-choice-boolean-string)
- [8. Matrices from Changed Files](#8-matrices-from-changed-files)
- [9. Cost Notes](#9-cost-notes)
- [10. Testing a Plan Locally](#10-testing-a-plan-locally)
- [11. Observability](#11-observability)
- [12. Limits](#12-limits)
- [13. Case Study: The Green Run That Tested Nothing](#13-case-study-the-green-run-that-tested-nothing)
- [14. Comparison: Adaptive Techniques](#14-comparison-adaptive-techniques)
- [15. Practical Tips](#15-practical-tips)
- [16. Demonstrated Failure Modes](#16-demonstrated-failure-modes)
- [17. Key Takeaways](#17-key-takeaways)
- [18. Exercises](#18-exercises)
- [19. Additional Resources](#19-additional-resources)
- [20. Appendix A: Code Index](#20-appendix-a-code-index)
   - [A.1 Validate a plan and model the guard](#a1-validate-a-plan-and-model-the-guard)
   - [A.2 Authorize and parse a ChatOps command](#a2-authorize-and-parse-a-chatops-command)
<!-- /TOC -->

---

## 1. Why Adaptive Workflows

A static matrix lists its legs in YAML. Sometimes the right list depends on **what changed** or **what exists**: test only the packages touched by a pull request, build only the images whose Dockerfile moved. And sometimes the automation should respond to **people**, not events: re-run a job, label a pull request, answer a question. These three techniques are how.

## 2. Running Example: Three Small Workflows

> 📌 **Running Example: three workflows.** `ch21-dynamic-matrix.yml`: a **plan** job reads `sandbox/ch21/targets.json` (three entries: `alpha`/3.11, `beta`/3.12, `gamma`/3.13) and emits a matrix; a **run** job fans out over it. A `choice` input `mode` makes the plan emit a `valid`, `invalid` (not JSON) or `empty` matrix. `ch21-github-script.yml`: on `pull_request`, posts (or updates) **one** comment listing the PR's changed files. `ch21-chatops.yml`: on `issue_comment`, runs `/tally ping` and `/tally echo <text>`. Real runs are cited in each section. Data: `fixtures/advanced_ch21_summary.json`. We return to them throughout.

## 3. Dynamic Matrices

The pattern (docs, verified 2026-10): one job writes JSON to `$GITHUB_OUTPUT`; the next job's `strategy.matrix` is `${{ fromJSON(needs.<job>.outputs.<name>) }}`.

```yaml
plan:
  outputs: { matrix: "${{ steps.m.outputs.matrix }}" }
  steps:
    - id: m
      run: echo "matrix=$(jq -c '{include: .}' sandbox/ch21/targets.json)" >> "$GITHUB_OUTPUT"
run:
  needs: [plan]
  strategy:
    matrix: ${{ fromJSON(needs.plan.outputs.matrix) }}
```

**The valid case** (run 37333637267). The plan printed `{"include":[{"name":"alpha","python":"3.11"},{"name":"beta","python":"3.12"},{"name":"gamma","python":"3.13"}]}` and three legs ran, named by their values in key order: **`run (alpha, 3.11)`**, `run (beta, 3.12)`, `run (gamma, 3.13)`. (An `include` list needs no axes: each object is one leg, as in Chapter 10.)

**The two bad cases**, and the docs' silence on both ("does not specify error handling for invalid JSON"):

| Plan emitted | Run | Jobs that appeared | Message |
| --- | --- | --- | --- |
| invalid JSON (`this is not json`) | **failure** (37333707626) | `plan` only | none via `gh` or the API |
| empty matrix (`{"include":[]}`) | **failure** (37333767896) | `plan` only | none via `gh` or the API |

In both cases the `run` job **never appears**: the error is raised when GitHub expands the matrix, before any job exists, so there is nothing to attach a log to. (The explanation is only on the run page; we could not retrieve it from the CLI or API, the same limit as Chapters 05, 16 and 20.)

**The tempting fix, and its trap.** Guard the job with the plan's count:

```yaml
run:
  needs: [plan]
  if: ${{ fromJSON(needs.plan.outputs.count) > 0 }}
```

The plan computed `count` with `jq`. For a malformed matrix `jq` fails to parse the document, so `count` is **empty** (not `-1`; see Section 10). Results with the guard:

| Plan emitted | Run job | Run conclusion |
| --- | --- | --- |
| valid | 3 legs ran | success (37335428986) |
| empty | **skipped** | success (37335372099) |
| invalid | **skipped** | **success** (37335483478) |

**What to notice:** the empty case is now handled cleanly. But the **invalid** case is now **green**. A false `if:` means the matrix expression is never evaluated, so the malformed JSON that used to fail the run now produces a skipped job and a successful run. **A guard converted a loud error into a silent no-op.** A broken planner would now go unnoticed until someone asks why nothing was tested.

**The right fix is to fail in the plan job**, where you control the message: validate with `jq -e` and `exit 1` on anything that is not a non-empty `include` array, and let the empty case be an explicit, logged decision. Treat the plan as an interface with a contract.

> 📝 **Full implementation:** See [Appendix A.1](#a1-validate-a-plan-and-model-the-guard)

## 4. `github-script`

`actions/github-script` (v9.0.0, `node24`, pinned `3a2844b7e9c422d3c10d287c895573f7108da1b3`) runs your JavaScript with `github` (an authenticated REST client), `context` (the event) and `core` (inputs, outputs, annotations) in scope. Our PR bot:

```yaml
- uses: actions/github-script@3a2844b7... # v9.0.0
  env:
    PR_TITLE: ${{ github.event.pull_request.title }}
  with:
    script: |
      const marker = '<!-- ch21-tally-bot -->';
      const files = await github.paginate(github.rest.pulls.listFiles, {...});
      const comments = await github.paginate(github.rest.issues.listComments, {...});
      const mine = comments.find((c) => c.body.includes(marker));
      if (mine) await github.rest.issues.updateComment({..., comment_id: mine.id, body});
      else     await github.rest.issues.createComment({..., body});
```

Needs `permissions: pull-requests: write` and `issues: write` (a PR comment is an issue comment); Chapter 15's `X-Accepted-GitHub-Permissions` is how you find that out.

**Idempotent by design.** We opened a throwaway PR (#6) and watched:

| Event | Run | Output | Comment |
| --- | --- | --- | --- |
| PR opened with 1 file | 37334461487 | `action=created files=1` | one comment: `this PR changes 1 file(s): sandbox/ch21/note.txt` |
| second commit pushed (`synchronize`) | 37334803026 | **`action=updated files=2`** | **still one comment**, now `2 file(s): note.txt, note2.txt` |

The hidden **marker** (`<!-- ch21-tally-bot -->`) is how the bot recognizes its own comment. Without it, every push would add another comment.

**Injection-safe.** The PR's title was `Demo: "quotes" and $(id -un) in a title`. The bot printed it **literally**:

```
Title (read from env, not interpolated): Demo: "quotes" and $(id -un) in a title
```

because the script reads `process.env.PR_TITLE` instead of writing `${{ github.event.pull_request.title }}` inside the script text. **The `script:` input is as dangerous a sink as `run:`**: the expression is substituted into the JavaScript source before it runs (Chapter 16). Our injection checker (`intro_gha/injection.py`) now scans `actions/github-script`'s `script` input as well as `run:`, and a test fails if either interpolates an untrusted context.

**Node runtime.** The script reported `node=v24.19.0`, the same Node 24 as Chapter 19's JavaScript action.

### The built-in output called `result`

The ChatOps handler first set `core.setOutput('result', 'ping')` and a later step read `steps.cmd.outputs.result`. It was **empty**, while a differently named output (`assoc`) arrived fine (runs 37334895791, 37334907699, 37334914023: `result= assoc=OWNER`). The cause is in the action's own metadata:

```
outputs:
  result:
    description: The return value of the script, stringified with `JSON.stringify`
```

`github-script` always sets its **own** output `result` (the script's return value, empty for a script that returns nothing) **after** your code, overwriting yours. Renaming ours to `outcome` fixed it: run 37335212282 reported `outcome=ping assoc=OWNER`. A test now fails any workflow whose `github-script` calls `setOutput('result', ...)`.

## 5. ChatOps: Commands in Comments

The `issue_comment` event fires for **every** comment on every issue **and pull request**. Our handler filters inside the job:

```yaml
on:
  issue_comment:
    types: [created]
jobs:
  command:
    if: ${{ startsWith(github.event.comment.body, '/tally') }}
```

and, inside a `github-script` step: **react** with 👀 so the user knows it was seen, **check authorization**, parse `/tally <sub> [args]`, and **reply**. The comment body, author and association all arrive through `env:` (untrusted text, Chapter 16).

We opened a throwaway issue (#7) and posted four comments:

| Comment | Run | Job | Bot reply | Reaction |
| --- | --- | --- | --- | --- |
| `/tally ping` | 37334895791 | success | `pong` | 👀 |
| `/tally echo hello    from   chatops` | 37334907699 | success | `hello from chatops` | 👀 |
| `/tally nonsense` | 37334914023 | success | `Commands: /tally ping, /tally echo <text>` | 👀 |
| `just a normal comment, no command` | 37334926790 | **skipped** | none | none |

(A fifth run, 37334883686, was **skipped** too: it was my own `gh pr close --comment ...` text on PR #6, a PR comment, which is also an `issue_comment`.)

**What to notice:**

- **Every comment makes a run.** Five runs for five comments, two of them skipped because the job-level `if` was false. A job-level filter cannot stop the *run* being created, so a busy repository fills its Actions list with skipped runs (they are not billed: no runner), and there is no trigger-level filter for comment text.
- **The bot's three replies started zero runs.** They were created with `GITHUB_TOKEN`, and events from that token start no workflow (Chapter 06). That is what prevents an infinite loop of the bot answering itself.
- **Whitespace was collapsed**: `hello    from   chatops` became `hello from chatops` (the handler splits on whitespace). Parse commands deliberately.
- **Authorization uses `author_association`.** My comments carried `OWNER`; the bot's replies carried **`NONE`**. The handler allows only `OWNER`, `MEMBER` and `COLLABORATOR`. We had one account, so the **denial path was not exercised live**; the lab models it. Without this check, **anyone who can comment** could run a command, and in a public repository that is everyone.

> 📝 **Full implementation:** See [Appendix A.2](#a2-authorize-and-parse-a-chatops-command)

## 6. Reacting and Replying Safely

ChatOps handlers read **untrusted text** from the comment, so the rules of Chapter 16 apply in full: pass the body through `env:`, never interpolate it into `script:` or `run:`; keep the command set tiny and fixed (a `switch`, not `eval`); do the privileged work in the handler, not in whatever the comment said. If a command must act on **pull-request code**, do not check it out under `issue_comment` with write permissions (Chapter 16's `pull_request_target` lesson applies equally): operate on the PR's metadata through the API instead.

## 7. Choosing Inputs: `choice`, `boolean`, `string`

> ⚠️ ADVANCED TOPIC: Skip on first read.

The dynamic-matrix workflow's `mode` input has type `choice` with `options: [valid, invalid, empty]`, which renders as a dropdown and restricts the value, a cheap way to keep a manual trigger from receiving free text. Use `choice` for fixed sets, `boolean` for switches, and `environment` for choosing a deployment target.

## 8. Matrices from Changed Files

> ⚠️ ADVANCED TOPIC: Skip on first read.

Our plan read a file; the common production plan reads **what changed** (`git diff --name-only <base>...HEAD`), maps paths to packages, and emits only those legs. Two cautions from Chapter 06: a `paths` filter is not applied to tag pushes, and for pull requests the diff base is the merge base, so compute it from `github.event.pull_request.base.sha`. Always emit a **non-empty** matrix or an explicit skip, never an accidental empty one (Section 3).

## 9. Cost Notes

> ⚠️ ADVANCED TOPIC: Skip on first read.

A dynamic matrix of N legs is N jobs, each rounding up to a minute (Chapter 18); the plan job is one more. For tiny legs, three legs cost 4 billed minutes against 1 for a single job doing the same work in sequence. Use a dynamic matrix when legs are slow and independent, and a loop in one job when they are seconds long.

## 10. Testing a Plan Locally

The plan is shell and `jq`, so test it before it runs on a runner. With the plan's output in `$MATRIX`:

```bash
echo "$MATRIX" | jq -e '.include | length'      # valid plan: prints 3
echo 'this is not json' | jq -e '.include | length'   # jq parse error, prints nothing
```

**What to notice:** a malformed document does not produce a number at all. `jq 'try ... catch -1'` cannot rescue it, because the parse error happens before the filter runs. We first assumed the plan's `count` would be `-1` for an invalid matrix; the run showed it was **empty**. Validate with `jq -e` and check the exit status instead of relying on a sentinel value.

## 11. Observability

- A matrix that fails to expand leaves **no job to read a log from**: the run fails with only the plan job present and no message in the API.
- A guarded job that is skipped shows as `skipped` in the jobs list and the run is green, so a dashboard of conclusions will not flag it.
- Each leg is named from its values, for example `run (alpha, 3.11)`.
- ChatOps starts **one workflow run per comment** (5 comments gave 5 runs, 2 of which skipped their job). The bot's own replies started 0 runs, because events created with `GITHUB_TOKEN` start no runs.

## 12. Limits

A matrix is capped at 256 jobs and a job output at about 1 MB (Chapter 18 measured about 524,288 ASCII characters). A plan that emits a large changed-files matrix can hit either. Cap the plan's output and fail loudly when it is exceeded.

## 13. Case Study: The Green Run That Tested Nothing

A monorepo's CI plan job computes which packages changed and emits them. A refactor of the plan script introduces a typo, and it emits `{"include": }`. The matrix job, guarded with `if: needs.plan.outputs.count > 0`, is skipped, the run is green, and branch protection passes. For two weeks no package is tested before merging. The fix is not a better guard but a **loud plan**: it validates its own output and fails with a message, and a final required job asserts that, for a non-docs change, at least one test leg ran. (This scenario is constructed from the silent-skip behavior we observed in Section 3.)

## 14. Comparison: Adaptive Techniques

| Technique | Setup Effort | Control | Failure Visibility | Security Exposure | Maintenance Burden |
| --- | --- | --- | --- | --- | --- |
| Static matrix | Minimal | Moderate - fixed legs | Excellent - every leg named in the file | Low | Low |
| Dynamic matrix | Moderate - a plan job | Strong - legs follow the repo | Weak - bad plans give a startup error or a silent skip | Low | Moderate - plan is a contract |
| `github-script` | Low - inline JS | Strong - full REST API | Fair - script errors in the log | Moderate - `script:` is an injection sink; token scope | Moderate - keep scripts small |
| ChatOps via `issue_comment` | Moderate | Strong - humans trigger on demand | Fair - replies show results | High - untrusted text; needs authorization | Moderate - skipped-run noise |
| Plain `workflow_dispatch` | Minimal | Moderate - needs UI or CLI | Excellent | Low - write access only | Low |

## 15. Practical Tips

- Validate the plan's JSON **in the plan job** (`jq -e`), and fail loudly.
- If you guard the matrix job, also guard against a silently skipped result (a final job that asserts work happened).
- Keep a `marker` in bot comments and update them, never append.
- Never write `${{ }}` inside `script:` for untrusted values; use `env:` and `process.env`.
- Do not name an output `result` in a `github-script` step.
- Check `author_association` (or your own allow-list) before any ChatOps command acts.
- Expect one run per comment; keep the job-level `if` cheap.
- Move long scripts into the repository and test them.

## 16. Demonstrated Failure Modes

**Failure 1: the malformed matrix.** `failure`, only the plan job, no message through the API.

**Failure 2: the empty matrix.** The same.

**Failure 3: the guard that hid the failure.** `if: count > 0` turned the malformed plan into a skipped job and a **green** run.

**Failure 4: the shadowed output.** `core.setOutput('result', ...)` arrived empty; the action's own `result` won.

**Failure 5: the comment storm.** Five comments, five runs, two of them skipped.

**Failure 6: the unauthorized caller (modelled).** Without the association check, any commenter could run commands; the lab shows the allow-list.

## 17. Key Takeaways

- A dynamic matrix is `fromJSON(needs.<job>.outputs.<x>)`; legs are named by their values.
- Malformed and empty matrices fail the run at expansion with no job and no API message.
- An `if:` guard turns that into a silent skip; validate in the plan job instead.
- `github-script` gives you an authenticated client; keep scripts small, pin by SHA, and read untrusted values from `env`.
- `github-script` owns an output named `result`; use another name.
- Update bot comments in place using a hidden marker.
- `issue_comment` fires for every comment; handlers need a job-level filter and an authorization check.
- A bot's `GITHUB_TOKEN` comments do not retrigger workflows.

## 18. Exercises

1. A plan emits `{"include":[{"name":"a"},{"name":"b"}]}`. What are the two job names for a job `build` with `matrix: ${{ fromJSON(...) }}`?
2. Your plan job has a bug and `count` is empty. The matrix job has `if: ${{ fromJSON(needs.plan.outputs.count) > 0 }}`. Predict the outcome and say how you would detect it.
3. In a `github-script` step you call `core.setOutput('result', 'ok')` and the next step reads `steps.x.outputs.result`. What does it read, and why?
4. A comment `/tally ping` is posted by a contributor whose `author_association` is `CONTRIBUTOR`. The allow-list is OWNER, MEMBER, COLLABORATOR. What does the handler reply, and does it still react with 👀?
5. (Hand arithmetic) A repository gets 30 comments a day; 4 are commands. How many workflow runs a day, how many with a skipped job, and, if each command run takes 8 seconds on Linux (private repo), billed minutes a day?

<details>
<summary>Answers</summary>

1. With a single key `name`, the names are `build (a)` and `build (b)` (values in key order, as `run (alpha, 3.11)` showed for two keys).
2. We observed it: in a job-level `if:`, `fromJSON` of an empty value does not error; the job is **skipped** and the run is green (runs 37335483478 and 37336333260). The same expression inside a step fails the step with `Error reading JToken`. Detect it by failing the plan job on an unexpected output and by a final job that asserts at least one leg ran.
3. It reads the action's own `result` output (the script's return value, empty here), because `github-script` sets it after your script and overwrites yours. Use another output name.
4. It replies `Not authorized (CONTRIBUTOR).` and, since the reaction is created before the check in our handler, it **does** react with 👀 first.
5. 30 runs a day; 26 have a skipped job; the 4 command runs bill 4 x ceil(8/60) = **4 billed minutes** (skipped jobs have no runner time).

</details>

## 19. Additional Resources

All verified 2026-10.

- GitHub Docs: Running variations of jobs in a workflow (dynamic matrix) - https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/run-job-variations
- actions/github-script - https://github.com/actions/github-script
- GitHub Docs: Events that trigger workflows (`issue_comment`) - https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows
- GitHub REST: Issue comments and reactions - https://docs.github.com/en/rest/issues/comments
- Octokit REST (the client inside `github-script`) - https://octokit.github.io/rest.js/
- Live evidence: runs 37333637267, 37333707626, 37333767896, 37335428986, 37335372099, 37335483478 (matrix); 37334461487, 37334803026 (PR bot); 37334895791, 37334907699, 37334914023, 37335212282 (ChatOps)
- Laster, *Learning GitHub Actions* (O'Reilly), Chapter 13

## 20. Appendix A: Code Index

> 💻 Complete, runnable code for this chapter. Skip when reading for concepts.

### A.1 Validate a plan and model the guard

```python
import json


def validate_plan(matrix_json: str) -> list[dict]:
    """The plan job's contract: a JSON object with a non-empty ``include`` list."""
    data = json.loads(matrix_json)                  # raises on malformed JSON
    legs = data["include"]
    if not isinstance(legs, list) or not legs:
        raise ValueError("matrix must contain at least one leg")
    return legs


def guarded_outcome(count: int) -> str:
    """What `if: count > 0` does to the matrix job."""
    return "runs" if count > 0 else "skipped"


assert len(validate_plan('{"include":[{"name":"a"}]}')) == 1
for bad in ("this is not json", '{"include":[]}'):
    try:
        validate_plan(bad)
        raise AssertionError(bad)
    except (ValueError, KeyError):
        pass
assert guarded_outcome(0) == "skipped"   # an empty or malformed plan skips silently
```

**Flow:** parse the plan; require a non-empty `include` list (loud failure in the plan job); model the guard, under which an empty plan skips silently (a malformed one yields an empty count, which also skips).

### A.2 Authorize and parse a ChatOps command

```python
ALLOWED = {"OWNER", "MEMBER", "COLLABORATOR"}


def handle(body: str, association: str) -> tuple[str, str]:
    """Return (outcome, reply) for a comment, as the workflow's script does."""
    _, sub, *rest = body.split()
    if association not in ALLOWED:
        return "denied", f"Not authorized ({association})."
    if sub == "ping":
        return "ping", "pong"
    if sub == "echo":
        return "echo", " ".join(rest) or "(nothing to echo)"
    return "help", "Commands: /tally ping, /tally echo <text>"


assert handle("/tally echo hello    from   chatops", "OWNER") == ("echo", "hello from chatops")
assert handle("/tally ping", "CONTRIBUTOR") == ("denied", "Not authorized (CONTRIBUTOR).")
assert handle("/tally nonsense", "OWNER")[0] == "help"
```

**Flow:** split the body on whitespace; deny unless the association is allowed; then dispatch on the subcommand with a fixed set.
