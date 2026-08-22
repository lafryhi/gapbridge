# PROJECT_BRIEF — GapBridge (working name)

> Status: Sprint 5 — local demo hardening; deterministic workflow and offline Strands UI implemented.
> Hackathon: Devpost "Agents for Humans" · Track: **Professional Agents**

---

## 1. Project working name

**GapBridge** *(provisional — final name decided before submission)*

Tagline: *From raw assessment scores to ready-to-teach remediation — with the teacher in charge.*

## 2. One-sentence pitch

GapBridge is an AI agent that turns classroom assessment results into explained learning-gap analysis, fair support groups, differentiated exercises, and follow-up reports — drafting everything, deciding nothing, because every pedagogical decision stays with the teacher.

## 3. Problem statement

After every test or quiz, teachers must manually: analyze class performance across skills, identify which learning gaps matter most, decide which students need which kind of support, group students sensibly, invent differentiated remediation activities, produce exercises at multiple difficulty levels, and write follow-up documentation. For a single class assessment this routinely consumes hours of unpaid evening time, and under time pressure the remediation that reaches struggling students is often generic — the same worksheet for everyone — rather than targeted to each diagnosed gap.

## 4. Target user

Primary: **classroom teachers** (initially grades 4–9, one subject per assessment) who give regular skills-based assessments and are responsible for remediation planning.
Secondary (future): instructional coaches, special-education support staff, school leaders reviewing intervention coverage.

## 5. Why the problem matters

- **Time:** remediation planning is repetitive analytical work done per class, per assessment, all year — high-frequency, high-effort, low-creativity work.
- **Equity:** students in large classes receive less individualized diagnosis; gaps compound silently across units and years.
- **Quality:** differentiation is pedagogically valuable but practically expensive; the canonical demo makes this concrete with 24 learners across four fraction skills.
- **Burnout:** administrative/analytical workload is a leading driver of teacher attrition. Any tool that cuts planning from hours to minutes returns time to actual teaching.

## 6. Why an AI agent is appropriate

This is a **multi-step analytical pipeline with judgment calls at specific points**: ingest data → compute statistics → detect gaps → partition learners → design interventions → produce materials → document. An agent fits because:

1. The steps form a coherent goal-driven workflow, not one isolated transformation.
2. Some steps need **reasoning over structured evidence** (interpreting score patterns, choosing teaching strategies, writing pedagogically sound exercises) — exactly where LLMs excel.
3. Other steps need **deterministic computation** (averages, thresholds, grouping rules) — the agent architecture lets us combine both reliably.
4. The output artifacts (plans, exercises, reports) must be **coherent across steps**, which an agent maintaining shared state does better than disconnected scripts.

## 7. Why this is not just a chatbot

| Chatbot | GapBridge |
|---|---|
| Answers questions reactively | Executes a defined 8-stage workflow with explicit state transitions |
| One prompt in, one answer out | Produces a set of interlinked artifacts (gap analysis → groups → plan → exercises → report) |
| No memory of process | Maintains auditable state; every artifact has provenance and can be revisited/approved/rejected |
| User re-prompts to iterate | Built-in review gates: approve / edit / regenerate at defined checkpoints |
| No guarantees about computation | All statistics and group membership come from deterministic code, never from the LLM |

The teacher never "chats" with GapBridge to get value — they run a pipeline and make decisions at gates.

## 8. Professional Agents track fit

The Professional Agents track targets agents that do real professional work. GapBridge qualifies because it:

- Serves a **defined profession** (teaching) with its real artifacts (remediation plans, differentiated worksheets, intervention reports).
- Performs **autonomous multi-step work** between human touchpoints — not assisted typing.
- Embeds **professional accountability**: the licensed professional (teacher) approves; the system explains and records.
- Is **measurably time-saving**, which we will demonstrate with a timed end-to-end scenario on synthetic data.

## 9. User journey (MVP)

1. **Import** — Teacher loads a synthetic assessment file (CSV: one row per student × skill scores).
2. **Analyze** — GapBridge computes per-skill mastery statistics and flags significant gaps, showing the numbers behind each flag.
3. **Group** — System deterministically assigns Mastered / Developing / Intensive Support with a plain-language reason for every learner.
4. **Review groups** — Teacher inspects and approves the computed memberships; AI cannot move learners. *(Gate 1)*
5. **Plan** — Agent drafts a remediation plan per group: objectives, strategies, session outline, success criteria.
6. **Approve plan** — Teacher edits/approves each group's plan. *(Gate 2)*
7. **Exercises** — Agent generates targeted exercises per group, aligned to the flagged gaps and group level.
8. **Finalize** — Teacher reviews exercises, triggers the consolidated teacher report (analysis + decisions + rationale + next steps). *(Gate 3)*
9. *(Post-MVP)* **Re-assess** — After reteaching, new results are compared against baseline; the plan updates with progress deltas.

