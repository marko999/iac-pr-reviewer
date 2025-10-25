# Integration Roadmap

_Status updated: 2025-10-25._

## GitHub Actions Enforcement
- ✅ Provide a reusable workflow (`.github/workflows/compliance.yml`) that:
  - Checks out the repository.
  - Installs Python 3.11, the CLI, PowerShell, and PSRule modules (via the packaged installer).
  - Restores PSRule module cache and executes the validator with configurable severity.
- ✅ Upload the JSON report artifact (`compliance-findings`) for downstream analysis.
- 🔄 Add optional Terraform/Terragrunt bootstrap helpers and document caching of `.terraform` directories when plan generation runs inside the workflow.
- 🔄 Surface richer findings:
  - Job summary with concise markdown report.
  - GitHub annotations (`::warning`/`::error`) pointing at resources when metadata is available.
- 🔄 Publish a short adoption guide, snippet, and status badge instructions in the README/docs once packaging is finalized.

## PR Reviewer Agent
- ⬜ Implement a reviewer service (initial CLI script, upgradeable to GitHub App) that triggers on pull request events.
- Responsibilities (planned):
  - Fetch changed IaC files or download the plan artifact produced by the GitHub Action.
  - Run the compliance CLI with corresponding configuration.
  - Generate structured feedback, grouping findings per resource with remediation hints and rule references.
  - Post review comments or a consolidated summary to the PR; auto-approve when no findings remain (configurable).
- Architecture sketch (unchanged):
  - `ReviewerService`: Orchestrates GitHub API client, compliance runner, and comment formatter.
  - `GitHubClient`: Handles authentication, PR file diffs, artifacts, and review submission.
  - `Formatter`: Converts findings into Markdown, including suggestion blocks when safe fixes are available.
- Deployment options:
  - Reuse GitHub Actions workflow to run reviewer in a follow-up job after plan generation.
  - Host as an external agent subscribed to webhook events for teams needing centralized control.

## Next Steps Toward Integration
- 🔄 Define configuration schema shared by CLI, workflow, and reviewer (`compliance.config.yaml` or JSON equivalent).
- 🔄 Provide sample repository showing both integrations in action (post-packaging).
- 🔄 Align reporting format with future analytics (e.g., storing history of violations for trend tracking) and capture in documentation.
