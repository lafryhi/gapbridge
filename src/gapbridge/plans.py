"""Deterministic, template-based remediation planning.

Plan generation is a pure function of (ClassAnalysis, config.PLAN_RULES).
No randomness and no AI: the same analysis always yields the same plans.
This module is the seam Sprint 3 will replace/augment with Strands-based
generation; assessment, grouping, approval, state and audit logic do not
depend on how plans are produced.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from . import config
from .models import ClassAnalysis, GroupName, GroupRemediationPlan, RemediationPlan

GROUP_SLUGS: dict[GroupName, str] = {
    GroupName.MASTERED: "mastered",
    GroupName.DEVELOPING: "developing",
    GroupName.INTENSIVE_SUPPORT: "intensive-support",
}


def group_members(analysis: ClassAnalysis, group: GroupName):
    """Return the learner analyses belonging to a group (stable order)."""
    return [la for la in analysis.learners if la.group is group]


def select_target_skills(
    members,
    group: GroupName,
    skill_order: tuple[str, ...] = config.REQUIRED_SKILLS,
) -> list[str]:
    """Pick target skills deterministically from group member scores.

    Severity of a skill = minimum member score for that skill.
    Ties are broken by configured skill order.

    - Intensive Support: critical-gap skills first (< CRITICAL_SKILL_THRESHOLD),
      then remaining skills by severity; capped at max_target_skills
      (smaller skill set by design).
    - Developing / Mastered: plain severity order; capped at max_target_skills.
    """
    rule = config.PLAN_RULES[group]
    max_skills = int(rule["max_target_skills"])  # type: ignore[arg-type]
    min_scores = {s: min(m.scores[s] for m in members) for s in skill_order}
    ranked = sorted(skill_order, key=lambda s: (min_scores[s], skill_order.index(s)))
    if group is GroupName.INTENSIVE_SUPPORT:
        critical = [
            s for s in ranked if min_scores[s] < config.CRITICAL_SKILL_THRESHOLD
        ]
        ordered = critical + [s for s in ranked if s not in critical]
    else:
        ordered = ranked
    return ordered[:max_skills]


def build_plan(
    analysis: ClassAnalysis,
    group: GroupName,
    version: int = 1,
) -> RemediationPlan:
    """Build one version of a group's remediation plan."""
    rule = config.PLAN_RULES[group]
    targets = select_target_skills(group_members(analysis, group), group)
    return RemediationPlan(
        plan_id=f"plan-{GROUP_SLUGS[group]}-v{version}",
        group=group,
        version=version,
        target_skills=targets,
        priority=str(rule["priority"]),
        session_count=int(rule["session_count"]),  # type: ignore[arg-type]
        instructional_focus=str(rule["instructional_focus"]),
        success_criteria=list(rule["success_criteria"]),  # type: ignore[arg-type]
        status="proposed",
    )


def propose_all(
    analysis: ClassAnalysis,
    version: int = 1,
) -> dict[GroupName, GroupRemediationPlan]:
    """Create version-1 plans for every remediation group."""
    return {
        group: GroupRemediationPlan(
            group=group, versions=[build_plan(analysis, group, version)]
        )
        for group in GroupName
    }


def revise_all(
    analysis: ClassAnalysis,
    plans: dict[GroupName, GroupRemediationPlan],
    current_version: int,
) -> int:
    """Append a new version to every group's plan history.

    Previous versions are preserved untouched; nothing is overwritten.
    Returns the new proposal version.
    """
    new_version = current_version + 1
    for group in GroupName:
        plans[group].add_version(build_plan(analysis, group, new_version))
    return new_version


def _plan_to_dict(plan: RemediationPlan) -> dict[str, object]:
    return {
        "plan_id": plan.plan_id,
        "group": plan.group.value,
        "version": plan.version,
        "target_skills": list(plan.target_skills),
        "priority": plan.priority,
        "session_count": plan.session_count,
        "instructional_focus": plan.instructional_focus,
        "success_criteria": list(plan.success_criteria),
        "status": plan.status,
    }


def _plan_from_dict(raw: dict[str, object]) -> RemediationPlan:
    return RemediationPlan(
        plan_id=str(raw["plan_id"]),
        group=GroupName(str(raw["group"])),
        version=int(raw["version"]),  # type: ignore[arg-type]
        target_skills=list(raw["target_skills"]),  # type: ignore[arg-type]
        priority=str(raw["priority"]),
        session_count=int(raw["session_count"]),  # type: ignore[arg-type]
        instructional_focus=str(raw["instructional_focus"]),
        success_criteria=list(raw["success_criteria"]),  # type: ignore[arg-type]
        status=str(raw["status"]),
    )


def save_plans(
    path: Path,
    plans: dict[GroupName, GroupRemediationPlan],
    proposal_version: int,
    status: str,
) -> None:
    """Persist all plan histories atomically as local JSON."""
    payload = {
        "proposal_version": proposal_version,
        "status": status,
        "groups": [
            {
                "group": group.value,
                "versions": [_plan_to_dict(p) for p in plans[group].versions],
            }
            for group in GroupName
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(tmp_path, path)


def load_plans(
    path: Path,
) -> tuple[dict[GroupName, GroupRemediationPlan], int, str]:
    """Load plan histories; returns (plans, proposal_version, status)."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    plans: dict[GroupName, GroupRemediationPlan] = {}
    for raw_group in payload["groups"]:  # type: ignore[index]
        group = GroupName(str(raw_group["group"]))
        versions = [_plan_from_dict(v) for v in raw_group["versions"]]
        plans[group] = GroupRemediationPlan(group=group, versions=versions)
    return (
        plans,
        int(payload["proposal_version"]),  # type: ignore[arg-type]
        str(payload["status"]),
    )
