"""Run-isolated persistence helpers for Sprint 3."""

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel

from . import config
from .audit import AuditLog
from .sprint3_schemas import ApprovalRecord
from .state import StateStore

RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
TModel = TypeVar("TModel", bound=BaseModel)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_run_id() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return f"gb-{timestamp}-{uuid.uuid4().hex[:8]}"


def validate_run_id(run_id: str) -> str:
    if not RUN_ID_PATTERN.fullmatch(run_id):
        raise ValueError(
            "run_id must contain only letters, numbers, underscores, or hyphens "
            "and be at most 64 characters"
        )
    return run_id


def stable_hash(value: Any) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")

    def encode_default(item: Any) -> Any:
        if isinstance(item, BaseModel):
            return item.model_dump(mode="json")
        raise TypeError(f"Object of type {type(item).__name__} is not JSON serializable")

    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=encode_default,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def save_model(path: Path, model: BaseModel) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(model.model_dump_json(indent=2), encoding="utf-8")
    os.replace(tmp_path, path)


def save_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    os.replace(tmp_path, path)


def load_model(path: Path, model_type: type[TModel]) -> TModel:
    return model_type.model_validate_json(path.read_text(encoding="utf-8"))


class ApprovalStore:
    """Append-only approval records scoped to exactly one run."""

    def __init__(self, path: Path, run_id: str) -> None:
        self.path = path
        self.run_id = validate_run_id(run_id)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, record: ApprovalRecord) -> None:
        if record.run_id != self.run_id:
            raise ValueError("approval run_id does not match this store")
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(record.model_dump_json() + "\n")

    def read_all(self) -> list[ApprovalRecord]:
        if not self.path.exists():
            return []
        records: list[ApprovalRecord] = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    record = ApprovalRecord.model_validate_json(line)
                    if record.run_id != self.run_id:
                        raise ValueError("approval file contains a different run_id")
                    records.append(record)
        return records

    def approved(self, gate: str, artifact_version: int | None = None) -> bool:
        return any(
            record.gate == gate
            and record.decision == "approved"
            and (artifact_version is None or record.artifact_version == artifact_version)
            for record in self.read_all()
        )


@dataclass(frozen=True)
class Sprint3RunContext:
    run_id: str
    run_dir: Path
    store: StateStore
    audit: AuditLog
    approvals: ApprovalStore
    manifest_path: Path
    analysis_path: Path
    groups_path: Path
    plans_path: Path
    exercises_path: Path
    report_path: Path


def _run_context(root: Path, run_id: str) -> Sprint3RunContext:
    """Build path-bound services for one already-validated run directory."""
    run_dir = (root / run_id).resolve()
    if run_dir.parent != root:
        raise ValueError("run directory escaped the configured runtime root")
    artifacts = run_dir / "artifacts"
    return Sprint3RunContext(
        run_id=run_id,
        run_dir=run_dir,
        store=StateStore(run_dir / "workflow_state.json"),
        audit=AuditLog(run_dir / "audit_log.jsonl"),
        approvals=ApprovalStore(run_dir / "approvals.jsonl", run_id),
        manifest_path=run_dir / "run_manifest.json",
        analysis_path=artifacts / "analysis.json",
        groups_path=artifacts / "groups.json",
        plans_path=artifacts / "remediation_plans.json",
        exercises_path=artifacts / "exercise_sets.json",
        report_path=artifacts / "teacher_report.md",
    )


def create_run_context(
    *,
    runtime_root: Path | None = None,
    run_id: str | None = None,
) -> Sprint3RunContext:
    resolved_run_id = validate_run_id(new_run_id() if run_id is None else run_id)
    root = (runtime_root or (config.PROJECT_ROOT / "runtime" / "runs")).resolve()
    run_dir = (root / resolved_run_id).resolve()
    if run_dir.parent != root:
        raise ValueError("run directory escaped the configured runtime root")
    run_dir.mkdir(parents=True, exist_ok=False)
    artifacts = run_dir / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=False)
    return _run_context(root, resolved_run_id)


def open_run_context(
    run_id: str,
    *,
    runtime_root: Path | None = None,
) -> Sprint3RunContext:
    """Reopen one existing run without creating or resetting its state."""
    resolved_run_id = validate_run_id(run_id)
    root = (runtime_root or (config.PROJECT_ROOT / "runtime" / "runs")).resolve()
    run_dir = (root / resolved_run_id).resolve()
    if run_dir.parent != root:
        raise ValueError("run directory escaped the configured runtime root")
    if not run_dir.is_dir():
        raise FileNotFoundError(f"GapBridge run '{resolved_run_id}' was not found")
    if not (run_dir / "artifacts").is_dir():
        raise ValueError(f"GapBridge run '{resolved_run_id}' is incomplete")
    return _run_context(root, resolved_run_id)
