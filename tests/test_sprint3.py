"""Sprint 3 tests: gates, isolation, providers, Strands tools and provenance."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from gapbridge import config, sprint3_workflow as workflow
from gapbridge.models import GroupName
from gapbridge.scripted_strands_model import OfflineScriptedModel
from gapbridge.sprint3_providers import DeterministicDraftProvider
from gapbridge.sprint3_schemas import (
    ApprovalRecord,
    ExerciseArtifact,
    PlanArtifact,
    PlanDraftBundle,
)
from gapbridge.sprint3_storage import (
    ApprovalStore,
    create_run_context,
    load_model,
    stable_hash,
)
from gapbridge.sprint3_tools import create_safe_tools
from gapbridge.state import WorkflowState
from gapbridge.strands_orchestrator import StrandsContentOrchestrator

DATA_PATH = config.PROJECT_ROOT / "data" / "synthetic_assessment.csv"


@pytest.fixture()
def started(tmp_path: Path):
    ctx = create_run_context(runtime_root=tmp_path / "runs", run_id="test-run")
    analysis = workflow.start_run(DATA_PATH, ctx)
    return ctx, analysis


@pytest.fixture()
def groups_approved(started):
    ctx, analysis = started
    workflow.approve_groups(ctx, actor="teacher", comment="Reviewed groups.")
    return ctx, analysis


def test_sprint3_states_are_explicit_and_reachable() -> None:
    for state in (
        WorkflowState.GROUPS_PROPOSED,
        WorkflowState.GROUPS_APPROVED,
        WorkflowState.PLAN_APPROVED,
        WorkflowState.EXERCISES_PROPOSED,
        WorkflowState.EXERCISES_APPROVED,
    ):
        assert state in WorkflowState


def test_start_run_stops_at_group_gate(started) -> None:
    ctx, _analysis = started
    record = ctx.store.load()
    assert record is not None
    assert record.current_state == "GROUPS_PROPOSED"
    assert record.history == [
        "UPLOADED",
        "ANALYZED",
        "GROUPED",
        "GROUPS_PROPOSED",
    ]


def test_plan_generation_cannot_skip_group_gate(started) -> None:
    ctx, analysis = started
    with pytest.raises(ValueError, match="GROUPS_APPROVED"):
        workflow.propose_plans(analysis, ctx, DeterministicDraftProvider())


def test_group_approval_is_persisted(groups_approved) -> None:
    ctx, _analysis = groups_approved
    approvals = ctx.approvals.read_all()
    assert len(approvals) == 1
    assert approvals[0].gate == "groups"
    assert approvals[0].decision == "approved"
    assert approvals[0].run_id == ctx.run_id
    assert ctx.store.load().current_state == "GROUPS_APPROVED"


def test_run_directories_are_isolated(tmp_path: Path) -> None:
    root = tmp_path / "runs"
    first = create_run_context(runtime_root=root, run_id="run-one")
    second = create_run_context(runtime_root=root, run_id="run-two")
    assert first.run_dir != second.run_dir
    assert first.store.path != second.store.path
    assert first.approvals.path != second.approvals.path
    assert first.run_dir.parent == second.run_dir.parent


@pytest.mark.parametrize("run_id", ["../escape", "with space", "", "a/b"])
def test_unsafe_run_ids_are_rejected(tmp_path: Path, run_id: str) -> None:
    with pytest.raises(ValueError, match="run_id"):
        create_run_context(runtime_root=tmp_path / "runs", run_id=run_id)


def test_existing_run_id_is_not_reused(tmp_path: Path) -> None:
    root = tmp_path / "runs"
    create_run_context(runtime_root=root, run_id="same-run")
    with pytest.raises(FileExistsError):
        create_run_context(runtime_root=root, run_id="same-run")


def test_approval_store_rejects_foreign_run(tmp_path: Path) -> None:
    store = ApprovalStore(tmp_path / "approvals.jsonl", "run-one")
    foreign = ApprovalRecord(
        approval_id="approval-test",
        run_id="run-two",
        gate="groups",
        decision="approved",
        actor="teacher",
        timestamp="2026-08-22T00:00:00+00:00",
        artifact_type="groups",
        artifact_version=1,
        artifact_hash="a" * 64,
    )
    with pytest.raises(ValueError, match="run_id"):
        store.append(foreign)


def test_structured_output_rejects_extra_fields(groups_approved) -> None:
    _ctx, analysis = groups_approved
    result = DeterministicDraftProvider().draft_plans(analysis, version=1)
    raw = result.value.model_dump(mode="json")
    raw["unexpected"] = True
    with pytest.raises(ValidationError, match="extra"):
        PlanDraftBundle.model_validate(raw)


def test_structured_output_rejects_duplicate_groups(groups_approved) -> None:
    _ctx, analysis = groups_approved
    result = DeterministicDraftProvider().draft_plans(analysis, version=1)
    raw = result.value.model_dump(mode="json")
    raw["plans"][1]["group"] = raw["plans"][0]["group"]
    with pytest.raises(ValidationError, match="exactly one"):
        PlanDraftBundle.model_validate(raw)


def test_safe_tool_allowlist_has_no_mutating_capabilities(groups_approved) -> None:
    ctx, analysis = groups_approved
    tools = create_safe_tools(ctx, analysis)
    names = {item.tool_name for item in tools}
    assert names == {
        "get_workflow_status",
        "get_class_evidence",
        "get_group_profile",
        "get_plan_constraints",
        "get_teacher_revision_feedback",
        "get_approved_plan",
        "validate_plan_alignment",
        "validate_exercise_set",
    }
    assert not names & {
        "save_state",
        "record_approval",
        "load_assessment",
        "assemble_report",
        "write_file",
    }


def test_safe_evidence_tools_return_controller_values(groups_approved) -> None:
    ctx, analysis = groups_approved
    tools = {item.tool_name: item for item in create_safe_tools(ctx, analysis)}
    status = tools["get_workflow_status"]()
    evidence = tools["get_class_evidence"]()
    profile = tools["get_group_profile"](group="Developing")
    assert status["run_id"] == ctx.run_id
    assert status["state"] == "GROUPS_APPROVED"
    assert evidence["learner_count"] == 24
    assert profile["member_count"] == 9


def test_empty_group_produces_inactive_plan(groups_approved) -> None:
    _ctx, analysis = groups_approved
    for learner in analysis.learners:
        if learner.group is GroupName.MASTERED:
            learner.group = GroupName.DEVELOPING
    result = DeterministicDraftProvider().draft_plans(analysis, version=1)
    mastered = next(plan for plan in result.value.plans if plan.group == "Mastered")
    assert mastered.active is False
    assert mastered.target_skills == []
    assert mastered.session_count == 0


def test_deterministic_fallback_is_explicitly_labelled(groups_approved) -> None:
    ctx, analysis = groups_approved
    artifact = workflow.propose_plans(
        analysis, ctx, DeterministicDraftProvider()
    )
    assert artifact.provenance.provider == "deterministic"
    assert artifact.provenance.generated_by == "deterministic-template-v1"
    assert artifact.provenance.fallback is True
    assert artifact.provenance.tool_calls == []


def test_strands_plan_draft_uses_real_tool_loop(groups_approved) -> None:
    ctx, analysis = groups_approved
    model = OfflineScriptedModel()
    provider = StrandsContentOrchestrator(ctx, analysis, model)
    artifact = workflow.propose_plans(analysis, ctx, provider)
    assert artifact.provenance.provider == "strands"
    assert artifact.provenance.model_id == "scripted-gapbridge-offline-v1"
    assert artifact.provenance.sdk_version == "1.52.0"
    assert "get_class_evidence" in artifact.provenance.tool_calls
    assert artifact.provenance.tool_calls.count("get_group_profile") == 3
    assert artifact.provenance.tool_calls[-1] == "PlanDraftBundle"


def test_exercises_require_persisted_plan_approval(groups_approved) -> None:
    ctx, analysis = groups_approved
    provider = DeterministicDraftProvider()
    workflow.propose_plans(analysis, ctx, provider)
    with pytest.raises(ValueError, match="PLAN_APPROVED"):
        workflow.propose_exercises(analysis, ctx, provider)


def test_report_requires_exercise_gate(groups_approved) -> None:
    ctx, analysis = groups_approved
    provider = DeterministicDraftProvider()
    workflow.propose_plans(analysis, ctx, provider)
    workflow.approve_plans(ctx, actor="teacher")
    workflow.propose_exercises(analysis, ctx, provider)
    with pytest.raises(ValueError, match="EXERCISES_APPROVED"):
        workflow.generate_report(analysis, ctx)


def test_full_sprint3_strands_path(groups_approved) -> None:
    ctx, analysis = groups_approved
    provider = StrandsContentOrchestrator(ctx, analysis, OfflineScriptedModel())
    plans = workflow.propose_plans(analysis, ctx, provider)
    workflow.approve_plans(ctx, actor="teacher", comment="Plans approved.")
    exercises = workflow.propose_exercises(analysis, ctx, provider)
    workflow.approve_exercises(
        ctx, actor="teacher", comment="Exercises approved."
    )
    report_path = workflow.generate_report(analysis, ctx)

    record = ctx.store.load()
    assert record is not None
    assert record.current_state == "REPORT_READY"
    assert record.history == [
        "UPLOADED",
        "ANALYZED",
        "GROUPED",
        "GROUPS_PROPOSED",
        "GROUPS_APPROVED",
        "PLAN_PROPOSED",
        "PLAN_APPROVED",
        "EXERCISES_PROPOSED",
        "EXERCISES_APPROVED",
        "REPORT_READY",
    ]
    approvals = ctx.approvals.read_all()
    assert [item.gate for item in approvals] == ["groups", "plans", "exercises"]
    assert all(item.decision == "approved" for item in approvals)
    assert all(item.run_id == ctx.run_id for item in approvals)
    assert len(exercises.draft.sets) == 3
    assert "validate_exercise_set" in exercises.provenance.tool_calls
    assert report_path.exists()
    report = report_path.read_text(encoding="utf-8")
    assert "## Approved Exercise Appendix" in report
    assert "## Teacher Approval Record" in report
    assert "scripted-gapbridge-offline-v1" in report
    assert report.count("**groups**: approved") == 1
    assert report.count("**plans**: approved") == 1
    assert report.count("**exercises**: approved") == 1
    assert plans.run_id == ctx.run_id


def test_persisted_artifacts_roundtrip(groups_approved) -> None:
    ctx, analysis = groups_approved
    provider = DeterministicDraftProvider()
    plans = workflow.propose_plans(analysis, ctx, provider)
    workflow.approve_plans(ctx, actor="teacher")
    exercises = workflow.propose_exercises(analysis, ctx, provider)
    loaded_plans = load_model(ctx.plans_path, PlanArtifact)
    loaded_exercises = load_model(ctx.exercises_path, ExerciseArtifact)
    assert loaded_plans.run_id == ctx.run_id
    assert loaded_plans.status == "approved"
    assert loaded_plans.draft == plans.draft
    assert loaded_exercises.draft == exercises.draft


def test_provenance_hash_is_stable_and_input_sensitive() -> None:
    assert stable_hash({"a": 1, "b": 2}) == stable_hash({"b": 2, "a": 1})
    assert stable_hash({"a": 1}) != stable_hash({"a": 2})


def test_audit_events_are_run_scoped(groups_approved) -> None:
    ctx, _analysis = groups_approved
    events = ctx.audit.read_all()
    assert events
    assert all(event.metadata["run_id"] == ctx.run_id for event in events)


def test_manifest_declares_synthetic_only(groups_approved) -> None:
    ctx, _analysis = groups_approved
    manifest = json.loads(ctx.manifest_path.read_text(encoding="utf-8"))
    assert manifest["run_id"] == ctx.run_id
    assert manifest["data_policy"] == "synthetic-only"
    assert manifest["workflow"] == "sprint3"
