"""GapBridge teacher-facing offline demo, hardened in Sprint 5."""

from __future__ import annotations

import os
import logging
import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from gapbridge.models import GroupName  # noqa: E402
from gapbridge.sprint3_evidence import class_evidence  # noqa: E402
from gapbridge.sprint4b_service import (  # noqa: E402
    AI_MODE,
    TeacherWorkflowService,
)
from gapbridge.sprint5_demo import DemoAction, friendly_demo_error  # noqa: E402
from gapbridge.state import WorkflowState  # noqa: E402

LOGGER = logging.getLogger("gapbridge.demo")

STATE_PROGRESS = {
    WorkflowState.GROUPS_PROPOSED: 0.30,
    WorkflowState.GROUPS_APPROVED: 0.42,
    WorkflowState.PLAN_PROPOSED: 0.55,
    WorkflowState.PLAN_APPROVED: 0.68,
    WorkflowState.EXERCISES_PROPOSED: 0.80,
    WorkflowState.EXERCISES_APPROVED: 0.90,
    WorkflowState.REPORT_READY: 1.0,
}


def _runtime_root() -> Path | None:
    configured = os.environ.get("GAPBRIDGE_UI_RUNTIME_ROOT", "").strip()
    return Path(configured) if configured else None


def _start_fresh_run() -> None:
    service = TeacherWorkflowService.start_fresh(runtime_root=_runtime_root())
    st.session_state["gapbridge_run_id"] = service.run_id
    st.query_params["run"] = service.run_id


def _load_service() -> TeacherWorkflowService | None:
    run_id = st.session_state.get("gapbridge_run_id") or st.query_params.get("run")
    if not run_id:
        return None
    try:
        service = TeacherWorkflowService.resume(
            str(run_id), runtime_root=_runtime_root()
        )
    except Exception as exc:
        LOGGER.exception("Could not resume GapBridge demo run")
        st.error(friendly_demo_error(DemoAction.RESUME, exc))
        st.session_state.pop("gapbridge_run_id", None)
        st.query_params.clear()
        return None
    st.session_state["gapbridge_run_id"] = service.run_id
    return service


def _action(
    label: str,
    callback,
    *,
    action: DemoAction,
    key: str,
    help_text: str = "",
    button_type: str = "primary",
) -> None:
    if st.button(label, key=key, type=button_type, width="stretch"):
        try:
            with st.spinner(help_text or "Working…"):
                callback()
        except Exception as exc:
            LOGGER.exception("GapBridge demo action failed: %s", action.value)
            st.error(friendly_demo_error(action, exc))
        else:
            st.rerun()


def _approval_status(gate_number: int, approved: bool) -> str:
    if approved:
        return f"Gate {gate_number} of 3 — APPROVED by teacher"
    return f"Gate {gate_number} of 3 — TEACHER REVIEW REQUIRED"


def _gate_progress(service: TeacherWorkflowService) -> None:
    approvals = service.approvals_by_gate()
    current_gate = {
        WorkflowState.GROUPS_PROPOSED: "groups",
        WorkflowState.PLAN_PROPOSED: "plans",
        WorkflowState.EXERCISES_PROPOSED: "exercises",
    }.get(service.state)
    columns = st.columns(3)
    for column, number, gate, label in zip(
        columns,
        (1, 2, 3),
        ("groups", "plans", "exercises"),
        ("Groups", "Plan", "Exercises"),
    ):
        if approvals[gate]:
            status = "Approved"
        elif current_gate == gate:
            status = "Review required"
        else:
            status = "Not reached"
        column.caption(f"Gate {number} · {label}")
        column.markdown(f"**{status}**")


