"""Run-scoped, read-only tools for the bounded Strands orchestrator."""

from __future__ import annotations

from typing import Any

from strands import tool

from .models import ClassAnalysis, GroupName
from .sprint3_evidence import class_evidence, group_profile, plan_constraints
from .sprint3_schemas import ExerciseDraftBundle, PlanArtifact, PlanDraftBundle
from .sprint3_storage import Sprint3RunContext, load_model


def create_safe_tools(ctx: Sprint3RunContext, analysis: ClassAnalysis) -> list[Any]:
    """Create an allowlist of tools bound to one run and one analysis snapshot."""

    @tool
    def get_workflow_status() -> dict[str, object]:
        """Return controller-owned workflow and approval state without changing it."""
        record = ctx.store.load()
        return {
            "run_id": ctx.run_id,
            "state": record.current_state if record else "UNINITIALIZED",
            "approved_gates": [
                approval.gate
                for approval in ctx.approvals.read_all()
                if approval.decision == "approved"
            ],
        }

    @tool
    def get_class_evidence() -> dict[str, object]:
        """Return computed class evidence; never calculate new official results."""
        return class_evidence(analysis)

    @tool
    def get_group_profile(group: str) -> dict[str, object]:
        """Return computed evidence for one deterministic learner group.

        Args:
            group: Exact group label: Mastered, Developing, or Intensive Support.
        """
        return group_profile(analysis, GroupName(group))

    @tool
    def get_plan_constraints(group: str) -> dict[str, object]:
        """Return deterministic targets and hard plan limits for one group.

        Args:
            group: Exact deterministic group label.
        """
        return plan_constraints(analysis, GroupName(group))

    @tool
    def get_teacher_revision_feedback(version: int) -> dict[str, object]:
        """Return persisted teacher feedback for a plan version.

        Args:
            version: Exact plan proposal version.
        """
        feedback = [
            approval.comment
            for approval in ctx.approvals.read_all()
            if approval.gate == "plans"
            and approval.artifact_version == version
            and approval.decision == "revision_requested"
        ]
        return {"version": version, "feedback": feedback}

    @tool
    def get_approved_plan(group: str) -> dict[str, object]:
        """Return an approved plan for one group when the plan gate is satisfied.

        Args:
            group: Exact deterministic group label.
        """
        artifact = load_model(ctx.plans_path, PlanArtifact)
        if artifact.status != "approved" or not ctx.approvals.approved(
            "plans", artifact.version
        ):
            raise ValueError("the plan gate is not approved")
        selected = next(plan for plan in artifact.draft.plans if plan.group == group)
        return selected.model_dump(mode="json")

    @tool
    def validate_plan_alignment(draft_json: str) -> dict[str, object]:
        """Validate a plan draft against deterministic constraints without persisting it.

        Args:
            draft_json: Complete PlanDraftBundle encoded as JSON.
        """
        errors: list[str] = []
        try:
            bundle = PlanDraftBundle.model_validate_json(draft_json)
            for plan in bundle.plans:
                constraints = plan_constraints(analysis, GroupName(plan.group))
                if not constraints["target_skills"]:
                    if plan.active or plan.target_skills or plan.session_count != 0:
                        errors.append(f"{plan.group}: empty group plan must be inactive")
                    continue
                if plan.target_skills != constraints["target_skills"]:
                    errors.append(f"{plan.group}: target skills do not match")
                if plan.session_count != constraints["session_count"]:
                    errors.append(f"{plan.group}: session count does not match")
                if plan.priority != constraints["priority"]:
                    errors.append(f"{plan.group}: priority does not match")
        except Exception as exc:  # validation result, not a workflow failure
            errors.append(str(exc))
        return {"valid": not errors, "errors": errors}

    @tool
    def validate_exercise_set(draft_json: str) -> dict[str, object]:
        """Validate exercise coverage against approved plans without persisting it.

        Args:
            draft_json: Complete ExerciseDraftBundle encoded as JSON.
        """
        errors: list[str] = []
        try:
            bundle = ExerciseDraftBundle.model_validate_json(draft_json)
            artifact = load_model(ctx.plans_path, PlanArtifact)
            if artifact.status != "approved" or not ctx.approvals.approved(
                "plans", artifact.version
            ):
                errors.append("plans are not approved")
            plan_targets = {
                plan.group: plan.target_skills for plan in artifact.draft.plans
            }
            for exercise_set in bundle.sets:
                if exercise_set.target_skills != plan_targets[exercise_set.group]:
                    errors.append(
                        f"{exercise_set.group}: exercise targets do not match approved plan"
                    )
        except Exception as exc:  # validation result, not a workflow failure
            errors.append(str(exc))
        return {"valid": not errors, "errors": errors}

    return [
        get_workflow_status,
        get_class_evidence,
        get_group_profile,
        get_plan_constraints,
        get_teacher_revision_feedback,
        get_approved_plan,
        validate_plan_alignment,
        validate_exercise_set,
    ]
