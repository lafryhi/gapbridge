"""Service-level tests for the Sprint 4B teacher experience."""

from __future__ import annotations

from pathlib import Path

import pytest

from gapbridge.sprint4b_service import AI_MODE, TeacherWorkflowService
from gapbridge.state import WorkflowState


def test_teacher_service_starts_at_group_approval_gate(tmp_path: Path) -> None:
    service = TeacherWorkflowService.start(runtime_root=tmp_path / "runs")

    assert service.state is WorkflowState.GROUPS_PROPOSED
    assert service.analysis.title == "Grade 5 Mathematics - Fractions"
    assert len(service.analysis.learners) == 24
    assert service.approvals_by_gate() == {
        "groups": False,
        "plans": False,
        "exercises": False,
    }


def test_teacher_service_resumes_same_isolated_run(tmp_path: Path) -> None:
    root = tmp_path / "runs"
    started = TeacherWorkflowService.start(runtime_root=root)
    started.approve_groups(comment="Reviewed.")

    resumed = TeacherWorkflowService.resume(started.run_id, runtime_root=root)

    assert resumed.run_id == started.run_id
    assert resumed.state is WorkflowState.GROUPS_APPROVED
    assert resumed.approvals_by_gate()["groups"] is True
    assert resumed.groups().computed_membership == resumed.groups().effective_membership


def test_teacher_service_cannot_skip_group_gate(tmp_path: Path) -> None:
    service = TeacherWorkflowService.start(runtime_root=tmp_path / "runs")

    with pytest.raises(ValueError, match="GROUPS_APPROVED"):
        service.generate_plans()


def test_teacher_service_completes_offline_three_gate_flow(tmp_path: Path) -> None:
    root = tmp_path / "runs"
    service = TeacherWorkflowService.start(runtime_root=root)
    service.approve_groups(comment="Groups reviewed.")
    plans = service.generate_plans()
    service.approve_plans(comment="Plans reviewed.")
    exercises = service.generate_exercises()
    service.approve_exercises(comment="Exercises reviewed.")
    report_path = service.generate_report()

    resumed = TeacherWorkflowService.resume(service.run_id, runtime_root=root)
    assert resumed.state is WorkflowState.REPORT_READY
    assert resumed.approvals_by_gate() == {
        "groups": True,
        "plans": True,
        "exercises": True,
    }
    assert plans.provenance.provider == "strands"
    assert plans.provenance.model_id == "scripted-gapbridge-offline-v1"
    assert exercises.provenance.validation_status == "passed"
    assert report_path.read_text(encoding="utf-8").startswith(
        "# GapBridge Teacher Report"
    )


def test_teacher_service_declares_offline_ai_mode() -> None:
    assert AI_MODE == "STRANDS_OFFLINE_TEST"


def test_teacher_service_rejects_unknown_run(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="was not found"):
        TeacherWorkflowService.resume("missing-run", runtime_root=tmp_path / "runs")
