from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Iterable, List, Optional


class PlanLoaderError(RuntimeError):
    """Exception raised when terraform plan ingestion fails."""


class PlanLoader:
    """Load Terraform plan data from supplied artifacts or by executing Terraform/Terragrunt."""

    def __init__(
        self,
        working_dir: str | os.PathLike[str] = ".",
        *,
        plan_json_path: str | os.PathLike[str] | None = None,
        plan_file_path: str | os.PathLike[str] | None = None,
        module_paths: Optional[Iterable[str | os.PathLike[str]]] = None,
        auto_discover_modules: bool = True,
        var_files: Optional[Iterable[str | os.PathLike[str]]] = None,
        env: Optional[dict[str, str]] = None,
        inherit_environment: bool = False,
        terraform_bin: str = "terraform",
        terragrunt_bin: str = "terragrunt",
        force_terragrunt: bool = False,
    ) -> None:
        self.working_dir = Path(working_dir).resolve()
        self.plan_json_path = Path(plan_json_path).resolve() if plan_json_path else None
        self.plan_file_path = Path(plan_file_path).resolve() if plan_file_path else None
        self.module_paths = [Path(path).resolve() for path in module_paths] if module_paths else None
        self.auto_discover_modules = auto_discover_modules
        self.var_files = [str(Path(path).resolve()) for path in var_files] if var_files else []
        self.env = env or {}
        self.inherit_environment = inherit_environment
        self.terraform_bin = terraform_bin
        self.terragrunt_bin = terragrunt_bin
        self.force_terragrunt = force_terragrunt

    def load_plan(self) -> Any:
        """Load plan data from an artifact or by executing Terraform."""

        if self.plan_json_path:
            return self._load_json_artifact(self.plan_json_path)

        if self.plan_file_path:
            return self._load_plan_file(self.plan_file_path)

        return self._generate_plan_from_source()

    # Artifact ingestion helpers -------------------------------------------------
    def _load_json_artifact(self, path: Path) -> Any:
        if not path.exists():
            raise PlanLoaderError(f"Terraform plan JSON artifact not found: {path}")

        with path.open("r", encoding="utf-8") as handle:
            try:
                return json.load(handle)
            except json.JSONDecodeError as exc:
                raise PlanLoaderError(f"Invalid JSON in plan artifact: {path}") from exc

    def _load_plan_file(self, path: Path) -> Any:
        if not path.exists():
            raise PlanLoaderError(f"Terraform plan file not found: {path}")

        completed = self._run_command(
            [self.terraform_bin, "show", "-json", str(path)],
            cwd=self.working_dir,
            capture_output=True,
        )
        return self._parse_command_output(completed.stdout)

    # Terraform/Terragrunt execution ---------------------------------------------
    def _generate_plan_from_source(self) -> Any:
        module_dirs = self._resolve_modules()
        env = self._build_environment()

        module_results: List[dict[str, Any]] = []
        for module_dir in module_dirs:
            if self._should_use_terragrunt(module_dir):
                plan_data = self._run_terragrunt_plan(module_dir, env)
            else:
                plan_data = self._run_terraform_plan(module_dir, env)

            module_results.append(
                {
                    "module_path": self._module_identifier(module_dir),
                    "plan": plan_data,
                }
            )

        if len(module_results) == 1:
            return module_results[0]["plan"]

        return {"modules": module_results}

    def _resolve_modules(self) -> List[Path]:
        if self.module_paths:
            return [path for path in self.module_paths]

        if not self.auto_discover_modules:
            return [self.working_dir]

        discovered = self._discover_modules()
        return discovered or [self.working_dir]

    def _discover_modules(self) -> List[Path]:
        module_dirs: set[Path] = set()
        for extension in ("*.tf", "*.tf.json"):
            for file_path in self.working_dir.rglob(extension):
                if ".terraform" in file_path.parts:
                    continue
                module_dirs.add(file_path.parent.resolve())

        terragrunt_configs = list(self.working_dir.rglob("terragrunt.hcl"))
        module_dirs.update(config.parent.resolve() for config in terragrunt_configs)

        return sorted(module_dirs)

    def _build_environment(self) -> dict[str, str]:
        if self.inherit_environment:
            env_vars = os.environ.copy()
        else:
            env_vars = {"PATH": os.environ.get("PATH", "")}

        env_vars.update(self.env)
        return env_vars

    def _should_use_terragrunt(self, module_dir: Path) -> bool:
        if self.force_terragrunt:
            return True
        return (module_dir / "terragrunt.hcl").exists()

    def _run_terraform_plan(self, module_dir: Path, env: dict[str, str]) -> Any:
        self._run_command([self.terraform_bin, "init", "-input=false"], cwd=module_dir, env=env)

        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = Path(tmpdir) / "iac-plan.tfplan"
            plan_cmd = [self.terraform_bin, "plan", "-input=false", f"-out={plan_path}"]
            for var_file in self.var_files:
                plan_cmd.append(f"-var-file={var_file}")

            self._run_command(plan_cmd, cwd=module_dir, env=env)

            show_cmd = [self.terraform_bin, "show", "-json", str(plan_path)]
            completed = self._run_command(show_cmd, cwd=module_dir, env=env, capture_output=True)

        return self._parse_command_output(completed.stdout)

    def _run_terragrunt_plan(self, module_dir: Path, env: dict[str, str]) -> Any:
        plan_cmd = [
            self.terragrunt_bin,
            "run-all",
            "plan",
            "--terragrunt-non-interactive",
            "--terragrunt-json",
            f"--terragrunt-working-dir={module_dir}",
        ]

        for var_file in self.var_files:
            plan_cmd.append(f"--var-file={var_file}")

        completed = self._run_command(plan_cmd, cwd=module_dir, env=env, capture_output=True)
        return self._parse_command_output(completed.stdout)

    def _module_identifier(self, module_dir: Path) -> str:
        try:
            relative = module_dir.relative_to(self.working_dir)
        except ValueError:
            return str(module_dir)
        return str(relative) or "."

    def _parse_command_output(self, output: str) -> Any:
        try:
            return json.loads(output)
        except json.JSONDecodeError as exc:
            raise PlanLoaderError("Command output was not valid JSON") from exc

    # Command runner -------------------------------------------------------------
    def _run_command(
        self,
        args: List[str],
        *,
        cwd: Path | None = None,
        env: Optional[dict[str, str]] = None,
        capture_output: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        try:
            completed = subprocess.run(
                args,
                cwd=cwd,
                env=env,
                check=True,
                capture_output=capture_output,
                text=True,
            )
        except FileNotFoundError as exc:
            raise PlanLoaderError(f"Executable not found: {args[0]}") from exc
        except subprocess.CalledProcessError as exc:
            raise PlanLoaderError(
                f"Command '{' '.join(args)}' failed with exit code {exc.returncode}"
            ) from exc

        return completed


__all__ = ["PlanLoader", "PlanLoaderError"]

