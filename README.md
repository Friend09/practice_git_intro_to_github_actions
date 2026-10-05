# Intro to GitHub Actions

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


### Phase 1: Foundations

| Done | Ch | Title | Book | Depth |
| --- | --- | --- | --- | --- |
| [x] | 00 | [Essentials: YAML, Git Refs, CI/CD Vocabulary](learning_modules/chapter_00_essentials_yaml_git_cicd.md) | Ch 1 | Core |
| [x] | 01 | [Why Actions? Cost vs Scripts and Jenkins](learning_modules/chapter_01_why_actions.md) | Ch 1 | Core |
| [x] | 02 | [How Actions Works: Event, Workflow, Job, Step, Runner](learning_modules/chapter_02_how_actions_works.md) | Ch 2 | Core |
| [x] | 03 | [Workflow YAML Anatomy and Your First Green Check](learning_modules/chapter_03_workflow_anatomy.md) | Ch 4 | Core |
| [x] | 04 | [What's in an Action: uses, Marketplace, Versioning](learning_modules/chapter_04_whats_in_an_action.md) | Ch 3 | Core |
| [x] | 05 | [Runners: Hosted, Larger, Self-Hosted, ARC](learning_modules/chapter_05_runners.md) | Ch 5 | Core |

### Phase 2: Core Mechanics

| Done | Ch | Title | Book | Depth |
| --- | --- | --- | --- | --- |
| [x] | 06 | [Events and Triggers in Depth](learning_modules/chapter_06_events_and_triggers.md) | Ch 4 | Core |
| [x] | 07 | [Contexts, Expressions and Conditionals](learning_modules/chapter_07_contexts_expressions.md) | Ch 8 | Core |
| [x] | 08 | [Variables, Secrets, Configuration and Environments](learning_modules/chapter_08_variables_secrets_environments.md) | Ch 6 | Core |
| [x] | 09 | [Data Between Steps and Jobs: Outputs, Artifacts, Caching](learning_modules/chapter_09_data_outputs_artifacts_caching.md) | Ch 7 | Core |
| [x] | 10 | [Execution Control: needs, Matrix, Concurrency, Timeouts](learning_modules/chapter_10_execution_control.md) | Ch 8 | Core |

### Phase 3: Real Pipelines

| Done | Ch | Title | Book | Depth |
| --- | --- | --- | --- | --- |
| [x] | 11 | [CI for Python: Lint, Test, Coverage Matrix](learning_modules/chapter_11_ci_for_python.md) | Ch 4, 7 | Core |
| [x] | 12 | [Containers, Service Containers and GHCR](learning_modules/chapter_12_containers_and_ghcr.md) | Ch 5, 12 | Core |
| [ ] | 13 | [Continuous Deployment: Environments and OIDC](learning_modules/chapter_13_continuous_deployment.md) | Ch 6, 9 | Core |
| [ ] | 14 | [Release Automation: Tags, Changelogs, Packages](learning_modules/chapter_14_release_automation.md) | Ch 12 | Core |

### Phase 4: Security & Operations

| Done | Ch | Title | Book | Depth |
| --- | --- | --- | --- | --- |
| [ ] | 15 | [GITHUB_TOKEN, Permissions and Least Privilege](learning_modules/chapter_15_token_and_permissions.md) | Ch 9 | Core |
| [ ] | 16 | [Supply-Chain Security: Pinning, Injection, Attestations](learning_modules/chapter_16_supply_chain_security.md) | Ch 9 | Core |
| [ ] | 17 | [Monitoring, Logging and Debugging](learning_modules/chapter_17_monitoring_debugging.md) | Ch 10 | Core |
| [ ] | 18 | [Cost, Performance and Limits](learning_modules/chapter_18_cost_performance_limits.md) | Ch 5, 10 | Core |

### Phase 5: Extending Actions

| Done | Ch | Title | Book | Depth |
| --- | --- | --- | --- | --- |
| [ ] | 19 | [Custom Actions: Composite, JavaScript, Docker](learning_modules/chapter_19_custom_actions.md) | Ch 11 | Core |
| [ ] | 20 | [Reusable Workflows and Workflow Templates](learning_modules/chapter_20_reusable_workflows.md) | Ch 12 | Core |
| [ ] | 21 | [Advanced Techniques: Dynamic Matrices, github-script, ChatOps](learning_modules/chapter_21_advanced_techniques.md) | Ch 13 | Optional Deep-Dive |
| [ ] | 22 | [Migrating to Actions: Jenkins, GitLab, Importer](learning_modules/chapter_22_migrating_to_actions.md) | Ch 14 | Optional Deep-Dive |
| [ ] | 23 | [Capstone: The Full Tally Pipeline](learning_modules/chapter_23_capstone.md) | all | Core |

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
