# Chapter 22: Migrating to Actions: Jenkins, GitLab, Importer

**Reading Time:** ~55 minutes
**Prerequisites:** Chapter 03 (workflow anatomy), Chapter 05 (runners), Chapter 07 (expressions), Chapter 10 (`needs`, matrix), Chapter 18 (billing)
**Practice Notebook:** `notebooks/practice_22.ipynb`
**Reference Notebook:** `notebooks/lab_22_migrating_to_actions.ipynb`
**Script:** `labs/lab_22_migrating_to_actions.py`
**Book Reference:** Laster, Learning GitHub Actions Ch 14 / GitHub Docs: Migrating to GitHub Actions
**Depth:** Optional Deep-Dive
**Default Runtime:** Offline fixtures

---

## Beginner's Guide

> ⭐ **Optional deep-dive.** Read this only if you have an existing Jenkins or GitLab CI pipeline to move. Nothing later in the course depends on it.

**Focus on first:** Section 3 (the concept map) and Section 6 (the one Jenkins feature with no keyword in Actions, and a real run showing what replaces it).

**Skip on first read:** Sections 8, 11 and 12.

**Key concepts in plain English:**

- **Migration:** moving a pipeline's _behavior_, not its syntax. A line-by-line translation can pass and still behave differently.
- **Concept map:** a table saying which Jenkins or GitLab construct corresponds to which Actions construct.
- **Importer:** GitHub's tool that converts a pipeline to a workflow automatically. It gets you most of the way; a human reviews the rest.
- **`post`:** a Jenkins block that runs after the stages whatever happened. Actions has no such keyword.

**If you know Jenkins or GitLab already**, treat this chapter as a diff: Sections 3-7 list where your habits stop working, each verified on a real run.

> **🔬 Platform Engineer's Lens:** Migrations fail quietly in the _error paths_. The happy path converts easily, and the first red build is where a dropped `post` block or a changed condition shows up, usually weeks later. This chapter runs the same translated pipeline green and red on purpose so the error-path behavior is observed, not assumed.

> **🚦 Native vs Marketplace vs Custom:** For conversion, the **native** answer is the GitHub Actions Importer (a first-party tool). For individual steps, prefer a Marketplace action only where a keyword does not exist (caching, artifacts). Writing your own converter, as we do here, is a **teaching model**, not a recommendation.

## What You'll Learn

- Map Jenkins and GitLab CI constructs to workflow keys
- Turn stage order into `needs` and predict the resulting waves
- Replace Jenkins `post` with `if: always()` and job-level `failure()`, and see why step-level `failure()` is not the same
- Explain what the Importer's `audit`, `forecast`, `dry-run` and `migrate` do, and what it does not do
- Review a converted workflow for dropped constructs
- Count what a split pipeline costs in billed minutes

## Table of Contents

<!-- toc-start -->

