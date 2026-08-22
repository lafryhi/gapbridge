"""Offline scripted Strands model used for tests and the Sprint 3 demo.

This is not an LLM. It drives the real Strands Agent/tool loop with a
prevalidated deterministic payload so the integration is testable without a
network or credentials.
"""

from __future__ import annotations

import json
from typing import Any

from strands.models.model import Model


class OfflineScriptedModel(Model):
    model_id = "scripted-gapbridge-offline-v1"

    def __init__(self) -> None:
        self._config: dict[str, Any] = {"model_id": self.model_id}
        self._steps: list[tuple[str, dict[str, Any]]] = []
        self._index = 0
        self.tool_calls: list[str] = []

    def prepare_invocation(
        self,
        stage: str,
        structured_tool_name: str,
        structured_payload: dict[str, Any],
    ) -> None:
        groups = ["Mastered", "Developing", "Intensive Support"]
        if stage == "plans":
            steps: list[tuple[str, dict[str, Any]]] = [
                ("get_workflow_status", {}),
                ("get_class_evidence", {}),
            ]
            for group in groups:
                steps.append(("get_group_profile", {"group": group}))
                steps.append(("get_plan_constraints", {"group": group}))
            steps.append(
                (
                    "validate_plan_alignment",
                    {"draft_json": json.dumps(structured_payload)},
                )
            )
        elif stage == "exercises":
            steps = [("get_workflow_status", {})]
            steps.extend(("get_approved_plan", {"group": group}) for group in groups)
            steps.append(
                (
                    "validate_exercise_set",
                    {"draft_json": json.dumps(structured_payload)},
                )
            )
        else:
            raise ValueError(f"Unknown scripted stage: {stage}")
        steps.append((structured_tool_name, structured_payload))
        self._steps = steps
        self._index = 0

    def update_config(self, **model_config: Any) -> None:
        self._config.update(model_config)

    def get_config(self) -> dict[str, Any]:
        return dict(self._config)

    async def structured_output(self, *args: Any, **kwargs: Any):
        raise AssertionError(
            "The deprecated direct structured-output path is not used by Sprint 3."
        )
        yield  # pragma: no cover

    async def stream(
        self,
        messages,
        tool_specs=None,
        system_prompt=None,
        **kwargs: Any,
    ):
        if self._index >= len(self._steps):
            raise RuntimeError("scripted invocation has no remaining steps")
        name, payload = self._steps[self._index]
        self._index += 1
        available = {spec["name"] for spec in (tool_specs or [])}
        if name not in available:
            raise RuntimeError(f"scripted tool '{name}' was not registered")
        tool_use_id = f"offline-{len(self.tool_calls) + 1}"
        self.tool_calls.append(name)
        yield {"messageStart": {"role": "assistant"}}
        yield {
            "contentBlockStart": {
                "start": {
                    "toolUse": {"toolUseId": tool_use_id, "name": name}
                }
            }
        }
        yield {
            "contentBlockDelta": {
                "delta": {"toolUse": {"input": json.dumps(payload)}}
            }
        }
        yield {"contentBlockStop": {}}
        yield {"messageStop": {"stopReason": "tool_use"}}
