# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Project Overview

A standalone, 24-chapter (00-23) **Intro to GitHub Actions** curriculum for a practitioner who
knows Git and Python. Content/authoring repo: the product is chapters + paired notebooks +
lab scripts; the Python package (`intro_gha`) and tests exist to support and validate it.
It is simultaneously the live lab: `.github/workflows/` holds real workflows that fire on this
repo (demos are path-filtered to `sandbox/**` or `workflow_dispatch`).

The course is **self-contained**: it does not depend on or link to sibling courses.
Canonical book: Laster, *Learning GitHub Actions* (`proj_Git/books_proj_Git/learninggithubactions.pdf`).
Verify every behavioral claim against current GitHub Docs and cite it, dated, in section 19.

**Running example:** *Tally*, a tiny Python repo in `sandbox/tally/`. Each chapter grows
its workflow one step, from a single green check (Ch 03) to CI -> release -> deploy (Ch 23).

## Architecture

- `learning_modules/chapter_XX_<slug>.md`: the reading (20 sections + Appendix A).
- `notebooks/lab_XX_<slug>.ipynb` + `practice_XX.ipynb`: paired; practice = lab with empty code cells.
- `labs/lab_XX_<slug>.py`: offline-by-default scripts (`GHA_MODE=fixture|live`).
- `src/intro_gha/`: shared helpers (workflow loader, matrix expander, trigger/path filters,
  cost arithmetic, chapter registry `chapters.py`).
- `sandbox/tally/`: the running-example app and its tests. `fixtures/`: event/run payloads.
- `.github/workflows/`: `ci.yml` + `chXX-<topic>.yml` demos. `.github/instructions/`: format contracts.
- `.github/skills/_shared/depth-spine.md`: the mandatory depth standard. Read it before writing a chapter.
- `scripts/validate_chapters.py`: structural validator. `tests/` enforces the contracts.

## Essential Commands

```bash
uv sync --group core
uv run ruff check .
uv run pytest
uv run python scripts/validate_chapters.py [chapter_XX]
actionlint .github/workflows/*.yml
make lab-03            # run a lab script offline
```

## Conventions

