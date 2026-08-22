"""Tests for the append-only audit log."""

import json
from pathlib import Path

from gapbridge.audit import AuditLog
from gapbridge.models import AuditEvent


def make_event(event_type: str, details: str) -> AuditEvent:
    return AuditEvent(
        timestamp="2026-01-01T00:00:00+00:00",
        event_type=event_type,
        state="GROUPED",
        actor="system",
        details=details,
        metadata={"mastered": 8},
    )


def test_events_append_and_parse(tmp_path: Path) -> None:
    log = AuditLog(tmp_path / "audit_log.jsonl")
    log.append(make_event("DATASET_UPLOADED", "loaded 24 learners"))
    log.append(make_event("GROUP_ASSIGNMENT_COMPLETED", "groups assigned"))

    events = log.read_all()
    assert len(events) == 2
    assert events[0].event_type == "DATASET_UPLOADED"
    assert events[1].details == "groups assigned"
    assert events[0].metadata == {"mastered": 8}


def test_previous_events_remain_unchanged(tmp_path: Path) -> None:
    log = AuditLog(tmp_path / "audit_log.jsonl")
    first = make_event("EVENT_ONE", "first entry")
    log.append(first)

    before = log.read_all()[0].to_dict()
    log.append(make_event("EVENT_TWO", "second entry"))
    after = log.read_all()

    assert len(after) == 2
    assert after[0].to_dict() == before


def test_file_is_valid_json_lines(tmp_path: Path) -> None:
    log = AuditLog(tmp_path / "audit_log.jsonl")
    for index in range(5):
        log.append(make_event(f"TYPE_{index}", f"entry {index}"))

    lines = (tmp_path / "audit_log.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 5
    parsed = [json.loads(line) for line in lines]
    assert [item["event_type"] for item in parsed] == [
        "TYPE_0",
        "TYPE_1",
        "TYPE_2",
        "TYPE_3",
        "TYPE_4",
    ]


def test_read_all_on_missing_file_returns_empty(tmp_path: Path) -> None:
    log = AuditLog(tmp_path / "does_not_exist.jsonl")
    assert log.read_all() == []


def test_roundtrip_preserves_all_fields(tmp_path: Path) -> None:
    log = AuditLog(tmp_path / "audit_log.jsonl")
    event = AuditEvent(
        timestamp="2026-08-21T12:00:00+00:00",
        event_type="GROUP_ASSIGNMENT_COMPLETED",
        state="GROUPED",
        actor="system",
        details="24 learners assigned to remediation groups",
        metadata={"mastered": 8, "developing": 9, "intensive_support": 7},
    )
    log.append(event)
    loaded = log.read_all()[0]
    assert loaded == event