## 10. Human-in-the-loop principle

- The agent **proposes**; the teacher **disposes**. No artifact becomes "final" without an explicit approval action.
- Three hard gates: group membership, remediation plan, final report/exercises.
- Every proposal carries an **explanation** (why this gap was flagged; why this student is in this group).
- The teacher explicitly approves each proposal; no AI draft advances without a persisted decision.
- The agent never communicates with students or parents directly, ever.

## 11. Privacy & safety principles

- **Synthetic data only** during the hackathon: generated, clearly-fake student records (IDs like `S07`, invented names).
- **Data minimization:** no real names, no birthdates, no contact details, no free-text behavioral notes; only pseudonymous IDs + scores.
- **Local-first:** analysis runs locally; nothing is persisted outside the project folder; no cloud storage in MVP.
- **No sensitive inference:** the agent diagnoses *skill gaps*, never labels students by ability, disability, or behavior.
- **Transparency:** every AI-generated item is labeled as such; deterministic outputs are labeled as computed.
- **Teacher authority:** the system explicitly frames output as drafts for professional review.

## 12. Measurable impact hypotheses (to demonstrate in demo/submission)

| # | Hypothesis | How measured (on synthetic-data demo) |
|---|---|---|
| H1 | Planning time drops from ~2–3 h to <15 min per assessment | Timed scripted task vs. documented manual baseline (cited estimate) |
| H2 | 100% of flagged gaps map to ≥1 targeted exercise | Automated coverage check in the report |
| H3 | Every group assignment has a stated rationale | Report audit: 0 unexplained assignments |
| H4 | Teacher edits are low-effort (few overrides needed) | Count of manual moves/edits in demo run |
| H5 | Re-assessment loop shows measurable progress delta | Before/after mastery comparison in report (post-MVP path) |

## 13. Potential competitive differentiators

1. **Deterministic core, generative shell** — numbers and grouping are computed, not hallucinated; judges can trust the analytics.
2. **Explainability as a first-class feature** — per-student assignment reasons, per-gap evidence, full audit trail.
3. **Real HITL gates** — a genuine approval workflow with recorded decisions, not a "human watches" demo.
4. **Closed-loop design** — built for the assess→remediate→re-assess cycle, not one-shot generation.
5. **Honest AI labeling** — provenance metadata distinguishing computed vs. generated content.
6. **Future multilingual reach** — Arabic/French roadmap for under-served education markets (mentioned, not in MVP).

## 14. Risks and assumptions

**Risks**
- AWS Bedrock account verification may remain blocked near submission → mitigate with provider abstraction + local model fallback (see ARCHITECTURE_PLAN).
- LLM-generated exercises may be pedagogically weak or contain errors → mitigate with templates, constraints, teacher gate, and demo framing ("drafts").
- Scope creep into a "school platform" → mitigated by strict MVP scope doc.
- Live-demo failure → mitigated with pre-baked run artifacts and scripted demo.
- Time pressure of hackathon → MVP deliberately thin.

**Assumptions**
- Judges value responsible-AI/HITL design (aligned with "Agents for Humans" theme).
- A CSV export (or equivalent tabular results) is a realistic starting artifact for teachers.
- Synthetic data is acceptable for demo per hackathon norms (privacy-safe).
- English-only output is acceptable for this submission.

## 15. Open questions to resolve before coding

1. **Q1 — Demo interface:** CLI-only, or minimal web UI (e.g., Streamlit) for presentation value?
2. **Q2 — Subject/topic of the synthetic dataset:** which grade, subject, and skill breakdown makes the demo most legible to non-educator judges?
3. **Q3 — Grouping method:** pure threshold rules, or rules + optional statistical clustering? How much may the LLM adjust membership (default: none)?
4. **Q4 — Persistence:** JSON state files vs SQLite for workflow state and audit log?
5. **Q5 — Model provider for dev/demo:** local Ollama vs Bedrock (once account unblocked) vs both behind config — and which model IDs.
6. **Q6 — Exercise format:** Markdown worksheets? Printable HTML? Per-group packet structure?
7. **Q7 — Submission mechanics:** exact Devpost dates, required license, video length, and whether AWS usage is required for eligibility (must confirm all code is authored within the submission window).

---
*Next documents: [MVP_SCOPE.md](MVP_SCOPE.md) · [Verified architecture](docs/architecture.md)*
