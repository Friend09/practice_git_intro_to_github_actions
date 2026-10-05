# Chapter 12: Containers, Service Containers and GHCR

**Reading Time:** ~55 minutes
**Prerequisites:** Chapter 08 (permissions, secrets), Chapter 09 (outputs), Chapter 11 (a working pipeline)
**Practice Notebook:** `notebooks/practice_12.ipynb`
**Reference Notebook:** `notebooks/lab_12_containers_and_ghcr.ipynb`
**Script:** `labs/lab_12_containers_and_ghcr.py`
**Book Reference:** Laster, Learning GitHub Actions Ch 5, 12 / GitHub Docs: Service containers, Publishing packages with Actions
**Depth:** Core
**Default Runtime:** Live repo

---

## Beginner's Guide

**Focus on first:** Sections 3 (a job that runs inside a container), 4 (a database next to your tests) and 6 (publishing an image, and the two ways it fails).

**Skip on first read:** Sections 10-12 (build caching, attestations, package cleanup).

**Key concepts in plain English:**

- **Container:** a lightweight, isolated environment built from an **image** (a packaged filesystem).
- **Container job:** a job whose steps run *inside* a container instead of directly on the runner VM.
- **Service container:** a helper container (a database, a cache) that starts beside your job and is thrown away after.
- **Registry:** a server that stores images. **GHCR** (`ghcr.io`) is GitHub's.
- **Digest:** the content hash of an image (`sha256:...`). A **tag** (`latest`) is a movable label for a digest.

**If you have run `docker compose up` for a test database**, a service container is that, started for you and removed afterwards.

> **🔬 Platform Engineer's Lens:** An image you publish is a deliverable other systems will pull and run, so its identity matters. A tag can be re-pointed; a digest cannot. Every deploy that references `:latest` is trusting that nobody pushed something else since you looked. This chapter publishes a real image, verifies it by digest in a second job, and shows the two failures that stop most first attempts.

> **🚦 Native vs Marketplace vs Custom:** Running a container job, starting a service container and logging in to GHCR with `GITHUB_TOKEN` are native features. For building we use plain `docker build` and `docker push`, which are installed on the runner, instead of a wrapper action; the Docker-maintained actions (`docker/build-push-action`, `docker/metadata-action`) add multi-platform builds, build caching and tag generation, and are worth adopting when you need those (Section 10).

## What You'll Learn

- Run a job inside a container and know what that changes
- Start a service container, wait for it to be healthy, and reach it
- State the networking rules for jobs on the runner versus jobs in a container
- Build an image and push it to GHCR using only `GITHUB_TOKEN`
- Explain the lowercase rule and the `packages: write` permission with their real error messages
- Verify a published image by digest in another job
- Read the visibility of a published package

## Table of Contents

