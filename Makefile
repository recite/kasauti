.PHONY: help install check fmt lint types test run report clean data analysis manifest

# The data pipeline, expressed as file dependencies rather than as a script that
# remembers the order. Make already is a DAG runner; a second one written here
# would be a worse copy of it, and the ordering is the part a reader most needs
# to be able to check.
#
# Sweeps are not a target. They take hours, they are the only stage that touches
# the network and the compiler, and they are keyed by package -- so they are run
# by hand (`kasauti sweep <package>`) and their timelines are tracked. Everything
# downstream of `sweeps/` rebuilds in seconds from what they left behind.

CORPUS ?= $(HOME)/Documents/GitHub/softverse

data/frame/packages.csv:
	uv run kasauti frame packages

data/frame/cran_usage.csv: data/frame/packages.csv
	uv run kasauti frame usage

data/frame/call_sites.csv:
	uv run kasauti frame extract --corpus $(CORPUS)

data/frame/package_loads.csv:
	uv run kasauti frame loads --corpus $(CORPUS)

data/frame/sampling_frame.csv: data/frame/call_sites.csv data/frame/packages.csv
	uv run kasauti frame build

data/episodes.csv data/changes.csv: $(wildcard sweeps/*/*.json)
	uv run kasauti episodes

docs/reach.md: data/builds.csv
	uv run kasauti build audit --out docs/reach.md

docs/screening.md: $(wildcard screens/*/*.json)
	uv run kasauti screen report

data: data/frame/cran_usage.csv data/frame/sampling_frame.csv data/episodes.csv \
      docs/reach.md docs/screening.md manifest  ## Rebuild every derived table

analysis: data/episodes.csv  ## Compute the four estimands
	Rscript --vanilla analysis/estimands.R

manifest:  ## Record the hash of every released table
	uv run kasauti manifest


help:
	@grep -E '^[a-z-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install:  ## Sync the Python environment
	uv sync --all-extras

fmt:  ## Format
	uv run ruff format src tests
	uv run ruff check --fix src tests

lint:  ## Lint
	uv run ruff format --check src tests
	uv run ruff check src tests

types:  ## Type-check
	uv run python -m pyright

test:  ## Unit tests (no subprocesses, no network)
	# `python -m` rather than the console script: a venv's entry-point
	# shebang can be stale and silently select another interpreter.
	uv run python -m pytest

check: lint types test  ## Everything CI would run

run:  ## Run the full cross-implementation suite
	uv run kasauti run --all

report:  ## Regenerate reports/latest.md
	uv run kasauti report

clean:
	rm -rf .pytest_cache .ruff_cache dist build
	find . -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true
