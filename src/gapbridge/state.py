"""Workflow state machine with local JSON persistence.

The Sprint 2 compatibility path remains valid while Sprint 3 adds explicit
group, plan, and exercise approval gates.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from . import config
from .models import WorkflowStateRecord


class WorkflowState(str, Enum):
    UPLOADED = "UPLOADED"
    ANALYZED = "ANALYZED"
    GROUPED = "GROUPED"
    GROUPS_PROPOSED = "GROUPS_PROPOSED"
    GROUPS_APPROVED = "GROUPS_APPROVED"
    PLAN_PROPOSED = "PLAN_PROPOSED"
    PLAN_APPROVED = "PLAN_APPROVED"
    APPROVED = "APPROVED"
    REVISION_REQUESTED = "REVISION_REQUESTED"
    EXERCISES_PROPOSED = "EXERCISES_PROPOSED"
    EXERCISES_APPROVED = "EXERCISES_APPROVED"
    MATERIALS_GENERATED = "MATERIALS_GENERATED"
    REPORT_READY = "REPORT_READY"


ALLOWED_TRANSITIONS: dict[WorkflowState, frozenset[WorkflowState]] = {
    WorkflowState.UPLOADED: frozenset({WorkflowState.ANALYZED}),
    WorkflowState.ANALYZED: frozenset({WorkflowState.GROUPED}),
    # PLAN_PROPOSED is retained as the Sprint 2 compatibility path. Sprint 3
    # uses GROUPS_PROPOSED so group approval is an explicit hard gate.
    WorkflowState.GROUPED: frozenset(
        {WorkflowState.PLAN_PROPOSED, WorkflowState.GROUPS_PROPOSED}
    ),
    WorkflowState.GROUPS_PROPOSED: frozenset({WorkflowState.GROUPS_APPROVED}),
    WorkflowState.GROUPS_APPROVED: frozenset({WorkflowState.PLAN_PROPOSED}),
    WorkflowState.PLAN_PROPOSED: frozenset(
        {
            WorkflowState.APPROVED,
            WorkflowState.PLAN_APPROVED,
            WorkflowState.REVISION_REQUESTED,
        }
    ),
    WorkflowState.PLAN_APPROVED: frozenset({WorkflowState.EXERCISES_PROPOSED}),
    WorkflowState.APPROVED: frozenset(
        {WorkflowState.MATERIALS_GENERATED, WorkflowState.REVISION_REQUESTED}
    ),
    WorkflowState.REVISION_REQUESTED: frozenset({WorkflowState.PLAN_PROPOSED}),
    WorkflowState.EXERCISES_PROPOSED: frozenset(
        {WorkflowState.EXERCISES_APPROVED}
    ),
    WorkflowState.EXERCISES_APPROVED: frozenset({WorkflowState.REPORT_READY}),
    WorkflowState.MATERIALS_GENERATED: frozenset({WorkflowState.REPORT_READY}),
    WorkflowState.REPORT_READY: frozenset(),
}


class InvalidTransitionError(Exception):
    pass


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_transition(current: WorkflowState, target: WorkflowState) -> None:
    if target not in ALLOWED_TRANSITIONS[current]:
        raise InvalidTransitionError(
            f"Transition {current.value} -> {target.value} is not allowed."
        )


class StateStore:
    """Persists the current workflow state as a single JSON file."""

    def __init__(self, path: str | Path = config.DEFAULT_STATE_PATH) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def path(self) -> Path:
        return self._path

    def save(self, record: WorkflowStateRecord) -> None:
        payload = {
            "current_state": record.current_state,
            "history": list(record.history),
            "updated_at": record.updated_at,
        }
        tmp_path = self._path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        os.replace(tmp_path, self._path)

    def load(self) -> WorkflowStateRecord | None:
        if not self._path.exists():
            return None
        raw = json.loads(self._path.read_text(encoding="utf-8"))
        return WorkflowStateRecord(
            current_state=str(raw["current_state"]),
            history=[str(item) for item in raw.get("history", [])],
            updated_at=str(raw.get("updated_at", "")),
        )


def initialize(store: StateStore) -> WorkflowStateRecord:
    record = WorkflowStateRecord(
        current_state=WorkflowState.UPLOADED.value,
        history=[WorkflowState.UPLOADED.value],
        updated_at=utc_now_iso(),
    )
    store.save(record)
    return record


def advance(store: StateStore, target: WorkflowState) -> WorkflowStateRecord:
    """Validate and perform one transition, then persist the new state."""
    record = store.load()
    if record is None:
        current = WorkflowState.UPLOADED
        history: list[str] = [current.value]
    else:
        current = WorkflowState(record.current_state)
        history = list(record.history)

    validate_transition(current, target)
    history.append(target.value)
    updated = WorkflowStateRecord(
        current_state=target.value,
        history=history,
        updated_at=utc_now_iso(),
    )
    store.save(updated)
    return updated
