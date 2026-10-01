# Nest Assistant.
#
# Every target here is a thin wrapper around `uv run nest <command>`. If `make`
# is not available on your machine (some Windows setups), run the uv command
# shown under each target directly — they do exactly the same thing.

.PHONY: help setup setup-lite warm check demo ingest search eval eval-save bot board test lint format hooks scan clean

UV ?= uv

help:  ## show this help
	@echo ""
	@echo "  Nest Assistant"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'
	@echo ""

# --- setup ------------------------------------------------------------------

setup:  ## install everything (do this at home, on good wifi — it is a big download)
	$(UV) sync --all-extras
	@echo ""
	@echo "  Installed. Now run: make check"
	@echo ""

setup-lite:  ## install the minimum (fast, works offline afterwards; no embeddings)
	$(UV) sync
	@echo ""
	@echo "  Minimal install done. 'make demo' works; the embedding model does not."
	@echo "  Run 'make setup' before the workshop when you have decent wifi."
	@echo ""

warm:  ## pre-download the embedding model so the workshop wifi never has to
	$(UV) run python -c "\
from nest_assistant.config import EMBEDDING_MODEL; \
from sentence_transformers import SentenceTransformer; \
print('downloading', EMBEDDING_MODEL); SentenceTransformer(EMBEDDING_MODEL); print('cached.')"

hooks:  ## install the git pre-commit hooks (TEAM 6 — everyone needs this)
	$(UV) run pre-commit install
	@echo "  Hooks installed. Try committing a file with a fake IBAN in it."

# --- the loop everyone runs all day -----------------------------------------

check:  ## verify the environment, then run the tests  [pre-work: must be green]
	@$(UV) run nest check
	@$(UV) run pytest

demo:  ## ask the assistant a question, end to end, with no API key required
	@$(UV) run nest demo

board:  ## which components are still stubs
	@$(UV) run nest board

test:  ## run the tests only
	$(UV) run pytest

lint:  ## check formatting and lint
	$(UV) run ruff check .
	$(UV) run ruff format --check .

format:  ## fix formatting and the auto-fixable lint
	$(UV) run ruff check --fix .
	$(UV) run ruff format .

scan:  ## scan the whole tree for Nest data and secrets
	$(UV) run python tools/scan_data.py --all

# --- the pipeline -----------------------------------------------------------

ingest:  ## build chunks.jsonl from data/ (or fixtures/ if data/ is empty)
	$(UV) run nest ingest

search:  ## search the index: make search Q="quanto costa una singola"
	@$(UV) run nest search "$(Q)" --tier $(or $(TIER),public)

# `nest eval` exits non-zero when tier_leaks > 0, so make reports an error.
# That is correct, and on the morning of the workshop it is expected: INDEX's
# stub does not filter by tier until task W1-2.2 lands. The scorecard prints
# either way — read it, do not just read the exit code.
eval:  ## score the system against eval/questions.yaml
	@$(UV) run nest eval

eval-save:  ## score it and write a dated scorecard to eval/results/
	@$(UV) run nest eval --save

bot:  ## start the bot (console until TEAM 4 lands Telegram)
	$(UV) run nest bot

clean:  ## remove generated files (never touches data/)
	rm -rf build .pytest_cache .ruff_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
