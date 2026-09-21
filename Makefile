# Central task menu: call the required runtime directly. Never proxy Python through pnpm.
# Business logic lives in scripts/; the optional pnpm aliases reuse the same modules.
SHELL := /bin/sh
.DEFAULT_GOAL := help
.DELETE_ON_ERROR:
.SUFFIXES:
.NOTPARALLEL:

PNPM ?= pnpm
NODE ?= node
BOOTSTRAP_PYTHON ?= python3.13
ifeq ($(OS),Windows_NT)
PYTHON ?= .venv/Scripts/python.exe
else
PYTHON ?= .venv/bin/python
endif
REPO ?= $(GITHUB_REPOSITORY)
TAG ?= $(RELEASE_TAG)
OUTPUT ?= dist
export PNPM NODE PYTHON BOOTSTRAP_PYTHON REPO CODEOWNER NAME DISPLAY_NAME TAG OUTPUT CONFIRM_PUBLISH
export SKILLS_JSON SHARD_INDEX SHARD_COUNT BASE_SHA HEAD_SHA PR_TITLE PR_BRANCH
export PYTHONDONTWRITEBYTECODE := 1

.PHONY: help install bootstrap setup bootstrap-reference configure verify-identity skill-new skill-activate skill-fingerprint skill-preview validate test test-python test-skills test-launchers check ci-check isolate plan plan-ci check-pr catalog catalog-update release-sync build-preview build-release publish-assets has-active has-active-ci interop

help: ## Show the task menu. No installs, tests, or writes.
	@awk 'BEGIN { print "J-Yoharu Skills maintenance tasks\n" } /^[a-z][a-z0-9-]*:.*## / { split($$0, parts, ":"); sub(/^.*## /, "", $$0); printf "  %-22s %s\n", parts[1], $$0 }' Makefile

install: ## Optional: install root JavaScript dependencies with pinned pnpm/frozen lockfile.
	@"$$PNPM" install --frozen-lockfile

bootstrap: ## Create/update .venv and install pinned Python dependencies (explicit network operation).
	@"$$BOOTSTRAP_PYTHON" scripts/bootstrap.py

setup: bootstrap ## Set up the Python environment. pnpm is not required for Make commands.

bootstrap-reference: ## Install optional external-validator dependencies after bootstrap (network).
	@"$$BOOTSTRAP_PYTHON" scripts/bootstrap.py --reference

configure: ## Configure local identity: REPO=OWNER/REPO [CODEOWNER=@OWNER]. No remote writes.
	@test -n "$$REPO" || { echo 'REPO is required.' >&2; exit 2; }
	@set -- --github "$$REPO"; if [ -n "$$CODEOWNER" ]; then set -- "$$@" --codeowner "$$CODEOWNER"; fi; "$$PYTHON" -m scripts configure "$$@"

verify-identity: ## Compare identity with REPO or GITHUB_REPOSITORY without network calls.
	@test -n "$$REPO" || { echo 'REPO or GITHUB_REPOSITORY is required.' >&2; exit 2; }
	@"$$PYTHON" -m scripts verify-identity --github "$$REPO"

skill-new: ## Create a draft: NAME=example-skill [DISPLAY_NAME="Example Skill"].
	@test -n "$$NAME" || { echo 'NAME is required.' >&2; exit 2; }
	@set -- "$$NAME"; if [ -n "$$DISPLAY_NAME" ]; then set -- "$$@" --display-name "$$DISPLAY_NAME"; fi; "$$PYTHON" -m scripts new "$$@"

skill-activate: ## Activate a genuinely evaluated draft: NAME=example-skill. Requires authorization.
	@test -n "$$NAME" || { echo 'NAME is required.' >&2; exit 2; }
	@"$$PYTHON" -m scripts activate "$$NAME"

skill-fingerprint: ## Print the content fingerprint, without approving it: NAME=example-skill.
	@test -n "$$NAME" || { echo 'NAME is required.' >&2; exit 2; }
	@"$$PYTHON" -m scripts fingerprint "$$NAME"

