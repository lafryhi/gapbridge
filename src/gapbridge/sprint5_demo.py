"""Offline demo hardening helpers for Sprint 5."""

from __future__ import annotations

import importlib
import json
import os
import sys
import tempfile
from dataclasses import dataclass
from enum import Enum
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from pydantic import ValidationError

from . import assessment, config
from .scripted_strands_model import OfflineScriptedModel
from .state import InvalidTransitionError


class DemoAction(str, Enum):
    START = "start"
    RESUME = "resume"
    APPROVE_GROUPS = "approve_groups"
    GENERATE_PLANS = "generate_plans"
    APPROVE_PLANS = "approve_plans"
    GENERATE_EXERCISES = "generate_exercises"
    APPROVE_EXERCISES = "approve_exercises"
    GENERATE_REPORT = "generate_report"
    RENDER = "render"


APPROVAL_ACTIONS = {
    DemoAction.APPROVE_GROUPS,
    DemoAction.APPROVE_PLANS,
    DemoAction.APPROVE_EXERCISES,
}
GENERATION_ACTIONS = {
    DemoAction.GENERATE_PLANS,
    DemoAction.GENERATE_EXERCISES,
}


def friendly_demo_error(action: DemoAction, error: Exception) -> str:
    """Translate internal failures into useful, non-technical teacher guidance."""
    message = str(error).lower()

    if isinstance(error, FileNotFoundError):
        if action is DemoAction.START or "synthetic_assessment.csv" in message:
            return (
                "The bundled Grade 5 Fractions dataset is missing. "
                "Run the demo preflight before starting again."
            )
        return (
            "A saved demo artifact is missing. Your earlier runs were not deleted; "
            "start a fresh demo run to continue safely."
        )

    if action in GENERATION_ACTIONS and (
        isinstance(error, ValidationError)
        or "strands did not return" in message
        or "not authoritative" in message
        or "differ" in message
    ):
        return (
            "The offline Strands draft did not pass GapBridge's safety checks. "
            "Nothing was approved or advanced; start a fresh run and try once more."
        )

    if isinstance(error, (ValidationError, json.JSONDecodeError)) or any(
        term in message for term in ("malformed", "invalid json", "artifact belongs")
    ):
        return (
            "A saved demo artifact could not be validated. The current run was left "
            "unchanged; start a fresh demo run to continue."
        )

    wrong_state = isinstance(error, InvalidTransitionError) or any(
        term in message
        for term in ("expected workflow state", "persisted", "approval is required")
    )
    if wrong_state and action in APPROVAL_ACTIONS:
        return (
            "This approval gate is not ready yet. Review and generate the preceding "
            "artifact first; GapBridge will not skip teacher checkpoints."
        )
    if wrong_state:
        return (
            "This step is not available yet. Complete the current review or approval "
            "gate before continuing."
        )

    if action is DemoAction.GENERATE_REPORT:
        return (
            "The teacher report could not be assembled. All approvals and saved drafts "
            "remain intact; run the preflight and try report generation again."
        )

    if action is DemoAction.RESUME or action is DemoAction.RENDER:
        return (
            "This saved run could not be opened safely. Its history is still preserved; "
            "start a fresh demo run to continue."
        )

    return (
        "GapBridge could not complete that step. The workflow was not advanced; "
        "run the demo preflight, then try again."
    )


@dataclass(frozen=True)
class PreflightCheck:
    name: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class PreflightReport:
    checks: tuple[PreflightCheck, ...]

    @property
    def ready(self) -> bool:
        return all(check.passed for check in self.checks)


REQUIRED_PROJECT_FILES = (
    "README.md",
    "requirements.txt",
    "streamlit_app.py",
    "run_sprint3_demo.py",
    "data/synthetic_assessment.csv",
    "src/gapbridge/sprint3_workflow.py",
    "src/gapbridge/sprint4b_service.py",
    "src/gapbridge/scripted_strands_model.py",
    "src/gapbridge/strands_orchestrator.py",
)


def _result(name: str, callback) -> PreflightCheck:
    try:
        detail = callback()
    except Exception as exc:  # Every check must report independently.
        return PreflightCheck(name=name, passed=False, detail=str(exc))
    return PreflightCheck(name=name, passed=True, detail=str(detail))


def _check_python() -> str:
    if sys.version_info < (3, 11):
        raise RuntimeError("Python 3.11 or newer is required")
    if sys.prefix == sys.base_prefix and not os.environ.get("VIRTUAL_ENV"):
        raise RuntimeError("run the command with the project .venv Python")
    return f"Python {sys.version.split()[0]} in an active virtual environment"


