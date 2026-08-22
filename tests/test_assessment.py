"""Tests for CSV loading and validation."""

from pathlib import Path

import pytest

from gapbridge.assessment import (
    DuplicateLearnerIDError,
    EmptyDatasetError,
    InvalidScoreError,
    MissingLearnerIDError,
    MissingSkillColumnError,
    UnexpectedColumnError,
    load_assessment_csv,
)

HEADER = (
    "learner_id,identifying_fractions,comparing_fractions,"
    "equivalent_fractions,adding_fractions\n"
)

REAL_DATASET = Path(__file__).resolve().parents[1] / "data" / "synthetic_assessment.csv"


def write_csv(tmp_path: Path, content: str) -> Path:
    file_path = tmp_path / "quiz.csv"
    file_path.write_text(content, encoding="utf-8")
    return file_path


def test_valid_csv_loads(tmp_path: Path) -> None:
    file_path = write_csv(tmp_path, HEADER + "S001,90,80,75,65\nS002,60,70,65,55\n")
    dataset = load_assessment_csv(file_path)
    assert [learner.learner_id for learner in dataset.learners] == ["S001", "S002"]
    assert dataset.learners[0].scores["comparing_fractions"] == 80.0
    assert dataset.skills[0] == "identifying_fractions"


def test_real_synthetic_dataset_loads() -> None:
    dataset = load_assessment_csv(REAL_DATASET)
    assert len(dataset.learners) == 24
    ids = [learner.learner_id for learner in dataset.learners]
    assert len(set(ids)) == 24


def test_non_numeric_score_rejected(tmp_path: Path) -> None:
    content = HEADER + "S001,90,eighty,75,65\n"
    with pytest.raises(InvalidScoreError):
        load_assessment_csv(write_csv(tmp_path, content))


def test_score_above_100_rejected(tmp_path: Path) -> None:
    content = HEADER + "S001,101,80,75,65\n"
    with pytest.raises(InvalidScoreError):
        load_assessment_csv(write_csv(tmp_path, content))


def test_score_below_0_rejected(tmp_path: Path) -> None:
    content = HEADER + "S001,-5,80,75,65\n"
    with pytest.raises(InvalidScoreError):
        load_assessment_csv(write_csv(tmp_path, content))


def test_duplicate_learner_rejected(tmp_path: Path) -> None:
    content = HEADER + "S001,90,80,75,65\nS001,60,70,65,55\n"
    with pytest.raises(DuplicateLearnerIDError):
        load_assessment_csv(write_csv(tmp_path, content))


def test_missing_skill_column_rejected(tmp_path: Path) -> None:
    content = "learner_id,identifying_fractions,comparing_fractions,adding_fractions\nS001,90,80,65\n"
    with pytest.raises(MissingSkillColumnError):
        load_assessment_csv(write_csv(tmp_path, content))


def test_missing_learner_id_column_rejected(tmp_path: Path) -> None:
    content = "student_id,identifying_fractions,comparing_fractions,equivalent_fractions,adding_fractions\nS001,90,80,75,65\n"
    with pytest.raises(MissingLearnerIDError):
        load_assessment_csv(write_csv(tmp_path, content))


def test_empty_learner_id_cell_rejected(tmp_path: Path) -> None:
    content = HEADER + "S001,90,80,75,65\n,50,50,50,50\n"
    with pytest.raises(MissingLearnerIDError):
        load_assessment_csv(write_csv(tmp_path, content))


def test_header_only_dataset_rejected(tmp_path: Path) -> None:
    with pytest.raises(EmptyDatasetError):
        load_assessment_csv(write_csv(tmp_path, HEADER))


def test_completely_empty_file_rejected(tmp_path: Path) -> None:
    with pytest.raises(EmptyDatasetError):
        load_assessment_csv(write_csv(tmp_path, ""))


def test_unexpected_extra_column_rejected(tmp_path: Path) -> None:
    content = (
        "learner_id,identifying_fractions,comparing_fractions,"
        "equivalent_fractions,adding_fractions,notes\n"
        "S001,90,80,75,65,ok\n"
    )
    with pytest.raises(UnexpectedColumnError):
        load_assessment_csv(write_csv(tmp_path, content))