<!-- TOC -->
- [1. Three Uses of Containers](#1-three-uses-of-containers)
- [2. Running Example: Tally in a Box](#2-running-example-tally-in-a-box)
- [3. Container Jobs](#3-container-jobs)
- [4. Service Containers](#4-service-containers)
- [5. Building an Image](#5-building-an-image)
- [6. Pushing to GHCR with `GITHUB_TOKEN`](#6-pushing-to-ghcr-with-github_token)
- [7. Tags Move, Digests Do Not](#7-tags-move-digests-do-not)
- [8. Visibility: Who Can Pull It?](#8-visibility-who-can-pull-it)
- [9. Image Size, Layers and Time](#9-image-size-layers-and-time)
- [10. Build Caching and Multi-Platform](#10-build-caching-and-multi-platform)
- [11. Provenance and Attestations](#11-provenance-and-attestations)
- [12. Cleaning Up Packages](#12-cleaning-up-packages)
- [13. Case Study: The Deploy That Ran Yesterday's Image](#13-case-study-the-deploy-that-ran-yesterdays-image)
- [14. Comparison: Ways to Build and Publish](#14-comparison-ways-to-build-and-publish)
- [15. Practical Tips](#15-practical-tips)
- [16. Demonstrated Failure Modes](#16-demonstrated-failure-modes)
- [17. Key Takeaways](#17-key-takeaways)
- [18. Exercises](#18-exercises)
- [19. Additional Resources](#19-additional-resources)
- [20. Appendix A: Code Index](#20-appendix-a-code-index)
   - [A.1 Image references and the published digest](#a1-image-references-and-the-published-digest)
<!-- /TOC -->

---

## 1. Three Uses of Containers

| Use | Syntax | Purpose |
| --- | --- | --- |
| Container job | `container: image` | Run all steps of a job in a chosen environment |
| Service container | `services:` | Run a dependency (database, cache) beside the job |
| Build and publish | `docker build` / `docker push` | Produce an image as the pipeline's output |

They solve different problems and combine freely.

## 2. Running Example: Tally in a Box

> 📌 **Running Example: `ch12-containers.yml`.** Six jobs in one run, **37322069271**. **service** starts a Redis service container and sends it `PING`. **in_container** runs inside `python:3.12-slim`. **uppercase_tag** tries to build an image tagged with the mixed-case owner `Friend09` (it should fail). **publish_denied** tries to push with only `contents: read` (it should fail). **publish** builds Tally's image from `sandbox/tally/Dockerfile` (`python:3.12-slim` plus the `tally/` package) and pushes it to `ghcr.io/friend09/tally`. **verify** `needs` publish, pulls the image **by digest** and runs it. Data: `fixtures/containers_ch12_summary.json`, `fixtures/containers_ch12_run.json`. We return to it throughout.

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY tally/ tally/
CMD ["python", "-c", "from tally.add import add; print(add(2, 3))"]
```

## 3. Container Jobs

```yaml
in_container:
  runs-on: ubuntu-latest
  container:
    image: python:3.12-slim
```

The runner VM is still `ubuntu-latest` (it hosts Docker), but every step now executes **inside** the container. What the real run reported from inside:

| Question | Answer |
| --- | --- |
| Operating system | **Debian GNU/Linux 13 (trixie)** (not the runner's Ubuntu) |
| Python | **3.12.15**, from the image |
| Is `git` installed? | **No** (`command -v git` printed nothing) |
| Did `actions/checkout` still work? | **Yes**: 20 top-level entries, `pyproject.toml` present |

The checkout log explains how, with no `git`:

```
The repository will be downloaded using the GitHub REST API
To create a local Git repository instead, add Git 2.18 or higher to the PATH
```

**What to notice:**

- A container job gives you a **reproducible toolchain**: the image, not whatever the runner has, decides the Python and OS. It is the Chapter 05 "runner label moves" problem solved by pinning an image tag (or better, a digest).
- `actions/checkout` degrades gracefully: with no `git` it downloads a tarball through the REST API. You get the **files** but **no `.git` directory**, so commands that need history (`git log`, version-from-tag tools) will fail. Install `git` in the image if you need it.
- The step's workspace path inside the container is `/__w/...`, mapped from the runner's workspace (visible in the checkout log).

## 4. Service Containers

```yaml
services:
  redis:
    image: redis:7-alpine
    ports:
      - 6379:6379
    options: >-
      --health-cmd "redis-cli ping" --health-interval 2s
      --health-timeout 3s --health-retries 10
```

GitHub starts the container before your steps, **waits for its health check**, and destroys it when the job ends (docs, verified 2026-10: "creates a fresh Docker container for each service configured in the workflow, and destroys the service container when the job completes"). The run's log shows the wait:

```
##[group]Waiting for all services to be ready
starting
healthy
redis service is healthy.
```

and the job's one step then opened a TCP connection to `localhost:6379`, sent `PING`, and read back `+PONG`. The whole job took 8 seconds.

**Networking, by docs (verified 2026-10):**

| Your job runs... | Reach the service at | Port mapping |
| --- | --- | --- |
| directly on the runner VM (this example) | `localhost:<mapped port>` | **required** (`ports: - 6379:6379`) |
| inside a container | the service's **label** as hostname (`redis:6379`) | not needed: containers on the same network expose all ports |

Service containers need an **Ubuntu (Linux)** runner on GitHub-hosted runners; Windows and macOS runners do not support them (docs). We tested only the on-runner case above.

> 📝 **Full implementation:** See [Appendix A.1](#a1-image-references-and-the-published-digest)

## 5. Building an Image

```bash
docker build \
  --label "org.opencontainers.image.source=https://github.com/OWNER/REPO" \
  -t ghcr.io/friend09/tally:<sha> -t ghcr.io/friend09/tally:latest .
```

Two tags on one image: the **commit SHA** (a unique, permanent name per build) and `latest` (a moving pointer). The `org.opencontainers.image.source` label is the standard way to record an image's source repository. We set it; the package ended up public (Section 8). We did not test publishing without it, so we cannot say what the label alone changes. The Docker CLI is preinstalled on the runner, so no setup action is needed.

The result: **6 layers, 47,236,038 compressed bytes (about 45 MiB)**, read from the registry's manifest. Almost all of it is the base image; our own `COPY` layer is a few kilobytes. The `publish` job took 23 seconds in total (build, login, two pushes), which on a private repo bills **1 minute** (Chapter 01).

## 6. Pushing to GHCR with `GITHUB_TOKEN`

No personal access token is needed. Docs (verified 2026-10): log in with the actor name and `GITHUB_TOKEN`, and give the job `packages: write`.

```yaml
publish:
  permissions:
    contents: read
    packages: write
  steps:
    - run: echo "$GH_TOKEN" | docker login ghcr.io -u "$GITHUB_ACTOR" --password-stdin
```

(`GH_TOKEN` is mapped from `${{ github.token }}` in `env:`, never pasted into the script.) The `permissions` block is what lets the token write packages (Chapter 15 covers what the token can do by default).

Two real ways it went wrong:

**Failure A: the uppercase owner.** The job `uppercase_tag` ran `docker build -t "ghcr.io/${GITHUB_REPOSITORY_OWNER}/tally:test"`. The owner is `Friend09`:

```
ERROR: failed to build: invalid tag "ghcr.io/Friend09/tally:test": repository name must be lowercase
```

Registries require lowercase repository names, but GitHub usernames are mixed case. The fix used everywhere in our workflow is Bash lowercasing: `owner="${GITHUB_REPOSITORY_OWNER,,}"`.

**Failure B: no `packages: write`.** The job `publish_denied` had only `contents: read` and tried the same push:

```
The push refers to repository [ghcr.io/friend09/tally-denied]
denied: installation not allowed to Create organization package
```

The wording says "organization package" even though this is a user-owned repo; the platform message is generic. What matters: the login **succeeded** (read access) and the **push** was refused. The package `tally-denied` was never created (the packages API answered `404 Package not found`).

> **Spot-the-diff.** Two jobs, identical except one line. `publish_denied`: `permissions: { contents: read }`. `publish`: `permissions: { contents: read, packages: write }`. Same Dockerfile, same commands. Only the second can push.

## 7. Tags Move, Digests Do Not

After `docker push`, the registry assigns the image a **digest**. The `publish` job read it and exposed it as an output (Chapter 09):

```
sha256:a54376929fa5cf6437159c5653bba212f72914f8ed35810654f24973bc94d21b
```

The `verify` job `needs` publish, receives that output, and pulls **by digest**, not by tag:

```
docker pull ghcr.io/friend09/tally@sha256:a5437692...
docker run --rm ghcr.io/friend09/tally@sha256:a5437692...      # prints 5
```

It printed `5` (Tally's `add(2, 3)`), proving the exact bytes that were published are the bytes that ran.

| Reference | Style | Can change under you? |
| --- | --- | --- |
| `ghcr.io/friend09/tally:latest` | tag | **Yes**: the next push re-points it |
| `ghcr.io/friend09/tally:2d37aef...` | tag (commit SHA) | Only if someone re-pushes that exact tag |
| `ghcr.io/friend09/tally@sha256:a5437692...` | digest | **No**: it is the content hash |

This is Chapter 04's tag-versus-SHA lesson, applied to images. A deployment should record the digest.

## 8. Visibility: Who Can Pull It?

Docs (verified 2026-10): when a workflow creates a package, it "inherits the visibility and permissions model of the repository where the workflow is run". This repository is public, and we confirmed the result **without any credentials**: an anonymous token request followed by `GET /v2/friend09/tally/manifests/latest` returned **HTTP 200**, and `GET /v2/friend09/tally/tags/list` returned `{"name":"friend09/tally","tags":["2d37aef402fe7c7d5adba73157558495c61ad4bd","latest"]}`. Anyone can pull this image.

**What to notice:** publishing from a public repo publishes to the world. If an image must stay private, build it from a private repo, or change the package's visibility in its settings. (Managing packages through the REST API needs the `read:packages` scope; our own CLI token lacked it and was refused with a `403`, so we verified visibility anonymously instead.)

## 9. Image Size, Layers and Time

An image is a stack of layers; the pull cost is the compressed total. Ours is 6 layers, 47.2 MB, almost all base. Practical consequences: use a **slim** base (`python:3.12-slim`, not the full image), order the Dockerfile from least to most frequently changing (so layers cache), and remember each `docker build` on a fresh runner starts with **no layer cache** unless you restore one (Section 10).

## 10. Build Caching and Multi-Platform

> ⚠️ ADVANCED TOPIC: Skip on first read.

`docker/build-push-action` with Buildx can cache layers in the Actions cache (Chapter 09) and build for several CPU architectures (`linux/amd64`, `linux/arm64`) in one go. We did not exercise these in this course's runs; use them when builds exceed a minute or you ship to ARM machines.

## 11. Provenance and Attestations

> ⚠️ ADVANCED TOPIC: Skip on first read.

A published image can carry a signed statement of **how and from what** it was built. Chapter 16 covers artifact attestations; the digest we recorded here is the identifier such statements attach to.

## 12. Cleaning Up Packages

> ⚠️ ADVANCED TOPIC: Skip on first read.

Every push adds a version. Without a retention policy a registry grows forever. Delete old versions by API or with a scheduled workflow (the `schedule` trigger, Chapter 06); keep tagged releases and the digests your deployments reference.

## 13. Case Study: The Deploy That Ran Yesterday's Image

A team deploys with `image: ghcr.io/org/app:latest`. A hot-fix is pushed at 10:02 and `latest` moves. A server restarted at 10:05 pulls the new image; the others still run the old one. Now two versions serve traffic, and the deploy log says "latest" for both. The fix is the pattern in this chapter: publish a **digest** (or SHA tag) as an output and deploy exactly that, so every environment runs the same bytes.

## 14. Comparison: Ways to Build and Publish

| Approach | Setup Effort | Control | Failure Visibility | Security Exposure | Maintenance Burden |
| --- | --- | --- | --- | --- | --- |
| Plain `docker build`/`push` (this chapter) | Minimal - preinstalled | Moderate - no cache or multi-arch | Strong - raw CLI output | Low - first-party token, scoped permissions | Low |
| `docker/build-push-action` | Low - one action | Strong - cache, multi-arch, attestations | Fair - action wrapper logs | Moderate - third-party action | Moderate - keep updated |
| Build on a laptop and push | Minimal | Weak - unreproducible | Weak - no record | High - personal credentials | High - tribal knowledge |
| External build service | High - account, integration | Strong | Fair - separate UI | High - extra credentials | Moderate |

## 15. Practical Tips

- Always lowercase the owner for image names: `${GITHUB_REPOSITORY_OWNER,,}`.
- Grant `packages: write` only to the job that pushes; give consumers `packages: read`.
- Output the digest and deploy by digest.
- Add the `org.opencontainers.image.source` label to record the image's source repo.
- Give service containers a health check so your steps do not race the startup.
- In a container job, install `git` if your tooling needs history.
- Pin base images (`python:3.12-slim` moves; a digest does not).

## 16. Demonstrated Failure Modes

**Failure 1: uppercase repository name.** `invalid tag "ghcr.io/Friend09/tally:test": repository name must be lowercase`. Fix: lowercase the owner in Bash.

**Failure 2: push without `packages: write`.** `denied: installation not allowed to Create organization package`; the package is not created. Fix: add the permission to that job only.

**Failure 3: the git-less container.** Not an error: checkout silently uses the REST API (`The repository will be downloaded using the GitHub REST API`) and the workspace has files but no `.git`. Symptom appears later, in a step that runs `git describe` or reads tags. Fix: install `git` in the image.

**Failure 4: the moving tag.** `:latest` named two different images across our pushes. The digest `sha256:a5437692...` named exactly one. Fix: reference digests.

(Service-container networking mistakes, such as using `localhost` from inside a container job, are described by the docs but we did not reproduce them in a run.)

## 17. Key Takeaways

- A container job runs steps inside an image you choose; `checkout` falls back to a tarball when `git` is absent.
- Service containers start before the steps, are health-checked, and die with the job; they need an Ubuntu runner.
- On the runner use `localhost` plus mapped ports; in a container job use the service label as the hostname.
- Pushing to GHCR needs `docker login` with `GITHUB_TOKEN` and `packages: write`; names must be lowercase.
- Tags move and digests do not; verify and deploy by digest.
- A package published from a public repo is public (we pulled it anonymously).
- An image is layers; base choice dominates the size (47.2 MB for ours).

## 18. Exercises

1. Why did `uppercase_tag` fail while `publish` (same Dockerfile) did not? Give the one-line difference.
2. A job runs on the runner and its service is named `db` on port 5432 with `ports: - 5432:5432`. What is the connection host and port? And if the job runs in a container?
3. `publish_denied` logged in successfully but the push failed. What does that tell you about login versus push permission?
4. You must roll back to the previous release. Which reference style lets you do it reliably: `:latest`, the SHA tag, or the digest? Why?
5. (Hand arithmetic) The image is 47,236,038 bytes compressed. Express it in MiB (1 MiB = 1,048,576 bytes), and compute the bytes moved if 20 jobs each pull it once.

<details>
<summary>Answers</summary>

1. The owner was not lowercased: `Friend09` versus `friend09` (`${GITHUB_REPOSITORY_OWNER,,}`).
2. On the runner: host `localhost`, port `5432`. In a container job: host `db`, port `5432` (no port mapping needed).
3. Reading and writing are separate permissions: `contents: read` let the token authenticate, but only `packages: write` allows creating or pushing a package.
4. The **digest** (or a SHA tag nobody re-pushes). `:latest` has already moved to the new release.
5. 47,236,038 / 1,048,576 = **45.05 MiB**. 20 pulls = 944,720,760 bytes, about **901 MiB**.

</details>

## 19. Additional Resources

All verified 2026-10.

- GitHub Docs: Communicating with Docker service containers - https://docs.github.com/en/actions/tutorials/use-containerized-services/use-docker-service-containers
- GitHub Docs: Publishing and installing a package with GitHub Actions - https://docs.github.com/en/packages/managing-github-packages-using-github-actions-workflows/publishing-and-installing-a-package-with-github-actions
- Docker docs: Dockerfile reference - https://docs.docker.com/reference/dockerfile/
- OCI Image Spec: annotations (`org.opencontainers.image.source`) - https://github.com/opencontainers/image-spec/blob/main/annotations.md
- Live evidence: run 37322069271 in this repo; image `ghcr.io/friend09/tally`
- Laster, *Learning GitHub Actions* (O'Reilly), Chapters 5 and 12

## 20. Appendix A: Code Index

> 💻 Complete, runnable code for this chapter. Skip when reading for concepts.

### A.1 Image references and the published digest

```python
import json
from pathlib import Path

from intro_gha.images import ghcr_ref, repository_name_ok

s = json.loads(Path("fixtures/containers_ch12_summary.json").read_text())
digest = s["publish"]["digest"]
assert not repository_name_ok("ghcr.io/Friend09/tally:test")      # the failing build
assert repository_name_ok(ghcr_ref("Friend09", "tally", tag="latest"))
assert ghcr_ref("Friend09", "tally", digest=digest).endswith("@" + digest)
assert s["verify"]["run_output"] == "5" and s["verify"]["digest_equal"]
```

**Flow:** lowercase the owner when building a reference; a digest reference is the base plus `@sha256:...`; compare what `verify` ran with what `publish` pushed.
