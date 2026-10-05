# Improvements Summary

## Live Verification Log

(Record real run IDs here as each phase is proven live.)

### 2026-10-05
- Scaffold pushed; `ci.yml` green (run 37307209752).
- Ch 00 live probe: YAML anchors (`&`/`*`) work in workflows. `actionlint` accepts them and
  `ch00-yaml-anchors.yml` ran `success` (run 37307545802). The workflow-syntax reference does not
  document anchors, so Ch 00 §10 calls them a convenience, not a contract.
- Limits verified against docs: 6 h/job, 256 matrix jobs, 1,000 req/h `GITHUB_TOKEN`, 20 concurrent (Free).

### Phase 1 live verification (2026-10-05)
| Chapter | Evidence | Run |
| --- | --- | --- |
| 02 | Real 3-job run: lint 2 s, test 4 s, build 3 s; `needs` honored | 37311041878 |
| 02 | Empty workspace: 0 entries before checkout, 20 after | 37311217505 |
| 03 | Green push run (14 s) and deliberate red run (`fail=true`, 16 s) | 37311496555 / 37311583393 |
| 04 | Tag `@v7` and its SHA resolve to the same commit `3d3c42e5aac5` | 37312325910 |
| 04 | `Unable to resolve action astral-sh/setup-uv@v10` (no such floating tag) | 37312465693 |
| 05 | Hosted specs on a public repo: 4 CPU/16 GB Linux+Windows, macOS ARM64 3 CPU/7 GB | 37312789542 |
| 05 | Job with unmatched self-hosted label stays `queued`, `runnerName: null` | 37313375076 |
| 03/05 | Invalid YAML pushed: run with `jobs: []`, titled by file path | 37313041440 |

### Corrections made while building Phase 1
- `cost.py` first used 1x/2x/10x multipliers; current docs give per-minute dollar rates (Linux $0.006, Windows $0.010, macOS $0.062), so the helper and Ch 01 use mills and per-job round-up only.
- Ch 04: the repo's own workflows pinned `checkout@v4`/`setup-python@v5` (node20, scheduled for removal 2026-09-23). Bumped to `@v7`; `setup-uv@v5` to `@v10.2.0` because no floating `v10` tag exists.
- Claims dropped because the docs did not confirm them: "Docker actions are Linux-only", Windows/macOS minute multipliers.

### Ch 06 live verification (2026-10-05)
Ten real experiments on this repo, all reproduced by `intro_gha.events.would_fire` (see `fixtures/events_ch06_observed.json`):
- A `paths`-only push trigger **fires on tag pushes** (paths are not applied to tags): runs 37314112978, 37315414127.
- `branches`-only ignores tag pushes; `tags`-only ignores branch pushes.
- Tag created with `GITHUB_TOKEN` matched `demo-v*` yet started **0 runs**; the same push by user credentials started 2.
- PR run: `github.sha` = merge commit (`b2459d83`) = API `merge_commit_sha`; `github.event.pull_request.head.sha` = `de54f8aa`.
- `workflow_run` downstream ran on main's HEAD (`4c4ee30f`) while reporting the upstream's commit (`de54f8aa`).
- `tags-ignore: ['**']` alone would also block branch pushes; the working fix is `branches: ['**']` + `tags-ignore: ['**']` (run 37315330848 fired, tag run did not).
- Deleting a tag and closing a PR started no runs. Throwaway PR #1, branches and tags were removed afterwards.

### Ch 07-08 live verification (2026-10-05)
- Ch 07: the engine evaluated 32 expressions in 2 runs (37316097820, 37316108422); `intro_gha.expr` reproduces all 64 results. `'false'`/`'0'` strings are truthy; `'10' > '9'` false vs `'10' > 9` true; `failure()` is false after a `continue-on-error` step fails (outcome `failure`, conclusion `success`); `hashFiles(file)` = `sha256(sha256(bytes))`.
- Ch 08: runs 37317079828 (config) and 37317091672 (environments). Environment var `green` overrides repo var `blue`; env secret length 0 in a job without the environment; secret printed `***` directly and as base64 but a reversed copy leaked until `::add-mask::`; `production` job sat `waiting` 51 s for approval via `pending_deployments` API. Dummy secrets deleted afterwards; `TALLY_COLOR` repo var and `staging`/`production` environments remain.
- Tooling lesson: `gh api -f` sends strings, so integer fields (`wait_timer`) need `--input` JSON.

