# MVP_SCOPE — GapBridge

> Principle: one thin slice, demonstrable end-to-end, every step honest.
> If a feature does not serve the 8-stage workflow demo, it is not in the MVP.

---

## 1. MUST HAVE (MVP boundary)

| # | Capability | Notes |
|---|---|---|
| M1 | **Synthetic assessment input** | One committed Grade 5 Mathematics — Fractions CSV with 24 anonymous learners × 4 skills, scored 0–100. |
| M2 | **Assessment analysis** | Deterministic per-skill statistics: class mean, per-student mastery, distribution. Displayed as tables/summary. |
| M3 | **Learning-gap detection** | Rule-based thresholds (e.g., skill class-mastery < 60% → gap; student < 50% on a gapped skill → flagged learner). Each flag lists its evidence. |
| M4 | **Learner grouping** | Deterministic assignment into Mastered / Developing / Intensive Support from explicit score rules. **Per-learner rationale string required.** |
| M5 | **Remediation-plan proposal** | LLM-drafted plan per group: objective(s), strategy outline, 2–3 session sketch, success criteria. Clearly marked DRAFT. |
| M6 | **Exercise generation** | LLM-generated targeted exercises per group (e.g., 5 items each), aligned to the specific gaps of that group. Marked DRAFT. |
| M7 | **Teacher approval** | Three gates: groups, plan, and exercises. No artifact becomes approved and no report is generated without the required recorded decisions. |
| M8 | **Explainability** | Why each gap was flagged (numbers), why each student is in their group (rationale), provenance labels (`computed` vs `ai-generated`) on every artifact. |
| M9 | **Teacher report** | Single consolidated Markdown report: analysis summary, approved groups + rationales, approved plans, exercises appendix, audit trail of decisions. Exported to file. |

**MVP interface:** minimal — CLI-driven workflow with readable console/file output is acceptable; a thin UI only if time permits (see SHOULD/NICE).

## 2. SHOULD HAVE (if time allows, in priority order)

- S1 — **Teacher edits at gates:** move a student between groups / edit plan text before approving (not just yes/no).
- S2 — **Configurable thresholds** (gap %, group cut lines) in a config file.
- S3 — **Audit log file** (`audit_log.jsonl`): append-only record of proposals, edits, approvals, timestamps.
- S4 — **Re-assessment comparison mode:** load second CSV, show before/after mastery delta per skill and per student (closes the loop visually).
- S5 — **Unit tests** for all deterministic modules (stats, gap rules, grouping).

## 3. NICE TO HAVE (only after MUST+SHOULD are stable)

- N1 — Simple web UI (Streamlit-style) wrapping the same workflow for presentation polish.
- N2 — Printable HTML/PDF exercise packets.
- N3 — Item-level (per-question) analysis input format.
- N4 — Multiple classes/subjects in one run.
- N5 — Arabic/French output toggle (**explicitly post-hackathon**).

## 4. OUT OF SCOPE FOR MVP (future ideas only)

Parent/guardian messaging · attendance · billing/payments · timetabling/scheduling · mobile/Android app · full school-management features · LMS integration (Google Classroom etc.) · autograding of student work · real student data of any kind · multi-school/multi-tenant anything · production deployment/cloud hosting · fine-tuning models.

## 5. One complete end-to-end demo scenario (the script we will submit)

> **Grade 5 Mathematics — Fractions** — 24 synthetic learners and 4 skills:
> identifying fractions · comparing fractions · equivalent fractions · adding fractions.
>
> The committed dataset produces three explainable support groups and visible class gaps while using anonymous IDs `S001`–`S024` only.
>
> 1. Teacher starts a fresh local Streamlit demo run using the bundled dataset.
> 2. GapBridge computes class evidence and learner rationales deterministically.
> 3. System proposes Mastered 8 / Developing 9 / Intensive Support 7; AI cannot change membership.
> 4. Teacher reviews the rationales and approves groups. *(Gate 1 recorded)*
> 5. The offline Strands agent drafts one remediation plan for each group from approved evidence. *(Gate 2 recorded after review)*
> 6. The offline Strands agent drafts 16 targeted exercise items from the approved plan. *(Gate 3 recorded after review)*
> 7. GapBridge deterministically assembles and offers the approved Markdown teacher report for download.
> 8. Presenter highlights provenance, all three approval records, and final workflow state `REPORT_READY`.

