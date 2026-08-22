"""Sprint 2 workflow tests: approval gate, revision, state machine,
audit events and the complete end-to-end deterministic pipeline."""

from __future__ import annotations

from pathlib import Path

import pytest

from gapbridge import config
from gapbridge.audit import AuditLog
from gapbridge.models import GroupName
from gapbridge.pipeline import (
    PipelineContext,
    approve_plans,
    generate_materials,
    generate_report,
    load_and_prepare,
    propose_plans,
    request_revision,
)
from gapbridge.plans import load_plans
from gapbridge.state import (
    InvalidTransitionError,
    StateStore,
    WorkflowState,
    advance,
)

DATA_PATH = config.PROJECT_ROOT / "data" / "synthetic_assessment.csv"


@pytest.fixture()
def ctx(tmp_path):
    return PipelineContext(
        store=StateStore(tmp_path / "state" / "workflow_state.json"),
        audit=AuditLog(tmp_path / "audit" / "audit_log.jsonl"),
        plans_path=tmp_path / "artifacts" / "remediation_plan.json",
        exercises_path=tmp_path / "artifacts" / "exercise_sets.json",
        report_path=tmp_path / "artifacts" / "teacher_report.md",
    )


def _event_types(ctx: PipelineContext) -> list[str]:
    return [event.event_type for event in ctx.audit.read_all()]


class TestApprovalGate:
    def test_approval_records_decision_fields(self, ctx):
        analysis = load_and_prepare(DATA_PATH, ctx)
        version = propose_plans(analysis, ctx)
        decision = approve_plans(
            ctx, version, actor="teacher", comment="Looks good."
        )
        assert decision.decision == "approved"
        assert decision.actor == "teacher"
        assert decision.timestamp
        assert decision.plan_version == 1
        assert decision.comment == "Looks good."

    def test_approval_persists_plan_status_and_audit_event(self, ctx):
        analysis = load_and_prepare(DATA_PATH, ctx)
        version = propose_plans(analysis, ctx)
        approve_plans(ctx, version, actor="teacher")
        plans, stored_version, status = load_plans(ctx.plans_path)
        assert stored_version == 1
        assert status == "approved"
        for group in GroupName:
            assert plans[group].current.status == "approved"
        events = _event_types(ctx)
        assert "PLAN_PROPOSED" in events
        assert "PLAN_APPROVED" in events

    def test_revision_request_flow_and_audit(self, ctx):
        analysis = load_and_prepare(DATA_PATH, ctx)
        propose_plans(analysis, ctx)
        new_version = request_revision(
            analysis,
            ctx,
            current_version=1,
            actor="teacher",
            comment="Add more practice for adding fractions.",
        )
        assert new_version == 2
        record = ctx.store.load()
        assert record is not None
        assert record.current_state == WorkflowState.PLAN_PROPOSED.value
        assert record.history == [
            "UPLOADED",
            "ANALYZED",
            "GROUPED",
            "PLAN_PROPOSED",
            "REVISION_REQUESTED",
            "PLAN_PROPOSED",
        ]
        events = _event_types(ctx)
        assert events.count("PLAN_PROPOSED") == 2
        assert "PLAN_REVISION_REQUESTED" in events

    def test_revision_preserves_previous_versions_on_disk(self, ctx):
        analysis = load_and_prepare(DATA_PATH, ctx)
        propose_plans(analysis, ctx)
        request_revision(analysis, ctx, current_version=1, actor="teacher")
        plans, stored_version, _status = load_plans(ctx.plans_path)
        assert stored_version == 2
        for group in GroupName:
            versions = plans[group].versions
            assert [v.version for v in versions] == [1, 2]
            assert versions[0].plan_id.endswith("-v1")

    def test_invalid_transitions_are_rejected(self, tmp_path):
        store = StateStore(tmp_path / "state.json")
        advance(store, WorkflowState.ANALYZED)  # from implicit UPLOADED
        with pytest.raises(InvalidTransitionError):
            advance(store, WorkflowState.APPROVED)  # ANALYZED -> APPROVED
        advance(store, WorkflowState.GROUPED)
        with pytest.raises(InvalidTransitionError):
            advance(store, WorkflowState.MATERIALS_GENERATED)
        advance(store, WorkflowState.PLAN_PROPOSED)
        advance(store, WorkflowState.REVISION_REQUESTED)
        with pytest.raises(InvalidTransitionError):
            advance(store, WorkflowState.REPORT_READY)


