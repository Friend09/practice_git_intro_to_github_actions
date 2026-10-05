# Chapter 15: GITHUB_TOKEN, Permissions and Least Privilege

**Reading Time:** ~55 minutes
**Prerequisites:** Chapter 08 (secrets), Chapter 12 (`packages: write`), Chapter 13 (`id-token: write`)
**Practice Notebook:** `notebooks/practice_15.ipynb`
**Reference Notebook:** `notebooks/lab_15_token_and_permissions.ipynb`
**Script:** `labs/lab_15_token_and_permissions.py`
**Book Reference:** Laster, Learning GitHub Actions Ch 9 / GitHub Docs: Workflow syntax (permissions), Secure use reference
**Depth:** Core
**Default Runtime:** Live repo

---

## Beginner's Guide

**Focus on first:** Sections 4 (what the token can do by default), 6 (the permission matrix, measured) and 7 (reading a 403).

**Skip on first read:** Sections 10-12 (rate limits in depth, forks, the scope list).

**Key concepts in plain English:**

- **`GITHUB_TOKEN`:** a credential GitHub creates automatically for each job so the job can call GitHub's API as "the workflow".
- **Permission scope:** one kind of access (`contents`, `issues`, `packages`...) at a level: `read`, `write` or `none`.
- **Least privilege:** give a job only the access it needs, so a bug or a hostile action can do little damage.
- **403:** the server understood the request and refused it. Here it means "your token lacks that permission".

**If you have used a restricted API key** (read-only vs read-write), the token is that, scoped per job, and GitHub tells you exactly which permission a refused call needed.

> **🔬 Platform Engineer's Lens:** The token is the most powerful credential in most pipelines, and the one nobody rotates because it is automatic. Every third-party action and every script in a job can use it. The cost of a permissive default is not a bill: it is that a single compromised step can create tags, labels, releases or packages in your name. In this chapter we measured exactly what each permission setting allows and what it does not.

> **🚦 Native vs Marketplace vs Custom:** The token, its scopes and the `permissions:` key are native, with nothing to build. Reach for a **personal access token or GitHub App token** only when the automatic one genuinely cannot do the job (Chapter 06: events from the token do not start workflows; Chapter 14: tags created by it do not trigger releases).

## What You'll Learn

- Describe the token (format, scope, how a job receives it)
- State the repository default permissions and what a workflow with no `permissions:` block gets
- Write `permissions:` at workflow and job level, including `{}`, `read-all` and `write-all`
- Explain why setting any one permission changes all the others to `none`
- Read a 403 and its `X-Accepted-GitHub-Permissions` header to fix it
- Name something the token can never do, whatever you grant
- Choose permissions for a real job using least privilege

## Table of Contents

