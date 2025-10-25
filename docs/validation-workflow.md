# Validation Workflow & Testing Strategy

_Status updated: 2025-10-25._

## Current State
- Terraform plan ingestion supports supplied artifacts and Terraform/Terragrunt execution with module auto-discovery.
- Resource normalization and PSRule evaluation ship as part of the `iac-compliance validate` CLI, with JSON reports used by CI.
- The packaged PowerShell wrapper now routes PSRule warnings to stderr so the CLI always receives valid JSON output.
- Integration tests exercise Azure fixtures to ensure end-to-end behaviour remains stable.

## Terraform Execution
- Primary workflow: check out the repository, determine the Terraform modules listed in `.github/iac-compliance.json`, and run `terraform init` / `terraform plan -out` for each module in an isolated temp directory.
- Persist the generated plan output with `terraform show -json` and feed that JSON into the CLI (via `--plan-json`) to exercise the full ingestion pipeline.
- When `plan_json` is explicitly provided via workflow inputs or configuration, reuse the supplied artifact and skip local plan generation.
- Support `--plan-file`, `--plan-json`, and `--working-dir` flags so users can point at artifacts or force local execution.
- Detect Terragrunt configuration (presence of `terragrunt.hcl`) and switch to `terragrunt plan` when the fallback path runs.
- Provide a dry-run mode to avoid remote applies while still enabling optional full execution during future integration testing.

## Plan Normalization
- Parse the plan JSON into a collection of resources with attributes: `type`, `name`, `address`, `change_actions`, and relevant properties.
- Capture module path and source file metadata to enable pinpointed reporting and GitHub annotations.
- For template formats that do not require a plan (e.g., ARM/Bicep), feed files directly into supporting rule adapters.

## CLI Behaviour
- Entry command shape: `iac-compliance validate [path] --plan-json plan.json --rule-manifest rules.yaml --format json|table --fail-on high`.
- Key flags:
  - `--plan-json` / `--plan-file` to ingest existing plan artifacts and skip Terraform execution.
  - `--module` / `--no-auto-discover` for explicit module selection.
  - `--var-file`, `--env`, `--inherit-env` forwarding execution context to Terraform and PSRule.
  - `--rule-manifest` and `--psrule-exec` controlling the PSRule adapter configuration.
- Warnings emitted by PSRule (for example, missing custom rule files) are captured and echoed on stderr, keeping stdout pure JSON for downstream parsing.
- Outputs:
  - Terminal table summarizing findings with severity, rule ID, resource, and remediation.
  - Optional JSON report for integrations and artifact storage.
- Exit codes driven by highest severity (configurable), enabling CI gating.

## Testing Strategy
- Fixture library under `examples/azure/<resource>/` containing compliant and non-compliant Terraform modules (App Service, Storage Account, AKS, Key Vault, SQL, VNet, Log Analytics, etc.).
- Unit tests (pytest or equivalent) covering:
  - RulePackManager configuration parsing.
  - ResourceNormalizer transformations for representative resources.
  - Adapter invocation using mocked plan data.
- Integration tests that run the CLI against fixture directories, verifying both CLI output and JSON report contents.
- Remaining gap: optional Terratest suite for apply-and-validate scenarios and longer-running Terragrunt plans.

## Developer Experience
- Provide Makefile shortcuts (`make plan`, `make validate`, `make test`) and a containerized dev environment with pinned Terraform, Terragrunt, and PSRule versions.
- Document pre-requisites (Terraform version, PowerShell Core for PSRule) and environment variables in project README.
- Ensure local runs are deterministic by isolating temp directories and cleaning up artifacts automatically.
