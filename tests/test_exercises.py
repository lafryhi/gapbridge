"""Tests for deterministic exercise generation."""

from __future__ import annotations

import pytest

from gapbridge import config, exercises, gaps, grouping
from gapbridge.assessment import load_assessment_csv
from gapbridge.models import GroupName
from gapbridge.plans import propose_all


@pytest.fixture(scope="module")
def analysis(tmp_path_factory):
    csv_path = tmp_path_factory.mktemp("data") / "synthetic_assessment.csv"
    source = config.PROJECT_ROOT / "data" / "synthetic_assessment.csv"
    csv_path.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    dataset = load_assessment_csv(csv_path)
    class_analysis = gaps.analyze_class(dataset.learners)
    grouping.assign_groups(class_analysis)
    return class_analysis


@pytest.fixture(scope="module")
def sets(analysis):
    plans = propose_all(analysis)
    return exercises.generate_exercises(analysis, plans)


class TestExerciseGeneration:
    def test_generation_is_deterministic(self, analysis, sets):
        plans = propose_all(analysis)
        regenerated = exercises.generate_exercises(analysis, plans)
        for group in GroupName:
            original = [(i.skill, i.prompt, i.answer) for i in sets[group].items]
            repeat = [(i.skill, i.prompt, i.answer) for i in regenerated[group].items]
            assert original == repeat

    def test_one_labelled_set_per_group(self, sets):
        assert set(sets.keys()) == set(GroupName)
        for group, exercise_set in sets.items():
            assert exercise_set.group is group
            assert group.value in exercise_set.title
            assert exercise_set.generated_by == "deterministic-template-v1"
            assert exercise_set.items

    def test_items_only_cover_plan_target_skills(self, analysis, sets):
        plans = propose_all(analysis)
        for group in GroupName:
            targets = set(plans[group].current.target_skills)
            for item in sets[group].items:
                assert item.skill in targets
                assert item.prompt
                assert item.answer

    def test_item_counts_match_group_rules(self, sets):
        for group in GroupName:
            per_skill = int(config.PLAN_RULES[group]["items_per_skill"])  # type: ignore[arg-type]
            cap = int(config.PLAN_RULES[group]["max_target_skills"])  # type: ignore[arg-type]
            expected = per_skill * min(
                cap,
                len(
                    [
                        s
                        for s in config.REQUIRED_SKILLS
                        if any(i.skill == s for i in sets[group].items)
                    ]
                ),
            )
            assert len(sets[group].items) == expected

    def test_unknown_skill_raises_clear_error(self, analysis):
        from gapbridge.models import RemediationPlan, GroupRemediationPlan

        bad_plan = RemediationPlan(
            plan_id="plan-bad-v1",
            group=GroupName.MASTERED,
            version=1,
            target_skills=["algebra"],
            priority="low",
            session_count=1,
            instructional_focus="n/a",
            success_criteria=[],
        )
        plans = {g: GroupRemediationPlan(group=g) for g in GroupName}
        plans[GroupName.MASTERED].add_version(bad_plan)
        with pytest.raises(ValueError, match="algebra"):
            exercises.generate_exercises(analysis, plans)

    def test_persistence_roundtrip(self, analysis, sets, tmp_path):
        path = tmp_path / "exercise_sets.json"
        exercises.save_exercises(path, sets)
        loaded = exercises.load_exercises(path)
        for group in GroupName:
            assert loaded[group].title == sets[group].title
            assert loaded[group].generated_by == sets[group].generated_by
            assert [
                (i.skill, i.prompt, i.answer) for i in loaded[group].items
            ] == [(i.skill, i.prompt, i.answer) for i in sets[group].items]
