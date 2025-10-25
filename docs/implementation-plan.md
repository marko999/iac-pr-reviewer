# Implementation Plan

This plan outlines the workstreams required to deliver the first iteration of the compliance tool. Tracks are designed to run in parallel where possible.  
_Status updated: 2025-10-25._

## Progress Snapshot
- ✅ Track A – Core Scaffolding (tooling, layout, tests in place)
- ✅ Track B – Plan Ingestion Pipeline (artifact ingestion + Terraform/Terragrunt fallback)
- ✅ Track C – Normalization Layer (resource models, normalization, coverage)
- ✅ Track D – Rule Engine Integration (PSRule packaging and wrapper hardening)
- ✅ Track E – CLI & Reporting (JSON/table outputs, `iac-compliance validate`, reports)
- ✅ Track F – Fixtures & Tests (fixture library and integration suite)
- 🟡 Track G – GitHub Actions Integration (workflow running; docs & reusable snippet pending)
- ⬜ Track H – PR Reviewer Prototype (not started)

## Track A – Core Scaffolding
- [x] Select implementation stack (Python 3.11 with `typer`, `pydantic`, `rich`) and capture decision in docs.
- [x] Establish repository layout: `src/compliance_service/`, `src/compliance_service/adapters/`, `src/compliance_service/cli/`, `src/compliance_service/models/`.
- [x] Configure development tooling: `pyproject.toml`, linting (`ruff`), formatting (`black`), testing (`pytest`), Makefile, and optional pre-commit hooks.
- [x] Seed a minimal `tests/` package so the configured `pytest` discovery runs cleanly.

## Track B – Plan Ingestion Pipeline
- [x] Implement `PlanLoader` that ingests provided artifacts (`--plan-json`, `--plan-file`) before falling back to executing Terraform/Terragrunt.
- [x] Provide configuration for module discovery, variable files, and environment isolation for the fallback path, including Terragrunt detection.
- [x] Add unit tests covering artifact ingestion and mocked Terraform/Terragrunt subprocess calls with reusable fixtures.

## Track C – Normalization Layer
- [x] Build `ResourceNormalizer` translating plan JSON to internal models with module, action, and metadata handling.
- [x] Define resource and finding dataclasses/pydantic models shared across adapters and reporting.
- [x] Cover with tests using representative Azure plan fixtures (App Service, Storage Account, etc.).

## Track D – Rule Engine Integration
- [x] Implement `RulePackManager` to load YAML manifests, merge defaults, and expose enabled rule sets.
- [x] Create `PSRuleAdapter` invoking PSRule for Azure, mapping responses to internal findings and respecting severity thresholds.
- [x] Define adapter interface to simplify future engines (e.g., OPA, Checkov).
- [x] Package PSRule install/run scripts and harden the wrapper so warnings no longer corrupt JSON output.

## Track E – CLI & Reporting
- [x] Deliver `iac-compliance validate` command orchestrating plan loading, normalization, rule evaluation, and reporting.
- [x] Provide output modes (table, JSON) and exit-code policy (`--fail-on` severity).
- [x] Document CLI usage and add smoke tests plus JSON reporting for end-to-end behaviour.
- [ ] Expand user-facing docs with worked examples and troubleshooting (tracked alongside Track G).

## Track F – Fixtures & Tests
- [x] Assemble Terraform examples under `examples/azure/<resource>` with compliant/non-compliant variants.
- [x] Implement integration tests invoking the CLI against fixtures, verifying findings and severity gating.
- [x] Configure continuous testing (GitHub Actions CI) and coverage reporting.
- [ ] Add larger real-world Terraform scenarios to stress Terragrunt and multi-module discovery.

## Track G – GitHub Actions Integration
- [x] Author `.github/workflows/compliance.yml` installing dependencies, restoring PSRule modules, and running the CLI.
- [x] Upload JSON findings artifacts for debugging and downstream tooling.
- [ ] Publish richer results (job summary, annotations) and harden failure handling for multi-module runs.
- [ ] Document workflow usage, release a reusable snippet, and add optional status badge guidance.

## Track H – PR Reviewer Prototype
- [ ] Scaffold reviewer service (e.g., `reviewer/` package) wrapping GitHub API access, compliance execution, and Markdown formatting.
- [ ] Implement CLI entry point (`iac-compliance review-pr`) to process PRs via metadata or artifacts.
- [ ] Draft deployment guidance for running as part of Actions or an external agent.
