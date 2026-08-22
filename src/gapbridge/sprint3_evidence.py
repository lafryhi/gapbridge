"""Deterministic evidence views exposed to Sprint 3 content providers."""

from __future__ import annotations

from . import config
from .models import ClassAnalysis, GroupName
from .plans import group_members, select_target_skills


def class_evidence(analysis: ClassAnalysis) -> dict[str, object]:
    skills: list[dict[str, object]] = []
    for skill in config.REQUIRED_SKILLS:
        average = round(
            sum(learner.scores[skill] for learner in analysis.learners)
            / len(analysis.learners),
            2,
        )
        skills.append(
            {
                "skill": skill,
                "class_average": average,
                "mastery_threshold": config.SKILL_MASTERY_THRESHOLD,
                "is_class_gap": average < config.SKILL_MASTERY_THRESHOLD,
                "learners_below_mastery": sum(
                    learner.scores[skill] < config.SKILL_MASTERY_THRESHOLD
                    for learner in analysis.learners
                ),
            }
        )
    return {
        "assessment_title": analysis.title,
        "learner_count": len(analysis.learners),
        "skills": skills,
        "group_counts": {
            group.value: analysis.group_counts()[group] for group in GroupName
        },
        "computed_by": "gapbridge-deterministic-core",
    }


def group_profile(analysis: ClassAnalysis, group: GroupName) -> dict[str, object]:
    members = group_members(analysis, group)
    if not members:
        return {
            "group": group.value,
            "member_count": 0,
            "member_ids": [],
            "target_skills": [],
            "skill_averages": {},
            "rationales": {},
        }
    return {
        "group": group.value,
        "member_count": len(members),
        "member_ids": [member.learner_id for member in members],
        "target_skills": select_target_skills(members, group),
        "skill_averages": {
            skill: round(
                sum(member.scores[skill] for member in members) / len(members), 2
            )
            for skill in config.REQUIRED_SKILLS
        },
        "rationales": {
            member.learner_id: member.explanation or "" for member in members
        },
    }


def plan_constraints(analysis: ClassAnalysis, group: GroupName) -> dict[str, object]:
    rule = config.PLAN_RULES[group]
    members = group_members(analysis, group)
    return {
        "group": group.value,
        "target_skills": select_target_skills(members, group) if members else [],
        "priority": rule["priority"],
        "session_count": rule["session_count"],
        "max_target_skills": rule["max_target_skills"],
        "items_per_skill": rule["items_per_skill"],
        "instructional_focus": rule["instructional_focus"],
        "success_criteria": list(rule["success_criteria"]),  # type: ignore[arg-type]
        "authority": "deterministic",
    }


def analysis_snapshot(analysis: ClassAnalysis) -> dict[str, object]:
    return {
        "title": analysis.title,
        "skills": list(analysis.skills),
        "learners": [
            {
                "learner_id": learner.learner_id,
                "scores": dict(learner.scores),
                "overall_average": learner.overall_average,
                "weakest_skill": learner.weakest_skill,
                "group": learner.group.value if learner.group else None,
                "explanation": learner.explanation,
            }
            for learner in analysis.learners
        ],
    }
