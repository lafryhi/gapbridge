"""Typed domain models for GapBridge's deterministic core."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class GroupName(str, Enum):
    MASTERED = "Mastered"
    DEVELOPING = "Developing"
    INTENSIVE_SUPPORT = "Intensive Support"


@dataclass(frozen=True)
class LearnerAssessment:
    """Raw imported scores for one learner (percentages 0-100)."""

    learner_id: str
    scores: dict[str, float]


@dataclass(frozen=True)
class LearningGap:
    """One sub-skill below the mastery threshold, with evidence."""

    skill: str
    score: float
    threshold: float


@dataclass
class LearnerAnalysis:
    """Computed performance profile for one learner."""

    learner_id: str
    scores: dict[str, float]
    overall_average: float
    weakest_skill: str
    weakest_score: float
    gaps_below_mastery: list[LearningGap]
    critical_gap_skills: list[str]
    group: GroupName | None = None
    explanation: str | None = None


@dataclass
class ClassAnalysis:
    """Analysis results for a whole class assessment."""

    title: str
    skills: list[str]
    learners: list[LearnerAnalysis]

    def group_counts(self) -> dict[GroupName, int]:
        counts: dict[GroupName, int] = {name: 0 for name in GroupName}
        for learner in self.learners:
            if learner.group is not None:
                counts[learner.group] += 1
        return counts


@dataclass
class WorkflowStateRecord:
    """Persisted workflow state with transition history."""

    current_state: str
    history: list[str] = field(default_factory=list)
    updated_at: str = ""


@dataclass
class AuditEvent:
    """One append-only audit trail entry."""

    timestamp: str
    event_type: str
    state: str
    actor: str
    details: str
    metadata: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "state": self.state,
            "actor": self.actor,
            "details": self.details,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, object]) -> AuditEvent:
        return cls(
            timestamp=str(raw["timestamp"]),
            event_type=str(raw["event_type"]),
            state=str(raw["state"]),
            actor=str(raw["actor"]),
            details=str(raw["details"]),
            metadata=dict(raw.get("metadata") or {}),  # type: ignore[arg-type]
        )


@dataclass(frozen=True)
class ExerciseItem:
    """One deterministic exercise with its expected answer."""

    skill: str
    prompt: str
    answer: str


@dataclass
class ExerciseSet:
    """Template-generated exercises for one remediation group."""

    group: GroupName
    title: str
    items: list[ExerciseItem]
    generated_by: str = "deterministic-template-v1"


@dataclass
class RemediationPlan:
    """One version of the remediation plan for a single group."""

    plan_id: str
    group: GroupName
    version: int
    target_skills: list[str]
    priority: str
    session_count: int
    instructional_focus: str
    success_criteria: list[str]
    status: str = "proposed"


@dataclass
class GroupRemediationPlan:
    """Append-only version history of one group's remediation plan."""

    group: GroupName
    versions: list[RemediationPlan] = field(default_factory=list)

    @property
    def current(self) -> RemediationPlan:
        if not self.versions:
            raise ValueError(f"No plan versions exist for group {self.group.value}.")
        return self.versions[-1]

    def add_version(self, plan: RemediationPlan) -> RemediationPlan:
        self.versions.append(plan)
        return plan


@dataclass
class ApprovalDecision:
    """A recorded teacher decision on a remediation-plan proposal."""

    decision: str  # "approved" | "revision_requested"
    actor: str
    timestamp: str
    plan_version: int
    comment: str = ""


@dataclass
class TeacherReportMetadata:
    """Provenance metadata attached to a generated teacher report."""

    report_id: str
    generated_at: str
    assessment_title: str
    learner_count: int
    plan_version: int
    source_file: str