def _render_header(service: TeacherWorkflowService) -> None:
    st.title("GapBridge")
    st.caption("From assessment evidence to teacher-approved remediation")
    mode, state = st.columns([1, 1])
    with mode.container(border=True):
        st.caption("AI mode")
        st.markdown(f"**{AI_MODE}**")
    state.metric("Workflow state", service.state.value)
    st.progress(
        STATE_PROGRESS.get(service.state, 0.05),
        text="Evidence → Groups → Plan → Exercises → Report",
    )
    _gate_progress(service)
    st.info(
        "Deterministic core: scores, gaps, and groups · Offline Strands: drafts "
        "plans and exercises · Teacher: makes all approval decisions."
    )


def _render_analysis(service: TeacherWorkflowService) -> None:
    analysis = service.analysis
    evidence = class_evidence(analysis)
    st.subheader("1 · Deterministic class analysis")
    st.caption("Computed from the synthetic assessment; AI is not used in this step.")
    left, middle, right = st.columns(3)
    class_average = sum(item.overall_average for item in analysis.learners) / len(
        analysis.learners
    )
    left.metric("Learners", len(analysis.learners))
    middle.metric("Class average", f"{class_average:.1f}%")
    right.metric(
        "Class-level gaps",
        sum(bool(skill["is_class_gap"]) for skill in evidence["skills"]),
    )
    st.dataframe(
        [
            {
                "Fraction skill": str(skill["skill"]).replace("_", " ").title(),
                "Class average": f"{float(skill['class_average']):.1f}%",
                "Below mastery": int(skill["learners_below_mastery"]),
                "Learning gap": "Yes" if skill["is_class_gap"] else "No",
            }
            for skill in evidence["skills"]
        ],
        hide_index=True,
        width="stretch",
    )


def _render_groups(service: TeacherWorkflowService) -> None:
    groups = service.groups()
    approvals = service.approvals_by_gate()
    st.subheader("2 · Deterministic learner groups · Gate 1")
    st.caption("Membership is computed from fixed thresholds and cannot be changed by AI.")
    columns = st.columns(3)
    for column, group in zip(columns, GroupName):
        members = groups.effective_membership[group.value]
        with column:
            st.metric(group.value, len(members), help="Computed learner count")
            st.caption(", ".join(members))

    example = next(
        learner for learner in service.analysis.learners if learner.explanation
    )
    with st.expander("See why a learner was placed in a group", expanded=True):
        st.markdown(f"**{example.learner_id} · {example.group.value}**")
        st.write(example.explanation)
        st.caption(
            "This explanation comes from deterministic scores and thresholds. "
            "The AI cannot move learners between groups."
        )

    st.write(_approval_status(1, approvals["groups"]))
    if service.state is WorkflowState.GROUPS_PROPOSED:
        comment = st.text_input(
            "Optional group-review note", key="groups_comment", max_chars=240
        )
        _action(
            "Approve groups · Gate 1",
            lambda: service.approve_groups(comment=comment),
            action=DemoAction.APPROVE_GROUPS,
            key="approve_groups",
            help_text="Recording your approval…",
        )


def _render_plans(service: TeacherWorkflowService) -> None:
    st.subheader("3 · Strands-assisted remediation plan · Gate 2")
    st.caption("Drafted by the bounded offline Strands agent from approved evidence.")
    if service.state is WorkflowState.GROUPS_APPROVED:
        st.write("Groups are approved. The offline Strands agent can now draft a plan.")
        _action(
            "Generate remediation plan",
            service.generate_plans,
            action=DemoAction.GENERATE_PLANS,
            key="generate_plans",
            help_text="The bounded offline Strands agent is drafting from approved evidence…",
        )
        return

    artifact = service.plans()
    if artifact is None:
        st.caption("Available after Gate 1 approval.")
        return

    st.caption(
        f"Version {artifact.version} · "
        f"{'TEACHER APPROVED' if artifact.status == 'approved' else 'AI DRAFT — NOT YET APPROVED'}"
    )
    for plan in artifact.draft.plans:
        with st.expander(f"{plan.group} · {plan.session_count} sessions"):
            st.markdown(
                "**Targets:** "
                + (", ".join(skill.replace("_", " ") for skill in plan.target_skills)
                   or "No active targets")
            )
            st.markdown("**Teaching strategies**")
            for strategy in plan.strategies:
                st.write(f"• {strategy}")
            st.markdown("**Success criteria**")
            for criterion in plan.success_criteria:
                st.write(f"• {criterion}")

    approved = service.approvals_by_gate()["plans"]
    st.write(_approval_status(2, approved))
    if service.state is WorkflowState.PLAN_PROPOSED:
        comment = st.text_input(
            "Optional plan-review note", key="plans_comment", max_chars=240
        )
        _action(
            "Approve remediation plan · Gate 2",
            lambda: service.approve_plans(comment=comment),
            action=DemoAction.APPROVE_PLANS,
            key="approve_plans",
            help_text="Recording your approval…",
        )


