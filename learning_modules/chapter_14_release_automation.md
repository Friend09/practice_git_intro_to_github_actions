# Chapter 14: Release Automation: Tags, Changelogs, Packages

**Reading Time:** ~55 minutes
**Prerequisites:** Chapter 06 (tag triggers, the token rule), Chapter 09 (artifacts), Chapter 13 (environments, OIDC)
**Practice Notebook:** `notebooks/practice_14.ipynb`
**Reference Notebook:** `notebooks/lab_14_release_automation.ipynb`
**Script:** `labs/lab_14_release_automation.py`
**Book Reference:** Laster, Learning GitHub Actions Ch 12 / GitHub Docs: Managing releases, Automatically generated release notes
**Depth:** Core
**Default Runtime:** Live repo (guarded)

---

## Beginner's Guide

**Focus on first:** Sections 4 (turn a tag into a validated version), 6 (generated notes and what they leave out) and 8 (two ways to start a release, only one of which a tag push can start).

**Skip on first read:** Sections 10-12 (immutable releases in depth, PyPI publishing, other registries).

**Key concepts in plain English:**

- **Semantic version (SemVer):** `MAJOR.MINOR.PATCH`, such as `0.1.3`. Bump MAJOR for breaking changes, MINOR for new features, PATCH for fixes.
- **Tag:** a permanent-ish label on one commit (`v0.1.0`). A **release** is a GitHub page built around a tag: notes plus downloadable files.
- **Asset:** a file attached to a release (here a wheel, a source archive and a checksum file).
- **Release notes:** the changelog text on the release page; GitHub can generate it from merged pull requests.
- **Pre-release:** a release marked "not ready for production".

**If you have ever zipped a build and emailed it**, a release is that, with a permanent URL, a checksum and a record of what changed.

> **🔬 Platform Engineer's Lens:** A release is a promise: "this exact set of bytes is version X". Automation breaks that promise in two quiet ways: a version typed wrongly flows into a package name, and a re-run overwrites files people already downloaded. This chapter validates versions before building, publishes checksums, and enables **immutable releases**, where after publishing the platform itself refuses to change an asset or delete the tag. We tested the refusals live.

> **🚦 Native vs Marketplace vs Custom:** Everything here is native: `gh release create` is preinstalled, notes generation is a GitHub feature, and checksums come from `sha256sum`. We use no release-wrapper action. The one third-party action, `pypa/gh-action-pypi-publish`, is the standard publisher for PyPI, and it is pinned by SHA and guarded because it needs an account only you can create.

## What You'll Learn

- Validate a version string and parse it as SemVer, including ordering rules
- Build a wheel and sdist with the version stamped from the tag
- Create a release with `gh release create`, with assets and generated notes
- Configure release-note categories and explain what the generator lists and omits
- Explain the previous-tag trap and fix it with `--notes-start-tag`
- Explain why a tag created by `GITHUB_TOKEN` starts no workflow, and how to release anyway
- Describe immutable releases and the three refusals they cause
- Guard a package-publishing job so it skips until you opt in

## Table of Contents

