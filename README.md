# GapBridge

**GapBridge turns synthetic assessment evidence into explained learner groups,
teacher-reviewed remediation plans, targeted exercises, and a final report—while
keeping every pedagogical decision under teacher control.**

GapBridge is an entry for the **Agents for Humans Hackathon**, Professional
Agents track.

## The Problem

Teachers often have assessment results but not enough time to turn every score
into differentiated, explainable remediation work. Reviewing gaps, grouping
learners, planning instruction, preparing exercises, and documenting the result
is cognitively expensive—especially when a class contains several levels of
readiness.

## What GapBridge Does

GapBridge runs a complete local workflow:

1. Loads a bundled synthetic Grade 5 Fractions assessment.
2. Validates scores and computes learner and class evidence.
3. Detects learning gaps and assigns deterministic learner groups with reasons.
4. Stops for the teacher to approve the groups.
5. Uses one bounded Strands content-orchestrator role to draft remediation
   plans from approved, read-only evidence.
6. Stops for the teacher to approve the plan.
7. Uses the same bounded orchestration role to draft differentiated exercises
   from the approved plan.
8. Stops for the teacher to approve the exercises.
9. Deterministically assembles a teacher report and reaches `REPORT_READY`.

Each run is isolated under a unique run ID. Workflow state, approvals, audit
events, artifacts, hashes, and provenance are persisted locally.

## Why It Is an Agent

GapBridge is not a chat interface around a prompt. A real `strands.Agent`:

- retrieves bounded assessment and workflow evidence through registered tools;
- reasons only over controller-approved educational context;
- drafts remediation plans and differentiated exercises;
- invokes pure validation tools before returning structured artifacts;
- returns strict Pydantic structured output; and
- stops at deterministic workflow and human-approval boundaries.

The agent cannot calculate official scores, alter group membership, advance the
workflow, approve its own output, write project files, or assemble the final
report. Those responsibilities stay outside the model boundary.

## Human-in-the-Loop Safety

GapBridge has three explicit, persisted approval gates:

1. **Gate 1 — Groups:** the teacher approves deterministic group membership.
2. **Gate 2 — Remediation plan:** the teacher approves the agent-drafted plan.
3. **Gate 3 — Exercises:** the teacher approves the agent-drafted exercise sets.

Later steps are unavailable until the required approval record exists. Every
approval is bound to a run ID, artifact type, version, and artifact hash.

## Architecture

The verified implementation diagram and responsibility boundaries are in
[docs/architecture.md](docs/architecture.md).

At a high level, the Streamlit teacher interface calls a deterministic workflow
controller. That controller owns evidence, state, approvals, validation, and
persistence; the bounded Strands orchestrator drafts content between the three
teacher gates; deterministic code assembles the report.

## Canonical Demo Scenario

- **Subject:** Grade 5 Mathematics
- **Unit:** Fractions
- **Dataset:** 24 anonymous synthetic learners
- **Skills:** identifying fractions, comparing fractions, equivalent fractions,
  and adding fractions
- **Mastered:** 8 learners
- **Developing:** 9 learners
- **Intensive Support:** 7 learners

Group membership is reproducible from fixed thresholds. Each learner receives
an evidence-based explanation, and the agent cannot move learners between
groups.

## Strands Agents SDK

- `strands-agents==1.52.0`
- `strands-agents-tools==0.8.6`
- Agent name: `gapbridge-content-orchestrator`

One bounded orchestrator role uses eight run-scoped tools. The first six read
controller-owned evidence; the final two perform pure validation. None can
persist state or approve an artifact.

1. `get_workflow_status`
2. `get_class_evidence`
3. `get_group_profile`
4. `get_plan_constraints`
5. `get_teacher_revision_feedback`
6. `get_approved_plan`
7. `validate_plan_alignment`
8. `validate_exercise_set`

## Deterministic vs AI-Assisted Responsibilities

