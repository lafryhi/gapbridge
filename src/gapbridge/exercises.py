"""Deterministic, template-based exercise generation.

Exercises are produced by fixed arithmetic templates parameterised only by
the item index — no randomness, no AI. The same (group, target skills)
always yields byte-identical exercise sets. This module is the seam Sprint 3
will replace/augment with Strands-based generation.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from . import config
from .models import ClassAnalysis, ExerciseItem, ExerciseSet, GroupName
from .plans import GroupRemediationPlan


def _identifying(i: int) -> tuple[str, str]:
    num = i % 5 + 1
    den = num + (i % 3) + 2
    return (
        f"A shape is divided into {den} equal parts and {num} parts are "
        f"shaded. What fraction is shaded?",
        f"{num}/{den}",
    )


def _comparing(i: int) -> tuple[str, str]:
    den = (4, 6, 8)[i % 3]
    n1 = i % 3 + 1
    n2 = n1 + 2
    return (
        f"Which fraction is larger: {n1}/{den} or {n2}/{den}?",
        f"{n2}/{den}",
    )


def _equivalent(i: int) -> tuple[str, str]:
    num = (1, 2, 3)[i % 3]
    base_den = (2, 3, 4)[i % 3]
    multiplier = i % 4 + 2
    return (
        f"Complete the equivalent fraction: {num}/{base_den} = ?/{base_den * multiplier}",
        f"{num * multiplier}/{base_den * multiplier}",
    )


def _adding(i: int) -> tuple[str, str]:
    den = (4, 5, 6, 8)[i % 4]
    a = i % 3 + 1
    b = a + 1
    return (
        f"Add the fractions: {a}/{den} + {b}/{den} = ?",
        f"{a + b}/{den}",
    )


GENERATORS = {
    "identifying_fractions": _identifying,
    "comparing_fractions": _comparing,
    "equivalent_fractions": _equivalent,
    "adding_fractions": _adding,
}


def generate_exercises(
    analysis: ClassAnalysis,
    plans: dict[GroupName, GroupRemediationPlan],
) -> dict[GroupName, ExerciseSet]:
    """Generate one labelled exercise set per group from its current plan."""
    sets: dict[GroupName, ExerciseSet] = {}
    for group in GroupName:
        plan = plans[group].current
        per_skill = int(config.PLAN_RULES[group]["items_per_skill"])  # type: ignore[arg-type]
        items: list[ExerciseItem] = []
        for skill in plan.target_skills:
            generator = GENERATORS.get(skill)
            if generator is None:
                raise ValueError(
                    f"No exercise template available for skill '{skill}'."
                )
            for i in range(per_skill):
                prompt, answer = generator(i)
                items.append(ExerciseItem(skill=skill, prompt=prompt, answer=answer))
        title = (
            f"{group.value} exercises - targets: {', '.join(plan.target_skills)}"
        )
        sets[group] = ExerciseSet(group=group, title=title, items=items)
    return sets


def save_exercises(path: Path, sets: dict[GroupName, ExerciseSet]) -> None:
    """Persist exercise sets atomically as local JSON."""
    payload = {
        "generated_by": "deterministic-template-v1",
        "sets": [
            {
                "group": exercise_set.group.value,
                "title": exercise_set.title,
                "generated_by": exercise_set.generated_by,
                "items": [
                    {
                        "skill": item.skill,
                        "prompt": item.prompt,
                        "answer": item.answer,
                    }
                    for item in exercise_set.items
                ],
            }
            for exercise_set in (sets[g] for g in GroupName)
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(tmp_path, path)


def load_exercises(path: Path) -> dict[GroupName, ExerciseSet]:
    """Load persisted exercise sets."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    sets: dict[GroupName, ExerciseSet] = {}
    for raw in payload["sets"]:  # type: ignore[index]
        group = GroupName(str(raw["group"]))
        items = [
            ExerciseItem(
                skill=str(item["skill"]),
                prompt=str(item["prompt"]),
                answer=str(item["answer"]),
            )
            for item in raw["items"]
        ]
        sets[group] = ExerciseSet(
            group=group,
            title=str(raw["title"]),
            items=items,
            generated_by=str(raw.get("generated_by", "deterministic-template-v1")),
        )
    return sets
