"""Deterministic remediation grouping with explicit precedence rules.

Group assignment depends only on scores and thresholds from
``gapbridge.config``. It never depends on an LLM. Given the same
scores and thresholds the result is always identical.

Precedence (first match wins):
1. Intensive Support: overall < DEVELOPING_MIN_OVERALL OR critical gaps >= 2
2. Mastered: overall >= MASTERED_MIN_OVERALL AND no sub-skill below mastery
3. Developing: everything else
"""

from __future__ import annotations

from . import config
from .models import ClassAnalysis, GroupName, LearnerAnalysis


def classify(
    overall_average: float,
    critical_gap_count: int,
    minimum_score: float,
    *,
    mastered_min_overall: float = config.MASTERED_MIN_OVERALL,
    mastery_threshold: float = config.SKILL_MASTERY_THRESHOLD,
    developing_min_overall: float = config.DEVELOPING_MIN_OVERALL,
    intensive_min_critical_gaps: int = config.INTENSIVE_MIN_CRITICAL_GAPS,
) -> GroupName:
    """Assign a remediation group from precomputed evidence."""
    if (
        overall_average < developing_min_overall
        or critical_gap_count >= intensive_min_critical_gaps
    ):
        return GroupName.INTENSIVE_SUPPORT
    if overall_average >= mastered_min_overall and minimum_score >= mastery_threshold:
        return GroupName.MASTERED
    return GroupName.DEVELOPING


def assign_groups(analysis: ClassAnalysis) -> ClassAnalysis:
    """Attach a group and a deterministic explanation to every learner."""
    for learner in analysis.learners:
        minimum_score = min(learner.scores.values())
        group = classify(
            learner.overall_average,
            len(learner.critical_gap_skills),
            minimum_score,
        )
        learner.group = group
        learner.explanation = build_explanation(learner, group)
    return analysis


def build_explanation(learner: LearnerAnalysis, group: GroupName) -> str:
    lines = [f"Learner {learner.learner_id} was assigned to {group.value} because:"]
    lines.append(f"- overall average = {format_percent(learner.overall_average)}%")
    for gap in learner.gaps_below_mastery:
        lines.append(f"- {gap.skill} = {format_percent(gap.score)}%")

    if group is GroupName.INTENSIVE_SUPPORT:
        if learner.overall_average < config.DEVELOPING_MIN_OVERALL:
            lines.append(
                "- overall average is below the developing threshold of "
                f"{format_percent(config.DEVELOPING_MIN_OVERALL)}%"
            )
        if len(learner.critical_gap_skills) >= config.INTENSIVE_MIN_CRITICAL_GAPS:
            lines.append(
                f"- {len(learner.critical_gap_skills)} sub-skills are below the "
                f"critical threshold of {format_percent(config.CRITICAL_SKILL_THRESHOLD)}%"
            )
    elif group is GroupName.MASTERED:
        lines.append(
            f"- overall average meets the {format_percent(config.MASTERED_MIN_OVERALL)}% "
            f"threshold and no sub-skill is below the "
            f"{format_percent(config.SKILL_MASTERY_THRESHOLD)}% mastery threshold"
        )
    else:
        lines.append(
            f"- overall average is at least "
            f"{format_percent(config.DEVELOPING_MIN_OVERALL)}% but Mastered criteria are not met"
        )
    return "\n".join(lines)


def format_percent(value: float) -> str:
    text = f"{round(value, 2):.2f}".rstrip("0").rstrip(".")
    return text
