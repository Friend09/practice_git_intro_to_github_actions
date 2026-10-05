# Chapter Depth Spine (GitHub Actions edition)

Use this whenever authoring or updating a chapter in `learning_modules/`. Every chapter
teaches its mechanism through one worked example with real values, not prose that narrates
around the mechanism.

## The Worked-Example Spine (MANDATORY)

1. **One named running example per chapter, drawn from Tally.** Tally is the course's tiny
   Python repo (`sandbox/tally/`: `tally/add.py` + `tests/test_add.py`). Introduce the
   chapter's slice of it once, with its full spec (the YAML, the event payload, the matrix
   axes, the timings), and thread it through every core section.

   ```markdown
   > 📌 **Running Example — [Name]:** [One paragraph; every value stated.] We return to this
   > example throughout Sections N-M.
   ```

2. **All values stated before first use.** Event payload fields, matrix axes, job durations in
   seconds, runner OS, cache keys: declared before any step consumes them.

3. **A worked trace for every key mechanism.** Show: state BEFORE, the exact YAML / command /
   event, the state AFTER (the run log, resulting job list, evaluated expression). Follow each
   shown output with 2-4 "What to notice:" bullets.

4. **State dump after each step.** After each worked step show the resulting state (job table,
   context values, cache contents, billed minutes) in a small table.

5. **Variants on the SAME example.** `push` vs `pull_request`, `needs` vs no `needs`,
   cache hit vs miss: demonstrate on the same Tally workflow so the difference is visible in
   the values.

## Demonstrated Failure Mode (MANDATORY)

At least one failure per chapter is shown concretely, not asserted: the configuration that
misbehaves, the observable symptom (the run that never fired, the 27-job matrix, the secret
printed as `***`, the expression that evaluates to a string `'false'` and is truthy), the cause,
and the fix.

## Formatting

- Display math (rare in this course: cost and matrix arithmetic) is `$$...$$` on **one
  physical line**, with a plain-English breakdown of each symbol.
- Code under 15 lines stays inline. Code of 20+ lines moves to Appendix A with a plain-English
  summary, an ASCII flow diagram, and `> 📝 **Full implementation:** See Appendix A.X`.
- Every example that touches GitHub names the exact `gh` subcommand or REST endpoint.

## Required Elements Beyond the Spine

- **Appendix A: Code Index** as the last section; `### A.X` headings; complete, runnable,
  commented code with docstrings on every Python function/class.
- **Exercises:** 3-5 per chapter, at least one hand-computation on the running example, with
  worked answers in a `<details>` block.
- **Citation floor:** at least 5 primary sources per chapter (GitHub Docs pages, the book,
  changelog posts), each with a year or "verified 2026-10".
- **Analogies:** label them (`**Analogy —**`) and say where they break down.

## Anti-Bloat

- Max 2-3 real-world examples per main section.
- Each numbered section targets 50-200 lines; over 300 means stacked examples.
- No trailing "latest research" surveys, no standalone misconceptions dump, no key-takeaways
  list over ~8 bullets.

## Depth Targets

- Core chapters: ~900-1,400 lines including Appendix A. Optional deep-dives may run longer.
- Reference notebooks: ~150-400 code lines, re-computing the chapter's worked numbers in code.