skill-preview: ## Copy one skill for local evaluation under dist/skill-preview: NAME=example-skill.
	@test -n "$$NAME" || { echo 'NAME is required.' >&2; exit 2; }
	@"$$PYTHON" -m scripts preview-skill "$$NAME"

validate: ## Validate skill boundaries, formats, versioning, and maintained docs.
	@"$$PYTHON" -m scripts validate

test-python: ## Run maintenance regression tests using Python directly.
	@"$$PYTHON" -m unittest discover -s tests/scripts -v

test-skills: ## Run skill unit suites; optional NAME=example-skill.
	@set --; if [ -n "$$NAME" ]; then set -- "$$@" --name "$$NAME"; fi; "$$PYTHON" -m scripts test-skills "$$@"

test-launchers: ## Run Node alias, real Make routing, and agent instruction contract tests.
	@"$$NODE" --test tests/launchers/*.test.mjs

test: test-launchers test-python test-skills ## Run all deterministic test suites (not LLM evaluation).

check: validate test isolate build-preview ## Full local gate; no pnpm installation or remote writes.

ci-check: ## Selective Python gate: validates all contracts, tests affected code, and isolates affected skills.
	@"$$PYTHON" -m scripts ci-check

isolate: ## Run copied-payload smoke checks; optional SKILLS_JSON or SHARD_INDEX/SHARD_COUNT.
	@set --; if [ -n "$$SKILLS_JSON" ]; then set -- "$$@" --skills-json "$$SKILLS_JSON"; fi; if [ -n "$$SHARD_INDEX" ] || [ -n "$$SHARD_COUNT" ]; then if [ -n "$$SKILLS_JSON" ] || [ -z "$$SHARD_INDEX" ] || [ -z "$$SHARD_COUNT" ]; then echo 'Use SKILLS_JSON or both SHARD_INDEX and SHARD_COUNT, not a mixture.' >&2; exit 2; fi; set -- "$$@" --shard-index "$$SHARD_INDEX" --shard-count "$$SHARD_COUNT"; fi; "$$PYTHON" -m scripts isolate "$$@"

plan: ## Print affected-skill planning; BASE_SHA/HEAD_SHA select the diff.
	@"$$PYTHON" -m scripts plan

plan-ci: ## Write planning outputs to GITHUB_OUTPUT.
	@"$$PYTHON" -m scripts plan --github-output

check-pr: ## Validate PR title/release intent using PR_TITLE, PR_BRANCH, BASE_SHA, HEAD_SHA.
	@"$$PYTHON" -m scripts check-pr

catalog: ## Print the generated catalog without modifying files.
	@"$$PYTHON" -m scripts catalog

catalog-update: ## Update the generated documentation catalog.
	@"$$PYTHON" -m scripts catalog --write

release-sync: ## Synchronize release components without changing versions.
	@"$$PYTHON" -m scripts sync

build-preview: ## Build active skills only, never drafts; optional OUTPUT=dist.
	@"$$PYTHON" -m scripts build --preview --output "$$OUTPUT"

build-release: ## Build from an exact clean release tag: TAG=v1.2.0 [OUTPUT=dist].
	@test -n "$$TAG" || { echo 'TAG or RELEASE_TAG is required.' >&2; exit 2; }
	@"$$PYTHON" -m scripts build --tag "$$TAG" --output "$$OUTPUT"

publish-assets: ## REMOTE WRITE: TAG=v1.2.0 CONFIRM_PUBLISH=yes. Requires authorization and credentials.
	@test -n "$$TAG" || { echo 'TAG or RELEASE_TAG is required.' >&2; exit 2; }
	@test "$$CONFIRM_PUBLISH" = yes || { echo 'Remote publication requires CONFIRM_PUBLISH=yes and explicit authorization.' >&2; exit 2; }
	@"$$PYTHON" -m scripts publish-assets --tag "$$TAG" --output "$$OUTPUT"

has-active: ## Print whether any skill is release eligible.
	@"$$PYTHON" -m scripts has-active

has-active-ci: ## Write release eligibility to GITHUB_OUTPUT.
	@"$$PYTHON" -m scripts has-active --github-output

interop: ## Run explicit external reference/installer integration after bootstrap-reference (network).
	@"$$PYTHON" -m scripts interop
