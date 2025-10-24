# Validation Workflow & Testing Strategy

## Terraform Execution
- Primary workflow: consume an existing plan artifact (`plan.tfplan` or pre-generated JSON) produced by CI. When JSON is supplied, skip Terraform entirely and proceed to normalization.
- Fallback workflow: if no plan artifact is provided, unpack the submission into a temp workspace, run `terraform init`, then `terraform plan -out=plan.tfplan`, followed by `terraform show -json plan.tfplan`.
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
- Future extension: Terratest suite for optional end-to-end apply-and-validate scenarios.

## Developer Experience
- Provide Makefile shortcuts (`make plan`, `make validate`, `make test`) and a containerized dev environment with pinned Terraform, Terragrunt, and PSRule versions.
- Document pre-requisites (Terraform version, PowerShell Core for PSRule) and environment variables in project README.
- Ensure local runs are deterministic by isolating temp directories and cleaning up artifacts automatically.
