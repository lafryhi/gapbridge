"""Loading and validation of assessment CSV files (deterministic).

Expected schema (UTF-8, one row per learner):

    learner_id,<skill_1>,<skill_2>,...

Scores are percentages in the closed range 0-100.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

from . import config
from .models import LearnerAssessment

LEARNER_ID_COLUMN = "learner_id"


class AssessmentError(Exception):
    """Base class for assessment data problems."""


class EmptyDatasetError(AssessmentError):
    pass


class MissingLearnerIDError(AssessmentError):
    pass


class DuplicateLearnerIDError(AssessmentError):
    pass


class MissingSkillColumnError(AssessmentError):
    pass


class UnexpectedColumnError(AssessmentError):
    pass


class InvalidScoreError(AssessmentError):
    pass


@dataclass(frozen=True)
class AssessmentDataset:
    title: str
    skills: tuple[str, ...]
    learners: list[LearnerAssessment]


def load_assessment_csv(
    path: str | Path,
    *,
    title: str = config.ASSESSMENT_TITLE,
    required_skills: tuple[str, ...] = config.REQUIRED_SKILLS,
) -> AssessmentDataset:
    csv_path = Path(path)
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames
        if not fieldnames:
            raise EmptyDatasetError(f"{csv_path.name}: file has no header row.")
        _validate_columns(fieldnames, required_skills)
        learners = _read_rows(reader, required_skills)

    if not learners:
        raise EmptyDatasetError(f"{csv_path.name}: header found but no learner rows.")
    return AssessmentDataset(title=title, skills=tuple(required_skills), learners=learners)


def _validate_columns(fieldnames: list[str], required_skills: tuple[str, ...]) -> None:
    columns = [column.strip() for column in fieldnames]

    if LEARNER_ID_COLUMN not in columns:
        raise MissingLearnerIDError(f"Required column '{LEARNER_ID_COLUMN}' is missing.")

    missing = [skill for skill in required_skills if skill not in columns]
    if missing:
        raise MissingSkillColumnError(
            "Missing required skill column(s): " + ", ".join(missing)
        )

    expected = {LEARNER_ID_COLUMN, *required_skills}
    unexpected = [column for column in columns if column not in expected]
    if unexpected:
        raise UnexpectedColumnError("Unexpected column(s): " + ", ".join(unexpected))


def _read_rows(reader: csv.DictReader[str], required_skills: tuple[str, ...]) -> list[LearnerAssessment]:
    learners: list[LearnerAssessment] = []
    seen_ids: set[str] = set()

    for line_number, row in enumerate(reader, start=2):
        learner_id = (row.get(LEARNER_ID_COLUMN) or "").strip()
        if not learner_id:
            raise MissingLearnerIDError(f"Line {line_number}: learner_id is empty.")
        if learner_id in seen_ids:
            raise DuplicateLearnerIDError(
                f"Line {line_number}: duplicate learner_id '{learner_id}'."
            )

        scores: dict[str, float] = {}
        for skill in required_skills:
            raw_value = (row.get(skill) or "").strip()
            try:
                value = float(raw_value)
            except ValueError as exc:
                raise InvalidScoreError(
                    f"Line {line_number}: score for '{skill}' of learner "
                    f"'{learner_id}' is not numeric: '{raw_value}'."
                ) from exc
            if value < 0 or value > 100:
                raise InvalidScoreError(
                    f"Line {line_number}: score for '{skill}' of learner "
                    f"'{learner_id}' is out of range (0-100): {value}."
                )
            scores[skill] = value

        seen_ids.add(learner_id)
        learners.append(LearnerAssessment(learner_id=learner_id, scores=scores))

    return learners
