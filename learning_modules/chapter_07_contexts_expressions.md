# Chapter 07: Contexts, Expressions and Conditionals

**Reading Time:** ~50 minutes
**Prerequisites:** Chapter 03 (`if:`, `env`), Chapter 06 (event values)
**Practice Notebook:** `notebooks/practice_07.ipynb`
**Reference Notebook:** `notebooks/lab_07_contexts_expressions.ipynb`
**Script:** `labs/lab_07_contexts_expressions.py`
**Book Reference:** Laster, Learning GitHub Actions Ch 8 / GitHub Docs: Evaluate expressions in workflows, Contexts reference
**Depth:** Core
**Default Runtime:** Live repo

---

## Beginner's Guide

**Focus on first:** Sections 3 (the two syntaxes), 5 (truthiness, measured) and 10 (status functions and the `if` that did not run).

**Skip on first read:** Sections 11-12 (`hashFiles` internals, object filters).

**Key concepts in plain English:**

- **Expression:** a tiny formula inside `${{ ... }}` that GitHub evaluates **before** your shell sees the text.
- **Context:** a named bundle of values you can read (`github`, `env`, `inputs`, `matrix`, `steps`, `runner` ...).
- **Truthy / falsy:** whether a value counts as "yes" or "no" in a condition. `false` the *string* counts as yes.
- **Status function:** `success()`, `failure()`, `always()`, `cancelled()`: conditions about how the job is going.

**If you have written shell conditions** (`[ "$X" = "y" ]`), expressions are similar but run in GitHub's engine, not in bash, and they do not do arithmetic.

> **🔬 Platform Engineer's Lens:** Expressions are evaluated by GitHub **before** the step starts, and their result is pasted into your script as plain text. That one fact explains the two most expensive classes of bug: a condition that silently takes the wrong branch (`'false'` is truthy) and a script-injection hole (a pull request title pasted straight into a shell). Both appear below, with real runs.

> **🚦 Native vs Marketplace vs Custom:** Everything here is native. Reach for an expression when the decision depends on workflow data (event, branch, input, earlier step). Reach for shell when you need arithmetic, loops or file inspection, because expressions have none.

## What You'll Learn

- Write conditions with `if:` and know when `${{ }}` is required
- State exactly which values are truthy and falsy, and prove it
- Predict `==`, `<` and `>` across strings, numbers and null
- Use `&&` and `||` as value-returning operators (defaults and ternaries)
- Use `contains`, `startsWith`, `format`, `join`, `toJSON`, `fromJSON` and `hashFiles`
- Choose the right context, and know where each function is allowed
- Use `success()`, `failure()` and `always()`, and read `outcome` versus `conclusion`

## Table of Contents

