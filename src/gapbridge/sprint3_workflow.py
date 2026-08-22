"""Deterministic outer workflow controller for Sprint 3."""

from __future__ import annotations

import os
import uuid
from pathlib import Path

from . import assessment, gaps, grouping, state as state_mod
from .models import AuditEvent, ClassAnalysis, GroupName
from .sprint3_evidence import (
    analysis_snapshot,
    class_evidence,
    plan_constraints,
)
from .sprint3_providers import ExerciseDraftProvider, PlanDraftProvider
from .sprint3_report import build_sprint3_report
from .sprint3_schemas import (
    ApprovalRecord,
    ArtifactProvenance,
    ExerciseArtifact,
    ExerciseDraftBundle,
    GroupProposalArtifact,
    PlanArtifact,
    PlanDraftBundle,
)
from .sprint3_storage import (
    Sprint3RunContext,
    load_model,
    save_json,
    save_model,
    stable_hash,
    utc_now_iso,
)
from .state import WorkflowState


def _current_state(ctx: Sprint3RunContext) -> WorkflowState:
    record = ctx.store.load()
    if record is None:
        return WorkflowState.UPLOADED
    return WorkflowState(record.current_state)


def _require_state(ctx: Sprint3RunContext, expected: WorkflowState) -> None:
    current = _current_state(ctx)
    if current is not expected:
        raise ValueError(
            f"Expected workflow state {expected.value}, found {current.value}."
        )


def _log(
    ctx: Sprint3RunContext,
    event_type: str,
    actor: str,
    details: str,
    metadata: dict[str, object] | None = None,
) -> None:
    ctx.audit.append(
        AuditEvent(
            timestamp=utc_now_iso(),
            event_type=event_type,
            state=_current_state(ctx).value,
            actor=actor,
            details=details,
            metadata={"run_id": ctx.run_id, **(metadata or {})},
        )
    )


def _group_artifact(analysis: ClassAnalysis, run_id: str) -> GroupProposalArtifact:
    membership = {
        group.value: [
            learner.learner_id
            for learner in analysis.learners
            if learner.group is group
        ]
        for group in GroupName
    }
    rationales = {
        learner.learner_id: learner.explanation or ""
        for learner in analysis.learners
    }
    return GroupProposalArtifact(
        run_id=run_id,
        status="proposed",
        computed_membership=membership,
        effective_membership={key: list(value) for key, value in membership.items()},
        rationales=rationales,
        input_hash=stable_hash(analysis_snapshot(analysis)),
    )


def start_run(
    csv_path: str | Path,
    ctx: Sprint3RunContext,
) -> ClassAnalysis:
    """Load, compute, group, and create the Gate 1 proposal."""
    dataset = assessment.load_assessment_csv(csv_path)
    state_mod.initialize(ctx.store)
    save_json(
        ctx.manifest_path,
        {
            "run_id": ctx.run_id,
            "created_at": utc_now_iso(),
            "source_file": Path(csv_path).name,
            "data_policy": "synthetic-only",
            "workflow": "sprint3",
        },
    )
    _log(
        ctx,
        "DATASET_UPLOADED",
        "system",
        f"Loaded {len(dataset.learners)} synthetic learners",
        {"source_file": Path(csv_path).name},
    )

    analysis = gaps.analyze_class(dataset.learners, title=dataset.title)
    state_mod.advance(ctx.store, WorkflowState.ANALYZED)
    _log(ctx, "ANALYSIS_COMPLETED", "system", "Computed learner evidence")

    grouping.assign_groups(analysis)
    state_mod.advance(ctx.store, WorkflowState.GROUPED)
    save_json(ctx.analysis_path, analysis_snapshot(analysis))
    _log(
        ctx,
        "GROUP_ASSIGNMENT_COMPLETED",
        "system",
        "Computed deterministic learner groups",
    )

    save_model(ctx.groups_path, _group_artifact(analysis, ctx.run_id))
    state_mod.advance(ctx.store, WorkflowState.GROUPS_PROPOSED)
    _log(ctx, "GROUPS_PROPOSED", "system", "Proposed deterministic groups")
    return analysis


