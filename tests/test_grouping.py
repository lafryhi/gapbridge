"""Tests for deterministic grouping rules, boundaries and precedence."""

from pathlib import Path

from gapbridge import assessment, config, gaps
from gapbridge.grouping import assign_groups, classify, format_percent
from gapbridge.models import GroupName

REAL_DATASET = Path(__file__).resolve().parents[1] / "data" / "synthetic_assessment.csv"


def test_mastered_example() -> None:
    assert classify(85.0, 0, 75.0) is GroupName.MASTERED


def test_developing_example() -> None:
    assert classify(65.0, 0, 55.0) is GroupName.DEVELOPING


def test_intensive_support_example_low_average() -> None:
    assert classify(43.5, 2, 28.0) is GroupName.INTENSIVE_SUPPORT


def test_intensive_support_by_critical_gaps_despite_high_average() -> None:
    assert classify(90.0, 2, 35.0) is GroupName.INTENSIVE_SUPPORT


def test_boundary_overall_exactly_80_is_mastered() -> None:
    assert classify(80.0, 0, 70.0) is GroupName.MASTERED


def test_boundary_just_below_80_is_not_mastered() -> None:
    assert classify(79.99, 0, 70.0) is GroupName.DEVELOPING


def test_boundary_minimum_score_exactly_at_mastery_threshold() -> None:
    assert classify(95.0, 0, 70.0) is GroupName.MASTERED


def test_boundary_minimum_score_just_below_mastery_threshold() -> None:
    assert classify(95.0, 0, 69.99) is GroupName.DEVELOPING


def test_boundary_overall_exactly_50_is_not_intensive() -> None:
    assert classify(50.0, 0, 45.0) is GroupName.DEVELOPING


def test_boundary_overall_just_below_50_is_intensive() -> None:
    assert classify(49.99, 0, 45.0) is GroupName.INTENSIVE_SUPPORT


def test_single_critical_gap_blocks_mastered_but_stays_developing() -> None:
    assert classify(85.0, 1, 39.99) is GroupName.DEVELOPING


def test_two_critical_gaps_override_high_average() -> None:
    assert classify(88.0, 2, 22.0) is GroupName.INTENSIVE_SUPPORT


def test_real_dataset_group_distribution() -> None:
    dataset = assessment.load_assessment_csv(REAL_DATASET)
    class_analysis = gaps.analyze_class(dataset.learners, title=dataset.title)
    assign_groups(class_analysis)
    counts = class_analysis.group_counts()
    assert counts[GroupName.MASTERED] == 8
    assert counts[GroupName.DEVELOPING] == 9
    assert counts[GroupName.INTENSIVE_SUPPORT] == 7


def test_every_learner_has_group_and_explanation() -> None:
    dataset = assessment.load_assessment_csv(REAL_DATASET)
    class_analysis = gaps.analyze_class(dataset.learners, title=dataset.title)
    assign_groups(class_analysis)
    for learner in class_analysis.learners:
        assert learner.group is not None
        assert learner.explanation is not None
        assert learner.learner_id in learner.explanation
        assert "overall average" in learner.explanation


def test_grouping_is_deterministic_and_repeatable() -> None:
    dataset = assessment.load_assessment_csv(REAL_DATASET)

    def run_once() -> list[tuple[str, str, str]]:
        class_analysis = gaps.analyze_class(dataset.learners, title=dataset.title)
        assign_groups(class_analysis)
        return [
            (learner.learner_id, learner.group.value, learner.explanation or "")
            for learner in class_analysis.learners
        ]

    assert run_once() == run_once()


def test_explanation_lists_evidence_for_intensive_learner() -> None:
    dataset = assessment.load_assessment_csv(REAL_DATASET)
    class_analysis = gaps.analyze_class(dataset.learners, title=dataset.title)
    assign_groups(class_analysis)
    s022 = next(l for l in class_analysis.learners if l.learner_id == "S022")
    assert s022.group is GroupName.INTENSIVE_SUPPORT
    assert "overall average = 59.75%" in (s022.explanation or "")
    assert "equivalent_fractions = 38%" in (s022.explanation or "")
    assert "adding_fractions = 22%" in (s022.explanation or "")
    assert "2 sub-skills are below the critical threshold of 40%" in (s022.explanation or "")


def test_format_percent_trims_trailing_zeros() -> None:
    assert format_percent(43.5) == "43.5"
    assert format_percent(35.0) == "35"
    assert format_percent(82.75) == "82.75"


def test_thresholds_come_from_config() -> None:
    assert config.MASTERED_MIN_OVERALL == 80.0
    assert config.SKILL_MASTERY_THRESHOLD == 70.0
    assert config.DEVELOPING_MIN_OVERALL == 50.0
    assert config.CRITICAL_SKILL_THRESHOLD == 40.0
    assert config.INTENSIVE_MIN_CRITICAL_GAPS == 2