### Ch 09-10 live verification (2026-10-05)
- Ch 09 data runs 37318380786 (cache miss), 37318461776 (hit), 37318514549 (new key). Cache job: miss 17 s of steps vs hit 4 s, both bill 1 min. `cache-hit` is an **empty string** on a miss. Artifact `tally-dist`: 277 bytes, `expires_at` = created + 1 day. Empty upload path = warning by default; duplicate name = `409 Conflict`.
- Ch 09 output limit: **"Job outputs exceed 1,048,576 bytes"**; 520,000 chars passed and 530,000 failed (consistent with 2 bytes/char, ~524,288 chars). Job time grows ~quadratically with output size (128 s at 400k, 215 s at 520k, 226 s at 530k); 1M+ jobs failed after ~13 min. Runs 37317645339, 37320026502.
- Ch 10: needs skip propagation (37318821322); matrix 6->5->6; `fail-fast:true` left 2 legs without runners (37319094292 vs 37319194753); `max-parallel: 2` peak overlap 2; concurrency pending run replaced (x2, y2) and cancellation not instantaneous (y1 ran 41 s steps then marked cancelled); job timeout of 60 s fired at 90 s, ended `cancelled` (37318827012).
- Runner notice seen in annotations: `ubuntu-latest` migrates to Ubuntu 26 beginning 2026-10-19.
- Process notes: probes that write large outputs are slow and can run ~13 min; cancel guards were used. `gh workflow run` prints a URL, so capture run ids from `gh run list`, not command substitution.

### Ch 11-14 live verification (2026-10-05)
- Ch 11 (runs 37321016076, 37321165485, 37321351215, 37321500402, 37321582147): coverage 52.94% (9 of 17 statements) failed an 80% gate on 4 Python legs (3.11.16, 3.12.14, 3.13.15, 3.14.7); a failing job saves **no** pip cache; pip cache key embeds runner image + exact Python + file hash; cache saved only 1 s on a 3-4 s install. **Bug found in our own workflow:** workflow-level `defaults.run.working-directory` hit the `ci-ok` job that never checked out (`No such file or directory`), masking the gate's verdict in every earlier run; static checker `jobs_missing_checkout_with_workflow_workdir` added. Ruff discovered the repo-root `pyproject.toml` from the sandbox (I001).
- Ch 12 (run 37322069271): `ghcr.io/friend09/tally` published with `GITHUB_TOKEN`; digest `sha256:a5437692...` pulled and run in a second job; image 6 layers / 47,236,038 bytes; public (anonymous pull HTTP 200). Failures: uppercase owner (`repository name must be lowercase`), push without `packages: write` (`denied: installation not allowed to Create organization package`). Container job with no git: checkout used the REST API fallback. Redis service `starting -> healthy`.
- Ch 13 (runs 37322740443, 37322900067, 37322974953): real OIDC token verified (RS256, 300 s lifetime, wrong audience and tampered signature rejected, 33 claims). Repos created after 2026-07-15 get an ID-based `sub`: `repo:Friend09@7501015/<repo>@1405684500:environment:staging`. With an environment the `sub` is identical on `main` and a feature branch; without it the `sub` carries the ref. `production` restricted to `main`: feature-branch deploy rejected instantly (`Branch "demo/ch13" is not allowed to deploy to production due to environment protection rules.`). Deployment statuses recorded (`waiting` is platform-set).
- Ch 14 (runs 37323902752, 37324188233, 37324433803, 37324580446, 37324320986): releases v0.1.0-v0.1.3 (all pre-releases, so none is `latest`). Asset digests = local sha256 = `SHA256SUMS`. Auto-generated notes list merged PRs only (by label via `.github/release.yml`); `v0.1.1` notes repeated PR #2 until `--notes-start-tag` was passed. Token-created tag started 0 push runs; the user-pushed tag also fired `ch03` and `ch11` (paths ignored for tags). Immutable releases: upload/delete asset and tag delete all refused (HTTP 422 / rule violation); immutability is per release and permanent.
- **Side effects left in the repo (documented for the owner):** release `v0.1.3` and tag `v0.1.3` are permanently immutable; public GHCR package `ghcr.io/friend09/tally`; tags v0.1.0-v0.1.2; `production` environment restricted to branch `main`; repo variable `TALLY_COLOR`; environments `staging`/`production`/(`pypi` not created). The immutable-releases repo setting was turned back off.
