import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from compliance_service.adapters import PlanLoader, PlanLoaderError

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def test_load_plan_from_json_artifact(tmp_path):
    plan_path = FIXTURES / "plan-minimal.json"
    loader = PlanLoader(working_dir=tmp_path, plan_json_path=plan_path)

    data = loader.load_plan()

    assert data["format_version"] == "1.0"
    assert data["planned_values"]["root_module"]["resources"] == []


def test_load_plan_from_plan_file(monkeypatch, tmp_path):
    plan_file = tmp_path / "saved-plan.tfplan"
    plan_file.write_text("", encoding="utf-8")

    recorded = {}

    def fake_run(self, args, cwd=None, env=None, capture_output=False):
        recorded["args"] = args
        recorded["cwd"] = cwd
        recorded["capture_output"] = capture_output
        if args[:2] == ["terraform", "show"]:
            return SimpleNamespace(stdout=json.dumps({"format_version": "1.0"}))
        return SimpleNamespace(stdout="")

    monkeypatch.setattr(PlanLoader, "_run_command", fake_run, raising=False)

    loader = PlanLoader(working_dir=tmp_path, plan_file_path=plan_file)
    data = loader.load_plan()

    assert data == {"format_version": "1.0"}
    assert recorded["args"] == ["terraform", "show", "-json", str(plan_file.resolve())]
    assert Path(recorded["cwd"]).resolve() == tmp_path.resolve()
    assert recorded["capture_output"] is True


def test_generate_plan_runs_terraform(monkeypatch, tmp_path):
    module_dir = tmp_path / "module_a"
    module_dir.mkdir()
    (module_dir / "main.tf").write_text(
        "resource \"null_resource\" \"example\" {}",
        encoding="utf-8",
    )

    var_file = tmp_path / "vars.tfvars"
    var_file.write_text("region=\"eastus\"", encoding="utf-8")

    commands = []

    def fake_run(self, args, cwd=None, env=None, capture_output=False):
        commands.append({
            "args": list(args),
            "cwd": Path(cwd) if cwd else None,
            "env": env,
            "capture_output": capture_output,
        })
        if args[:2] == ["terraform", "show"]:
            return SimpleNamespace(stdout=json.dumps({"module": "example"}))
        return SimpleNamespace(stdout="")

    monkeypatch.setattr(PlanLoader, "_run_command", fake_run, raising=False)

    loader = PlanLoader(
        working_dir=tmp_path,
        var_files=[var_file],
        env={"TF_VAR_region": "eastus"},
        inherit_environment=False,
    )

    data = loader.load_plan()

    assert data == {"module": "example"}

    plan_command = next(cmd for cmd in commands if cmd["args"][1] == "plan")
    assert any(
        arg.endswith(str(var_file.resolve())) for arg in plan_command["args"]
    )  # -var-file path
    assert plan_command["env"]["TF_VAR_region"] == "eastus"
    assert plan_command["env"]["PATH"] == os.environ.get("PATH", "")

    for command in commands:
        assert command["cwd"].resolve() == module_dir.resolve()


def test_generate_plan_handles_terragrunt(monkeypatch, tmp_path):
    terraform_module = tmp_path / "module_tf"
    terraform_module.mkdir()
    (terraform_module / "main.tf").write_text("terraform {}", encoding="utf-8")

    terragrunt_module = tmp_path / "module_tg"
    terragrunt_module.mkdir()
    (terragrunt_module / "terragrunt.hcl").write_text("", encoding="utf-8")

    terraform_calls = []
    terragrunt_calls = []

    def fake_run(self, args, cwd=None, env=None, capture_output=False):
        if args[0] == "terragrunt":
            terragrunt_calls.append({
                "args": list(args),
                "cwd": Path(cwd) if cwd else None,
                "capture_output": capture_output,
            })
            return SimpleNamespace(stdout=json.dumps({"kind": "terragrunt"}))

        terraform_calls.append({
            "args": list(args),
            "cwd": Path(cwd) if cwd else None,
            "capture_output": capture_output,
        })

        if args[:2] == ["terraform", "show"]:
            return SimpleNamespace(stdout=json.dumps({"kind": "terraform"}))

        return SimpleNamespace(stdout="")

    monkeypatch.setattr(PlanLoader, "_run_command", fake_run, raising=False)

    loader = PlanLoader(working_dir=tmp_path)
    data = loader.load_plan()

    assert "modules" in data
    assert len(data["modules"]) == 2

    terragrunt_entry = next(item for item in data["modules"] if item["module_path"] == "module_tg")
    terraform_entry = next(item for item in data["modules"] if item["module_path"] == "module_tf")

    assert terragrunt_entry["plan"] == {"kind": "terragrunt"}
    assert terraform_entry["plan"] == {"kind": "terraform"}

    terragrunt_command = terragrunt_calls[0]
    assert terragrunt_command["args"][0] == "terragrunt"
    assert "--terragrunt-json" in terragrunt_command["args"]
    assert terragrunt_command["capture_output"] is True
    assert terragrunt_command["cwd"].resolve() == terragrunt_module.resolve()

    terraform_show = next(call for call in terraform_calls if call["args"][1] == "show")
    assert terraform_show["capture_output"] is True
    assert terraform_show["cwd"].resolve() == terraform_module.resolve()


def test_missing_artifact_raises(tmp_path):
    loader = PlanLoader(working_dir=tmp_path, plan_json_path=tmp_path / "missing.json")
    with pytest.raises(PlanLoaderError):
        loader.load_plan()

    loader = PlanLoader(working_dir=tmp_path, plan_file_path=tmp_path / "missing.tfplan")
    with pytest.raises(PlanLoaderError):
        loader.load_plan()
