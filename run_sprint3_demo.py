"""GapBridge Sprint 3 offline demo using one bounded Strands Agent.

The model is scripted and local: it performs no LLM, AWS, Bedrock, Ollama,
credential, or network operation. It drives the real Strands Agent/tool loop
around deterministic evidence and strict structured outputs.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from gapbridge import config, sprint3_workflow as workflow  # noqa: E402
from gapbridge.models import GroupName  # noqa: E402
from gapbridge.scripted_strands_model import OfflineScriptedModel  # noqa: E402
from gapbridge.sprint3_storage import create_run_context  # noqa: E402
from gapbridge.strands_orchestrator import StrandsContentOrchestrator  # noqa: E402

DATA_PATH = PROJECT_ROOT / "data" / "synthetic_assessment.csv"


def main() -> None:
    ctx = create_run_context()
    analysis = workflow.start_run(DATA_PATH, ctx)
    counts = analysis.group_counts()

    workflow.approve_groups(
        ctx, actor="teacher (demo)", comment="Deterministic groups reviewed."
    )

    model = OfflineScriptedModel()
    provider = StrandsContentOrchestrator(ctx, analysis, model)
    plans = workflow.propose_plans(analysis, ctx, provider)
    workflow.approve_plans(
        ctx, actor="teacher (demo)", comment="Draft plans reviewed."
    )

    exercises = workflow.propose_exercises(analysis, ctx, provider)
    workflow.approve_exercises(
        ctx, actor="teacher (demo)", comment="Exercise drafts reviewed."
    )
    report_path = workflow.generate_report(analysis, ctx)

    total_items = sum(len(item.items) for item in exercises.draft.sets)
    record = ctx.store.load()
    print("=== GapBridge Sprint 3 demo (offline scripted Strands) ===")
    print(f"Run ID: {ctx.run_id}")
    print(f"Learners: {len(analysis.learners)}")
    print(
        "Groups: "
        + " / ".join(f"{group.value} {counts[group]}" for group in GroupName)
    )
    print("Gate 1 groups: APPROVED")
    print(
        f"Plans: {len(plans.draft.plans)} drafts; "
        f"Strands tool calls {len(plans.provenance.tool_calls)}"
    )
    print("Gate 2 plans: APPROVED")
    print(
        f"Exercises: {len(exercises.draft.sets)} sets, {total_items} items; "
        f"Strands tool calls {len(exercises.provenance.tool_calls)}"
    )
    print("Gate 3 exercises: APPROVED")
    print(f"Workflow state: {record.current_state if record else 'UNKNOWN'}")
    print(f"Run directory: {ctx.run_dir}")
    print(f"Teacher report: {report_path}")
    print("External model/AWS calls: NONE")


if __name__ == "__main__":
    main()