| Owner | Responsibilities |
|---|---|
| **Deterministic code** | Dataset validation, score calculation, gap detection, learner explanations, group membership, target constraints, workflow transitions, approval enforcement, controller-side schema and evidence validation, run isolation, persistence, audit logging, and report assembly |
| **Strands-assisted drafting** | Teacher-readable remediation-plan wording, differentiated exercise drafting, and plan revision wording guided by persisted teacher feedback |
| **Teacher** | Approve groups, approve the remediation plan, and approve exercises |

The current learner-analysis wording and group explanations are deterministic;
GapBridge does not use AI to reinterpret scores or group assignments.

## Current AI Provider Status

The current hackathon demo mode is:

```text
STRANDS_OFFLINE_TEST
```

`OfflineScriptedModel` provides deterministic local model responses while the
real Strands Agent executes the registered tool loop and
`structured_output_model` path. This makes orchestration visible, repeatable,
and fully testable without AWS, Bedrock, Ollama, or another external LLM.

The `PlanDraftProvider` and `ExerciseDraftProvider` interfaces support a future
Bedrock-backed implementation. Bedrock is **not** currently generating
GapBridge output. The single approved Amazon Nova Lite test in `us-east-1`
returned an AWS account-level authorization error:

```text
ValidationException: Operation not allowed
```

The current status is **provider-ready / pending AWS authorization**. No Bedrock
provider is implemented or active. AgentCore is not implemented, and nothing
is deployed.

## Run Locally

### Requirements

- Windows PowerShell
- Python 3.11 or newer
- A fresh clone of this repository

From the repository root:

```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Run the network-free preflight:

```powershell
.venv\Scripts\python.exe demo_preflight.py
```

Run the full test suite:

```powershell
.venv\Scripts\python.exe -m pytest tests -v
```

Launch the teacher UI:

```powershell
.venv\Scripts\python.exe -m streamlit run streamlit_app.py
```

Then choose **Start fresh demo run**. The page URL keeps the run ID so a refresh
reopens the same persisted workflow. **Start fresh run (keeps history)** creates
a clean run without deleting earlier runs or audit logs.

For a terminal-only orchestration demonstration:

```powershell
.venv\Scripts\python.exe run_sprint3_demo.py
```

All demo commands use the bundled synthetic dataset and current
`STRANDS_OFFLINE_TEST` provider mode.

## Tests

Verified baseline: **126 tests passing**.

The suite covers:

- dataset validation and score boundaries;
- learning-gap detection and deterministic grouping;
- state-machine transitions and all three approval gates;
- run isolation, persisted approvals, hashes, and audit events;
- strict structured-output validation and safe-tool behavior;
- the real offline Strands tool loop and deterministic fallback;
- report content and artifact persistence;
- Streamlit service behavior, refresh-safe resume, demo reset, friendly errors,
  preflight, metrics, and canonical-scenario consistency.

## Repository Structure

```text
GapBridge/
├── data/
│   └── synthetic_assessment.csv
├── docs/
│   └── architecture.md
├── src/gapbridge/
│   ├── assessment.py
│   ├── grouping.py
│   ├── sprint3_workflow.py
│   ├── sprint3_tools.py
│   ├── strands_orchestrator.py
│   └── sprint4b_service.py
├── tests/
├── demo_preflight.py
├── run_sprint3_demo.py
├── streamlit_app.py
├── requirements.txt
├── LICENSE
└── README.md
```

Generated state and artifacts live under `runtime/`, which is intentionally
git-ignored.

## Privacy

- The demo requires only synthetic educational data.
- Learners are anonymous IDs `S001`–`S024`; the dataset contains no names,
  emails, accounts, or contact details.
- No real student data is included or required.
- Runtime runs, audit logs, approvals, reports, caches, environments,
  credentials, `.env` files, and Streamlit secrets are excluded from future
  publication by `.gitignore`.

## Limitations

- The current Strands model is a deterministic scripted local test model, not a
  production foundation model.
- Production Bedrock invocation remains blocked by AWS account authorization.
- The Streamlit demo is a local, single-process application.
- AgentCore is not implemented.
- No production deployment or live public demo exists.
- The project has not been evaluated with real student data and should not be
  used for consequential educational decisions without additional validation,
  privacy review, and institutional approval.

## License

License: **MIT**. See [LICENSE](LICENSE).
