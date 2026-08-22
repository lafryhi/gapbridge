"""End-to-end deterministic workflow orchestration.

Small, explicit step functions shared by the demo runner and tests.
Each step: performs one domain action, advances the state machine,
and appends an audit event. Sprint 3 can swap plan/exercise generation
for Strands-based implementations without touching these steps' callers.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import assessment, config, exercises as exercises_mod, gaps, grouping
from . import plans as plans_mod, report as report_mod, state as state_mod
from .audit import AuditLog
from .models import (
    ApprovalDecision,
    AuditEvent,
    ClassAnalysis,
    ExerciseSet,
    GroupName,
    TeacherReportMetadata,
)
from .state import StateStore, WorkflowState, utc_now_iso


@dataclass(frozen=True)
class PipelineContext:
    """Local paths used by one workflow run."""

    store: StateStore
    audit: AuditLog
    plans_path: Path
    exercises_path: Path
    report_path: Path


def default_context() -> PipelineContext:
    """Context bound to the project's default runtime locations."""
    config.ensure_runtime_dirs()
    return PipelineContext(
        store=StateStore(config.DEFAULT_STATE_PATH),
        audit=AuditLog(config.DEFAULT_AUDIT_PATH),
        plans_path=config.DEFAULT_PLANS_PATH,
        exercises_path=config.DEFAULT_EXERCISES_PATH,
        report_path=config.DEFAULT_REPORT_PATH,
    )


def _log(
    ctx: PipelineContext,
    event_type: str,
    actor: str,
    details: str,
    metadata: dict[str, object] | None = None,
) -> None:
    record = ctx.store.load()
    current_state = record.current_state if record else WorkflowState.UPLOADED.value
    ctx.audit.append(
        AuditEvent(
            timestamp=utc_now_iso(),
            event_type=event_type,
            state=current_state,
            actor=actor,
            details=details,
            metadata=metadata or {},
        )
    )


def load_and_prepare(csv_path: str | Path, ctx: PipelineContext) -> ClassAnalysis:
    """CSV -> analysis -> grouping (UPLOADED -> ANALYZED -> GROUPED)."""
    dataset = assessment.load_assessment_csv(csv_path)
    state_mod.initialize(ctx.store)
    _log(
        ctx,
        "DATASET_UPLOADED",
        "system",
        f"Loaded {len(dataset.learners)} learners from {Path(csv_path).name}",
        {"skills": list(dataset.skills)},
    )

    analysis = gaps.analyze_class(dataset.learners, title=dataset.title)
    state_mod.advance(ctx.store, WorkflowState.ANALYZED)
    _log(
        ctx,
        "ANALYSIS_COMPLETED",
        "system",
        f"Analyzed {len(analysis.learners)} learners across {len(analysis.skills)} sub-skills",
    )

    grouping.assign_groups(analysis)
    counts = analysis.group_counts()
    state_mod.advance(ctx.store, WorkflowState.GROUPED)
    _log(
        ctx,
        "GROUP_ASSIGNMENT_COMPLETED",
        "system",
        f"{len(analysis.learners)} learners assigned to remediation groups",
        {
            "mastered": counts[GroupName.MASTERED],
            "developing": counts[GroupName.DEVELOPING],
            "intensive_support": counts[GroupName.INTENSIVE_SUPPORT],
        },
    )
    return analysis


def propose_plans(analysis: ClassAnalysis, ctx: PipelineContext) -> int:
    """Generate version-1 remediation plans (GROUPED -> PLAN_PROPOSED)."""
    plans = plans_mod.propose_all(analysis)
    plans_mod.save_plans(ctx.plans_path, plans, proposal_version=1, status="proposed")
    state_mod.advance(ctx.store, WorkflowState.PLAN_PROPOSED)
    _log(
        ctx,
        "PLAN_PROPOSED",
        "system",
        "Proposed remediation plans for all groups (version 1)",
        {"proposal_version": 1},
    )
    return 1