def _approve_gate(
    ctx: Sprint3RunContext,
    *,
    gate: str,
    actor: str,
    artifact_type: str,
    artifact_version: int,
    artifact_hash: str,
    target_state: WorkflowState,
    comment: str,
) -> ApprovalRecord:
    current = _current_state(ctx)
    state_mod.validate_transition(current, target_state)
    existing = next(
        (
            item
            for item in ctx.approvals.read_all()
            if item.gate == gate
            and item.artifact_version == artifact_version
            and item.decision == "approved"
        ),
        None,
    )
    if existing is not None:
        if existing.artifact_hash != artifact_hash:
            raise ValueError("existing approval hash does not match the artifact")
        state_mod.advance(ctx.store, target_state)
        return existing
    record = ApprovalRecord(
        approval_id=f"approval-{uuid.uuid4().hex}",
        run_id=ctx.run_id,
        gate=gate,
        decision="approved",
        actor=actor,
        timestamp=utc_now_iso(),
        artifact_type=artifact_type,
        artifact_version=artifact_version,
        artifact_hash=artifact_hash,
        comment=comment,
    )
    ctx.approvals.append(record)
    state_mod.advance(ctx.store, target_state)
    _log(
        ctx,
        f"{gate.upper()}_APPROVED",
        actor,
        f"Approved {artifact_type} version {artifact_version}",
        {"approval_id": record.approval_id, "artifact_hash": artifact_hash},
    )
    return record


def approve_groups(
    ctx: Sprint3RunContext,
    *,
    actor: str,
    comment: str = "",
) -> ApprovalRecord:
    _require_state(ctx, WorkflowState.GROUPS_PROPOSED)
    artifact = load_model(ctx.groups_path, GroupProposalArtifact)
    if artifact.computed_membership != artifact.effective_membership:
        raise ValueError("Sprint 3 does not permit unrecorded group changes")
    state_mod.validate_transition(
        _current_state(ctx), WorkflowState.GROUPS_APPROVED
    )
    artifact.status = "approved"
    save_model(ctx.groups_path, artifact)
    decision = _approve_gate(
        ctx,
        gate="groups",
        actor=actor,
        artifact_type="groups",
        artifact_version=artifact.version,
        artifact_hash=stable_hash(
            {
                "membership": artifact.effective_membership,
                "rationales": artifact.rationales,
            }
        ),
        target_state=WorkflowState.GROUPS_APPROVED,
        comment=comment,
    )
    return decision


def _validate_plan_bundle(
    analysis: ClassAnalysis, bundle: PlanDraftBundle
) -> None:
    for plan in bundle.plans:
        constraints = plan_constraints(analysis, GroupName(plan.group))
        if not constraints["target_skills"]:
            if plan.active or plan.target_skills or plan.session_count != 0:
                raise ValueError(f"{plan.group}: empty group plan must be inactive")
            continue
        if plan.target_skills != constraints["target_skills"]:
            raise ValueError(f"{plan.group}: target skills are not authoritative")
        if plan.session_count != constraints["session_count"]:
            raise ValueError(f"{plan.group}: session count is not authoritative")
        if plan.priority != constraints["priority"]:
            raise ValueError(f"{plan.group}: priority is not authoritative")


def _provenance(
    ctx: Sprint3RunContext,
    result,
    input_value: object,
) -> ArtifactProvenance:
    return ArtifactProvenance(
        generated_by=result.generated_by,
        provider=result.provider,
        model_id=result.model_id,
        agent_name=result.agent_name,
        sdk_version=result.sdk_version,
        timestamp=utc_now_iso(),
        run_id=ctx.run_id,
        input_hash=stable_hash(input_value),
        tool_calls=result.tool_calls,
        fallback=result.fallback,
    )


def propose_plans(
    analysis: ClassAnalysis,
    ctx: Sprint3RunContext,
    provider: PlanDraftProvider,
    *,
    version: int = 1,
    revision_feedback: str = "",
) -> PlanArtifact:
    _require_state(ctx, WorkflowState.GROUPS_APPROVED)
    if not ctx.approvals.approved("groups", 1):
        raise ValueError("persisted group approval is required")
    groups = load_model(ctx.groups_path, GroupProposalArtifact)
    if groups.status != "approved":
        raise ValueError("approved group artifact is required")
    result = provider.draft_plans(
        analysis, version=version, revision_feedback=revision_feedback
    )
    _validate_plan_bundle(analysis, result.value)
    input_value = {
        "evidence": class_evidence(analysis),
        "constraints": {
            group.value: plan_constraints(analysis, group) for group in GroupName
        },
        "version": version,
        "revision_feedback": revision_feedback,
    }
    artifact = PlanArtifact(
        run_id=ctx.run_id,
        version=version,
        status="proposed",
        draft=result.value,
        provenance=_provenance(ctx, result, input_value),
    )
    state_mod.validate_transition(_current_state(ctx), WorkflowState.PLAN_PROPOSED)
    save_model(ctx.plans_path, artifact)
    state_mod.advance(ctx.store, WorkflowState.PLAN_PROPOSED)
    _log(
        ctx,
        "PLAN_PROPOSED",
        "system",
        f"Proposed remediation plans v{version}",
        {"provider": result.provider, "tool_calls": result.tool_calls},
    )
    return artifact


