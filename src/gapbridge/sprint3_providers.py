"""Provider interfaces and deterministic Sprint 3 fallback."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel

from . import config
from .exercises import GENERATORS
from .models import ClassAnalysis, GroupName
from .sprint3_evidence import plan_constraints
from .sprint3_schemas import (
    ExerciseDraftBundle,
    ExerciseItemDraft,
    ExerciseSetDraft,
    PlanArtifact,
    PlanDraft,
    PlanDraftBundle,
)

T = TypeVar("T", bound=BaseModel)


@dataclass(frozen=True)
class DraftResult(Generic[T]):
    value: T
    generated_by: str
    provider: str
    model_id: str
    agent_name: str | None
    sdk_version: str | None
    tool_calls: list[str]
    fallback: bool


@runtime_checkable
class PlanDraftProvider(Protocol):
    def draft_plans(
        self,
        analysis: ClassAnalysis,
        *,
        version: int,
        revision_feedback: str = "",
    ) -> DraftResult[PlanDraftBundle]: ...


@runtime_checkable
class ExerciseDraftProvider(Protocol):
    def draft_exercises(
        self,
        analysis: ClassAnalysis,
        approved_plans: PlanArtifact,
        *,
        version: int,
    ) -> DraftResult[ExerciseDraftBundle]: ...


class DeterministicDraftProvider(PlanDraftProvider, ExerciseDraftProvider):
    """Existing template behavior adapted to the Sprint 3 provider contracts."""

    def draft_plans(
        self,
        analysis: ClassAnalysis,
        *,
        version: int,
        revision_feedback: str = "",
    ) -> DraftResult[PlanDraftBundle]:
        drafts: list[PlanDraft] = []
        for group in GroupName:
            constraints = plan_constraints(analysis, group)
            targets = list(constraints["target_skills"])  # type: ignore[arg-type]
            if not targets:
                drafts.append(
                    PlanDraft(
                        group=group.value,
                        active=False,
                        target_skills=[],
                        objectives=["No remediation plan is needed for an empty group"],
                        strategies=["No instruction scheduled"],
                        session_sketch=["No sessions scheduled"],
                        success_criteria=["Not applicable while the group is empty"],
                        session_count=0,
                        priority="low",
                    )
                )
                continue
            focus = str(constraints["instructional_focus"])
            session_count = int(constraints["session_count"])  # type: ignore[arg-type]
            strategies = [focus]
            if revision_feedback.strip():
                strategies.append(
                    "Teacher revision note to apply: " + revision_feedback.strip()
                )
            drafts.append(
                PlanDraft(
                    group=group.value,
                    target_skills=targets,
                    objectives=[
                        f"Strengthen accurate reasoning in {skill.replace('_', ' ')}"
                        for skill in targets
                    ],
                    strategies=strategies,
                    session_sketch=[
                        f"Session {index}: model, practise, and check the targeted fraction skills"
                        for index in range(1, session_count + 1)
                    ],
                    success_criteria=list(constraints["success_criteria"]),  # type: ignore[arg-type]
                    session_count=session_count,
                    priority=str(constraints["priority"]),
                )
            )
        bundle = PlanDraftBundle(version=version, plans=drafts)
        return DraftResult(
            value=bundle,
            generated_by="deterministic-template-v1",
            provider="deterministic",
            model_id="none",
            agent_name=None,
            sdk_version=None,
            tool_calls=[],
            fallback=True,
        )

    def draft_exercises(
        self,
        analysis: ClassAnalysis,
        approved_plans: PlanArtifact,
        *,
        version: int,
    ) -> DraftResult[ExerciseDraftBundle]:
        sets: list[ExerciseSetDraft] = []
        difficulty = {
            GroupName.INTENSIVE_SUPPORT: "foundational",
            GroupName.DEVELOPING: "guided",
            GroupName.MASTERED: "enrichment",
        }
        plan_by_group = {plan.group: plan for plan in approved_plans.draft.plans}
        for group in GroupName:
            plan = plan_by_group[group.value]
            items: list[ExerciseItemDraft] = []
            if not plan.active:
                sets.append(
                    ExerciseSetDraft(
                        group=group.value,
                        active=False,
                        title=f"{group.value} — no exercises for empty group",
                        target_skills=[],
                        items=[],
                    )
                )
                continue
            per_skill = int(config.PLAN_RULES[group]["items_per_skill"])  # type: ignore[arg-type]
            for skill in plan.target_skills:
                generator = GENERATORS.get(skill)
                if generator is None:
                    raise ValueError(
                        f"No deterministic exercise template for skill '{skill}'."
                    )
                for index in range(per_skill):
                    prompt, answer = generator(index)
                    slug = group.name.lower().replace("_", "-")
                    items.append(
                        ExerciseItemDraft(
                            item_id=(
                                f"{slug}-{skill.replace('_', '-')}-{index + 1}"
                            ),
                            skill=skill,
                            prompt=prompt,
                            expected_answer=answer,
                            difficulty=difficulty[group],
                        )
                    )
            sets.append(
                ExerciseSetDraft(
                    group=group.value,
                    active=True,
                    title=f"{group.value} targeted fraction exercises",
                    target_skills=list(plan.target_skills),
                    items=items,
                )
            )
        bundle = ExerciseDraftBundle(version=version, sets=sets)
        return DraftResult(
            value=bundle,
            generated_by="deterministic-template-v1",
            provider="deterministic",
            model_id="none",
            agent_name=None,
            sdk_version=None,
            tool_calls=[],
            fallback=True,
        )
