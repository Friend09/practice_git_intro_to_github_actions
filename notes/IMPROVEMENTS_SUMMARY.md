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
