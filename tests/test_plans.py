"""Tests for deterministic remediation-plan rules and versioning."""

from __future__ import annotations

import pytest

from gapbridge import config, gaps, grouping
from gapbridge.assessment import load_assessment_csv
from gapbridge.models import GroupName
from gapbridge.plans import (
    build_plan,
    propose_all,
    revise_all,
    select_target_skills,
)


@pytest.fixture(scope="module")
def analysis(tmp_path_factory):
    csv_path = tmp_path_factory.mktemp("data") / "synthetic_assessment.csv"
    source = config.PROJECT_ROOT / "data" / "synthetic_assessment.csv"
    csv_path.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    dataset = load_assessment_csv(csv_path)
    class_analysis = gaps.analyze_class(dataset.learners)
    grouping.assign_groups(class_analysis)
    return class_analysis


class TestPlanRules:
    def test_priorities_and_session_counts_follow_config(self, analysis):
        plans = propose_all(analysis)
        for group in GroupName:
            rule = config.PLAN_RULES[group]
            plan = plans[group].current
            assert plan.priority == rule["priority"]
            assert plan.session_count == rule["session_count"]
            assert plan.instructional_focus == rule["instructional_focus"]
            assert plan.success_criteria == list(rule["success_criteria"])

    def test_intensive_plan_prioritizes_critical_gaps(self, analysis):
        plan = build_plan(analysis, GroupName.INTENSIVE_SUPPORT)
        # adding_fractions (min 20) and equivalent_fractions (min 30) are the
        # most severe critical gaps among Intensive Support members.
        assert plan.target_skills == ["adding_fractions", "equivalent_fractions"]
        assert plan.priority == "high"
        assert plan.session_count == 6
        assert plan.plan_id == "plan-intensive-support-v1"

    def test_developing_plan_targets_weakest_skills(self, analysis):
        plan = build_plan(analysis, GroupName.DEVELOPING)
        assert plan.target_skills == [
            "adding_fractions",
            "equivalent_fractions",
            "comparing_fractions",
        ]
        assert plan.session_count == 4

    def test_mastered_plan_is_enrichment_only(self, analysis):
        plan = build_plan(analysis, GroupName.MASTERED)
        # Relative weaknesses only; fewer sessions.
        assert plan.target_skills == ["equivalent_fractions", "adding_fractions"]
        assert plan.session_count == 2
        assert plan.priority == "low"
        assert "Enrichment" in plan.instructional_focus

    def test_target_skill_counts_respect_config_caps(self, analysis):
        for group in GroupName:
            members = [
                la for la in analysis.learners if la.group is group
            ]
            targets = select_target_skills(members, group)
            cap = int(config.PLAN_RULES[group]["max_target_skills"])  # type: ignore[arg-type]
            assert len(targets) <= cap


class TestPlanVersioning:
    def test_revision_preserves_previous_version(self, analysis):
        plans = propose_all(analysis)
        v1 = {g: plans[g].current for g in GroupName}
        new_version = revise_all(analysis, plans, current_version=1)

        assert new_version == 2
        for group in GroupName:
            history = plans[group].versions
            assert len(history) == 2
            assert history[0] is v1[group]
            assert history[0].version == 1
            assert history[1].version == 2
            assert plans[group].current.version == 2

    def test_revised_plan_ids_carry_version(self, analysis):
        plans = propose_all(analysis)
        revise_all(analysis, plans, current_version=1)
        assert plans[GroupName.MASTERED].current.plan_id == "plan-mastered-v2"
        assert (
            plans[GroupName.INTENSIVE_SUPPORT].current.plan_id
            == "plan-intensive-support-v2"
        )

    def test_revision_is_deterministic(self, analysis):
        plans_a = propose_all(analysis)
        plans_b = propose_all(analysis)
        revise_all(analysis, plans_a, current_version=1)
        revise_all(analysis, plans_b, current_version=1)
        for group in GroupName:
            a, b = plans_a[group].current, plans_b[group].current
            assert a.plan_id == b.plan_id
            assert a.target_skills == b.target_skills