def request_revision(
    analysis: ClassAnalysis,
    ctx: PipelineContext,
    current_version: int,
    *,
    actor: str,
    comment: str = "",
) -> int:
    """Teacher requests changes; a new plan version is proposed.

    Path: PLAN_PROPOSED -> REVISION_REQUESTED -> PLAN_PROPOSED.
    The previous plan versions are preserved untouched.
    """
    plans, stored_version, _status = plans_mod.load_plans(ctx.plans_path)
    if stored_version != current_version:
        raise ValueError(
            f"Stored plan version {stored_version} does not match "
            f"expected {current_version}."
        )
    new_version = plans_mod.revise_all(analysis, plans, current_version)

    state_mod.advance(ctx.store, WorkflowState.REVISION_REQUESTED)
    _log(
        ctx,
        "PLAN_REVISION_REQUESTED",
        actor,
        "Revision requested on proposed remediation plans",
        {"plan_version": current_version, "comment": comment},
    )

    plans_mod.save_plans(ctx.plans_path, plans, new_version, status="proposed")
    state_mod.advance(ctx.store, WorkflowState.PLAN_PROPOSED)
    _log(
        ctx,
        "PLAN_PROPOSED",
        "system",
        f"Re-proposed remediation plans (version {new_version})",
        {"proposal_version": new_version},
    )
    return new_version


def approve_plans(
    ctx: PipelineContext,
    plan_version: int,
    *,
    actor: str,
    comment: str = "",
) -> ApprovalDecision:
    """Record teacher approval of the current proposal (PLAN_PROPOSED -> APPROVED)."""
    plans, stored_version, _status = plans_mod.load_plans(ctx.plans_path)
    if stored_version != plan_version:
        raise ValueError(
            f"Stored plan version {stored_version} does not match "
            f"expected {plan_version}."
        )
    for group_plan in plans.values():
        group_plan.current.status = "approved"
    plans_mod.save_plans(ctx.plans_path, plans, plan_version, status="approved")

    decision = ApprovalDecision(
        decision="approved",
        actor=actor,
        timestamp=utc_now_iso(),
        plan_version=plan_version,
        comment=comment,
    )
    state_mod.advance(ctx.store, WorkflowState.APPROVED)
    _log(
        ctx,
        "PLAN_APPROVED",
        actor,
        f"Remediation plans approved at version {plan_version}",
        {
            "decision": decision.decision,
            "actor": decision.actor,
            "plan_version": decision.plan_version,
            "comment": decision.comment,
        },
    )
    return decision


def generate_materials(
    analysis: ClassAnalysis,
    ctx: PipelineContext,
) -> dict[GroupName, ExerciseSet]:
    """Generate exercises from approved plans (APPROVED -> MATERIALS_GENERATED)."""
    plans, _version, status = plans_mod.load_plans(ctx.plans_path)
    if status != "approved":
        raise ValueError("Plans must be approved before generating materials.")
    sets = exercises_mod.generate_exercises(analysis, plans)
    exercises_mod.save_exercises(ctx.exercises_path, sets)

    total_items = sum(len(s.items) for s in sets.values())
    state_mod.advance(ctx.store, WorkflowState.MATERIALS_GENERATED)
    _log(
        ctx,
        "MATERIALS_GENERATED",
        "system",
        f"Generated exercise sets for {len(sets)} groups ({total_items} items)",
        {"groups": [g.value for g in GroupName], "total_items": total_items},
    )
    return sets


def generate_report(
    analysis: ClassAnalysis,
    ctx: PipelineContext,
    plan_version: int,
    approvals: list[ApprovalDecision],
    source_name: str,
) -> Path:
    """Assemble and save the teacher report (MATERIALS_GENERATED -> REPORT_READY)."""
    plans, _version, _status = plans_mod.load_plans(ctx.plans_path)
    sets = exercises_mod.load_exercises(ctx.exercises_path)
    metadata = TeacherReportMetadata(
        report_id=f"gapbridge-report-{utc_now_iso().replace(':', '').replace('+', '')}",
        generated_at=utc_now_iso(),
        assessment_title=analysis.title,
        learner_count=len(analysis.learners),
        plan_version=plan_version,
        source_file=source_name,
    )
    content = report_mod.build_report(analysis, plans, sets, approvals, metadata)
    saved_path = report_mod.save_report(ctx.report_path, content)

    state_mod.advance(ctx.store, WorkflowState.REPORT_READY)
    _log(
        ctx,
        "REPORT_GENERATED",
        "system",
        f"Teacher report written to {saved_path.name}",
        {"report_path": str(saved_path), "plan_version": plan_version},
    )
    return saved_path