def approve_plans(
    ctx: Sprint3RunContext,
    *,
    actor: str,
    comment: str = "",
) -> ApprovalRecord:
    _require_state(ctx, WorkflowState.PLAN_PROPOSED)
    artifact = load_model(ctx.plans_path, PlanArtifact)
    state_mod.validate_transition(_current_state(ctx), WorkflowState.PLAN_APPROVED)
    artifact.status = "approved"
    save_model(ctx.plans_path, artifact)
    decision = _approve_gate(
        ctx,
        gate="plans",
        actor=actor,
        artifact_type="remediation_plans",
        artifact_version=artifact.version,
        artifact_hash=stable_hash(artifact.draft),
        target_state=WorkflowState.PLAN_APPROVED,
        comment=comment,
    )
    return decision


def _validate_exercise_bundle(
    bundle: ExerciseDraftBundle, plans: PlanArtifact
) -> None:
    plan_targets = {plan.group: plan.target_skills for plan in plans.draft.plans}
    for exercise_set in bundle.sets:
        if exercise_set.target_skills != plan_targets[exercise_set.group]:
            raise ValueError(
                f"{exercise_set.group}: exercise targets differ from approved plan"
            )


def propose_exercises(
    analysis: ClassAnalysis,
    ctx: Sprint3RunContext,
    provider: ExerciseDraftProvider,
    *,
    version: int = 1,
) -> ExerciseArtifact:
    _require_state(ctx, WorkflowState.PLAN_APPROVED)
    plans = load_model(ctx.plans_path, PlanArtifact)
    if plans.status != "approved" or not ctx.approvals.approved(
        "plans", plans.version
    ):
        raise ValueError("persisted plan approval is required")
    result = provider.draft_exercises(analysis, plans, version=version)
    _validate_exercise_bundle(result.value, plans)
    artifact = ExerciseArtifact(
        run_id=ctx.run_id,
        version=version,
        status="proposed",
        draft=result.value,
        provenance=_provenance(
            ctx,
            result,
            {"approved_plan": plans.draft, "version": version},
        ),
    )
    state_mod.validate_transition(
        _current_state(ctx), WorkflowState.EXERCISES_PROPOSED
    )
    save_model(ctx.exercises_path, artifact)
    state_mod.advance(ctx.store, WorkflowState.EXERCISES_PROPOSED)
    _log(
        ctx,
        "EXERCISES_PROPOSED",
        "system",
        f"Proposed exercise sets v{version}",
        {"provider": result.provider, "tool_calls": result.tool_calls},
    )
    return artifact


def approve_exercises(
    ctx: Sprint3RunContext,
    *,
    actor: str,
    comment: str = "",
) -> ApprovalRecord:
    _require_state(ctx, WorkflowState.EXERCISES_PROPOSED)
    artifact = load_model(ctx.exercises_path, ExerciseArtifact)
    state_mod.validate_transition(
        _current_state(ctx), WorkflowState.EXERCISES_APPROVED
    )
    artifact.status = "approved"
    save_model(ctx.exercises_path, artifact)
    decision = _approve_gate(
        ctx,
        gate="exercises",
        actor=actor,
        artifact_type="exercise_sets",
        artifact_version=artifact.version,
        artifact_hash=stable_hash(artifact.draft),
        target_state=WorkflowState.EXERCISES_APPROVED,
        comment=comment,
    )
    return decision


def generate_report(
    analysis: ClassAnalysis,
    ctx: Sprint3RunContext,
) -> Path:
    _require_state(ctx, WorkflowState.EXERCISES_APPROVED)
    approvals = ctx.approvals.read_all()
    if {item.gate for item in approvals if item.decision == "approved"} != {
        "groups",
        "plans",
        "exercises",
    }:
        raise ValueError("all three persisted approvals are required")
    groups = load_model(ctx.groups_path, GroupProposalArtifact)
    plans = load_model(ctx.plans_path, PlanArtifact)
    exercises = load_model(ctx.exercises_path, ExerciseArtifact)
    if not (
        groups.status == "approved"
        and plans.status == "approved"
        and exercises.status == "approved"
    ):
        raise ValueError("the report can include approved artifacts only")
    content = build_sprint3_report(
        analysis, groups, plans, exercises, approvals
    )
    state_mod.validate_transition(_current_state(ctx), WorkflowState.REPORT_READY)
    ctx.report_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = ctx.report_path.with_suffix(".md.tmp")
    tmp_path.write_text(content, encoding="utf-8")
    os.replace(tmp_path, ctx.report_path)
    state_mod.advance(ctx.store, WorkflowState.REPORT_READY)
    _log(
        ctx,
        "REPORT_GENERATED",
        "system",
        "Generated teacher report from approved artifacts",
        {"report_path": str(ctx.report_path)},
    )
    return ctx.report_path