def _check_packages(project_root: Path) -> str:
    requirement_lines = (project_root / "requirements.txt").read_text(
        encoding="utf-8"
    ).splitlines()
    checked: list[str] = []
    for line in requirement_lines:
        requirement = line.strip()
        if not requirement or requirement.startswith("#"):
            continue
        if "==" not in requirement:
            raise RuntimeError(f"unlocked requirement: {requirement}")
        package, expected = requirement.split("==", maxsplit=1)
        try:
            installed = version(package)
        except PackageNotFoundError as exc:
            raise RuntimeError(f"missing package: {package}") from exc
        if installed != expected:
            raise RuntimeError(
                f"{package} {installed} is installed; expected {expected}"
            )
        checked.append(f"{package} {installed}")
    return f"{len(checked)} pinned packages available"


def _check_dataset(project_root: Path) -> str:
    data_path = project_root / "data" / "synthetic_assessment.csv"
    dataset = assessment.load_assessment_csv(data_path)
    if dataset.title != config.ASSESSMENT_TITLE:
        raise RuntimeError("assessment title does not match the canonical scenario")
    if len(dataset.learners) != 24:
        raise RuntimeError("canonical demo requires exactly 24 synthetic learners")
    if dataset.skills != config.REQUIRED_SKILLS:
        raise RuntimeError("dataset skills do not match deterministic configuration")
    return "Grade 5 Mathematics - Fractions; 24 synthetic learners; 4 skills"


def _check_runtime_write(project_root: Path) -> str:
    runtime_dir = project_root / "runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    marker: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            prefix=".gapbridge-preflight-",
            suffix=".tmp",
            dir=runtime_dir,
            delete=False,
        ) as handle:
            handle.write("GapBridge preflight write check")
            marker = Path(handle.name)
        if marker.read_text(encoding="utf-8") != "GapBridge preflight write check":
            raise RuntimeError("runtime write verification failed")
    finally:
        if marker is not None:
            marker.unlink(missing_ok=True)
    return "local runtime directory is writable"


def _check_strands_import() -> str:
    module = importlib.import_module("strands")
    if not getattr(module, "Agent", None):
        raise RuntimeError("strands.Agent is unavailable")
    return f"strands-agents {version('strands-agents')} imports successfully"


def _check_streamlit_import() -> str:
    module = importlib.import_module("streamlit")
    return f"Streamlit {module.__version__} imports successfully"


def _check_scripted_model() -> str:
    model = OfflineScriptedModel()
    model_id = model.get_config().get("model_id")
    if model_id != "scripted-gapbridge-offline-v1":
        raise RuntimeError("offline scripted model configuration is invalid")
    return f"offline scripted model available: {model_id}"


def _check_project_files(project_root: Path) -> str:
    missing = [path for path in REQUIRED_PROJECT_FILES if not (project_root / path).is_file()]
    if missing:
        raise RuntimeError("missing required files: " + ", ".join(missing))
    return f"{len(REQUIRED_PROJECT_FILES)} required project files present"


def run_demo_preflight(project_root: Path | None = None) -> PreflightReport:
    """Run local-only checks. This function performs no network operation."""
    root = (project_root or config.PROJECT_ROOT).resolve()
    checks = (
        _result("Python environment", _check_python),
        _result("Required packages", lambda: _check_packages(root)),
        _result("Synthetic dataset", lambda: _check_dataset(root)),
        _result("Runtime write access", lambda: _check_runtime_write(root)),
        _result("Strands import", _check_strands_import),
        _result("Streamlit import", _check_streamlit_import),
        _result("Scripted model", _check_scripted_model),
        _result("Required project files", lambda: _check_project_files(root)),
    )
    return PreflightReport(checks=checks)


def format_preflight_report(report: PreflightReport) -> str:
    lines = ["GapBridge demo preflight (local only)"]
    for check in report.checks:
        status = "PASS" if check.passed else "FAIL"
        lines.append(f"[{status}] {check.name}: {check.detail}")
    passed = sum(check.passed for check in report.checks)
    final = "READY" if report.ready else "NOT READY"
    lines.extend(
        [
            f"{final}: {passed}/{len(report.checks)} checks passed.",
            "Network, AWS, Bedrock, and external model calls: NONE",
        ]
    )
    return "\n".join(lines)
