"""Central configuration for GapBridge's deterministic core.

All grouping thresholds live here so behaviour is never hardcoded
across modules. Changing these values changes grouping results
consistently everywhere.

Grouping precedence rules (checked in order, first match wins):

1. INTENSIVE_SUPPORT
   overall_average < DEVELOPING_MIN_OVERALL
   OR critical_gap_count >= INTENSIVE_MIN_CRITICAL_GAPS
   (a critical gap is a sub-skill score < CRITICAL_SKILL_THRESHOLD)
2. MASTERED
   overall_average >= MASTERED_MIN_OVERALL
   AND minimum sub-skill score >= SKILL_MASTERY_THRESHOLD
3. DEVELOPING
   anything remaining (rule 1 did not match, so overall_average
   is >= DEVELOPING_MIN_OVERALL by construction)
"""

from __future__ import annotations

from pathlib import Path

from .models import GroupName

PROJECT_ROOT = Path(__file__).resolve().parents[2]

ASSESSMENT_TITLE = "Grade 5 Mathematics - Fractions"

REQUIRED_SKILLS: tuple[str, ...] = (
    "identifying_fractions",
    "comparing_fractions",
    "equivalent_fractions",
    "adding_fractions",
)

MASTERED_MIN_OVERALL = 80.0
SKILL_MASTERY_THRESHOLD = 70.0
DEVELOPING_MIN_OVERALL = 50.0
CRITICAL_SKILL_THRESHOLD = 40.0
INTENSIVE_MIN_CRITICAL_GAPS = 2

DEFAULT_STATE_PATH = PROJECT_ROOT / "runtime" / "state" / "workflow_state.json"
DEFAULT_AUDIT_PATH = PROJECT_ROOT / "runtime" / "audit" / "audit_log.jsonl"

ARTIFACTS_DIR = PROJECT_ROOT / "runtime" / "artifacts"
DEFAULT_PLANS_PATH = ARTIFACTS_DIR / "remediation_plan.json"
DEFAULT_EXERCISES_PATH = ARTIFACTS_DIR / "exercise_sets.json"
DEFAULT_REPORT_PATH = ARTIFACTS_DIR / "teacher_report.md"

# Deterministic remediation-plan rules, keyed by group.
# These are the ONLY knobs controlling plan generation; the generator
# in plans.py is a pure function of (class analysis, these rules).
PLAN_RULES: dict[GroupName, dict[str, object]] = {
    GroupName.INTENSIVE_SUPPORT: {
        "priority": "high",
        "session_count": 6,
        "max_target_skills": 2,
        "items_per_skill": 3,
        "instructional_focus": (
            "Prerequisite-focused reteaching with concrete representations "
            "and small-step practice on critical gaps first"
        ),
        "success_criteria": [
            "Learner reaches at least 60% on each targeted skill at re-assessment",
            "Learner completes all prerequisite practice tasks",
        ],
    },
    GroupName.DEVELOPING: {
        "priority": "medium",
        "session_count": 4,
        "max_target_skills": 3,
        "items_per_skill": 2,
        "instructional_focus": (
            "Guided practice targeting the weakest sub-skills with gradual "
            "release of responsibility"
        ),
        "success_criteria": [
            "Learner reaches at least 70% on each targeted skill at re-assessment",
            "Learner completes guided practice sets independently",
        ],
    },
    GroupName.MASTERED: {
        "priority": "low",
        "session_count": 2,
        "max_target_skills": 2,
        "items_per_skill": 2,
        "instructional_focus": (
            "Enrichment and reinforcement extending fraction reasoning on "
            "relative weaknesses only"
        ),
        "success_criteria": [
            "Learner maintains an average of 80% or higher across all sub-skills",
            "Learner completes the enrichment challenge set",
        ],
    },
}


def ensure_runtime_dirs() -> None:
    """Create local runtime directories if they do not exist."""
    DEFAULT_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