def _render_exercises(service: TeacherWorkflowService) -> None:
    st.subheader("4 · Strands-assisted targeted exercises · Gate 3")
    st.caption("Drafted only from the teacher-approved remediation plan.")
    if service.state is WorkflowState.PLAN_APPROVED:
        st.write("The approved plan can now be turned into targeted practice.")
        _action(
            "Generate targeted exercises",
            service.generate_exercises,
            action=DemoAction.GENERATE_EXERCISES,
            key="generate_exercises",
            help_text="The bounded offline Strands agent is drafting from the approved plan…",
        )
        return

    artifact = service.exercises()
    if artifact is None:
        st.caption("Available after Gate 2 approval.")
        return

    total_items = sum(len(exercise_set.items) for exercise_set in artifact.draft.sets)
    st.caption(
        f"{total_items} exercises · "
        f"{'TEACHER APPROVED' if artifact.status == 'approved' else 'AI DRAFT — NOT YET APPROVED'}"
    )
    for exercise_set in artifact.draft.sets:
        with st.expander(f"{exercise_set.group} · {len(exercise_set.items)} items"):
            if not exercise_set.items:
                st.write("No exercises needed for this empty group.")
            for index, item in enumerate(exercise_set.items, start=1):
                st.markdown(f"**{index}.** {item.prompt}")
                st.caption(
                    f"{item.skill.replace('_', ' ')} · {item.difficulty} · "
                    f"Answer: {item.expected_answer}"
                )

    approved = service.approvals_by_gate()["exercises"]
    st.write(_approval_status(3, approved))
    if service.state is WorkflowState.EXERCISES_PROPOSED:
        comment = st.text_input(
            "Optional exercise-review note", key="exercises_comment", max_chars=240
        )
        _action(
            "Approve exercises · Gate 3",
            lambda: service.approve_exercises(comment=comment),
            action=DemoAction.APPROVE_EXERCISES,
            key="approve_exercises",
            help_text="Recording your approval…",
        )


def _render_report(service: TeacherWorkflowService) -> None:
    st.subheader("5 · Approved teacher report")
    if service.state is WorkflowState.EXERCISES_APPROVED:
        st.write("All three teacher approvals are recorded. The report is ready to assemble.")
        _action(
            "Generate teacher report",
            service.generate_report,
            action=DemoAction.GENERATE_REPORT,
            key="generate_report",
            help_text="Assembling the approved evidence and drafts…",
        )
        return

    report = service.report()
    if report is None:
        st.caption("Available after Gate 3 approval.")
        return

    st.success("Workflow complete · REPORT_READY")
    st.download_button(
        "Download teacher report (.md)",
        data=report,
        file_name=f"GapBridge-{service.run_id}-teacher-report.md",
        mime="text/markdown",
        width="stretch",
    )
    with st.expander("View full teacher report"):
        st.markdown(report)