- [Chapter 22: Migrating to Actions: Jenkins, GitLab, Importer](#chapter-22-migrating-to-actions-jenkins-gitlab-importer)
  - [Beginner's Guide](#beginners-guide)
  - [What You'll Learn](#what-youll-learn)
  - [Table of Contents](#table-of-contents)
  - [1. Why Migrate, and When Not To](#1-why-migrate-and-when-not-to)
  - [2. Running Example: Tally's Old Pipelines](#2-running-example-tallys-old-pipelines)
  - [3. The Concept Map](#3-the-concept-map)
  - [4. Translating the Pipeline: Stages Become `needs`](#4-translating-the-pipeline-stages-become-needs)
  - [5. Agents, Images and Tags](#5-agents-images-and-tags)
  - [6. `post` Has No Keyword](#6-post-has-no-keyword)
  - [7. Conditions: `when` and `rules` Become `if`](#7-conditions-when-and-rules-become-if)
  - [8. Caching, Artifacts and Credentials](#8-caching-artifacts-and-credentials)
  - [9. The GitHub Actions Importer](#9-the-github-actions-importer)
  - [10. Testing a Translation Locally](#10-testing-a-translation-locally)
  - [11. Observability](#11-observability)
  - [12. Limits and Cost Differences](#12-limits-and-cost-differences)
  - [13. Case Study: The Migration That Stopped Reporting Failures](#13-case-study-the-migration-that-stopped-reporting-failures)
  - [14. Comparison: Migration Approaches](#14-comparison-migration-approaches)
  - [15. Practical Tips](#15-practical-tips)
  - [16. Demonstrated Failure Modes](#16-demonstrated-failure-modes)
  - [17. Key Takeaways](#17-key-takeaways)
  - [18. Exercises](#18-exercises)
  - [19. Additional Resources](#19-additional-resources)
  - [20. Appendix A: Code Index](#20-appendix-a-code-index)
    - [A.1 Convert a GitLab file and read its waves](#a1-convert-a-gitlab-file-and-read-its-waves)
    - [A.2 Price a split pipeline](#a2-price-a-split-pipeline)

## 1. Why Migrate, and When Not To

Reasons that hold up: one platform for code and automation; hosted runners instead of maintaining Jenkins agents; the Marketplace; permissions tied to the repository. Reasons that do not: "it is newer". A pipeline that works, is cheap to run, and has an owner may not be worth moving. The honest cost of migrating is the **error paths and the long tail**: the 20% of a pipeline that is not `script:` lines.

GitHub's own docs state a target of "an 80% conversion rate for every workflow", with the actual rate depending on the pipeline, and say converted workflows "should be inspected for correctness before using it as a production workload" (docs, verified 2026-10). Plan for the other 20%.

## 2. Running Example: Tally's Old Pipelines

> 📌 **Running Example: Tally on Jenkins and on GitLab.** Suppose Tally's CI had lived on two other platforms. Both files are in `sandbox/ch22/` and neither is run in this course; they are the _source_.
>
> - `Jenkinsfile` (Declarative): agent `docker { image 'python:3.12-slim' }`; `environment { TALLY_COLOR = 'blue' }`; a 10-minute timeout; three stages (**Lint**, **Test**, **Deploy**, the last with `when { branch 'main' }`); a `post` block with `always { archiveArtifacts ... }` and `failure { echo ... }`.
> - `gitlab-ci.yml`: `stages: [lint, test, deploy]`, a default image `python:3.12-slim`, a `variables:` block, jobs `lint`, `test` (with `tags`, `cache`, `artifacts`) and `deploy` (with a `rules:` condition on `main`).
>
> Our target is `.github/workflows/ch22-translated.yml`, translated by hand and run live. We return to it throughout Sections 3-7 and 10-13.

## 3. The Concept Map

From the GitHub docs' migration guides (verified 2026-10):

| Jenkins            | GitLab CI                 | GitHub Actions                                                 |
| ------------------ | ------------------------- | -------------------------------------------------------------- |
| `pipeline`         | the file                  | a workflow file                                                |
| `stages` / `stage` | `stages:` + `stage:`      | `jobs`, ordered only by `needs`                                |
| `steps` / `sh`     | `script:`                 | `steps` / `run`                                                |
| `agent`            | `tags` (runner) / `image` | `runs-on` and/or `container`                                   |
| `environment`      | `variables`               | `env`                                                          |
| `when`             | `rules: - if:`            | `if:`                                                          |
| `post`             | `after_script` (loosely)  | **no keyword** (docs table says "None")                        |
| `parallel`         | jobs in the same stage    | jobs without `needs` (default); `max-parallel` limits a matrix |
| cache              | `cache:`                  | `actions/cache`                                                |
| artifacts          | `artifacts:`              | `actions/upload-artifact`                                      |

**What to notice:**

- Stage order is **implicit** in Jenkins and GitLab (stages run in sequence) and **explicit** in Actions: a job with no `needs` starts immediately. The most common silent change in a migration is that "stages" run all at once.
- The docs' Jenkins page maps `parallel` to `max-parallel`. That is loose: parallelism is the default in Actions, and `max-parallel` only caps a matrix.
- Cache and artifacts are **actions**, not keywords.

## 4. Translating the Pipeline: Stages Become `needs`

Our model (`intro_gha.migrate.gitlab_to_workflow`) converts the GitLab file's stage order into `needs`. Trace for `gitlab-ci.yml`:

| Step                                       | State                                                |
| ------------------------------------------ | ---------------------------------------------------- |
| Read `stages`                              | `[lint, test, deploy]`                               |
| Group jobs by stage                        | `lint: [lint]`, `test: [test]`, `deploy: [deploy]`   |
| Each job `needs` the previous stage's jobs | `test needs [lint]`, `deploy needs [test]`           |
| `execution_waves` (Chapter 10)             | `[[lint], [test], [deploy]]`: three sequential waves |

**What to notice:** drop the `needs` and the waves become `[[deploy, lint, test]]`, one wave of three. Same file, different behavior, no error. That is the failure to look for first.

## 5. Agents, Images and Tags

`agent { docker { image ... } }` and GitLab `image:` both map to `container:`; `tags` and agent labels map to `runs-on`. In our translation each job has `runs-on: ubuntu-latest` and `container: python:3.12-slim`.

One observed detail: inside the slim image there is **no `git`**, and `actions/checkout` fell back to downloading a **tarball** (the log shows `tar xz`) instead of cloning. It worked, but the checkout has no `.git` directory, so any step that runs `git log` would fail. We did not test which common steps break.

The GitLab `tags: [linux]` has no direct meaning here: tags select _your_ runners, while `ubuntu-latest` is a GitHub-hosted label. The model reports it as a note rather than guess.

## 6. `post` Has No Keyword

Jenkins runs `post { always { ... } failure { ... } }` after the stages. Actions has no such keyword; the docs table says "None". The replacement is a **final job** that depends on the others and runs whatever happened:

```yaml
post:
  needs: [lint, test, deploy]
  if: ${{ always() }}
```

Three real runs of `ch22-translated.yml` (a `fail` input forces the test stage to exit 1):

| Run                        | lint    | test        | deploy      | post                                       |
| -------------------------- | ------- | ----------- | ----------- | ------------------------------------------ |
| `fail=false` (37337727565) | success | success     | success     | success; saw `success/success/success`     |
| `fail=true` (37337741533)  | success | **failure** | **skipped** | **success**; saw `success/failure/skipped` |

**What to notice:** with `if: always()` the `post` job ran after a failure and could read each upstream result through `needs.<job>.result`. Without it, `post` would have been skipped like `deploy`.

**The trap we hit: `failure()` is not the same at job and step level.** We added a step to `post` with `if: ${{ failure() }}`, expecting it to play Jenkins' `post { failure }`. In run 37337741533 that step was **skipped**. A run adding a separate job with `needs: [test]` and `if: ${{ failure() }}` (run 37338093415) **ran**:

| Where `failure()` is used                     | Upstream `test` failed    | Observed    |
| --------------------------------------------- | ------------------------- | ----------- |
| Job-level `if:` on a job that `needs: [test]` | yes                       | **ran**     |
| Step-level `if:` inside the `post` job        | yes (a direct dependency) | **skipped** |

The docs say `failure()` "Returns `true` when any previous step of a job fails. If you have a chain of dependent jobs, `failure()` returns `true` if any ancestor job fails." Our step-level observation does not match the second sentence. We did not find why; we report what ran. To get a "failure" branch inside the `post` job, test the result explicitly:

```yaml
- if: ${{ needs.test.result == 'failure' }}
```

(We did not run that exact expression; it follows from the `needs.test.result` value the `post` job did read as `failure`.)

## 7. Conditions: `when` and `rules` Become `if`

`when { branch 'main' }` and `rules: - if: '$CI_COMMIT_BRANCH == "main"'` both become a job-level `if: github.ref == 'refs/heads/main'`. On the `main` run `deploy` ran; in the failing run it was skipped because its `needs` failed, not because of the branch. Two different reasons, one `skipped` label (Chapter 10). A condition that is wrong for tags or pull requests will not error; it just skips. Check `github.ref` for each trigger you keep (Chapter 06).

GitLab `rules` can express `when: manual`, `allow_failure` and variable matching; none has a one-line `if:`. The model reports `rules` as a note for a human.

## 8. Caching, Artifacts and Credentials

> ⚠️ ADVANCED TOPIC: Skip on first read.

- **Cache:** add `actions/cache` with an explicit key (Chapter 09). GitLab's path-only `cache` has no key semantics to copy.
- **Artifacts:** add `actions/upload-artifact`. Jenkins' `archiveArtifacts` inside `post { always }` becomes an upload step in the final job with `if: always()`; GitLab's `artifacts: when: always` is the same idea.
- **Credentials:** Jenkins `credentials()` and GitLab masked variables become **secrets**, scoped through environments when they must be protected (Chapter 08). Re-create the values; they cannot be exported from the old system.

## 9. The GitHub Actions Importer

From the docs (verified 2026-10): it supports "Azure DevOps, Bamboo, Bitbucket Pipelines, CircleCI, GitLab (both cloud and self-hosted), Jenkins, Travis CI"; it is "distributed as a Docker container, and uses a GitHub CLI extension" installed with `gh extension install github/gh-actions-importer`. Its commands:

| Command    | Purpose (docs wording)                                                |
| ---------- | --------------------------------------------------------------------- |
| `audit`    | "Plan your CI/CD migration by analyzing your current CI/CD footprint" |
| `forecast` | reviews historical usage to forecast Actions usage                    |
| `dry-run`  | converts pipelines and writes the workflow to your local filesystem   |
| `migrate`  | converts a pipeline and opens a pull request                          |

> **We did not run the Importer.** It is not installed here (`gh actions-importer` is an unknown command), it needs Docker and credentials for the source system, and this course has no Jenkins or GitLab server. Everything above is from the docs. The part we _did_ test is the manual translation it automates.

Use the order the docs imply: `audit` to size the job, `forecast` for cost, `dry-run` to read what it produces, and only then `migrate`.

## 10. Testing a Translation Locally

Before running anything on a runner:

```bash
uv run python -c "import yaml; from intro_gha.migrate import gitlab_to_workflow as g; \
print(g(yaml.safe_load(open('sandbox/ch22/gitlab-ci.yml')))[1])"
actionlint .github/workflows/ch22-translated.yml
```

The first prints the model's **notes**: for our file, `tags`, `rules`, `cache` and `artifacts` are each reported, never silently dropped. The second catches syntax and expression errors. Neither proves behavior: only a run does, which is why Section 6 uses `workflow_dispatch` with a failure switch.

`jenkins_inventory` counts constructs in a Jenkinsfile the way an audit would. For ours: 3 `stage`, 3 `sh` steps, 1 `when`, 1 `post`, 1 `agent docker`.

## 11. Observability

> ⚠️ ADVANCED TOPIC: Skip on first read.

- Job names in the run come from the **job ids**, so keep the old stage names (`lint`, `test`, `deploy`) to keep dashboards and branch-protection rules readable.
- A required status check (Chapter 08) is matched by **job name**; renaming a job during migration silently removes the requirement.
- `needs.<job>.result` is the Actions counterpart of Jenkins' `currentBuild.result` for the final job.

## 12. Limits and Cost Differences

> ⚠️ ADVANCED TOPIC: Skip on first read.

A Jenkins build on your own agent costs nothing per minute; on hosted runners every job rounds up to a whole minute (Chapter 18; Linux $0.006 per minute). A one-job-per-stage translation of a short pipeline therefore bills **per job**: our four-job pipeline bills at least 4 minutes ($0.024) per green run, even if the stages total 40 seconds. The failing run billed fewer (3 jobs ran; `deploy` was skipped and a skipped job has no runner time). Merge tiny stages into one job (Chapter 18) unless you need the isolation.

## 13. Case Study: The Migration That Stopped Reporting Failures

A team migrates a Jenkins pipeline whose `post { failure { notify } }` block posts to chat. In the translation, the notify is a step with `if: failure()` in a final `post` job. Weeks later a deployment breaks and nobody is told. The step was never running: `failure()` at step level inside a _different_ job did not fire (Section 6). The happy-path migration test passed because the step is skipped when everything is green, exactly as it should be. The fix is a job-level `if: failure()` job (observed to run) or an explicit `needs.<job>.result` check, **plus a migration test that makes a stage fail on purpose**. (The scenario is constructed; the skipped step is observed.)

## 14. Comparison: Migration Approaches

| Approach                          | Setup Effort                                | Control                      | Failure Visibility                     | Security Exposure                          | Maintenance Burden  |
| --------------------------------- | ------------------------------------------- | ---------------------------- | -------------------------------------- | ------------------------------------------ | ------------------- |
| Manual rewrite                    | High                                        | Full                         | Excellent if you test error paths      | Low                                        | Low once done       |
| Importer `dry-run` then edit      | Moderate - needs Docker, source credentials | Moderate - you review output | Fair - gaps are in the unconverted 20% | Moderate - holds source-system credentials | Low                 |
| Importer `migrate` (PR)           | Moderate                                    | Low until reviewed           | Fair                                   | Moderate                                   | Low                 |
| Run both in parallel for a period | Moderate                                    | High                         | Excellent - compare results            | Low                                        | Temporarily doubled |
| Stay on the old system            | None                                        | Full                         | Whatever you have                      | Whatever you have                          | Ongoing             |

## 15. Practical Tips

- Convert the **error paths** first: make a stage fail and confirm the final job and notifications behave.
- Keep job ids equal to the old stage names.
- Add `needs` deliberately; stages are not implicit in Actions.
- Use `if: always()` on the final job; use job-level `failure()` or `needs.<job>.result` for failure-only work.
- Run old and new pipelines side by side until the results agree.
- Re-create secrets; do not hunt for an export.
- Pin third-party actions by SHA from the start (Chapter 16).

## 16. Demonstrated Failure Modes

**Failure 1: stages that ran all at once (modelled).** Without `needs`, three stage-jobs form one wave. `execution_waves` shows `[[deploy, lint, test]]` against `[[lint], [test], [deploy]]`.

**Failure 2: the dead `failure()` step (observed).** Step-level `if: failure()` in the `post` job was `skipped` after `test` failed (run 37337741533); a job-level `failure()` job ran (run 37338093415).

**Failure 3: the unreadable skip.** `deploy` shows `skipped` both when its branch condition is false and when its `needs` failed. Read `needs.<job>.result` to tell them apart.

**Failure 4: the checkout with no git (observed behavior).** In `python:3.12-slim`, checkout downloaded a tarball; there is no repository history.

## 17. Key Takeaways

- Migrate behavior, not syntax; the error paths are the risk.
- Stage order becomes explicit `needs`.
- `post` has no keyword: use a final job with `if: always()`.
- Job-level `failure()` ran; step-level `failure()` in the final job was skipped in our run.
- The Importer (`audit`, `forecast`, `dry-run`, `migrate`) targets about 80% conversion and needs review; we did not run it.
- Cache, artifacts and credentials are actions or secrets, not keywords.
- Each job rounds up to a minute: a split pipeline bills per job.

## 18. Exercises

1. A GitLab file has `stages: [build, test]`, jobs `build_a` and `build_b` in `build`, and `test_ab` in `test`. Write the `needs` and give the waves.
2. Which Actions construct replaces Jenkins `post { always { ... } }`, and what happens to it if you leave out `if: always()` and an upstream job fails?
3. In run 37337741533 `post` read `lint=success test=failure deploy=skipped`. Write the step `if:` that runs only when `test` failed, using that value.
4. You rename the job `test` to `unit` during migration, and branch protection requires `test`. What happens to the requirement?
5. (Hand arithmetic) Your pipeline has four stages of 20, 30, 15 and 25 seconds. As four jobs on Linux, how many billed minutes and dollars per green run? As one job?

<details>
<summary>Answers</summary>

1. `test_ab` has `needs: [build_a, build_b]`. Waves: `[[build_a, build_b], [test_ab]]`.
2. A final job that `needs` the others with `if: ${{ always() }}`. Without it, the job is skipped when a dependency fails, like `deploy` was.
3. `if: ${{ needs.test.result == 'failure' }}` (or an env-variable comparison). We saw the value `failure` in the report; we did not run this exact expression.
4. The required check named `test` no longer exists, so it is never reported; depending on settings the requirement can block merging or stop protecting. Keep the old job id or update the rule. Chapter 16 Section 5 measured this: with the rule naming a check nothing reports, an all-green PR stayed `blocked`.
5. Four jobs: each rounds up to 1 minute, so 4 billed minutes = 4 x $0.006 = **$0.024**. One job: 90 seconds rounds up to 2 minutes = **$0.012**.

</details>

## 19. Additional Resources

All verified 2026-10.

- GitHub Docs, [Automating migration with GitHub Actions Importer](https://docs.github.com/en/actions/migrating-to-github-actions/automated-migrations/automating-migration-with-github-actions-importer) (supported platforms, commands, Docker/CLI, 80% target)
- GitHub Docs, [Migrating from GitLab CI/CD to GitHub Actions](https://docs.github.com/en/actions/migrating-to-github-actions/manually-migrating-to-github-actions/migrating-from-gitlab-cicd-to-github-actions)
- GitHub Docs, [Migrating from Jenkins to GitHub Actions](https://docs.github.com/en/actions/migrating-to-github-actions/manually-migrating-to-github-actions/migrating-from-jenkins-to-github-actions) (concept table; `post` "None")
- GitHub Docs, [Expressions: status check functions](https://docs.github.com/en/actions/reference/workflows-and-actions/expressions) (`failure()`, `always()`)
- GitHub Docs, [Workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax) (`needs`, `container`, `if`)
- Laster, _Learning GitHub Actions_ (O'Reilly), Chapter 14

## 20. Appendix A: Code Index

> 💻 Complete, runnable code for this chapter. Skip when reading for concepts.

### A.1 Convert a GitLab file and read its waves

```python
import yaml

from intro_gha import REPO_ROOT
from intro_gha.migrate import gitlab_to_workflow
from intro_gha.workflow import execution_waves

doc = yaml.safe_load((REPO_ROOT / "sandbox" / "ch22" / "gitlab-ci.yml").read_text())
workflow, notes = gitlab_to_workflow(doc)
graph = {job: spec.get("needs", []) for job, spec in workflow["jobs"].items()}
assert execution_waves(graph) == [["lint"], ["test"], ["deploy"]]
no_needs = {job: [] for job in graph}
assert execution_waves(no_needs) == [["deploy", "lint", "test"]]   # stages lost
assert any("rules" in n for n in notes)
```

**Flow:** convert; build the `needs` graph; compute waves; remove `needs` to see the failure; confirm unmapped `rules` was reported.

### A.2 Price a split pipeline

```python
from intro_gha.cost import billed_minutes

stages = [20, 30, 15, 25]                     # seconds
split = sum(billed_minutes(s) for s in stages)
single = billed_minutes(sum(stages))
assert (split, single) == (4, 2)
assert split * 6 == 24 and single * 6 == 12   # mills at $0.006 per Linux minute
```

**Flow:** each job rounds up on its own, so four short jobs bill 4 minutes against 2 for one job running the same 90 seconds.