- Namespace `intro_gha`; env prefix `GHA_` (`GHA_MODE`, `GHA_REPO`, `GHA_OUTPUT_DIR`).
- **Every `.py` file needs module, function and class docstrings** (user's global rule); type hints; `pathlib.Path`.
- Workflows: explicit top-level `permissions:`; credential-dependent ones guarded by
  `if: vars.GHA_ENABLE_<X> == 'true'`; `actionlint` clean; SHA-pin third-party actions from Ch 16.
- Never write a token into source, notebook output, or logs.
- Don't make unrequested extra edits. Log progress in `notes/THINGS_TASK_TRACKER.md` and
  `notes/IMPROVEMENTS_SUMMARY.md`.

## Chapter Map (single source of truth; generated from `src/intro_gha/chapters.py`)

| Ch | Title | Practice | Reference | Script | Book | Depth |
| --- | --- | --- | --- | --- | --- | --- |
| 00 | Essentials: YAML, Git Refs, CI/CD Vocabulary | practice_00.ipynb | lab_00_essentials_yaml_git_cicd.ipynb | lab_00_essentials_yaml_git_cicd.py | Ch 1 | Core |
| 01 | Why Actions? Cost vs Scripts and Jenkins | practice_01.ipynb | lab_01_why_actions.ipynb | lab_01_why_actions.py | Ch 1 | Core |
| 02 | How Actions Works: Event, Workflow, Job, Step, Runner | practice_02.ipynb | lab_02_how_actions_works.ipynb | lab_02_how_actions_works.py | Ch 2 | Core |
| 03 | Workflow YAML Anatomy and Your First Green Check | practice_03.ipynb | lab_03_workflow_anatomy.ipynb | lab_03_workflow_anatomy.py | Ch 4 | Core |
| 04 | What's in an Action: uses, Marketplace, Versioning | practice_04.ipynb | lab_04_whats_in_an_action.ipynb | lab_04_whats_in_an_action.py | Ch 3 | Core |
| 05 | Runners: Hosted, Larger, Self-Hosted, ARC | practice_05.ipynb | lab_05_runners.ipynb | lab_05_runners.py | Ch 5 | Core |
| 06 | Events and Triggers in Depth | practice_06.ipynb | lab_06_events_and_triggers.ipynb | lab_06_events_and_triggers.py | Ch 4 | Core |
| 07 | Contexts, Expressions and Conditionals | practice_07.ipynb | lab_07_contexts_expressions.ipynb | lab_07_contexts_expressions.py | Ch 8 | Core |
| 08 | Variables, Secrets, Configuration and Environments | practice_08.ipynb | lab_08_variables_secrets_environments.ipynb | lab_08_variables_secrets_environments.py | Ch 6 | Core |
| 09 | Data Between Steps and Jobs: Outputs, Artifacts, Caching | practice_09.ipynb | lab_09_data_outputs_artifacts_caching.ipynb | lab_09_data_outputs_artifacts_caching.py | Ch 7 | Core |
| 10 | Execution Control: needs, Matrix, Concurrency, Timeouts | practice_10.ipynb | lab_10_execution_control.ipynb | lab_10_execution_control.py | Ch 8 | Core |
| 11 | CI for Python: Lint, Test, Coverage Matrix | practice_11.ipynb | lab_11_ci_for_python.ipynb | lab_11_ci_for_python.py | Ch 4, 7 | Core |
| 12 | Containers, Service Containers and GHCR | practice_12.ipynb | lab_12_containers_and_ghcr.ipynb | lab_12_containers_and_ghcr.py | Ch 5, 12 | Core |
| 13 | Continuous Deployment: Environments and OIDC | practice_13.ipynb | lab_13_continuous_deployment.ipynb | lab_13_continuous_deployment.py | Ch 6, 9 | Core |
| 14 | Release Automation: Tags, Changelogs, Packages | practice_14.ipynb | lab_14_release_automation.ipynb | lab_14_release_automation.py | Ch 12 | Core |
| 15 | GITHUB_TOKEN, Permissions and Least Privilege | practice_15.ipynb | lab_15_token_and_permissions.ipynb | lab_15_token_and_permissions.py | Ch 9 | Core |
| 16 | Supply-Chain Security: Pinning, Injection, Attestations | practice_16.ipynb | lab_16_supply_chain_security.ipynb | lab_16_supply_chain_security.py | Ch 9 | Core |
| 17 | Monitoring, Logging and Debugging | practice_17.ipynb | lab_17_monitoring_debugging.ipynb | lab_17_monitoring_debugging.py | Ch 10 | Core |
| 18 | Cost, Performance and Limits | practice_18.ipynb | lab_18_cost_performance_limits.ipynb | lab_18_cost_performance_limits.py | Ch 5, 10 | Core |
| 19 | Custom Actions: Composite, JavaScript, Docker | practice_19.ipynb | lab_19_custom_actions.ipynb | lab_19_custom_actions.py | Ch 11 | Core |
| 20 | Reusable Workflows and Workflow Templates | practice_20.ipynb | lab_20_reusable_workflows.ipynb | lab_20_reusable_workflows.py | Ch 12 | Core |
| 21 | Advanced Techniques: Dynamic Matrices, github-script, ChatOps | practice_21.ipynb | lab_21_advanced_techniques.ipynb | lab_21_advanced_techniques.py | Ch 13 | Optional Deep-Dive |
| 22 | Migrating to Actions: Jenkins, GitLab, Importer | practice_22.ipynb | lab_22_migrating_to_actions.ipynb | lab_22_migrating_to_actions.py | Ch 14 | Optional Deep-Dive |
| 23 | Capstone: The Full Tally Pipeline | practice_23.ipynb | lab_23_capstone.ipynb | lab_23_capstone.py | all | Core |

Phases: 1 Foundations (00-05) | 2 Core Mechanics (06-10) | 3 Real Pipelines (11-14) |
4 Security & Operations (15-18) | 5 Extending (19-23).

## Live-Demo Limits

Not demonstrable live without owner-only credentials: Ch 13 OIDC to a cloud, Ch 14 PyPI
publish, Ch 05 self-hosted runners/ARC. These are taught offline and `actionlint`-validated,
with guarded workflows that skip rather than fail.