def _render_demo_summary(service: TeacherWorkflowService) -> None:
    summary = service.demo_summary()
    with st.expander(
        "Demo summary",
        expanded=service.state is WorkflowState.REPORT_READY,
    ):
        learners, plans, exercises, gates = st.columns(4)
        learners.metric("Learners analyzed", summary.learners_analyzed)
        plans.metric("Plans drafted", summary.plans_drafted)
        exercises.metric("Exercise items", summary.exercise_items_generated)
        gates.metric("Approval gates", f"{summary.approval_gates_completed}/3")
        st.markdown(
            "**Groups:** "
            + " · ".join(
                f"{group} {count}" for group, count in summary.group_counts.items()
            )
        )
        st.markdown(
            "**Priority gaps:** "
            + (
                ", ".join(item.replace("_", " ").title() for item in summary.priority_gaps)
                or "None detected"
            )
        )
        st.markdown(f"**Workflow state:** `{summary.workflow_state}`")


def _render_provenance(service: TeacherWorkflowService) -> None:
    plans = service.plans()
    exercises = service.exercises()
    if plans is None and exercises is None:
        return
    with st.expander("AI provenance and safeguards"):
        st.markdown(f"**Current AI mode:** `{AI_MODE}`")
        for label, artifact in (("Plan", plans), ("Exercises", exercises)):
            if artifact is None:
                continue
            provenance = artifact.provenance
            st.markdown(f"**{label}**")
            st.write(
                f"Provider: {provenance.provider} · Model: {provenance.model_id} · "
                f"Validation: {provenance.validation_status}"
            )
            st.caption(
                f"Agent: {provenance.agent_name} · Strands SDK: "
                f"{provenance.sdk_version} · Run: {provenance.run_id}"
            )
        st.caption(
            "Synthetic data only. No AWS, Bedrock, external LLM, credentials, "
            "or network calls are used by this demo mode."
        )


def main() -> None:
    st.set_page_config(
        page_title="GapBridge · Teacher remediation workflow",
        page_icon="🌉",
        layout="wide",
    )
    st.markdown(
        """
        <style>
        .block-container {max-width: 1080px; padding-top: 2rem; padding-bottom: 4rem;}
        [data-testid="stMetric"] {background: #f7f9fc; border: 1px solid #e5eaf2;
            padding: 1rem; border-radius: .75rem;}
        h2 {margin-top: 2.4rem !important;}
        </style>
        """,
        unsafe_allow_html=True,
    )

    service = _load_service()
    if service is None:
        st.title("GapBridge")
        st.subheader("Every learner gets the right next step — with the teacher in control.")
        st.write(
            "Explore a Grade 5 Mathematics — Fractions assessment for 24 synthetic "
            "learners, review deterministic groups, and approve Strands-assisted "
            "remediation content at three clear gates."
        )
        st.info(
            f"Demo mode: {AI_MODE}. This local experience makes no external model calls."
        )
        _action(
            "Start fresh demo run",
            _start_fresh_run,
            action=DemoAction.START,
            key="fresh_welcome",
            help_text="Creating a clean isolated run…",
        )
        st.caption("Fresh runs preserve every previous run and audit log.")
        return

    with st.sidebar:
        st.header("Demo run")
        st.caption(service.run_id)
        st.write(f"**State:** {service.state.value}")
        _action(
            "Start fresh run (keeps history)",
            _start_fresh_run,
            action=DemoAction.START,
            key="fresh_sidebar",
            help_text="Creating a clean isolated run…",
            button_type="secondary",
        )

    try:
        _render_header(service)
        _render_analysis(service)
        _render_groups(service)
        _render_plans(service)
        _render_exercises(service)
        _render_report(service)
        _render_demo_summary(service)
        _render_provenance(service)
    except Exception as exc:
        LOGGER.exception("Could not render GapBridge demo run")
        st.error(friendly_demo_error(DemoAction.RENDER, exc))
        st.info("Use ‘Start fresh run (keeps history)’ to continue without deleting this run.")


if __name__ == "__main__":
    main()
