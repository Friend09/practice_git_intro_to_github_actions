"""Notebook helpers: ``python -m intro_gha.notebooks`` prints the execution policy."""

from __future__ import annotations


def main() -> None:
    """Print how notebooks are executed and committed in this repo."""
    print(
        "Notebooks run locally (offline, GHA_MODE=fixture by default) and are "
        "committed with cleared outputs.\n"
        "  jupyter nbconvert --to notebook --execute --inplace notebooks/lab_*.ipynb\n"
        "  jupyter nbconvert --ClearOutputPreprocessor.enabled=True --inplace "
        "notebooks/lab_*.ipynb"
    )


if __name__ == "__main__":
    main()
