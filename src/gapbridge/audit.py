"""Append-only JSON Lines audit log.

Events are never modified or removed; ``append`` only ever adds lines.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import config
from .models import AuditEvent


class AuditLog:
    def __init__(self, path: str | Path = config.DEFAULT_AUDIT_PATH) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def path(self) -> Path:
        return self._path

    def append(self, event: AuditEvent) -> None:
        line = json.dumps(event.to_dict(), ensure_ascii=False)
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")

    def read_all(self) -> list[AuditEvent]:
        if not self._path.exists():
            return []
        events: list[AuditEvent] = []
        with self._path.open("r", encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if stripped:
                    events.append(AuditEvent.from_dict(json.loads(stripped)))
        return events
