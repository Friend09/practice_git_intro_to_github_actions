# Improvements Summary

## Live Verification Log

(Record real run IDs here as each phase is proven live.)

### 2026-10-05
- Scaffold pushed; `ci.yml` green (run 37307209752).
- Ch 00 live probe: YAML anchors (`&`/`*`) work in workflows. `actionlint` accepts them and
  `ch00-yaml-anchors.yml` ran `success` (run 37307545802). The workflow-syntax reference does not
  document anchors, so Ch 00 §10 calls them a convenience, not a contract.
- Limits verified against docs: 6 h/job, 256 matrix jobs, 1,000 req/h `GITHUB_TOKEN`, 20 concurrent (Free).