class TestEndToEndWorkflow:
    def test_full_accepted_plan_path(self, ctx):
        analysis = load_and_prepare(DATA_PATH, ctx)
        version = propose_plans(analysis, ctx)
        decision = approve_plans(
            ctx, version, actor="teacher (simulated)", comment="Demo approval."
        )
        sets = generate_materials(analysis, ctx)
        report_path = generate_report(
            analysis, ctx, plan_version=version,
            approvals=[decision], source_name=DATA_PATH.name,
        )

        record = ctx.store.load()
        assert record is not None
        assert record.current_state == WorkflowState.REPORT_READY.value
        assert record.history == [
            "UPLOADED",
            "ANALYZED",
            "GROUPED",
            "PLAN_PROPOSED",
            "APPROVED",
            "MATERIALS_GENERATED",
            "REPORT_READY",
        ]
        assert ctx.plans_path.exists()
        assert ctx.exercises_path.exists()
        assert report_path.exists()
        content = report_path.read_text(encoding="utf-8")
        assert "# GapBridge Teacher Report" in content
        assert "Plan version: 1" in content
        total_items = sum(len(s.items) for s in sets.values())
        assert total_items > 0

    def test_full_revision_then_accept_path(self, ctx):
        analysis = load_and_prepare(DATA_PATH, ctx)
        propose_plans(analysis, ctx)
        version = request_revision(
            analysis, ctx, current_version=1, actor="teacher", comment="Revise."
        )
        decision = approve_plans(ctx, version, actor="teacher")
        generate_materials(analysis, ctx)
        report_path = generate_report(
            analysis, ctx, plan_version=version,
            approvals=[decision], source_name=DATA_PATH.name,
        )
        content = report_path.read_text(encoding="utf-8")
        assert "Plan version: 2" in content
        plans, stored_version, _status = load_plans(ctx.plans_path)
        assert stored_version == 2
        for group in GroupName:
            assert len(plans[group].versions) == 2

    def test_audit_trail_covers_all_sprint2_events(self, ctx):
        analysis = load_and_prepare(DATA_PATH, ctx)
        version = propose_plans(analysis, ctx)
        decision = approve_plans(ctx, version, actor="teacher")
        generate_materials(analysis, ctx)
        generate_report(
            analysis, ctx, plan_version=version,
            approvals=[decision], source_name=DATA_PATH.name,
        )
        expected = [
            "DATASET_UPLOADED",
            "ANALYSIS_COMPLETED",
            "GROUP_ASSIGNMENT_COMPLETED",
            "PLAN_PROPOSED",
            "PLAN_APPROVED",
            "MATERIALS_GENERATED",
            "REPORT_GENERATED",
        ]
        events = _event_types(ctx)
        assert events == expected
        approved_event = next(
            e for e in ctx.audit.read_all() if e.event_type == "PLAN_APPROVED"
        )
        assert approved_event.metadata["actor"] == "teacher"
        assert approved_event.metadata["plan_version"] == 1

    def test_materials_require_approved_plans(self, ctx):
        analysis = load_and_prepare(DATA_PATH, ctx)
        propose_plans(analysis, ctx)
        with pytest.raises(ValueError, match="approved"):
            generate_materials(analysis, ctx)

    def test_approval_rejects_mismatched_version(self, ctx):
        analysis = load_and_prepare(DATA_PATH, ctx)
        propose_plans(analysis, ctx)
        with pytest.raises(ValueError, match="does not match"):
            approve_plans(ctx, 99, actor="teacher")


class TestSprint1Regression:
    def test_grouping_logic_unchanged(self, ctx):
        analysis = load_and_prepare(DATA_PATH, ctx)
        counts = analysis.group_counts()
        assert counts[GroupName.MASTERED] == 8
        assert counts[GroupName.DEVELOPING] == 9
        assert counts[GroupName.INTENSIVE_SUPPORT] == 7
