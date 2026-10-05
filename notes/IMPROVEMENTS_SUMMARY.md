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
