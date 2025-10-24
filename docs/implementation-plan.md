# Implementation Plan

This plan outlines the workstreams required to deliver the first iteration of the compliance tool. Tracks are designed to run in parallel where possible.

## Track A – Core Scaffolding
- Select implementation stack (Python 3.11 recommended with `typer`, `pydantic`, `rich`) and capture decision in docs.
- Establish repository layout: `src/compliance_service/`, `src/compliance_service/adapters/`, `src/compliance_service/cli/`, `src/compliance_service/models/`.
- Configure development tooling: `pyproject.toml`, linting (`ruff`), formatting (`black`), testing (`pytest`), Makefile, and optional pre-commit hooks.
- Seed a minimal `tests/` package (e.g., placeholder smoke test) so the configured `pytest` discovery runs cleanly once Track A lands.

## Track B – Plan Ingestion Pipeline
- Implement `PlanLoader` that first looks for supplied plan artifacts (`--plan-json`, `--plan-file`) and parses them; only falls back to running `terraform init/plan` + `terraform show -json` when no artifact exists.
- Provide configuration for module discovery, variable files, and environment isolation for the fallback execution path, including Terragrunt detection.
- Add unit tests covering both artifact ingestion and mocked Terraform subprocess calls, plus plan JSON fixtures for repeatability.

## Track C – Normalization Layer
- Build `ResourceNormalizer` translating plan JSON to internal models, capturing module paths, change actions, and key attributes.
- Define resource and finding dataclasses/pydantic models shared across adapters and reporting.
- Cover with tests using representative Azure plan fixtures (App Service, Storage Account, etc.).

## Track D – Rule Engine Integration
- [x] Implement `RulePackManager` to load YAML manifests, merge defaults, and expose enabled rule sets.
- [x] Create `PSRuleAdapter` invoking PSRule for Azure, mapping responses to internal findings and respecting severity thresholds.
- [x] Define adapter interface to simplify future engines (e.g., OPA, Checkov).

## Track E – CLI & Reporting
- Deliver `iac-compliance validate` command orchestrating plan loading, normalization, rule evaluation, and reporting.
- Provide output modes (table, JSON) and exit-code policy (`--fail-on` severity).
- Document CLI usage and add smoke tests to ensure end-to-end behaviour.

## Track F – Fixtures & Tests
- Assemble Terraform examples under `examples/azure/<resource>` with compliant/non-compliant variants.
- Implement integration tests invoking the CLI against fixtures, verifying findings and severity gating.
- Configure continuous testing (e.g., GitHub Actions) and coverage reporting.

## Track G – GitHub Actions Integration
- Author `.github/workflows/compliance.yml` installing dependencies, caching Terraform plugins, and running the CLI.
- Publish results via job summary, annotations, and optional JSON artifact upload.
- Document workflow usage and optional badge in the repository README.

## Track H – PR Reviewer Prototype
- Scaffold reviewer service (e.g., `reviewer/` package) wrapping GitHub API access, compliance execution, and Markdown formatting.
- Implement CLI entry point (`iac-compliance review-pr`) to process PRs via metadata or artifacts.
- Draft deployment guidance for running as part of Actions or an external agent.
