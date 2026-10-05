---
description: "Chapter structure conventions for the Intro to GitHub Actions learning modules. Use when editing, creating, or reviewing files in learning_modules/."
applyTo: "learning_modules/**/*.md"
---

# Chapter Content Conventions

Applies to every markdown file under `learning_modules/`. This is a standalone, foundations-first
GitHub Actions course; every topic is taught self-contained.

## Required Header Block

```markdown
# Chapter XX: Title

**Reading Time:** ~NN minutes
**Prerequisites:** Chapter N or "None"
**Practice Notebook:** `notebooks/practice_XX.ipynb` or `-`
**Reference Notebook:** `notebooks/lab_XX_<topic>.ipynb` or `-`
**Script:** `labs/lab_XX_<topic>.py` or `-`
**Book Reference:** Laster, Learning GitHub Actions Ch N / GitHub Docs § ...
**Depth:** Core | Optional Deep-Dive
**Default Runtime:** Offline fixtures | Live repo | Live repo (guarded)
```

`CLAUDE.md` holds the chapter map.

## Required Structural Elements

1. **Beginner's Guide** right after the first `---`: what to focus on, what to SKIP on first
   read, 3-5 plain-English definitions, and a link to what the reader may already know.
2. `> **🔬 Platform Engineer's Lens:**` callout: the production cost when this goes wrong.
3. `> **🚦 Native vs Marketplace vs Custom:**` callout: does GitHub or the Marketplace already
   do this, or must you write it?
4. **What You'll Learn**: 6-8 concrete outcomes.
5. A 20-section table of contents (anchor links) with matching `## N.` headings.
6. **Advanced markers** `> ⚠️ ADVANCED TOPIC: ...` on skippable sections.
7. The worked-example spine from `.github/skills/_shared/depth-spine.md`.
8. **Appendix A: Code Index** as the final section.

## 20-Section Skeleton

- 1-2 Introduction and motivation
- 3-8 Core mechanics with ASCII diagrams and worked traces
- 9-12 Advanced topics
- 13-15 Case studies, comparisons, practical tips
- 16 Demonstrated failure modes and pitfalls
- 17 Key takeaways (<= 8 bullets)
- 18 Exercises with answers
- 19 Additional resources (>= 5 sources, dated)
- 20 Appendix A: Code Index

## Domain Rules

- **Comparison tables** across: Setup Effort, Control, Failure Visibility, Security Exposure,
  Maintenance Burden. No star ratings. Quality axes (Control, Failure Visibility) use
  Weak / Fair / Moderate / Strong / Excellent; cost axes (the rest) use
  Minimal / Low / Moderate / High / Very High. Cell format `Level - brief note`.
- **Concrete numbers**, never "fast" or "usually": rate limits, timeouts in seconds, matrix
  sizes, billed minutes, artifact retention days.
- **Exact mechanism**: name the `gh` subcommand or REST endpoint behind any example.
- **Verify, then date it**: every behavioral claim is checked against current GitHub Docs and
  cited in section 19 as "verified 2026-10".
- **Pin third-party actions** in demo workflows once Chapter 16 is reached; before that, major
  tags (`@v4`) are acceptable and the chapter says so.

## Placement Guardrails

Never renumber a `## N.` header. New depth goes in `###` subsections or Appendix A.x.
Validate with `uv run python scripts/validate_chapters.py chapter_XX`.
