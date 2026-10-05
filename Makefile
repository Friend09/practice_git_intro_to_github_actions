UV ?= uv

.PHONY: sync lint test validate lint-workflows run-notebooks pr hooks

sync:
	$(UV) sync --group core

lint:
	$(UV) run ruff check .

test:
	$(UV) run pytest

validate:
	$(UV) run python scripts/validate_chapters.py

# actionlint every workflow (brew install actionlint)
lint-workflows:
	actionlint .github/workflows/*.yml

run-notebooks:
	$(UV) run python -m intro_gha.notebooks

lab-%:
	$(UV) run python labs/lab_$*_*.py

# Open a throwaway PR touching sandbox/** so the demo workflows fire:
#   make pr BRANCH=demo-ch03
pr:
	git switch -c $(BRANCH) && echo "# touch $$(date +%s)" >> sandbox/tally/tally/__init__.py \
	  && git commit -am "sandbox: demo $(BRANCH)" && git push -u origin $(BRANCH) \
	  && gh pr create --fill

# Enable the pre-commit gate (ruff + actionlint + pytest) for this clone.
hooks:
	git config core.hooksPath .githooks
