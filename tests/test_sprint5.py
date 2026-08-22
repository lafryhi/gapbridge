"""Sprint 5 tests for preflight, safe reset, errors, and demo consistency."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from gapbridge import assessment, config
from gapbridge.models import GroupName
from gapbridge.sprint4b_service import TeacherWorkflowService
from gapbridge.sprint5_demo import (
    DemoAction,
    format_preflight_report,
    friendly_demo_error,
    run_demo_preflight,
)
from gapbridge.state import WorkflowState


def test_demo_preflight_passes_without_network_requirements() -> None:
    report = run_demo_preflight(config.PROJECT_ROOT)

    assert report.ready is True
    assert [check.name for check in report.checks] == [
        "Python environment",
        "Required packages",
        "Synthetic dataset",
        "Runtime write access",
        "Strands import",
        "Streamlit import",
        "Scripted model",
        "Required project files",
    ]
    rendered = format_preflight_report(report)
    assert "READY: 8/8 checks passed." in rendered
    assert "Network, AWS, Bedrock, and external model calls: NONE" in rendered


def test_demo_preflight_reports_missing_dataset(tmp_path: Path) -> None:
    report = run_demo_preflight(tmp_path)
    dataset_check = next(
        check for check in report.checks if check.name == "Synthetic dataset"
    )

    assert report.ready is False
    assert dataset_check.passed is False
    assert "synthetic_assessment.csv" in dataset_check.detail


def test_fresh_demo_run_preserves_history_and_audit(tmp_path: Path) -> None:
    root = tmp_path / "runs"
    first = TeacherWorkflowService.start_fresh(runtime_root=root)
    original_audit = first.ctx.audit.path.read_bytes()
    original_state = first.ctx.store.path.read_bytes()

    second = TeacherWorkflowService.start_fresh(runtime_root=root)

    assert first.run_id != second.run_id
    assert first.ctx.run_dir.is_dir()
    assert second.ctx.run_dir.is_dir()
    assert first.ctx.audit.path.read_bytes() == original_audit
    assert first.ctx.store.path.read_bytes() == original_state
    assert first.state is WorkflowState.GROUPS_PROPOSED
    assert second.state is WorkflowState.GROUPS_PROPOSED


def test_resume_rejects_malformed_saved_artifact(tmp_path: Path) -> None:
    root = tmp_path / "runs"
    service = TeacherWorkflowService.start_fresh(runtime_root=root)
    service.approve_groups()
    service.generate_plans()
    service.ctx.plans_path.write_text("{not valid json", encoding="utf-8")

    with pytest.raises(ValidationError):
        TeacherWorkflowService.resume(service.run_id, runtime_root=root)


@pytest.mark.parametrize(
    ("action", "error", "expected"),
    [
        (
            DemoAction.GENERATE_PLANS,
            ValueError("Expected workflow state GROUPS_APPROVED"),
            "not available yet",
        ),
        (
            DemoAction.APPROVE_PLANS,
            ValueError("Expected workflow state PLAN_PROPOSED"),
            "approval gate is not ready",
        ),
        (
            DemoAction.RENDER,
            FileNotFoundError("remediation_plans.json"),
            "saved demo artifact is missing",
        ),
        (
            DemoAction.GENERATE_EXERCISES,
            ValueError("Strands did not return a valid ExerciseDraftBundle"),
            "did not pass GapBridge's safety checks",
        ),
        (
            DemoAction.START,
            FileNotFoundError("synthetic_assessment.csv"),
            "Grade 5 Fractions dataset is missing",
        ),
        (
            DemoAction.GENERATE_REPORT,
            OSError("permission denied"),
            "report could not be assembled",
        ),
    ],
)
def test_teacher_friendly_error_mapping(
    action: DemoAction, error: Exception, expected: str
) -> None:
    message = friendly_demo_error(action, error)

    assert expected in message
    assert str(error) not in message


def test_demo_summary_tracks_only_persisted_workflow_results(tmp_path: Path) -> None:
    service = TeacherWorkflowService.start_fresh(runtime_root=tmp_path / "runs")
    initial = service.demo_summary()
    assert initial.learners_analyzed == 24
    assert initial.group_counts == {
        "Mastered": 8,
        "Developing": 9,
        "Intensive Support": 7,
    }
    assert initial.plans_drafted == 0
    assert initial.exercise_items_generated == 0
    assert initial.approval_gates_completed == 0

    service.approve_groups()
    service.generate_plans()
    service.approve_plans()
    service.generate_exercises()
    service.approve_exercises()
    service.generate_report()
    final = service.demo_summary()

    assert final.plans_drafted == 3
    assert final.exercise_items_generated == 16
    assert final.approval_gates_completed == 3
    assert final.workflow_state == "REPORT_READY"
    assert final.priority_gaps == [
        "adding_fractions",
        "equivalent_fractions",
        "comparing_fractions",
    ]


def test_canonical_scenario_and_visible_documents_are_consistent() -> None:
    dataset = assessment.load_assessment_csv(
        config.PROJECT_ROOT / "data" / "synthetic_assessment.csv"
    )
    assert dataset.title == "Grade 5 Mathematics - Fractions"
    assert len(dataset.learners) == 24
    assert dataset.skills == config.REQUIRED_SKILLS
    assert [group.value for group in GroupName] == [
        "Mastered",
        "Developing",
        "Intensive Support",
    ]

    visible_files = (
        "README.md",
        "PROJECT_BRIEF.md",
        "MVP_SCOPE.md",
        "docs/architecture.md",
        "streamlit_app.py",
    )
    combined = "\n".join(
        (config.PROJECT_ROOT / path).read_text(encoding="utf-8")
        for path in visible_files
    ).lower()
    for stale in (
        "grade 6",
        "28 synthetic learners",
        "28 synthetic students",
        "five skills",
        "5 skills",
        "reteach / practice / enrich",
        "reteach 9 / practice 11 / enrich 8",
    ):
        assert stale not in combined