<!-- TOC -->
- [1. Why Expressions](#1-why-expressions)
- [2. Running Example: The Engine Answers Back](#2-running-example-the-engine-answers-back)
- [3. Two Syntaxes](#3-two-syntaxes)
- [4. Types and Literals](#4-types-and-literals)
- [5. Truthiness, Measured](#5-truthiness-measured)
- [6. Comparison and Coercion](#6-comparison-and-coercion)
- [7. `&&` and `||` Return Values](#7--and--return-values)
- [8. Built-in Functions](#8-built-in-functions)
- [9. Contexts and Where They Are Allowed](#9-contexts-and-where-they-are-allowed)
- [10. Status Functions and the `if` That Did Not Run](#10-status-functions-and-the-if-that-did-not-run)
- [11. `hashFiles` and Cache Keys](#11-hashfiles-and-cache-keys)
- [12. Object Filters and `toJSON` Debugging](#12-object-filters-and-tojson-debugging)
- [13. Case Study: The Release That Always Deployed](#13-case-study-the-release-that-always-deployed)
- [14. Comparison: Where to Decide](#14-comparison-where-to-decide)
- [15. Practical Tips](#15-practical-tips)
- [16. Demonstrated Failure Modes](#16-demonstrated-failure-modes)
- [17. Key Takeaways](#17-key-takeaways)
- [18. Exercises](#18-exercises)
- [19. Additional Resources](#19-additional-resources)
- [20. Appendix A: Code Index](#20-appendix-a-code-index)
   - [A.1 Run the evaluator against real engine results](#a1-run-the-evaluator-against-real-engine-results)
   - [A.2 Extract and replay every expression from the workflow](#a2-extract-and-replay-every-expression-from-the-workflow)
<!-- /TOC -->

---

## 1. Why Expressions

Chapter 03's `if: ${{ inputs.fail }}` was an expression, and so was `${{ env.PYTHON_VERSION }}`. This chapter makes them precise. We will not reason from memory about how GitHub evaluates them: a workflow made the real engine evaluate dozens of expressions, we saved its answers, and we wrote a small evaluator (`intro_gha/expr.py`) that reproduces every one of them.

## 2. Running Example: The Engine Answers Back

> 📌 **Running Example: `ch07-expressions.yml`.** A workflow with three jobs that prints `REPORT key=value` lines. Job **literals** has 34 `echo` lines; 32 of them each interpolate one expression (`${{ '0' && 'truthy' || 'falsy' }}`, `${{ '10' > '9' }}`, ...). Job **status** has a step that fails on purpose with `continue-on-error: true`, then steps guarded by `success()`, `failure()` and `always()`. Job **matrixed** runs a 2-entry matrix and prints `toJSON(matrix)` and `hashFiles(...)`. We ran it twice: **run 37316097820** with the defaults (`name` empty, `flag` false) and **run 37316108422** with `name=Tally flag=true`. Data: `fixtures/ctx_ch07_defaults.json` and `fixtures/ctx_ch07_inputs.json`. We return to it in every section.

The evaluator in `src/intro_gha/expr.py` reproduces **all 32 single-expression results in both runs (64 comparisons)**, checked by `tests/test_expr.py`. The other two lines (`toJSON` output) go through `jq` and are shown in Section 8. When the chapter says "the engine returns X", X is a value GitHub printed, not a claim.

## 3. Two Syntaxes

| Where | Syntax | Example |
| --- | --- | --- |
| Anywhere in a value | `${{ expression }}` | `run: echo "${{ github.ref_name }}"` |
| In an `if:` | the bare expression is accepted | `if: github.event_name == 'push'` |

**Always wrap in `${{ }}`** when the expression starts with `!`. YAML reads a leading `!` as a *tag* indicator. `actionlint` shows the failure:

```
if: !cancelled()
  -> string should not be empty [syntax-check]
if: ${{ !cancelled() }}
  -> (passes)
```

String literals inside an expression use **single quotes**: `'main'`, never `"main"`. To include a quote, double it: `'it''s'`.

**Evaluation order.** Before step `Truthiness and comparison` ran, GitHub replaced each `${{ ... }}` in the `run:` text with its result. Bash never saw the braces. Using Chapter 02's bracket:

| Moment | State |
| --- | --- |
| Before evaluation | `echo "REPORT eq_num_str=${{ 1 == '1' }}"` |
| After evaluation | `echo "REPORT eq_num_str=true"` |
| Bash prints | `REPORT eq_num_str=true` |

## 4. Types and Literals

Six types: **null**, **boolean** (`true`, `false`), **number** (`1`, `3.5`), **string** (`'text'`), **array**, **object**. Contexts hold objects (`github.event`), arrays (`github.event.commits`) and strings.

**There is no arithmetic.** `${{ 1 + 1 }}` does not work; `actionlint` rejects `${{ fromJSON('3') + 1 }}` with:

```
got unexpected character '+' while lexing expression
```

Our evaluator raises the same error for `+`. To compute, do it in shell (`$((x + 1))`) or in a script step.

## 5. Truthiness, Measured

Docs (verified 2026-10): the **falsy** values are `false`, `0`, `-0`, `''` (empty string) and `null`. Everything else is **truthy**. The real engine's answers, using the pattern `X && 'truthy' || 'falsy'`:

| Expression value | Type | Engine result |
| --- | --- | --- |
| `'false'` | string | **truthy** |
| `'0'` | string | **truthy** |
| `0` | number | falsy |
| `''` | string | falsy |
| `null` | null | falsy |
| `fromJSON('false')` | boolean | falsy |
| `env.FLAG_TEXT` (set to `'false'`) | string | **truthy** |
| `inputs.flag` (boolean `false`) | boolean | falsy |
| `inputs.flag` (boolean `true`) | boolean | truthy |

**What to notice:**

- **`'false'` and `'0'` are truthy.** They are non-empty strings. Environment variables and `$GITHUB_OUTPUT` values are always strings, so `if: env.FLAG` is true even when `FLAG: 'false'`. This is the classic silent wrong-branch bug.
- A **boolean workflow input** (`type: boolean`) is a real boolean in the `inputs` context, so `if: inputs.flag` works as expected. Chapter 03's `if: ${{ inputs.fail }}` was safe for that reason.
- To compare a string flag, compare explicitly: `env.FLAG == 'true'`, or convert: `fromJSON(env.FLAG)`.

> 📝 **Full implementation:** See [Appendix A.1](#a1-run-the-evaluator-against-real-engine-results)

## 6. Comparison and Coercion

`==`, `!=`, `<`, `<=`, `>` and `>=` follow two rules (docs, verified 2026-10): if the types differ GitHub converts **both to numbers** (null to 0, `true` to 1, `false` to 0, an empty string to 0, a string parsed as JSON else NaN, arrays and objects NaN); and **string comparison ignores case**. Engine results:

| Expression | Result | Why |
| --- | --- | --- |
| `1 == '1'` | true | string `'1'` becomes the number 1 |
| `'abc' == 'ABC'` | true | strings compare case-insensitively |
| `null == ''` | true | null is 0 and `''` is 0 |
| `env.NOPE == ''` | true | a missing value is null, which is 0, which equals `''` |
| `10 > 9` | true | numbers |
| `'10' > '9'` | **false** | two strings: compared as text, `'1'` sorts before `'9'` |
| `'10' > 9` | true | mixed types: `'10'` becomes 10 |

**What to notice:** `'10' > '9'` is false but `'10' > 9` is true. The same digits give opposite answers depending on whether *both* sides are strings. Values from `env`, `outputs` and `matrix` are strings, so a version comparison like `matrix.py > '3.9'` is a text comparison. Text compares one character at a time: for `'3.10'` against `'3.9'` the first difference is the third character, where `'1'` sorts before `'9'`, so `'3.10' > '3.9'` is **false** (by the rule we measured with `'10' > '9'`). Compare versions in a script, not in an expression.

## 7. `&&` and `||` Return Values

They are not just booleans: `a && b` returns `a` if `a` is falsy, else `b`; `a || b` returns `a` if truthy, else `b`.

| Expression | Engine result |
| --- | --- |
| `'a' && 'b'` | `b` |
| `'' \|\| 'default'` | `default` |
| `!'x'` | false (`!` always returns a boolean) |
| `inputs.name \|\| 'world'` (name empty) | `world` |
| `inputs.name \|\| 'world'` (name = `Tally`) | `Tally` |

Two idioms follow:

- **Default value:** `${{ inputs.name || 'world' }}`. (Chapter 03's `run-name` used `inputs.fail || false` for the same reason: a push event has no inputs.)
- **Ternary:** `${{ cond && 'yes' || 'no' }}`. It breaks if the "yes" value is falsy: `cond && '' || 'no'` always gives `no`.

## 8. Built-in Functions

All results below are real engine output:

| Call | Result | Note |
| --- | --- | --- |
| `contains('Hello World', 'WORLD')` | true | case-insensitive substring |
| `contains(fromJSON('["a","b"]'), 'b')` | true | array membership |
| `startsWith('refs/heads/main', 'refs/heads/')` | true | |
| `endsWith('report.md', '.md')` | true | |
| `format('{0}-{1}-{0}', 'a', 'b')` | `a-b-a` | positional |
| `format('{{literal}} {0}', 'x')` | `{literal} x` | `{{ }}` escapes braces |
| `join(fromJSON('["x","y","z"]'), '+')` | `x+y+z` | |
| `fromJSON('3')` | `3` | JSON text to a value |
| `toJSON(fromJSON('[1,2]'))` | `[1,2]` after `jq -c` | the engine pretty-prints; we compacted it |
| `hashFiles('sandbox/tally/tally/add.py')` | `1df4e1f8...20ddf` | see Section 11 |

`toJSON` is the debugging tool: `${{ toJSON(github) }}` prints the whole context. In run 37316097820 the matrix job printed `toJSON(matrix)` as `{"py":"3.10"}` for the first entry and `{"py":"3.12","extra":"only-on-312"}` for the second. Note that `extra` exists **only** on the entry that an `include` added it to; on the other entry `matrix.extra` was an empty string (`extra=[]` in the report).

## 9. Contexts and Where They Are Allowed

| Context | Holds | Example |
| --- | --- | --- |
| `github` | event and run metadata | `github.event_name`, `github.ref_name` |
| `env` | environment variables you set | `env.PYTHON_VERSION` |
| `vars` | repository/org variables | `vars.GHA_ENABLE_SELFHOSTED` (Chapter 08) |
| `secrets` | secret values (masked in logs) | `secrets.MY_TOKEN` (Chapter 08) |
| `inputs` | `workflow_dispatch` / `workflow_call` inputs | `inputs.flag` |
| `job` | the running job | `job.status` |
| `steps` | earlier steps' outputs and results | `steps.flaky.outcome` |
| `runner` | the machine | `runner.os` |
| `strategy`, `matrix` | the matrix leg | `matrix.py` |
| `needs` | upstream jobs' outputs and results | `needs.build.outputs.v` (Chapter 09) |

Not every context works everywhere. Real `actionlint` output (1.7.12) when we put `success()` inside a `run:` line:

```
calling function "success" is not allowed here. "success" is only available in
"jobs.<job_id>.if", "jobs.<job_id>.steps.if".
```

Rule of thumb: **status functions belong in `if:` only**. Likewise `actionlint` rejects `runs-on: ${{ env.OS }}` with `context "env" is not allowed here. available contexts are "github", "inputs", "matrix", "needs", "strategy", "vars"`, so a runner label cannot come from `env`; use `vars`, `inputs` or `matrix`. The official availability table is in the contexts reference (Section 19); `actionlint` enforces it for you.

## 10. Status Functions and the `if` That Did Not Run

Without an `if:`, a step runs only if all previous steps succeeded, as if it said `if: success()`. The four status functions (docs, verified 2026-10):

| Function | True when |
| --- | --- |
| `success()` | all previous steps succeeded (the default) |
| `failure()` | a previous step of the job failed |
| `always()` | always, even if the run was cancelled |
| `cancelled()` | the workflow was cancelled |

Job `status` in run 37316097820 had a step `flaky` that ran `exit 1` with `continue-on-error: true`, followed by four guarded steps. The result:

| Step | Condition | Ran? |
| --- | --- | --- |
| `flaky` | (runs `exit 1`) | ran, exit code 1 |
| `Outcome vs conclusion` | default | yes: printed the two values below |
| `Runs only on success()` | `success()` | **yes** (`success_step_ran=yes`) |
| `Runs only on failure()` | `failure()` | **no** (no `failure_step_ran` line exists) |
| `Runs always` | `always()` | yes (`always_step_ran=yes`) |

and the two status values of the failed step:

| `steps.flaky.outcome` | `steps.flaky.conclusion` |
| --- | --- |
| `failure` | `success` |

**What to notice:**

- **`outcome`** is what the step actually did (`failure`); **`conclusion`** is the result after `continue-on-error` is applied (`success`). With `continue-on-error: true`, the failure is "forgiven" at the job level.
- Because the forgiven step counts as a success, `success()` stayed true and **`failure()` stayed false** even though a command exited 1. The step guarded by `failure()` never ran. This is the observed behavior; our reading is that the status functions look at conclusions. If you need to react to the *real* result of a forgiven step, test `steps.flaky.outcome == 'failure'`.
- Use `always()` for cleanup that must run, and `if: ${{ failure() }}` for "tell me when it breaks" steps; they only fire on an unforgiven failure.

## 11. `hashFiles` and Cache Keys

> ⚠️ ADVANCED TOPIC: Skip on first read.

`hashFiles('path/**')` returns one hash for a set of files, used for cache keys (Chapter 09). Docs (verified 2026-10): it computes a SHA-256 of each file, then a SHA-256 over those. We checked the single-file case exactly: the engine returned `1df4e1f839cdb864080ba7277e7331d515c6e8b8695da58fb4a22c04b2820ddf` for `sandbox/tally/tally/add.py`, and in Python `sha256(sha256(file_bytes))` gives the same value, whereas a single `sha256(file_bytes)` gives `df34d80f...`. (Several-file behavior follows the docs' description; we verified only one file.) If no file matches, it returns an empty string.

## 12. Object Filters and `toJSON` Debugging

> ⚠️ ADVANCED TOPIC: Skip on first read.

The `*` filter selects across an array: `github.event.issue.labels.*.name` yields every label name. Combine with `contains(...)` to ask "does the PR carry the label `deploy`?": `contains(github.event.pull_request.labels.*.name, 'deploy')`. When unsure what a context contains, print it with `toJSON` first, as Chapter 06 did.

## 13. Case Study: The Release That Always Deployed

A workflow sets `DEPLOY: 'false'` for dry runs and gates the deploy step with `if: env.DEPLOY`. Every run deploys, including dry runs. The cause is Section 5: `'false'` is a non-empty string, so it is truthy. The fix is one explicit comparison: `if: env.DEPLOY == 'true'`. The more insidious variant is a step output (`echo "deploy=false" >> $GITHUB_OUTPUT`), which is also a string.

## 14. Comparison: Where to Decide

| Approach | Setup Effort | Control | Failure Visibility | Security Exposure | Maintenance Burden |
| --- | --- | --- | --- | --- | --- |
| Expression in `if:` | Minimal - one line | Moderate - no arithmetic or loops | Fair - skipped steps show as skipped | Low - no shell involved | Low |
| Expression inside `run:` text | Minimal - inline | Moderate - evaluated before the shell | Weak - result is baked into the script text | High - input is pasted into the shell | Moderate - quoting traps |
| Shell conditional in `run:` | Low - plain bash | Excellent - full language | Strong - the log shows the branch | Low - values come from env vars | Low |
| Separate decision job with outputs | Moderate - wire `needs` | Strong - reusable decision | Strong - own job in the UI | Low | Moderate - more jobs, more minutes |

## 15. Practical Tips

- Wrap anything starting with `!` in `${{ }}`.
- Never compare strings that hold booleans with a bare truthiness test: write `== 'true'`.
- Pass untrusted values (`github.event.pull_request.title`, branch names, issue bodies) into `run:` through an `env:` variable, never inline: `actionlint` flags the inline form as "potentially untrusted".
- Use `|| 'default'` for optional inputs, and remember it also replaces `0` and `false`.
- Compare versions in a script, not with `<`/`>` on strings.
- Debug with `echo '${{ toJSON(github) }}'` in a throwaway run; remove it afterwards (it can print sensitive data).

## 16. Demonstrated Failure Modes

**Failure 1: the truthy `'false'`.** Evidence: `env.FLAG_TEXT` set to `'false'` evaluated `env.FLAG_TEXT && 'truthy' || 'falsy'` to **`truthy`** (run 37316097820), while the boolean input `inputs.flag = false` gave `falsy`. Symptom: a "disabled" step runs. Fix: compare with `== 'true'`.

**Failure 2: arithmetic.** `actionlint`: `got unexpected character '+' while lexing expression`. Symptom: the workflow file is rejected. Fix: compute in shell.

**Failure 3: the status function in the wrong place.** `actionlint`: `calling function "success" is not allowed here`. Fix: move it to an `if:`.

**Failure 4: the guard that never fires.** A step `if: failure()` after a `continue-on-error` step never ran, because the forgiven step counts as success. Fix: test `steps.<id>.outcome == 'failure'`.

**Failure 5: inline untrusted input.** `actionlint`: `"github.event.pull_request.title" is potentially untrusted. avoid using it directly in inline scripts. instead, pass it through an environment variable.` Our workflow passes it through `env: PR_TITLE` and prints `[$PR_TITLE]`; on a dispatch event it was empty (`[]`). The attack this prevents is the subject of Chapter 16.

## 17. Key Takeaways

- `${{ }}` is evaluated by GitHub before the shell sees the text.
- Falsy: `false`, `0`, `-0`, `''`, `null`. The strings `'false'` and `'0'` are truthy.
- Mismatched types compare as numbers; two strings compare case-insensitively as text (`'10' > '9'` is false).
- `&&` and `||` return values; use them for defaults and ternaries.
- There is no arithmetic and status functions work only in `if:`.
- `outcome` is the raw result; `conclusion` is after `continue-on-error`; `failure()` follows conclusions.
- `hashFiles` of one file is `sha256(sha256(bytes))`.
- Pass untrusted values through `env:`, never inline.

## 18. Exercises

1. What does `${{ inputs.name || 'world' }}` print when `name` is empty? When it is `0`?
2. Which of these is falsy: `'0'`, `0`, `'false'`, `''`?
3. Evaluate by hand: `'9' > '10'`, `9 > '10'`, `'ABC' == 'abc'`, `null == 0`.
4. A step has `if: failure()` and follows a step with `continue-on-error: true` that exits 1. Does it run? What would you write to run it?
5. (Hand arithmetic) `format('{0}/{1}@{0}', 'tally', 'v7')`, and `join(fromJSON('[1,2,3]'), '-')`.

<details>
<summary>Answers</summary>

1. `world` for empty. For the string `0`: the string `'0'` is truthy, so it prints `0`; if the value is the number 0 it is falsy and prints `world`.
2. `0` (the number) and `''`. The strings `'0'` and `'false'` are truthy.
3. `'9' > '10'`: both strings, text compare `'9'` vs `'1'`: true. `9 > '10'`: mixed, `'10'` becomes 10: false. `'ABC' == 'abc'`: true. `null == 0`: null becomes 0: true.
4. It does not run (observed): the forgiven step's conclusion is success, so `failure()` is false. Use `if: ${{ steps.<id>.outcome == 'failure' }}`.
5. `tally/v7@tally`; `1-2-3`.

</details>

## 19. Additional Resources

All verified 2026-10.

- GitHub Docs: Evaluate expressions in workflows and actions - https://docs.github.com/en/actions/reference/workflows-and-actions/expressions
- GitHub Docs: Contexts reference (including context availability) - https://docs.github.com/en/actions/reference/workflows-and-actions/contexts
- GitHub Docs: Workflow syntax (`jobs.<job_id>.steps[*].if`, `continue-on-error`) - https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax
- GitHub Docs: Secure use reference (script injection) - https://docs.github.com/en/actions/reference/security/secure-use
- actionlint checks (expression and context-availability rules) - https://github.com/rhysd/actionlint/blob/main/docs/checks.md
- Live evidence: runs 37316097820 and 37316108422 in this repo
- Laster, *Learning GitHub Actions* (O'Reilly), Chapter 8

## 20. Appendix A: Code Index

> 💻 Complete, runnable code for this chapter. Skip when reading for concepts.

### A.1 Run the evaluator against real engine results

```python
from intro_gha.expr import evaluate, stringify

ctx = {"env": {"FLAG_TEXT": "false"}, "inputs": {"name": "", "flag": False}}
assert stringify(evaluate("env.FLAG_TEXT && 'truthy' || 'falsy'", ctx)) == "truthy"
assert stringify(evaluate("inputs.flag && 'truthy' || 'falsy'", ctx)) == "falsy"
assert stringify(evaluate("'10' > '9'", ctx)) == "false"
assert stringify(evaluate("'10' > 9", ctx)) == "true"
assert stringify(evaluate("inputs.name || 'world'", ctx)) == "world"
assert stringify(evaluate("format('{0}/{1}@{0}', 'tally', 'v7')", ctx)) == "tally/v7@tally"
```

**Flow:** tokenize the expression -> recursive descent by precedence (`||`, `&&`, `==`, comparison, `!`) -> evaluate with coercion rules -> `stringify` the result as `${{ }}` would.

### A.2 Extract and replay every expression from the workflow

```python
import json, re
from intro_gha import FIXTURES_DIR, WORKFLOWS_DIR
from intro_gha.expr import evaluate, stringify

ECHO = re.compile(r'echo "REPORT (\w+)=\$\{\{ (.+) \}\}"$')
lines = (WORKFLOWS_DIR / "ch07-expressions.yml").read_text().splitlines()
exprs = {m[1]: m[2] for l in lines if (m := ECHO.search(l.strip()))}
data = json.loads((FIXTURES_DIR / "ctx_ch07_defaults.json").read_text())
ctx = {"github": {"event_name": "workflow_dispatch", "ref_name": "main",
                  "event": {"pull_request": {"title": None}}},
       "runner": {"os": "Linux"}, "job": {"status": "success"},
       "env": {"FLAG_TEXT": "false", "ZERO_TEXT": "0", "EMPTY": ""},
       "inputs": {"name": "", "flag": False}}
for key, observed in data["reports"]["literals"].items():
    if key in exprs:
        assert stringify(evaluate(exprs[key], ctx)) == observed, key
```

**Flow:** regex the `echo "REPORT key=${{ expr }}"` lines out of the workflow -> evaluate each against the contexts the run had -> compare to the string the real runner printed.
