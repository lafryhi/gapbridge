"""Teacher-facing service adapter for the local GapBridge demo.

This module contains no Streamlit code. It keeps UI reruns thin and testable
while delegating every authoritative transition to the Sprint 3 controller.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from . import assessment, config, gaps, grouping, sprint3_workflow as workflow
from .models import ClassAnalysis, GroupName
from .scripted_strands_model import OfflineScriptedModel
from .sprint3_evidence import analysis_snapshot, class_evidence
from .sprint3_schemas import (
    ExerciseArtifact,
    GroupProposalArtifact,
    PlanArtifact,
)
from .sprint3_storage import (
    Sprint3RunContext,
    create_run_context,
    load_model,
    open_run_context,
    stable_hash,
)
from .state import WorkflowState
from .strands_orchestrator import StrandsContentOrchestrator

AI_MODE = "STRANDS_OFFLINE_TEST"
SYNTHETIC_DATA_PATH = config.PROJECT_ROOT / "data" / "synthetic_assessment.csv"


@dataclass(frozen=True)
class DemoSummary:
    learners_analyzed: int
    group_counts: dict[str, int]
    priority_gaps: list[str]
    plans_drafted: int
    exercise_items_generated: int
    approval_gates_completed: int
    workflow_state: str


def _recompute_analysis(data_path: Path) -> ClassAnalysis:
    dataset = assessment.load_assessment_csv(data_path)
    analysis = gaps.analyze_class(dataset.learners, title=dataset.title)
    grouping.assign_groups(analysis)
    return analysis


@dataclass
class TeacherWorkflowService:
    """A resumable, run-scoped adapter for the teacher demo."""

    ctx: Sprint3RunContext
    analysis: ClassAnalysis

    @classmethod
    def start(
        cls,
        *,
        runtime_root: Path | None = None,
        data_path: Path = SYNTHETIC_DATA_PATH,
    ) -> TeacherWorkflowService:
        if data_path.resolve() != SYNTHETIC_DATA_PATH.resolve():
            raise ValueError("The local demo accepts only the bundled synthetic dataset")
        ctx = create_run_context(runtime_root=runtime_root)
        analysis = workflow.start_run(data_path, ctx)
        return cls(ctx=ctx, analysis=analysis)

    @classmethod
    def start_fresh(
        cls,
        *,
        runtime_root: Path | None = None,
        data_path: Path = SYNTHETIC_DATA_PATH,
    ) -> TeacherWorkflowService:
        """Create a clean isolated run without altering any historical run."""
        return cls.start(runtime_root=runtime_root, data_path=data_path)

    @classmethod
    def resume(
        cls,
        run_id: str,
        *,
        runtime_root: Path | None = None,
        data_path: Path = SYNTHETIC_DATA_PATH,
    ) -> TeacherWorkflowService:
        """Reopen a run and verify it still matches deterministic evidence."""
        if data_path.resolve() != SYNTHETIC_DATA_PATH.resolve():
            raise ValueError("The local demo accepts only the bundled synthetic dataset")
        ctx = open_run_context(run_id, runtime_root=runtime_root)
        manifest = json.loads(ctx.manifest_path.read_text(encoding="utf-8"))
        if (
            manifest.get("run_id") != run_id
            or manifest.get("data_policy") != "synthetic-only"
            or manifest.get("source_file") != data_path.name
        ):
            raise ValueError("run manifest does not match the Sprint 4B demo policy")

        analysis = _recompute_analysis(data_path)
        groups = load_model(ctx.groups_path, GroupProposalArtifact)
        if groups.run_id != run_id:
            raise ValueError("group artifact belongs to a different run")
        if groups.input_hash != stable_hash(analysis_snapshot(analysis)):
            raise ValueError("stored analysis no longer matches deterministic evidence")
        if groups.computed_membership != groups.effective_membership:
            raise ValueError("stored group membership differs from computed membership")
        service = cls(ctx=ctx, analysis=analysis)
        service._validate_persisted_artifacts()
        return service

    def _validate_persisted_artifacts(self) -> None:
        """Ensure the artifacts required by the persisted state are readable."""
        if self.state in {
            WorkflowState.PLAN_PROPOSED,
            WorkflowState.PLAN_APPROVED,
            WorkflowState.EXERCISES_PROPOSED,
            WorkflowState.EXERCISES_APPROVED,
            WorkflowState.REPORT_READY,
        } and self.plans() is None:
            raise FileNotFoundError("saved remediation plan artifact is missing")
        if self.state in {
            WorkflowState.EXERCISES_PROPOSED,
            WorkflowState.EXERCISES_APPROVED,
            WorkflowState.REPORT_READY,
        } and self.exercises() is None:
            raise FileNotFoundError("saved exercise artifact is missing")
        if self.state is WorkflowState.REPORT_READY and not self.ctx.report_path.is_file():
            raise FileNotFoundError("saved teacher report is missing")

    @property
    def run_id(self) -> str:
        return self.ctx.run_id

    @property
    def state(self) -> WorkflowState:
        record = self.ctx.store.load()
        if record is None:
            raise ValueError("workflow state is missing")
        return WorkflowState(record.current_state)

    def approve_groups(self, *, comment: str = "") -> None:
        workflow.approve_groups(
            self.ctx,
            actor="teacher (local demo)",
            comment=comment,
        )

    def generate_plans(self) -> PlanArtifact:
        provider = StrandsContentOrchestrator(
            self.ctx, self.analysis, OfflineScriptedModel()
        )
        return workflow.propose_plans(self.analysis, self.ctx, provider)

    def approve_plans(self, *, comment: str = "") -> None:
        workflow.approve_plans(
            self.ctx,
            actor="teacher (local demo)",
            comment=comment,
        )

    def generate_exercises(self) -> ExerciseArtifact:
        provider = StrandsContentOrchestrator(
            self.ctx, self.analysis, OfflineScriptedModel()
        )
        return workflow.propose_exercises(self.analysis, self.ctx, provider)

    def approve_exercises(self, *, comment: str = "") -> None:
        workflow.approve_exercises(
            self.ctx,
            actor="teacher (local demo)",
            comment=comment,
        )

    def generate_report(self) -> Path:
        return workflow.generate_report(self.analysis, self.ctx)

    def groups(self) -> GroupProposalArtifact:
        return load_model(self.ctx.groups_path, GroupProposalArtifact)

    def plans(self) -> PlanArtifact | None:
        if not self.ctx.plans_path.exists():
            return None
        artifact = load_model(self.ctx.plans_path, PlanArtifact)
        if artifact.run_id != self.run_id:
            raise ValueError("plan artifact belongs to a different run")
        return artifact

    def exercises(self) -> ExerciseArtifact | None:
        if not self.ctx.exercises_path.exists():
            return None
        artifact = load_model(self.ctx.exercises_path, ExerciseArtifact)
        if artifact.run_id != self.run_id:
            raise ValueError("exercise artifact belongs to a different run")
        return artifact

    def report(self) -> str | None:
        if not self.ctx.report_path.exists():
            return None
        return self.ctx.report_path.read_text(encoding="utf-8")

    def approvals_by_gate(self) -> dict[str, bool]:
        return {
            gate: self.ctx.approvals.approved(gate)
            for gate in ("groups", "plans", "exercises")
        }

    def demo_summary(self) -> DemoSummary:
        evidence = class_evidence(self.analysis)
        gaps_by_priority = sorted(
            (
                item
                for item in evidence["skills"]  # type: ignore[union-attr]
                if item["is_class_gap"]
            ),
            key=lambda item: float(item["class_average"]),
        )
        plans = self.plans()
        exercises = self.exercises()
        return DemoSummary(
            learners_analyzed=len(self.analysis.learners),
            group_counts={
                group.value: self.analysis.group_counts()[group]
                for group in GroupName
            },
            priority_gaps=[str(item["skill"]) for item in gaps_by_priority],
            plans_drafted=len(plans.draft.plans) if plans else 0,
            exercise_items_generated=(
                sum(len(item.items) for item in exercises.draft.sets)
                if exercises
                else 0
            ),
            approval_gates_completed=sum(self.approvals_by_gate().values()),
            workflow_state=self.state.value,
        )
