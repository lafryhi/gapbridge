"""Sprint 2 demo: full deterministic end-to-end remediation workflow.

CSV -> analysis -> grouping -> plan proposal -> teacher approval
-> exercise generation -> teacher report, with state + audit trail.

No AWS, no Bedrock, no LLM calls of any kind.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from gapbridge import pipeline  # noqa: E402
from gapbridge.models import GroupName  # noqa: E402

DATA_PATH = PROJECT_ROOT / "data" / "synthetic_assessment.csv"


def main() -> None:
    ctx = pipeline.default_context()

    analysis = pipeline.load_and_prepare(DATA_PATH, ctx)
    counts = analysis.group_counts()
    print("=== GapBridge Sprint 2 demo ===")
    print(f"Learners analyzed: {len(analysis.learners)}")
    print(
        "Groups: "
        f"Mastered {counts[GroupName.MASTERED]} / "
        f"Developing {counts[GroupName.DEVELOPING]} / "
        f"Intensive Support {counts[GroupName.INTENSIVE_SUPPORT]}"
    )

    version = pipeline.propose_plans(analysis, ctx)
    print(f"Remediation plans proposed (version {version})")

    decision = pipeline.approve_plans(
        ctx,
        version,
        actor="teacher (simulated)",
        comment="Plans look appropriate for this class.",
    )
    print(f"Teacher approval recorded: {decision.decision} (v{decision.plan_version})")

    sets = pipeline.generate_materials(analysis, ctx)
    total_items = sum(len(s.items) for s in sets.values())
    print(f"Exercise sets generated: {len(sets)} groups, {total_items} items")

    report_path = pipeline.generate_report(
        analysis,
        ctx,
        plan_version=version,
        approvals=[decision],
        source_name=DATA_PATH.name,
    )
    record = ctx.store.load()
    print(f"Workflow state: {record.current_state if record else 'UNKNOWN'}")
    print(f"Teacher report: {report_path}")
    print("Audit log:      ", ctx.audit.path)


if __name__ == "__main__":
    main()
