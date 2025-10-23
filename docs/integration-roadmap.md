# Integration Roadmap

## GitHub Actions Enforcement
- Provide a reusable workflow (`.github/workflows/compliance.yml`) that:
  - Checks out the repository.
  - Installs Terraform, Terragrunt (optional), PowerShell Core, and PSRule modules.
  - Runs `terraform init` and `terraform plan -out` (configurable working directory).
  - Executes the compliance CLI with `--fail-on error` (overridable).
- Use caching for Terraform plugin directories (`.terraform`) to speed up repeated runs.
- Surface findings via:
  - CLI exit code (fail build on policy violation).
  - Job summary with concise markdown report.
  - GitHub annotations (`::warning`/`::error`) pointing at module files when metadata is available.
- Optionally upload the JSON report as an artifact for downstream tooling.
- Document usage snippet and optional badge for projects adopting the workflow.

## PR Reviewer Agent
- Implement a reviewer service (initially CLI script, upgradeable to GitHub App) that triggers on pull request events.
- Responsibilities:
  - Fetch changed IaC files or download the plan artifact produced by the GitHub Action.
  - Run the compliance CLI with corresponding configuration.
  - Generate structured feedback, grouping findings per resource with remediation hints and rule references.
  - Post review comments or a consolidated summary to the PR; auto-approve when no findings remain (configurable).
- Architecture sketch:
  - `ReviewerService`: Orchestrates GitHub API client, compliance runner, and comment formatter.
  - `GitHubClient`: Handles authentication, PR file diffs, artifacts, and review submission.
  - `Formatter`: Converts findings into Markdown, including suggestion blocks when safe fixes are available.
- Deployment options:
  - Reuse GitHub Actions workflow to run reviewer in a follow-up job after plan generation.
  - Host as an external agent subscribed to webhook events for teams needing centralized control.

## Next Steps Toward Integration
- Define configuration schema shared by CLI, workflow, and reviewer (`compliance.config.yaml`).
- Provide sample repository showing both integrations in action.
- Align reporting format with future analytics (e.g., storing history of violations for trend tracking).
