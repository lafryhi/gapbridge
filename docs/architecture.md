# GapBridge Architecture

This document describes the architecture implemented in the current local
hackathon demo. It distinguishes deterministic authority, AI-assisted drafting,
and teacher decisions explicitly.

```mermaid
flowchart TB
    TEACHER["Teacher<br/>HUMAN DECISION"]
    UI["Streamlit teacher UI<br/>streamlit_app.py"]
    DATA[("Synthetic Grade 5 Fractions dataset<br/>24 anonymous learners")]

    subgraph DET["DETERMINISTIC — authoritative application boundary"]
        CTRL["Workflow controller<br/>state transitions · gate enforcement · controller validation"]
        ASSESS["Assessment loading and validation"]
        GAPS["Score analysis and gap detection"]
        GROUPS["Deterministic grouping and learner explanations"]
        REPORT["Deterministic report assembly"]
    end

    GATE1{{"Gate 1<br/>Teacher approves groups<br/>HUMAN DECISION"}}

    subgraph AI["AI-ASSISTED — one bounded Strands content-orchestrator role"]
        TOOLS["Eight run-scoped safe tools<br/>read-only evidence retrieval + pure validation"]
        PLAN["Remediation-plan drafting<br/>strict PlanDraftBundle"]
        EXERCISES["Differentiated exercise drafting<br/>strict ExerciseDraftBundle"]
        MODE["Current provider mode<br/>STRANDS_OFFLINE_TEST"]
    end

    GATE2{{"Gate 2<br/>Teacher approves remediation plan<br/>HUMAN DECISION"}}
    GATE3{{"Gate 3<br/>Teacher approves exercises<br/>HUMAN DECISION"}}
    READY["Teacher report<br/>REPORT_READY"]

    subgraph STORE["RUN-SCOPED LOCAL PERSISTENCE"]
        RUNS[("Isolated run directory and artifacts")]
        APPROVALS[("Append-only approval records")]
        AUDIT[("Append-only audit log")]
        PROVENANCE[("Artifact provenance<br/>provider · model · agent · SDK · hash · validation")]
    end

    TEACHER --> UI
    UI --> CTRL
    DATA --> ASSESS
    CTRL --> ASSESS --> GAPS --> GROUPS --> GATE1
    GATE1 --> CTRL
    CTRL --> PLAN
    TOOLS <--> PLAN
    MODE -.-> PLAN
    PLAN --> CTRL
    CTRL --> GATE2
    GATE2 --> CTRL
    CTRL --> EXERCISES
    TOOLS <--> EXERCISES
    MODE -.-> EXERCISES
    EXERCISES --> CTRL
    CTRL --> GATE3
    GATE3 --> CTRL
    CTRL --> REPORT --> READY
    READY --> TEACHER

    CTRL -.-> RUNS
    GATE1 -.-> APPROVALS
    GATE2 -.-> APPROVALS
    GATE3 -.-> APPROVALS
    CTRL -.-> AUDIT
    PLAN -.-> PROVENANCE
    EXERCISES -.-> PROVENANCE

    classDef human fill:#fff4cc,stroke:#8a6700,color:#241a00;
    classDef deterministic fill:#e8f1ff,stroke:#245c9f,color:#071b33;
    classDef assisted fill:#f0eaff,stroke:#6541a5,color:#1d1038;
    classDef data fill:#edf7ef,stroke:#327a43,color:#0d2914;
    class TEACHER,GATE1,GATE2,GATE3 human;
    class CTRL,ASSESS,GAPS,GROUPS,REPORT deterministic;
    class TOOLS,PLAN,EXERCISES,MODE assisted;
    class DATA,RUNS,APPROVALS,AUDIT,PROVENANCE,READY data;
```

Color is supplementary: every decision boundary is also labeled
**DETERMINISTIC**, **AI-ASSISTED**, or **HUMAN DECISION** in text.

## Implemented component map

| Responsibility | Implemented by |
|---|---|
| Teacher interface and refresh-safe run reopening | `streamlit_app.py`, `sprint4b_service.py` |
| Assessment validation and score analysis | `assessment.py`, `gaps.py` |
| Deterministic grouping and explanations | `grouping.py`, `config.py` |
| Authoritative workflow and three gates | `sprint3_workflow.py`, `state.py` |
| One bounded Strands orchestration role | `strands_orchestrator.py` |
| Safe evidence and validation tools | `sprint3_tools.py` |
| Strict structured-output contracts | `sprint3_schemas.py` |
| Run isolation, approvals, hashes, and local persistence | `sprint3_storage.py` |
| Deterministic report assembly | `sprint3_report.py` |

## Authority boundaries

- **Deterministic:** assessment validation, scoring, learning gaps, group
  membership, target constraints, state transitions, approval enforcement,
  structured-output revalidation, artifact persistence, and report assembly.
- **AI-assisted:** remediation-plan wording and differentiated exercise drafting
  within approved deterministic constraints. Teacher revision feedback may
  guide later draft wording.
- **Human decision:** approval of groups, remediation plans, and exercises.

The orchestrator can retrieve evidence or run pure validation through its eight
allowlisted tools. It cannot change groups, advance workflow state, approve an
artifact, write files, or assemble the final report.

## Provider status

The current demo mode is `STRANDS_OFFLINE_TEST`. A deterministic scripted local
model drives the real Strands Agent tool loop and structured-output path, so
the demo remains repeatable without an external model call.

The provider interfaces can accept a future Bedrock-backed implementation, but
Bedrock is not operational in this project. The approved availability test for
Amazon Nova Lite in `us-east-1` returned:

```text
ValidationException: Operation not allowed
```

Bedrock is therefore **provider-ready / pending AWS account authorization**.
AgentCore is not implemented or represented in this architecture.
