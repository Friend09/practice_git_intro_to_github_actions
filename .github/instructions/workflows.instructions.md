---
description: "Conventions for workflow files in .github/workflows/. These run for real; read first."
applyTo: ".github/workflows/*.yml"
---

# Workflow Conventions

- Every workflow sets top-level `permissions:` explicitly (default `contents: read`).
- Demo workflows are named `chXX-<topic>.yml`. They trigger only on `workflow_dispatch` or a
  `paths: ['sandbox/**']` filter so curriculum edits never fire them; `ci.yml` is the exception.
- Workflows needing credentials only the owner can create are guarded with
  `if: vars.GHA_ENABLE_<X> == 'true'` so they skip instead of failing.
- Run `actionlint .github/workflows/*.yml` before every commit.
- Third-party actions are SHA-pinned from Chapter 16 onward.
