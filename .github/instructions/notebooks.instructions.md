---
description: "Notebook conventions for the Intro to GitHub Actions labs. Use when editing files in notebooks/."
applyTo: "notebooks/**/*.ipynb"
---

# Notebook Conventions

- Pairs: `lab_XX_<topic>.ipynb` is the runnable reference; `practice_XX.ipynb` has identical
  markdown cells, cell order and code-cell positions, with every code cell empty.
- Cell order: title, Learning Objectives, setup code (imports + `GHA_MODE` toggle), then
  narrated sections, Takeaways, Chapter Link.
- Every code cell is preceded by a markdown cell saying what, why, and the expected output.
- The setup cell reads `GHA_MODE` (`fixture` default | `live`) and `GHA_REPO`. Live cells say
  so in the preceding markdown and show the fixture fallback.
- Re-compute the chapter's worked numbers in code and `assert` them.
- Never print or store a token. Commit notebooks with cleared outputs.
- Write real newlines, not literal `\n`, when generating notebook JSON.
