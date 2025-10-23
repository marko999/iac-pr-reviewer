# Compliance Architecture

## Goals
- Provide a modular compliance engine that supports naming, tagging, cost, and broader governance rules.
- Reuse community-maintained Azure rules (PSRule for Azure) while keeping the door open for alternative engines.
- Offer consistent reporting regardless of rule backend and keep remediation guidance close to findings.

## Rule Engine Strategy
- **Primary engine:** PSRule for Azure — mature Terraform/Terragrunt support, aligns with Azure Policy, easy to extend with PowerShell DSL.
- **Secondary options (future):** Open Policy Agent/Rego for cross-cloud flexibility, or Checkov for broad IaC coverage. These plug in through adapters.
- **Adapter layer:** Each engine implements a `RuleEngineAdapter` interface responsible for accepting normalized plan data and returning findings with severity, message, remediation, and scope metadata.

## Core Components
- `ComplianceService`: Entry point that orchestrates loading IaC assets, generating Terraform plans, invoking engine adapters, and consolidating results.
- `PlanLoader`: Handles Terraform `plan -out` and `show -json` execution, including temp workspace management and Terragrunt detection.
- `ResourceNormalizer`: Converts Terraform plan JSON (and other template formats) into a consistent resource graph consumed by adapters.
- `ReportAggregator`: Merges findings, applies severity thresholds, and produces CLI/JSON outputs.
- `RulePackManager`: Loads rule manifests (YAML) that enable/disable rule groups without code changes.

## Data Flow
```
IaC template/archive
    ↓
PlanLoader (terraform plan / terragrunt plan / static parse)
    ↓
ResourceNormalizer (intermediate model: type, name, change, attributes)
    ↓
RuleEngineAdapter (PSRuleAdapter, OPAAdapter, CheckovAdapter…)
    ↓
ReportAggregator (table, JSON, GitHub annotations)
```

## Rule Packs & Configuration
- Rule packs are declared in YAML manifest files (e.g. `rules/naming.yaml`, `rules/cost.yaml`) pointing to underlying engine rules or composing custom wrappers.
- Users can toggle packs per run via CLI flags or config file, allowing teams to tailor enforcement without modifying code.
- Severity levels and failure thresholds are configurable, enabling `--fail-on error` or similar controls.

## Extensibility Considerations
- Keep adapters stateless so they can be invoked in parallel when needed.
- Expose a lightweight plugin contract so additional rule engines can be added without editing the orchestrator.
- Preserve environment metadata (workspace, module path) in the normalized model to support granular findings and future visualization features.