<!-- TOC -->
- [1. The Token Behind Every Run](#1-the-token-behind-every-run)
- [2. Running Example: Six Jobs That Differ by One Line](#2-running-example-six-jobs-that-differ-by-one-line)
- [3. What the Token Looks Like](#3-what-the-token-looks-like)
- [4. The Default: Read-Only](#4-the-default-read-only)
- [5. Writing `permissions:`](#5-writing-permissions)
- [6. The Matrix, Measured](#6-the-matrix-measured)
- [7. Reading a 403](#7-reading-a-403)
- [8. What the Token Can Never Do](#8-what-the-token-can-never-do)
- [9. Least Privilege in Practice](#9-least-privilege-in-practice)
- [10. Rate Limits](#10-rate-limits)
- [11. Forks](#11-forks)
- [12. Tokens That Are Not `GITHUB_TOKEN`](#12-tokens-that-are-not-github_token)
- [13. Case Study: The Workflow That Could Do Everything](#13-case-study-the-workflow-that-could-do-everything)
- [14. Comparison: How to Set Permissions](#14-comparison-how-to-set-permissions)
- [15. Practical Tips](#15-practical-tips)
- [16. Demonstrated Failure Modes](#16-demonstrated-failure-modes)
- [17. Key Takeaways](#17-key-takeaways)
- [18. Exercises](#18-exercises)
- [19. Additional Resources](#19-additional-resources)
- [20. Appendix A: Code Index](#20-appendix-a-code-index)
   - [A.1 Resolve the token permissions and predict the matrix](#a1-resolve-the-token-permissions-and-predict-the-matrix)
<!-- /TOC -->

---

## 1. The Token Behind Every Run

Every job has a credential in `github.token` (also `secrets.GITHUB_TOKEN`), created for the run and used by `actions/checkout`, `gh` and any step you write. We have been using it silently since Chapter 03: checkout used it, Chapter 12 logged in to GHCR with it, Chapter 14 created releases with it. This chapter makes its limits explicit and testable.

## 2. Running Example: Six Jobs That Differ by One Line

> 📌 **Running Example: `ch15-token-probes.yml`.** Six jobs, identical except for their `permissions:` block: `none` (`permissions: {}`), `contents_read`, `contents_write`, `issues_write`, `both_write` (contents and issues) and `write_all`. Each job runs the same three API calls with the job's token: **tag** (create and delete a lightweight tag: `POST /git/refs`), **label** (create and delete an issue label: `POST /labels`) and **secrets** (`GET /actions/secrets`, a call a workflow token can never make). A seventh workflow, `ch15-default-permissions.yml`, has **no** `permissions:` key at all. Real runs: **37325286661** (the six jobs), **37325291300** (the default), **37325596047** (a rate-limit probe). Data: `fixtures/token_ch15_summary.json`. We return to them throughout.

## 3. What the Token Looks Like

Printing only the first four characters and the length (never the token):

| Property | Value |
| --- | --- |
| Prefix | `ghs_` |
| Length | **377** characters (identical in all six jobs) |
| Where it comes from | `${{ github.token }}`, passed to steps via `env:` (here `GH_TOKEN`, which `gh` reads) |

The `ghs_` prefix is GitHub's format for an installation access token, which fits the error wording in Section 7 ("not accessible by **integration**"): the token acts as an app installed on the repository. GitHub masks it in logs (Chapter 08), but masking does not stop a step from sending it somewhere, so what it *can* do is the real protection.

## 4. The Default: Read-Only

Two places define what a job's token can do when the workflow says nothing. Real settings for this repository:

```
GET /repos/OWNER/REPO/actions/permissions/workflow
{"default_workflow_permissions":"read","can_approve_pull_request_reviews":false}
```

`read` means the token gets **read** access to repository contents and nothing else (docs: "read access only for repository contents"); the switch letting workflows approve pull-request reviews is off. The separate workflow `ch15-default-permissions.yml` has no `permissions:` key, and its job ran our probes:

| Probe | Status with the repository default |
| --- | --- |
| tag (needs `contents: write`) | **403** |
| label (needs `issues: write`) | **403** |
| secrets list | **403** |

**What to notice:** with the default, every write was refused. Docs (verified 2026-10): "It's good security practice to set the default permission for the `GITHUB_TOKEN` to read access only for repository contents", with increases granted per job. This repository follows that advice. Older repositories may have the permissive default (read and write); check your own setting, and do not rely on it: put an explicit `permissions:` block in **every workflow** (our convention since Chapter 03).

## 5. Writing `permissions:`

The scopes (docs, verified 2026-10): `actions`, `artifact-metadata`, `attestations`, `checks`, `code-quality`, `contents`, `deployments`, `discussions`, `id-token`, `issues`, `packages`, `pages`, `pull-requests`, `security-events`, `statuses`, `vulnerability-alerts`: sixteen. Each takes `read`, `write` or `none`, and **`write` includes `read`**.

```yaml
permissions:            # workflow level: applies to every job unless it overrides
  contents: read

jobs:
  publish:
    permissions:        # job level: REPLACES the workflow block for this job
      contents: read
      packages: write
```

Shorthands: `permissions: {}` (every scope `none`), `read-all`, `write-all`. And the rule that surprises people (docs): **when you set any permission, every scope you did not list becomes `none`.** Job-level blocks override workflow-level ones entirely; they do not merge.

> 📝 **Full implementation:** See [Appendix A.1](#a1-resolve-the-token-permissions-and-predict-the-matrix)

## 6. The Matrix, Measured

All six jobs, three probes, real HTTP statuses (run 37325286661):

| Job `permissions` | tag (`contents: write`) | label (`issues: write`) | secrets list |
| --- | --- | --- | --- |
| `{}` | 403 | 403 | 403 |
| `contents: read` | 403 | 403 | 403 |
| `contents: write` | **201** | 403 | 403 |
| `issues: write` | **403** | **201** | 403 |
| `contents: write` + `issues: write` | **201** | **201** | 403 |
| `write-all` | **201** | **201** | **403** |

**What to notice:**

- **`issues: write` alone could not create a tag.** The tag call needs `contents: write`, and because we set one permission, `contents` fell to `none`. This is the "unspecified becomes `none`" rule, observed. A job that needs both must list both.
- The permissions are **independent**: `contents: write` does not help the label call, and vice versa.
- **`write-all` is the only setting that passes everything, and even it is refused on the last column.** Section 8 explains why.
- `contents: read` and `{}` are indistinguishable for these three probes: both only read.
- The model in `intro_gha/perms.py` predicts all 18 cells (6 jobs x 3 probes) from the permission blocks and the header in Section 7; `tests/test_perms.py` checks it against these runs.

## 7. Reading a 403

Every refused call returned HTTP 403 with the same body message:

```
Resource not accessible by integration
```

"Integration" is GitHub's word for an app: the token is the app's, and the app lacks that permission. The message does not say *which* permission, but a response header does: **`X-Accepted-GitHub-Permissions`**. The real values:

| Call | `X-Accepted-GitHub-Permissions` | Meaning |
| --- | --- | --- |
| create a tag | `contents=write;contents=write,workflows=write` | `contents: write`, **or** `contents: write` **and** `workflows: write` (the second form covers tags whose commits touch workflow files) |
| create a label | `issues=write;pull_requests=write` | `issues: write` **or** `pull-requests: write` |
| list secrets | `secrets=read` | a permission that does not exist for the workflow token (Section 8) |

How to read it: **`;` separates alternatives; `,` joins permissions that are all required.** Our `satisfies()` function implements exactly that. In practice, when a step fails with `Resource not accessible by integration`, rerun the call with `gh api -i` and read this header: it names the line to add to `permissions:`.

> **Spot-the-diff.** Two jobs: `permissions: { issues: write }` and `permissions: { contents: write }`. Same three calls. The first creates a label and cannot create a tag; the second does the reverse. Neither can list secrets.

## 8. What the Token Can Never Do

The `secrets` column is 403 in **every** row, including `write-all`. Its required permission, `secrets=read`, is not one of the sixteen scopes you can put in `permissions:`. There is no setting that gives a workflow token the ability to *list or manage* the repository's secrets through the API. (A job still **uses** a secret you pass it with `${{ secrets.NAME }}`; Chapter 08. What it cannot do is enumerate or administer them.)

The same is true of repository administration generally: the token is a deliberately limited identity. If automation must change settings (create environments, set branch protection), it needs a personal access token or a GitHub App with the right scope, which is a bigger decision than a `permissions:` line.

## 9. Least Privilege in Practice

A pattern that has run through this course:

```yaml
permissions:
  contents: read            # workflow default: read-only

jobs:
  test:                     # inherits read-only
    ...
  release:
    permissions:
      contents: write       # only this job can write, and only contents
```

| Job in this course | Permissions it actually needs |
| --- | --- |
| CI lint and tests (Chapter 11) | `contents: read` |
| Publish a container (Chapter 12) | `contents: read`, `packages: write` |
| Request an OIDC token (Chapter 13) | `contents: read`, `id-token: write` |
| Create a release (Chapter 14) | `contents: write` |
| Post a label (this chapter) | `issues: write` |

Rules: start from `contents: read` at workflow level; add the minimum per **job**, never per workflow; never use `write-all` in a workflow that runs code you did not write; and re-read each job's block when you add a step.

## 10. Rate Limits

> ⚠️ ADVANCED TOPIC: Skip on first read.

The token is also rate-limited. The docs we read (rate-limits page, verified 2026-10) say **1,000 requests per hour per repository** for `GITHUB_TOKEN`, versus 5,000 for an authenticated user. We tested it: a job made **1,150** cheap authenticated calls in a row with the job token (run 37325596047, 363 seconds):

| Measure | Value |
| --- | --- |
| Calls made / succeeded / failed | 1,150 / **1,150** / **0** |
| `x-ratelimit-limit` header | **5000** (resource `core`) |
| `x-ratelimit-remaining` before / after | 4,921 / 3,852 |

**What to notice:** the documented 1,000 did **not** apply to this token on this day: we exceeded it by 150 calls with no error, and the response headers reported a limit of 5,000. We do not know whether the docs are stale, whether the figure depends on plan or repository type (ours is a public repository on a free account), or whether the limit changed; **measure your own** (`gh api rate_limit`, or the `x-ratelimit-*` headers) before designing around either number. The secondary limit (docs): no more than 100 concurrent requests, and 900 points per minute for REST, where a read costs 1 point and a write 5.

## 11. Forks

> ⚠️ ADVANCED TOPIC: Skip on first read.

Docs (verified 2026-10): when a workflow is triggered by a pull request from a **fork** (not `pull_request_target`), and the admin has not enabled write tokens for forks, any `write` permission is reduced to **read-only**. Secrets are also withheld (Chapter 08). A workflow that labels or comments on PRs will therefore work for branches in your repo and silently fail for forks; Chapter 16 covers the safe patterns. We did not test fork behavior (it needs a second account).

## 12. Tokens That Are Not `GITHUB_TOKEN`

> ⚠️ ADVANCED TOPIC: Skip on first read.

Personal access tokens (PATs) and GitHub App tokens act as a person or an app with whatever scope they were created with. They are the answer when you need an action to **trigger** further workflows (Chapter 06, 14) or to perform administration. They also last longer and are easier to over-scope, so prefer a GitHub App with narrow permissions, store the secret in an **environment** (Chapter 08), and never reuse a personal token across repositories.

## 13. Case Study: The Workflow That Could Do Everything

A repository sets `permissions: write-all` "to stop the 403s". Six months later a popular lint action is compromised and its new version runs a one-line step: use the token to create a release, push a tag and upload a malicious asset. Every one of those is a write the workflow granted. With `contents: read` at workflow level and the lint job unprivileged, the same compromised action could read a public repository and nothing more. (This scenario is constructed to illustrate the matrix in Section 6; we did not run a hostile action.)

## 14. Comparison: How to Set Permissions

| Approach | Setup Effort | Control | Failure Visibility | Security Exposure | Maintenance Burden |
| --- | --- | --- | --- | --- | --- |
| Rely on the repository default | Minimal - nothing to write | Weak - invisible in the file | Fair - 403 later | Moderate - whatever the setting says | Low - but drifts with settings |
| Workflow-level `contents: read`, job-level adds | Low - a few lines | Strong - explicit per job | Strong - failures point at a job | Low - minimal grants | Low |
| `write-all` | Minimal | Weak - everything allowed | Weak - nothing ever fails | Very High - full write for any step | Low until an incident |
| `permissions: {}` plus per-job grants | Moderate - list everything | Excellent - nothing implicit | Strong | Very Low - nothing by default | Moderate - every job lists its needs |
| PAT or App token | High - create and store | Strong - separate identity | Moderate | High if over-scoped | High - rotation |

## 15. Practical Tips

- Put `permissions: contents: read` at the top of every workflow; add per job.
- When a call fails with `Resource not accessible by integration`, run it with `gh api -i` and read `X-Accepted-GitHub-Permissions`.
- Remember that setting one scope zeroes the others: list all that a job needs.
- Never use `write-all`; never grant `write` at workflow level when only one job needs it.
- Check the repository's default (`GET .../actions/permissions/workflow`) and set it to `read`.
- Pass the token to steps through `env:`, not inline, and never print it.
- Measure the rate limit (`x-ratelimit-limit`) instead of trusting a documented number.

## 16. Demonstrated Failure Modes

**Failure 1: no permission, no write.** `permissions: {}` and `contents: read` returned 403 for every write. Fix: read the header and grant the named permission to that job.

**Failure 2: the permission you "kept" is gone.** `issues: write` alone could not create a tag (403): setting one scope zeroed `contents`. Fix: list every scope the job needs.

**Failure 3: the silent default.** The workflow with no block got 403 on every write because this repo's default is read-only. In a repo with a permissive default the same workflow would have succeeded, and the behavior changes when someone flips a setting. Fix: write the block.

**Failure 4: a call no setting can fix.** The secrets list was 403 under `write-all`. Fix: do not try; use a PAT or App if you truly must administer.

**Failure 5: the documented limit that was not.** 1,150 calls passed against a documented 1,000. Not a failure of the token, a failure of a number we should not have trusted: measure it.

## 17. Key Takeaways

- Each job gets a `ghs_`-prefixed app token; its power is whatever `permissions:` allows.
- This repository's default is read-only; always write an explicit block.
- Setting any permission makes all unlisted scopes `none`; job blocks replace workflow blocks.
- A 403 `Resource not accessible by integration` plus the `X-Accepted-GitHub-Permissions` header tells you what to grant (`;` = or, `,` = and).
- Even `write-all` cannot list repository secrets.
- Grant the minimum per job; start from `contents: read`.
- Documented rate limits can differ from observed ones; measure.
- Fork pull requests get read-only tokens and no secrets.

## 18. Exercises

1. A workflow sets `permissions: {contents: read}`. A job in it sets `permissions: {issues: write}`. What is that job's `contents` level?
2. A step fails with `Resource not accessible by integration`. The header says `X-Accepted-GitHub-Permissions: pull_requests=write;issues=write`. What is the smallest fix?
3. Which of `{}`, `contents: write`, `write-all` can create a label? Which can create a tag?
4. You want the token to list the repo's secrets. What are your options?
5. (Hand arithmetic) The rate-limit probe's header said 4,921 remaining before and 3,852 after 1,150 calls. How many requests did the limit counter record, and how does that compare with the calls made?

<details>
<summary>Answers</summary>

1. **`none`**: the job block replaces the workflow's, and `contents` was not listed in it.
2. Add `issues: write` (or `pull-requests: write`) to that job's `permissions:`: either alternative satisfies the header. Keep any other scopes the job already needs, since adding a key zeroes the rest.
3. Label: only `write-all` (a bare `contents: write` or `{}` cannot). Tag: `contents: write` and `write-all`.
4. None with `permissions:`. Use a personal access token or a GitHub App with the right scope, stored as a secret in an environment.
5. 4,921 - 3,852 = **1,069** counted, against 1,150 calls made (plus the header probes). The counter did not rise one-for-one; we did not determine why (headers can lag and requests can be counted in different buckets), which is another reason to measure rather than assume.

</details>

## 19. Additional Resources

All verified 2026-10.

- GitHub Docs: Workflow syntax, `permissions` - https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#permissions
- GitHub Docs: Secure use reference (least-privilege token, pinning, injection) - https://docs.github.com/en/actions/reference/security/secure-use
- GitHub Docs: Rate limits for the REST API - https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api
- GitHub Docs: Authenticate with the GITHUB_TOKEN - https://docs.github.com/en/actions/tutorials/authenticate-with-github_token
- GitHub REST: Workflow permissions for a repository - https://docs.github.com/en/rest/actions/permissions
- Live evidence: runs 37325286661, 37325291300 and 37325596047 in this repo
- Laster, *Learning GitHub Actions* (O'Reilly), Chapter 9

## 20. Appendix A: Code Index

> 💻 Complete, runnable code for this chapter. Skip when reading for concepts.

### A.1 Resolve the token permissions and predict the matrix

```python
import json
from pathlib import Path

from intro_gha.perms import effective, satisfies

s = json.loads(Path("fixtures/token_ch15_summary.json").read_text())
JOBS = {
    "none": {}, "contents_read": {"contents": "read"},
    "contents_write": {"contents": "write"}, "issues_write": {"issues": "write"},
    "both_write": {"contents": "write", "issues": "write"}, "write_all": "write-all",
}
for job, block in JOBS.items():
    perms = effective({"contents": "read"}, block)        # the job replaces the workflow
    for probe, header in s["accepted_permissions"].items():
        assert satisfies(perms, header) == (s["matrix"][job][probe] in (200, 201))
assert effective(None, {"issues": "write"})["contents"] == "none"
```

**Flow:** pick the job block (it replaces the workflow's); set unlisted scopes to `none`; for each probe, split the accepted header on `;` into alternatives, split each on `,` into required pairs, and allow the call if any alternative is fully met.
