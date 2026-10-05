---
description: "Conventions for Python lab scripts and helpers in the Intro to GitHub Actions course."
applyTo: "{labs,src,scripts,tests,sandbox}/**/*.py"
---

# Python Conventions

- Module, function and class docstrings are required on every `.py` file.
- Type hints on all function signatures; `pathlib.Path` for paths.
- Namespace `intro_gha`; env vars use the `GHA_` prefix.
- Stdlib, then third-party, then `intro_gha` imports.
- Every lab runs offline by default (`GHA_MODE=fixture`) and may support `GHA_MODE=live`.
- Never write a token into output or source.
- Lab scripts are importable (guard with `if __name__ == "__main__":`).
