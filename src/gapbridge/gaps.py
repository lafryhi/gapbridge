"""Deterministic learner performance analysis and gap detection."""

from __future__ import annotations

from . import config
from .models import ClassAnalysis, LearnerAnalysis, LearnerAssessment, LearningGap


def analyze_learner(
    learner: LearnerAssessment,
    *,
    skill_order: tuple[str, ...] = config.REQUIRED_SKILLS,
) -> LearnerAnalysis:
    """Compute overall average, weakest skill, mastery gaps and critical gaps.

    The overall average is rounded to 2 decimals before any comparison so
    results are stable and reproducible. Weakest-skill ties are broken by
    the configured skill order (first lowest wins).
    """
    scores = learner.scores
    overall_average = round(sum(scores[skill] for skill in skill_order) / len(skill_order), 2)

    weakest_skill = skill_order[0]
    weakest_score = scores[weakest_skill]
    for skill in skill_order[1:]:
        if scores[skill] < weakest_score:
            weakest_skill = skill
            weakest_score = scores[skill]

    gaps_below_mastery = [
        LearningGap(
            skill=skill,
            score=scores[skill],
            threshold=config.SKILL_MASTERY_THRESHOLD,
        )
        for skill in skill_order
        if scores[skill] < config.SKILL_MASTERY_THRESHOLD
    ]
    critical_gap_skills = [
        skill for skill in skill_order if scores[skill] < config.CRITICAL_SKILL_THRESHOLD
    ]

    return LearnerAnalysis(
        learner_id=learner.learner_id,
        scores=dict(scores),
        overall_average=overall_average,
        weakest_skill=weakest_skill,
        weakest_score=weakest_score,
        gaps_below_mastery=gaps_below_mastery,
        critical_gap_skills=critical_gap_skills,
    )


def analyze_class(
    learners: list[LearnerAssessment],
    *,
    title: str = config.ASSESSMENT_TITLE,
    skill_order: tuple[str, ...] = config.REQUIRED_SKILLS,
) -> ClassAnalysis:
    analyses = [analyze_learner(learner, skill_order=skill_order) for learner in learners]
    return ClassAnalysis(title=title, skills=list(skill_order), learners=analyses)