## 6. MVP success criteria (definition of done)

1. A fresh run on the committed sample CSV completes all stages end-to-end without errors.
2. All three approval gates function; no path exists to a "final" artifact without an approval record.
3. Every group assignment includes a rationale; every gap flag includes numeric evidence.
4. Statistics are unit-tested and match hand-computed values on a fixture dataset.
5. Every artifact carries correct provenance labeling (`computed` / `ai-generated`).
6. Demo completes live in ≤15 minutes including teacher interactions; fallback artifacts pre-generated.
7. Runs fully offline if using local model provider; no AWS calls required for the MVP demo.
8. No real personal data anywhere in repo; README states synthetic-data-only policy.

## 7. Minimum data model concepts

| Concept | Fields (indicative) |
|---|---|
| **Learner** | `learner_id` (pseudonymous, e.g., `S07`), display alias (fake name) — nothing else |
| **Skill** | `skill_id`, `name`, `description` |
| **Assessment** | `assessment_id`, `title`, `skill_ids[]` |
| **ScoreRecord** | `learner_id`, `skill_id`, `score` (0–100), optional `assessment_id` |
| **GapFlag** | `skill_id`, `metric`, `threshold`, `observed_value`, `flagged_learners[]`, `evidence` |
| **SupportGroup** | `group_id`, `label` (Mastered/Developing/Intensive Support), `member_ids[]`, `membership_rationale{learner_id→text}`, `status` (proposed/approved) |
| **RemediationPlan** | `plan_id`, `group_id`, `objectives[]`, `strategies[]`, `session_sketch`, `success_criteria`, `content` (markdown), `status`, `provenance` |
| **ExerciseSet** | `set_id`, `group_id`, `items[]{prompt, answer, skill_id, difficulty}`, `status`, `provenance` |
| **ApprovalDecision** | `gate` (groups/plan/exercises), `action` (approved/edited/regenerated), `actor` ("teacher"), `timestamp`, `notes`, `diff?` |
| **AuditEvent** | append-only log entries referencing the above |
| **Report** | assembled markdown document + generation metadata |

Storage: files under `data/` and `artifacts/` (JSON/markdown) — format decision pending (Open Question Q4).

## 8. Deterministic vs AI-generated (hard rule)

| Component | Mode | Rationale |
|---|---|---|
| CSV parsing/validation | **Deterministic** | Correctness non-negotiable |
| Per-skill/per-student statistics | **Deterministic** | Must be reproducible & testable |
| Gap detection flags | **Deterministic** (rules/thresholds) | Auditable evidence chain |
| Group membership assignment | **Deterministic** | Fairness + explainability; LLM never moves students |
| Group labels/descriptions | Hybrid: deterministic membership, **LLM** writes plain-language description | Readability |
| Gap narrative for teacher | **AI-generated** (grounded in computed numbers, prompted with exact stats) | Communication quality |
| Remediation plan content | **AI-generated** draft + template skeleton | Pedagogical creativity |
| Exercise items | **AI-generated** draft, constrained by skill/difficulty metadata | Content generation |
| Approval recording, audit log | **Deterministic** | Integrity |
| Report assembly | **Deterministic** assembly of approved artifacts (+ light **LLM** executive summary, clearly labeled) | Trustworthy document |

**Rule of thumb:** *anything a judge could recompute must be computed; anything requiring professional judgment is drafted by AI and approved by the teacher.*
