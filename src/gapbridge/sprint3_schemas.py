"""Strict Sprint 3 schemas at the deterministic/agent boundary."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

GroupLabel = Literal["Mastered", "Developing", "Intensive Support"]
GateName = Literal["groups", "plans", "exercises"]
ArtifactStatus = Literal["proposed", "approved"]


class StrictModel(BaseModel):
    """Base schema that rejects unrecognized model output fields."""

    model_config = ConfigDict(extra="forbid")


class PlanDraft(StrictModel):
    group: GroupLabel
    active: bool = True
    target_skills: list[str]
    objectives: list[str]
    strategies: list[str]
    session_sketch: list[str]
    success_criteria: list[str]
    session_count: int = Field(ge=0, le=12)
    priority: Literal["low", "medium", "high"]
    status: Literal["draft"] = "draft"

    @field_validator(
        "target_skills",
        "objectives",
        "strategies",
        "session_sketch",
        "success_criteria",
    )
    @classmethod
    def no_blank_list_values(cls, values: list[str]) -> list[str]:
        if any(not value.strip() for value in values):
            raise ValueError("list values must not be blank")
        if len(values) != len(set(values)):
            raise ValueError("list values must be unique")
        return values

    @model_validator(mode="after")
    def active_plan_has_content(self) -> PlanDraft:
        content_lists = (
            self.target_skills,
            self.objectives,
            self.strategies,
            self.session_sketch,
            self.success_criteria,
        )
        if self.active and (self.session_count == 0 or any(not item for item in content_lists)):
            raise ValueError("an active plan requires sessions and complete content")
        if not self.active and (self.target_skills or self.session_count != 0):
            raise ValueError("an inactive empty-group plan cannot target skills or sessions")
        return self


class PlanDraftBundle(StrictModel):
    version: int = Field(ge=1)
    plans: list[PlanDraft] = Field(min_length=3, max_length=3)

    @model_validator(mode="after")
    def exactly_one_plan_per_group(self) -> PlanDraftBundle:
        expected = {"Mastered", "Developing", "Intensive Support"}
        actual = {plan.group for plan in self.plans}
        if actual != expected or len(actual) != len(self.plans):
            raise ValueError("exactly one plan is required for each group")
        return self


class ExerciseItemDraft(StrictModel):
    item_id: str = Field(min_length=1, pattern=r"^[a-z0-9-]+$")
    skill: str = Field(min_length=1)
    prompt: str = Field(min_length=5)
    expected_answer: str = Field(min_length=1)
    difficulty: Literal["foundational", "guided", "enrichment"]


class ExerciseSetDraft(StrictModel):
    group: GroupLabel
    active: bool = True
    title: str = Field(min_length=3)
    target_skills: list[str]
    items: list[ExerciseItemDraft]
    status: Literal["draft"] = "draft"

    @model_validator(mode="after")
    def items_match_targets(self) -> ExerciseSetDraft:
        targets = set(self.target_skills)
        if self.active and (not targets or not self.items):
            raise ValueError("an active exercise set requires targets and items")
        if not self.active and (targets or self.items):
            raise ValueError("an inactive empty-group exercise set must be empty")
        if any(item.skill not in targets for item in self.items):
            raise ValueError("every exercise item must use a declared target skill")
        covered = {item.skill for item in self.items}
        if covered != targets:
            raise ValueError("every target skill must have at least one exercise")
        if len({item.item_id for item in self.items}) != len(self.items):
            raise ValueError("exercise item IDs must be unique within a set")
        return self


class ExerciseDraftBundle(StrictModel):
    version: int = Field(ge=1)
    sets: list[ExerciseSetDraft] = Field(min_length=3, max_length=3)

    @model_validator(mode="after")
    def exactly_one_set_per_group(self) -> ExerciseDraftBundle:
        expected = {"Mastered", "Developing", "Intensive Support"}
        actual = {exercise_set.group for exercise_set in self.sets}
        if actual != expected or len(actual) != len(self.sets):
            raise ValueError("exactly one exercise set is required for each group")
        all_ids = [item.item_id for exercise_set in self.sets for item in exercise_set.items]
        if len(all_ids) != len(set(all_ids)):
            raise ValueError("exercise item IDs must be unique across the bundle")
        return self


class ArtifactProvenance(StrictModel):
    generated_by: Literal["deterministic-template-v1", "strands-agent-scripted"]
    provider: Literal["deterministic", "strands"]
    model_id: str
    agent_name: str | None = None
    sdk_version: str | None = None
    timestamp: str
    run_id: str
    input_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    validation_status: Literal["passed"] = "passed"
    tool_calls: list[str] = Field(default_factory=list)
    fallback: bool = False


class PlanArtifact(StrictModel):
    run_id: str
    artifact_type: Literal["remediation_plans"] = "remediation_plans"
    version: int = Field(ge=1)
    status: ArtifactStatus
    draft: PlanDraftBundle
    provenance: ArtifactProvenance


class ExerciseArtifact(StrictModel):
    run_id: str
    artifact_type: Literal["exercise_sets"] = "exercise_sets"
    version: int = Field(ge=1)
    status: ArtifactStatus
    draft: ExerciseDraftBundle
    provenance: ArtifactProvenance


class ApprovalRecord(StrictModel):
    approval_id: str
    run_id: str
    gate: GateName
    decision: Literal["approved", "revision_requested"]
    actor: str = Field(min_length=1)
    timestamp: str
    artifact_type: Literal["groups", "remediation_plans", "exercise_sets"]
    artifact_version: int = Field(ge=1)
    artifact_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    comment: str = ""


class GroupProposalArtifact(StrictModel):
    run_id: str
    artifact_type: Literal["groups"] = "groups"
    version: int = 1
    status: ArtifactStatus
    computed_membership: dict[str, list[str]]
    effective_membership: dict[str, list[str]]
    rationales: dict[str, str]
    input_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
