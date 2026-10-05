"""Generate README.md from the chapter registry so tables never drift."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from intro_gha.chapters import CHAPTERS, PHASES, chapter_stem  # noqa: E402

INTRO = """# Intro to GitHub Actions

A hands-on, reading-first curriculum that takes you from "what is a workflow file?" to a full
CI -> release -> deploy pipeline. Every chapter is built around one tiny running example,
**Tally** (a small Python repo), and the repo you are reading is also the live lab: its
`.github/workflows/` run for real.

## What you will be able to do

- Read and write workflows: events, jobs, steps, runners, contexts and expressions
- Move data safely with outputs, artifacts, caches, secrets and environments
- Build real CI for Python, containers (GHCR), releases and guarded deployments
- Lock pipelines down: least-privilege tokens, SHA pinning, script-injection defence
- Debug runs that never fired, control cost, and write reusable and custom actions

## Prerequisites

Comfortable with Git (commit, branch, push, PR) and basic Python. No prior CI/CD experience.

## How each chapter reads

Beginner's Guide, a **Platform Engineer's Lens**, a **Native vs Marketplace vs Custom** callout,
then 20 sections built on a worked-example spine (real values, a trace, a state dump), one
demonstrated failure, exercises with answers, dated sources, and a code appendix.

## Learning schedules

| Pace | Plan | Duration |
| --- | --- | --- |
| Relaxed | 1 chapter / 2 days | ~7 weeks |
| Moderate | 1 chapter / day | ~3.5 weeks |
| Intensive | 2 chapters / day | ~2 weeks |

Optional deep-dives (Ch 21-22) can be skipped on a first pass.

## Curriculum
"""

OUTRO = """
## Running the labs

```bash
uv sync --group core
uv run pytest                      # offline contract tests
make lab-03                        # run a lab script (fixture mode)
GHA_MODE=live make lab-03          # against the real repo (needs `gh auth login`)
```

## Live demos that need your credentials

Ch 13 (OIDC to a cloud), Ch 14 (PyPI publish) and Ch 05 (self-hosted runners / ARC) cannot run
without accounts only you can create. Their workflows are guarded by repository variables
(`GHA_ENABLE_<X>=true`) and skip, rather than fail, until you opt in.

## Repository structure

```
learning_modules/   chapter_XX_<slug>.md
notebooks/          lab_XX_<slug>.ipynb + practice_XX.ipynb
labs/               lab_XX_<slug>.py
src/intro_gha/      shared helpers + chapter registry
sandbox/tally/      the running-example app
fixtures/           event and run payloads
.github/workflows/  ci.yml + chXX demo workflows (live)
.github/instructions/, .github/skills/   authoring contracts
```

Reference book: Laster, *Learning GitHub Actions* (O'Reilly). Behavioral claims are checked
against GitHub Docs and dated in each chapter's resources section.
"""


def build() -> str:
    """Assemble the README text."""
    out = [INTRO]
    for phase, name in PHASES.items():
        out.append(f"\n### Phase {phase}: {name}\n")
        out.append("| Done | Ch | Title | Book | Depth |")
        out.append("| --- | --- | --- | --- | --- |")
        for c in (c for c in CHAPTERS if c.phase == phase):
            link = f"[{c.title}](learning_modules/chapter_{chapter_stem(c)}.md)"
            out.append(f"| [ ] | {c.num:02d} | {link} | {c.book} | {c.depth} |")
    out.append(OUTRO)
    return "\n".join(out)


if __name__ == "__main__":
    (ROOT / "README.md").write_text(build())
