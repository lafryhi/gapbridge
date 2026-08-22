"""Tests for the workflow state machine and JSON persistence."""

import pytest

from gapbridge.models import WorkflowStateRecord
from gapbridge.state import (
    ALLOWED_TRANSITIONS,
    InvalidTransitionError,
    StateStore,
    WorkflowState,
    advance,
    initialize,
    validate_transition,
)


def test_valid_transition_succeeds() -> None:
    validate_transition(WorkflowState.UPLOADED, WorkflowState.ANALYZED)
    validate_transition(WorkflowState.ANALYZED, WorkflowState.GROUPED)


def test_invalid_transition_fails() -> None:
    with pytest.raises(InvalidTransitionError):
        validate_transition(WorkflowState.UPLOADED, WorkflowState.GROUPED)


def test_skipping_multiple_states_fails() -> None:
    with pytest.raises(InvalidTransitionError):
        validate_transition(WorkflowState.UPLOADED, WorkflowState.REPORT_READY)


def test_terminal_state_has_no_transitions() -> None:
    with pytest.raises(InvalidTransitionError):
        validate_transition(WorkflowState.REPORT_READY, WorkflowState.UPLOADED)


def test_state_persistence_roundtrip(tmp_path) -> None:
    store = StateStore(tmp_path / "state.json")
    record = WorkflowStateRecord(
        current_state="GROUPED",
        history=["UPLOADED", "ANALYZED", "GROUPED"],
        updated_at="2026-01-01T00:00:00+00:00",
    )
    store.save(record)
    assert store.load() == record


def test_load_missing_file_returns_none(tmp_path) -> None:
    store = StateStore(tmp_path / "missing.json")
    assert store.load() is None


def test_advance_walks_sprint1_path_and_persists(tmp_path) -> None:
    store = StateStore(tmp_path / "state.json")
    initialize(store)

    advance(store, WorkflowState.ANALYZED)
    final = advance(store, WorkflowState.GROUPED)

    assert final.current_state == "GROUPED"
    reloaded = store.load()
    assert reloaded is not None
    assert reloaded.current_state == "GROUPED"
    assert reloaded.history == ["UPLOADED", "ANALYZED", "GROUPED"]


def test_advance_rejects_illegal_jump(tmp_path) -> None:
    store = StateStore(tmp_path / "state.json")
    initialize(store)
    with pytest.raises(InvalidTransitionError):
        advance(store, WorkflowState.REPORT_READY)


def test_full_declared_graph_is_connected() -> None:
    reachable = {WorkflowState.UPLOADED}
    frontier = [WorkflowState.UPLOADED]
    while frontier:
        current = frontier.pop()
        for target in ALLOWED_TRANSITIONS[current]:
            if target not in reachable:
                reachable.add(target)
                frontier.append(target)
    assert reachable == set(WorkflowState)
