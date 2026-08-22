"""Sprint 1 verification demo: deterministic core only.

No AI, no LLM, no AWS, no network. Loads the synthetic dataset,
analyzes it, assigns remediation groups, prints a class summary with
example explanations, persists workflow state and appends audit events.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from gapbridge import assessment, config, gaps, grouping  # noqa: E402
from gapbridge.audit import AuditLog  # noqa: E402
from gapbridge.models import AuditEvent, GroupName  # noqa: E402
from gapbridge.state import (  # noqa: E402
    StateStore,
    WorkflowState,
    advance,
    initialize,
    utc_now_iso,
)

EXAMPLE_LEARNERS = ("S007", "S011", "S022")


def main() -> int:
    config.ensure_runtime_dirs()
    csv_path = PROJECT_ROOT / "data" / "synthetic_assessment.csv"

    dataset = assessment.load_assessment_csv(csv_path)
    store = StateStore()
    audit = AuditLog()

    initialize(store)
    audit.append(
        AuditEvent(
            timestamp=utc_now_iso(),
            event_type="DATASET_UPLOADED",
            state=WorkflowState.UPLOADED.value,
            actor="system",
            details=f"Loaded {len(dataset.learners)} learners from {csv_path.name}",
            metadata={"skills": list(dataset.skills)},
        )
    )

    analysis = gaps.analyze_class(dataset.learners, title=dataset.title)
    advance(store, WorkflowState.ANALYZED)
    audit.append(
        AuditEvent(
            timestamp=utc_now_iso(),
            event_type="ANALYSIS_COMPLETED",
            state=WorkflowState.ANALYZED.value,
            actor="system",
            details=(
                f"Analyzed {len(analysis.learners)} learners across "
                f"{len(analysis.skills)} sub-skills"
            ),
            metadata={},
        )
    )

    grouping.assign_groups(analysis)
    counts = analysis.group_counts()
    advance(store, WorkflowState.GROUPED)
    audit.append(
        AuditEvent(
            timestamp=utc_now_iso(),
            event_type="GROUP_ASSIGNMENT_COMPLETED",
            state=WorkflowState.GROUPED.value,
            actor="system",
            details=f"{len(analysis.learners)} learners assigned to remediation groups",
            metadata={
                "mastered": counts[GroupName.MASTERED],
                "developing": counts[GroupName.DEVELOPING],
                "intensive_support": counts[GroupName.INTENSIVE_SUPPORT],
            },
        )
    )

    print("GapBridge Sprint 1")
    print()
    print(f"Learners analyzed: {len(analysis.learners)}")
    print()
    print(f"Mastered: {counts[GroupName.MASTERED]}")
    print(f"Developing: {counts[GroupName.DEVELOPING]}")
    print(f"Intensive Support: {counts[GroupName.INTENSIVE_SUPPORT]}")
    print()

    for learner in analysis.learners:
        if learner.learner_id in EXAMPLE_LEARNERS:
            print(learner.explanation)
            print()

    record = store.load()
    print(f"Workflow state: {record.current_state if record else 'UNKNOWN'}")
    print("Audit log written successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
