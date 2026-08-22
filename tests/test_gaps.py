"""Tests for learner analysis and gap detection."""

from gapbridge import config
from gapbridge.gaps import analyze_class, analyze_learner
from gapbridge.models import LearnerAssessment


def make_learner(scores: list[float]) -> LearnerAssessment:
    return LearnerAssessment(
        learner_id="T001",
        scores=dict(zip(config.REQUIRED_SKILLS, scores)),
    )


def test_average_calculated_correctly() -> None:
    analysis = analyze_learner(make_learner([90, 80, 75, 65]))
    assert analysis.overall_average == 77.5


def test_weakest_skill_identified() -> None:
    analysis = analyze_learner(make_learner([90, 80, 75, 65]))
    assert analysis.weakest_skill == "adding_fractions"
    assert analysis.weakest_score == 65.0


def test_weakest_skill_tie_broken_by_skill_order() -> None:
    analysis = analyze_learner(make_learner([50, 50, 80, 80]))
    assert analysis.weakest_skill == "identifying_fractions"


def test_below_mastery_gaps_detected() -> None:
    analysis = analyze_learner(make_learner([90, 65, 80, 69.9]))
    assert [gap.skill for gap in analysis.gaps_below_mastery] == [
        "comparing_fractions",
        "adding_fractions",
    ]
    assert all(gap.threshold == 70.0 for gap in analysis.gaps_below_mastery)


def test_scores_at_mastery_threshold_are_not_gaps() -> None:
    analysis = analyze_learner(make_learner([70, 70, 70, 70]))
    assert analysis.gaps_below_mastery == []


def test_critical_gap_counting() -> None:
    analysis = analyze_learner(make_learner([90, 35, 20, 80]))
    assert analysis.critical_gap_skills == [
        "comparing_fractions",
        "equivalent_fractions",
    ]


def test_score_exactly_critical_threshold_is_not_critical() -> None:
    analysis = analyze_learner(make_learner([40, 40, 39.99, 90]))
    assert analysis.critical_gap_skills == ["equivalent_fractions"]


def test_analyze_class_covers_all_learners() -> None:
    learners = [
        make_learner([90, 80, 75, 65]),
        make_learner([60, 70, 65, 55]),
    ]
    class_analysis = analyze_class(learners)
    assert class_analysis.title
    assert len(class_analysis.learners) == 2
    assert class_analysis.learners[1].overall_average == 62.5
