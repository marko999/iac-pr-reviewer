# IaC Compliance Reviewer

Infrastructure-as-code (IaC) teams need fast feedback on governance, cost, and naming policies before changes merge. This project delivers a locally runnable compliance tool with CI and PR review integrations so Azure Terraform repositories stay compliant without slowing engineers down.

## What We're Building
- **Rule-driven validation engine:** Modular compliance service centring on PSRule for Azure with adapters for future rule engines.
- **Terraform-first workflow:** Ingest plan artifacts from CI when available (with local plan generation as fallback), normalize results, and evaluate policies with actionable remediation guidance.
- **Developer-friendly outputs:** Human-readable CLI summaries, JSON reports, and GitHub annotations tuned for iterative fixes.
- **Built-in integration points:** Reusable GitHub Actions workflow and a PR reviewer agent that comments on policy issues automatically.

## Current Focus
- Finish core scaffolding, plan-loading pipeline, and resource normalization (`docs/architecture.md`, `docs/validation-workflow.md`).
- Implement PSRule-backed compliance evaluation with manifest-driven rule packs.
- Ship `iac-compliance validate` CLI plus example fixtures and automated tests.
- Prepare CI workflow and reviewer prototype for repository-level adoption.

## Project Documentation
- `docs/architecture.md` — service layout, adapters, and data flow.
- `docs/validation-workflow.md` — Terraform execution, CLI behaviour, testing strategy.
- `docs/integration-roadmap.md` — GitHub Actions and PR reviewer plans.
- `docs/implementation-plan.md` — parallelizable tracks for delivering the MVP.

## Roadmap Snapshot
See the [Implementation Plan](docs/implementation-plan.md) for the eight workstreams covering scaffolding, Terraform integration, rule adapters, CLI UX, fixtures/tests, CI workflow, and reviewer automation.

## Getting Started
Tooling is under active development. Once the CLI skeleton lands, this section will include prerequisites, installation steps, and quick-start commands (`iac-compliance validate examples/azure/storageaccount`). For now, follow the documentation in `docs/` when contributing.

### Configuring the Compliance Workflow

- Repository-level defaults for the reusable GitHub Actions workflow live in `.github/iac-compliance.json`. Update the `plan_json`, `fail_on`, and `rule_manifests` keys to point at your Terraform plan artifacts and PSRule manifests without modifying the workflow YAML.
- When triggering `workflow_dispatch` runs, override these values from the Actions UI by supplying inputs for the plan path, failure severity, and manifest list (newline separated).
- Sample Terraform plan JSON fixtures are available under `tests/fixtures/azure/` (for example `app_service.json`, `key_vault.json`, and `sql_server.json`). Provide one of these paths to the `plan-json` workflow input to validate against the corresponding resource type.

### Python 3.11 Virtual Environment

1. Confirm Python 3.11 is available (on Windows, use `py -3.11 --version`):

   ```bash
   python3.11 --version
   ```

2. Create and activate a dedicated virtual environment:

   ```bash
   python3.11 -m venv .venv
   source .venv/bin/activate
   # Windows (PowerShell)
   # .\.venv\Scripts\Activate.ps1
   ```

3. Upgrade packaging tools and install the project with development extras:

   ```bash
   python -m pip install --upgrade pip setuptools wheel
   python -m pip install -e ".[dev]"
   ```

4. Run formatters, linters, or tests from the activated environment (for example, `ruff check`, `black`, or `pytest`).

## Contributing
Issues and pull requests are welcome as we bootstrap the project. Please keep the documentation up to date when adding features, and coordinate across tracks to maintain parallel velocity.