<!-- TOC -->
- [1. What a Release Is](#1-what-a-release-is)
- [2. Running Example: Four Releases of Tally](#2-running-example-four-releases-of-tally)
- [3. SemVer and Tag Patterns](#3-semver-and-tag-patterns)
- [4. From a Tag (or an Input) to a Validated Version](#4-from-a-tag-or-an-input-to-a-validated-version)
- [5. Building and Verifying the Assets](#5-building-and-verifying-the-assets)
- [6. The Release and Its Generated Notes](#6-the-release-and-its-generated-notes)
- [7. The Previous-Tag Trap](#7-the-previous-tag-trap)
- [8. Two Ways to Start a Release](#8-two-ways-to-start-a-release)
- [9. Pre-release, Draft and Latest](#9-pre-release-draft-and-latest)
- [10. Immutable Releases](#10-immutable-releases)
- [11. Publishing to PyPI](#11-publishing-to-pypi)
- [12. Other Registries](#12-other-registries)
- [13. Case Study: The Release That Listed Itself Twice](#13-case-study-the-release-that-listed-itself-twice)
- [14. Comparison: Ways to Make a Release](#14-comparison-ways-to-make-a-release)
- [15. Practical Tips](#15-practical-tips)
- [16. Demonstrated Failure Modes](#16-demonstrated-failure-modes)
- [17. Key Takeaways](#17-key-takeaways)
- [18. Exercises](#18-exercises)
- [19. Additional Resources](#19-additional-resources)
- [20. Appendix A: Code Index](#20-appendix-a-code-index)
   - [A.1 SemVer parsing, ordering and the release facts](#a1-semver-parsing-ordering-and-the-release-facts)
<!-- /TOC -->

---

## 1. What a Release Is

A **tag** names a commit. A **release** wraps a tag with a title, notes and files. Automating releases means: decide the version, build once, attach the build and its checksum, write the notes, and publish, the same way every time. The skill is in the edges: where the version comes from, what the notes include, and what stops a release from being quietly changed afterwards.

## 2. Running Example: Four Releases of Tally

> 📌 **Running Example: `ch14-release.yml` and four real releases.** Tally now has a `pyproject.toml` (package `tally-demo`) so it can be built. The workflow has three jobs: **build** (validate the version, stamp it into `pyproject.toml`, `python -m build`, upload `dist/` as an artifact), **release** (`gh release create` with the files, a `SHA256SUMS` file and generated notes) and **publish_pypi_guarded** (skipped until `vars.GHA_ENABLE_PYPI` is `true`). It starts two ways: a **tag push** matching `v[0-9]*.[0-9]*.[0-9]*`, or `workflow_dispatch` with a `version` input. Real runs: **37323902752** (tag `v0.1.0`, pushed by me), **37324188233** (dispatch, `v0.1.1`), **37324433803** (dispatch, `v0.1.2`), **37324580446** (dispatch, `v0.1.3`, with immutable releases on), plus **37324320986** (an invalid version). Before tagging we merged PR #2 (labelled `enhancement`) so the notes had something to list. Data: `fixtures/release_ch14_summary.json`. We return to it throughout.

All four releases are marked **pre-release** because they are demos.

## 3. SemVer and Tag Patterns

A tag filter in a workflow is a **glob**, not a regular expression (Chapter 06). Ours:

```yaml
on:
  push:
    tags: ['v[0-9]*.[0-9]*.[0-9]*']
```

`v0.1.0` matches; `v1.0` does not (two parts); `release-1` does not. The glob is loose (`v1.2.3-anything` matches), so the workflow **validates again** in code. The `intro_gha.semver` helper encodes the precise rules, tested in `tests/test_semver.py`:

| Input | Valid SemVer? | Why |
| --- | --- | --- |
| `0.1.0` | yes | |
| `1.2.3-rc.1` | yes | pre-release suffix |
| `1.0` | **no** | two parts |
| `v1.0.0` | **no** | the leading `v` belongs to the **tag**, not the version |
| `01.0.0` | **no** | leading zero |
| `1.0.0.0` | **no** | four parts |

**Ordering is numeric, not textual**, and pre-releases sort **below** the release they precede:

| Compare | Result | Rule |
| --- | --- | --- |
| `0.1.10` vs `0.1.9` | `0.1.10` is higher | 10 > 9 as numbers (as text `'1' < '9'` would say the opposite: Chapter 07) |
| `1.0.0-rc.1` vs `1.0.0` | `1.0.0` is higher | a pre-release is lower than its release |
| `1.0.0-alpha.10` vs `1.0.0-alpha.2` | `alpha.10` is higher | numeric identifiers compare as numbers |

> 📝 **Full implementation:** See [Appendix A.1](#a1-semver-parsing-ordering-and-the-release-facts)

## 4. From a Tag (or an Input) to a Validated Version

The build job derives one version from either start path and refuses anything else:

```bash
if [ "$EVENT" = "push" ]; then v="${REF_NAME#v}"; else v="$INPUT_VERSION"; fi
printf '%s' "$v" | grep -Eq '^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(-[0-9A-Za-z.-]+)?$' \
  || { echo "::error title=Not a semantic version::'$v' is not MAJOR.MINOR.PATCH"; exit 1; }
```

(`REF_NAME` and `INPUT_VERSION` arrive through `env:`, never inline: Chapter 07.) Real runs:

| Run | Start | Input | Version derived | Result |
| --- | --- | --- | --- | --- |
| 37323902752 | tag push `v0.1.0` | n/a | `0.1.0` | success |
| 37324188233 | dispatch | `0.1.1` | `0.1.1` | success |
| 37324320986 | dispatch | **`v1.0`** | rejected | **build failed**, release **skipped** |

The failure's annotation: title **`Not a semantic version`**, message `'v1.0' is not MAJOR.MINOR.PATCH`. Because `release` `needs` `build`, the bad version stopped everything before any release or tag could exist.

## 5. Building and Verifying the Assets

The build stamps the version, then builds both package formats:

```bash
sed -i "s/^version = .*/version = \"$VERSION\"/" pyproject.toml
python -m build            # writes dist/*.whl and dist/*.tar.gz
```

What `v0.1.0` produced, as stored on the release (sizes and digests from the API):

| Asset | Size | SHA-256 digest (first 24 hex) |
| --- | --- | --- |
| `tally_demo-0.1.0-py3-none-any.whl` | 2,035 bytes | `c7093cb66a4baf6f29514af2...` |
| `tally_demo-0.1.0.tar.gz` | 1,909 bytes | `6a6d9caf4b923f2af153af78...` |
| `SHA256SUMS` | 194 bytes | `50143b93d4de5d65c1f27fb6...` |

Three independent checks agreed:

1. GitHub computed a `sha256:` **digest** for each asset (the table above).
2. A local `shasum -a 256` of the downloaded files gave the same hashes.
3. `shasum -a 256 -c SHA256SUMS` on the downloaded release printed `OK` for both packages.

And the wheel's own metadata, read from inside the zip: `Name: tally-demo`, **`Version: 0.1.0`**. The version in the tag, in the file names and in the package metadata all matched, because they all came from the one validated string.

**What to notice:** the build ran **once**, in its own job; the release job only *downloads* that artifact (Chapter 09). Rebuilding in the release job could produce different bytes than the ones you tested. Build once, publish what you built.

## 6. The Release and Its Generated Notes

```bash
gh release create "$TAG" dist/* --title "Tally $VERSION" \
  --generate-notes --target "$GITHUB_SHA" --prerelease
```

The job needs only `permissions: contents: write`, and `gh` authenticates through `GH_TOKEN` mapped from `${{ github.token }}`. The release recorded `target` `35fe0d57...` (the merged PR's commit), `isDraft: false`, `isPrerelease: true`.

`--generate-notes` builds the body from **merged pull requests**, grouped by the categories in `.github/release.yml`. Docs (verified 2026-10): the generated notes contain "a list of merged pull requests, a list of contributors to the release, and a link to a full changelog"; the previous tag is optional to specify.

```yaml
changelog:
  categories:
    - title: Features
      labels: [enhancement]
    - title: Fixes
      labels: [bug]
    - title: Other changes
      labels: ["*"]
```

The real notes for `v0.1.0`:

```
## What's Changed
### Features
* Document clamp behavior at the boundaries by @Friend09 in .../pull/2

## New Contributors
* @Friend09 made their first contribution in .../pull/2

**Full Changelog**: https://github.com/Friend09/practice_git_intro_to_github_actions/commits/v0.1.0
```

**What to notice:**

- PR #2 is under **Features** because it carried the `enhancement` label. The label is the only thing that decided the category. Unlabelled PRs fall to the `*` bucket.
- The notes list **one** entry. This repository has dozens of commits, but they were pushed **directly** to `main`. Only merged **pull requests** appear. A team that pushes to `main` without PRs gets empty notes.
- The header comment records which config file produced them (`.github/release.yml at main`).

## 7. The Previous-Tag Trap

The second release (`v0.1.1`) was created at the **same commit** as `v0.1.0`, so its notes should be empty. They were not. The auto-generated body listed **PR #2 again**, with "New Contributors". Asking the API for the notes with the base given explicitly fixed it:

| Request | What it listed |
| --- | --- |
| `POST .../releases/generate-notes` for `v0.1.1`, no `previous_tag_name` | **PR #2 again** (as if nothing had been released) |
| same, with `previous_tag_name=v0.1.0` | no entries; only `Full Changelog: compare/v0.1.0...v0.1.1` |

Our inference (not documented in what we read): with no explicit base, the generator compares against the last **non-pre-release** release, and every release we had made was a pre-release, so it fell back to the start of history. The remedy is to name the base yourself. `gh release create` has `--notes-start-tag`, and the workflow now finds the highest other `v*` tag and passes it:

```bash
prev=$(gh api "repos/$GITHUB_REPOSITORY/tags" --paginate -q '.[].name' \
  | grep -E '^v[0-9]+\.[0-9]+\.[0-9]+' | grep -vx "$TAG" | sort -V | tail -1)
flags+=(--notes-start-tag "$prev")
```

Verified on run 37324433803: the report said `notes_start_tag=v0.1.1`, and the release body for `v0.1.2` was empty apart from `compare/v0.1.1...v0.1.2`, which is correct (nothing changed since `v0.1.1`).

## 8. Two Ways to Start a Release

Chapter 06 predicted this; here are the real results.

| How the tag came to exist | Created by | Workflows started by the tag |
| --- | --- | --- |
| `git push origin v0.1.0` from my machine | **my credentials** | `ch14 release`, **and also** `ch03 tally ci` and `ch11 python ci` |
| `gh release create v0.1.1` inside a workflow | **`GITHUB_TOKEN`** | **none**: 0 push runs for tag `v0.1.1` |

**What to notice:**

- **A tag created with `GITHUB_TOKEN` starts nothing.** That is why our dispatch path builds and releases **in the same workflow run** instead of creating a tag and hoping a second workflow reacts. The dispatch run created tag `v0.1.1` (the API confirmed `refs/tags/v0.1.1 -> 35fe0d5`) and no tag-triggered run followed.
- **A user-pushed tag fires everything that listens to tags**, including two workflows with `paths:` filters. Chapter 06: `paths` is not applied to tags. Our release tag therefore also ran the Python CI and the Chapter 03 demo. If that is unwanted, add `tags-ignore` (with `branches`) to those workflows.
- To make a **tag push** the trigger *and* automate the tagging, create the tag with a **personal access token or a GitHub App token** (Chapter 15) instead of `GITHUB_TOKEN`.

## 9. Pre-release, Draft and Latest

| State | Meaning | Our releases |
| --- | --- | --- |
| Draft | not public; can be edited and have assets added | none |
| Pre-release | public, flagged "not ready for production" | all four |
| Latest | the release GitHub shows as the current stable one | **none** |

`gh release list` showed `isLatest=false` for all four: pre-releases are never "latest" (docs, verified 2026-10: the latest label is assigned by semantic versioning when you do not choose it). A repo whose releases are all pre-releases has no "latest", which breaks tools that fetch "the latest release". Publish a non-pre-release when you mean it.

## 10. Immutable Releases

GitHub can make a published release **immutable**. Docs (verified 2026-10): with immutable releases enabled you "cannot add, replace, or delete assets after a release is published, and you cannot move or delete its tag while the release exists". It is a repository setting (`GET`/`PUT`/`DELETE repos/OWNER/REPO/immutable-releases`), and it applies to releases **published while it is on**.

We tested all of it. **Baseline** (setting off): uploading `extra.txt` to `v0.1.2` worked, and deleting it worked. Then we enabled the setting and released `v0.1.3` (run 37324580446):

| Action on `v0.1.3` | Result |
| --- | --- |
| Create the release with 3 assets (`gh release create`) | **success** (the files were attached as part of creating it) |
| `gh release upload v0.1.3 extra.txt` | `HTTP 422: Cannot upload assets to an immutable release.` |
| `gh release delete-asset v0.1.3 SHA256SUMS` | `HTTP 422 ... Cannot delete asset from an immutable release` |
| Delete the tag through the API | `Repository rule violations found: Cannot delete this tag` |
| `GET releases/tags/v0.1.3` | `"immutable": true` |

After we turned the setting **off again**, `v0.1.3` stayed immutable (`true`) while `v0.1.2` was still `false`. **Immutability is a property of each release, set at publish time, and cannot be undone.** `v0.1.3` and its tag are permanent in this repository.

**What to notice:** this is the platform enforcing "a release is a promise". It also means a mistake in an immutable release cannot be fixed in place: you publish `0.1.4`. Consider adding a `draft` step (create as draft, attach everything, verify, then publish) so mistakes are caught before they become permanent.

## 11. Publishing to PyPI

> ⚠️ ADVANCED TOPIC: Skip on first read.

`publish_pypi_guarded` uses `pypa/gh-action-pypi-publish` (v1.14.2, pinned to commit `dc37677b2e1c63e2034f94d8a5b11f265b73ba33`) (an earlier draft of this chapter pinned the annotated **tag object** `a892a5a6...` by mistake; Chapter 16 Section 6 tells the story) with an `environment: pypi` and `permissions: id-token: write`: PyPI **trusted publishing** is Chapter 13's OIDC, with PyPI as the relying party, so no API token is stored. It needs a PyPI project configured to trust this repo, workflow and environment, which only you can create. The job is guarded by `vars.GHA_ENABLE_PYPI == 'true'`, and in all four real runs it was **skipped**. To opt in: configure the trusted publisher on PyPI, create the `pypi` environment (give it a required reviewer), then `gh variable set GHA_ENABLE_PYPI --body true`. Publishing is the one step here you generally cannot undo (PyPI's policy is not to allow a version's files to be re-uploaded; we did not publish to test it), which is another reason to gate it behind an environment approval.

## 12. Other Registries

> ⚠️ ADVANCED TOPIC: Skip on first read.

Container images go to GHCR (Chapter 12). Other ecosystems have their own registries (npm, RubyGems, NuGet, Maven); each has its own publisher action and, increasingly, its own OIDC trusted-publishing setup. The pattern is constant: build once, verify, publish from a guarded job with the smallest permission, record a checksum or digest. We did not publish to any external registry in this course's runs.

## 13. Case Study: The Release That Listed Itself Twice

A team ships `v2.0.0-rc.1`, then `v2.0.0-rc.2`, then `v2.0.0`, each marked pre-release until the last. The notes for `rc.2` repeat everything from `rc.1`, and the notes for `v2.0.0` list every change since `v1.9.0`. Users complain the changelog is noise. The cause is Section 7: the generator picks its comparison base on its own, and pre-releases are not a base. The fix is a one-liner in the release job: always pass `--notes-start-tag` with the previous tag **you** mean. (Our own run showed the repeat with `v0.1.1`; the three-release scenario is constructed from that observation.)

## 14. Comparison: Ways to Make a Release

| Approach | Setup Effort | Control | Failure Visibility | Security Exposure | Maintenance Burden |
| --- | --- | --- | --- | --- | --- |
| Manual (build locally, upload by hand) | Minimal | Weak - unrepeatable | Weak - no record | High - personal credentials | High - tribal knowledge |
| Tag-push workflow (this chapter) | Low - one file | Strong - the tag is the trigger | Excellent - a run per release | Low - `contents: write` on one job | Low |
| Dispatch workflow (this chapter) | Low | Strong - explicit human intent | Excellent | Low | Low |
| Release bot (conventional commits) | Moderate - commit conventions | Moderate - automated bumps | Fair - bot PRs | Moderate - a bot token | Moderate |
| Immutable releases on top | Minimal - one setting | Excellent - tamper-proof | Excellent - refusals are explicit | Low | Low - fix by new version |

## 15. Practical Tips

- Validate the version string in code, even when a tag glob matched.
- Build once; publish what you built; ship a `SHA256SUMS`.
- Give only the release job `contents: write`.
- Always pass `--notes-start-tag` (or `previous_tag_name`) explicitly.
- Label PRs (`enhancement`, `bug`) and keep `.github/release.yml` categories; merge through PRs if you want notes.
- Decide on purpose whether tag pushes should trigger other workflows (`tags-ignore`).
- Turn on immutable releases for anything people download, and create as a draft first.
- Guard registry-publishing jobs behind an environment with a reviewer.

## 16. Demonstrated Failure Modes

**Failure 1: the bad version.** Run 37324320986: input `v1.0` failed the build with annotation `Not a semantic version`, and the release job was skipped. No tag, no release, no assets. The system working.

**Failure 2: the duplicated notes.** `v0.1.1`'s auto notes repeated PR #2. Fix: `--notes-start-tag` (verified on `v0.1.2`).

**Failure 3: the tag that started nothing.** The token-created `v0.1.1` produced 0 push runs. Fix: build and release in one run (as here), or create the tag with a PAT/App token.

**Failure 4: the tag that started too much.** The user-pushed `v0.1.0` also ran `ch11` and `ch03` (paths are ignored for tags). Fix: `tags-ignore` on workflows that should not run for releases.

**Failure 5: the surprise `latest`.** Four pre-releases, no `latest`. Fix: publish a stable release when you mean "current".

**Failure 6: the change that is no longer allowed.** On the immutable `v0.1.3` every edit was refused with an explicit `HTTP 422`. Not a bug: the guarantee.

## 17. Key Takeaways

- A release is a tag plus notes plus assets; automate it as validate, build once, checksum, publish.
- Validate SemVer in code; compare numerically; pre-releases sort below their release.
- Generated notes list merged **PRs** grouped by label via `.github/release.yml`; direct commits are not listed.
- Pass `--notes-start-tag`, or notes can repeat old changes.
- A tag created by `GITHUB_TOKEN` starts no workflow; a user-pushed tag also triggers `paths`-filtered workflows.
- Pre-releases are never `latest`.
- Immutable releases are per-release and permanent: assets cannot be added or removed and the tag cannot be deleted.
- Guard publishing to external registries behind a variable and an environment.

## 18. Exercises

1. Which are valid SemVer: `2.0.0`, `2.0`, `v2.0.0`, `2.0.0-beta.1`, `02.0.0`? Order `2.0.0`, `2.0.0-beta.1`, `1.9.10`, `1.9.9` from lowest to highest.
2. A workflow with `on: push: tags: ['v[0-9]*.[0-9]*.[0-9]*']` also has `paths: ['src/**']`. A tag `v3.0.0` is pushed with no file changes. Does it run?
3. Your release job creates tag `v5.0.0` with `GITHUB_TOKEN` and a second workflow listens to `on: push: tags: ['v*']`. Will it run? What are two fixes?
4. You published an immutable release and spot a typo in an asset name. What can you do?
5. (Hand arithmetic) `SHA256SUMS` is 194 bytes and has two lines in the form `<64 hex>  ./<filename>\n`. Check that it matches the two file names in Section 5.

<details>
<summary>Answers</summary>

1. Valid: `2.0.0`, `2.0.0-beta.1`. Invalid: `2.0` (two parts), `v2.0.0` (leading v), `02.0.0` (leading zero). Order: `1.9.9`, `1.9.10`, `2.0.0-beta.1`, `2.0.0`.
2. **Yes.** `paths` is not applied to tag pushes (Chapter 06; our `v0.1.0` ran `ch11` the same way).
3. **No**: events created with `GITHUB_TOKEN` start no workflow runs. Fixes: create the tag with a PAT or GitHub App token, or put the build in the same workflow run (or call it as a reusable workflow).
4. Nothing in place: assets cannot be replaced or deleted. Publish a new version (`5.0.1`) with the corrected asset.
5. Line 1: 64 + 2 spaces + `./tally_demo-0.1.0-py3-none-any.whl` (35 characters) + newline = 64 + 2 + 35 + 1 = 102 bytes. Line 2: 64 + 2 + `./tally_demo-0.1.0.tar.gz` (25) + 1 = 92 bytes. Total 102 + 92 = **194 bytes**. It matches.

</details>

## 19. Additional Resources

All verified 2026-10.

- GitHub Docs: Managing releases in a repository - https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository
- GitHub Docs: Automatically generated release notes - https://docs.github.com/en/repositories/releasing-projects-on-github/automatically-generated-release-notes
- GitHub CLI manual: `gh release create` - https://cli.github.com/manual/gh_release_create
- Semantic Versioning 2.0.0 - https://semver.org/spec/v2.0.0.html
- Python Packaging: Publishing with a trusted publisher - https://docs.pypi.org/trusted-publishers/
- pypa/gh-action-pypi-publish - https://github.com/pypa/gh-action-pypi-publish
- Live evidence: runs 37323902752, 37324188233, 37324433803, 37324580446, 37324320986 and releases `v0.1.0` to `v0.1.3` in this repo
- Laster, *Learning GitHub Actions* (O'Reilly), Chapter 12

## 20. Appendix A: Code Index

> 💻 Complete, runnable code for this chapter. Skip when reading for concepts.

### A.1 SemVer parsing, ordering and the release facts

```python
import json
from pathlib import Path

from intro_gha.semver import latest, parse, tag_to_version

assert str(tag_to_version("v0.1.0")) == "0.1.0"
for bad in ("1.0", "v1.0.0", "01.0.0"):
    try:
        parse(bad)
        raise AssertionError(bad)
    except ValueError:
        pass
assert latest(["0.1.9", "0.1.10"]) == "0.1.10"
assert latest(["1.0.0-rc.1", "1.0.0"]) == "1.0.0"

s = json.loads(Path("fixtures/release_ch14_summary.json").read_text())
assert s["dispatch"]["push_runs_started_for_tag"] == 0       # GITHUB_TOKEN tag
assert s["immutable"]["release_api_immutable"] is True
assert all(r["latest"] is False for r in s["releases_listed"])  # all pre-releases
```

**Flow:** parse strictly (reject two-part, leading-`v` and leading-zero versions); compare numerically with pre-releases below releases; then assert the facts recorded from the real runs.
