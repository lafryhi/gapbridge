# GapBridge Build Journey Log

This is the official append-only development journal. Historical entries below
are reconstructed from verified project reports; dates were not supplied unless
shown explicitly. Unverified details are intentionally omitted.

## Reconstructed history from verified reports

### Registration and rules review

- The Agents for Humans hackathon requirements and judging priorities were reviewed.
- GapBridge was aligned to the Professional Agents track and a teacher-controlled end-to-end workflow.

### AWS account setup

- A new AWS account was created for the project.
- No project AWS infrastructure or credentials were created by GapBridge implementation work.

### AWS Builder ID

- AWS Builder ID setup was recorded in the verified project history.
- No additional account details were included in the verified reports.

### $50 AWS credit request

- Submission of the $50 AWS credit request was recorded in the verified project history.
- Approval or redemption status was not documented and is not inferred here.

### Bedrock authorization blocker

- A single approved Console invocation used Amazon Nova Lite in `us-east-1`.
- Exact result: `ValidationException: Operation not allowed`.
- No bypass, additional model/region testing, IAM change, or credential creation followed.

### Strands local setup

- `strands-agents==1.52.0` and `strands-agents-tools==0.8.6` were installed and import-verified locally.
- The project uses one bounded content orchestrator with an offline scripted model for testing and demos.

### Sprint 1

- Implemented the deterministic Grade 5 Fractions assessment core, gap detection, grouping, persisted state, and append-only audit log.
- Verified result: **52 tests passed**.

### Sprint 2

- Added deterministic plans, teacher approval/revision handling, exercises, report generation, and full workflow persistence.
- Verified result: **83 tests passed**.

### Sprint 3

- Added the deterministic outer controller, one bounded Strands orchestrator, three persisted approval gates, run isolation, strict schemas, safe tools, provenance, offline scripted mode, and deterministic fallback.
- Verified result: **108 tests passed**.

### Sprint 4A

- Bedrock remained blocked with `ValidationException: Operation not allowed` for Amazon Nova Lite in `us-east-1`.
- Real-provider implementation stopped; the local architecture remained unchanged.

### Sprint 4B

- Added the local Streamlit teacher experience, refresh-safe run reopening, report viewing/download, and service-level tests.
- Verified result: **114 tests passed**.

## Current entries

### Sprint 5 — 2026-08-22

- Started demo hardening and presentation-readiness work.
- Scope is limited to local preflight, safe fresh runs, teacher-friendly errors, UI clarity/accessibility, canonical scenario consistency, demo metrics, tests, and documentation.
- AWS, Bedrock, external LLMs, deployment, AgentCore, GitHub publishing, architecture-diagram work, and final submission work remain out of scope.

### Sprint 5 completion — 2026-08-22

- Added an eight-check, network-free demo preflight and a safe fresh-run path that preserves historical runs and audit logs.
- Added teacher-friendly failure mapping, explicit ownership and gate status, canonical scenario cleanup, accessibility-focused labels, and a factual final demo summary.
- Screenshot-based local UI review confirmed the fresh-run, Gate 1, completed-report, metrics, and recovery states without browser console errors.
- Verified preflight result: **8/8 checks passed**.
- Verified regression result: **126 tests passed in 8.66s**.

### Sprint 6 — 2026-08-22

- Added a 4-minute-40-second rehearsal flow, local presenter recovery drills, an offline readiness checklist, and a five-minute presenter-script outline without adding product features.
- Completed a focused local accessibility spot check with saved evidence for the completed workflow, zoom-equivalent reflow, keyboard focus, report metrics, and provenance. The large workflow-state card truncates at reduced effective widths; the full state remains text-visible elsewhere and actual-browser zoom plus screen-reader traversal remain recording-day checks.
- Completed a read-only submission audit. The license, final architecture diagram, public GitHub repository, public demo video, live demo link, and `builder.aws.com` article are missing; the existing README is not yet final.
- Verified preflight result: **8/8 checks passed** with no network, AWS, Bedrock, or external model calls.
- Verified regression result: **126 tests passed in 6.96s**.

### Sprint 7 — 2026-08-22

- Selected the standard MIT License with copyright attribution to GapBridge contributors and added the public `LICENSE` file.
- Completed a local publication safety review covering credential values, account identifiers, secrets, emails, personal/local paths, session identifiers, cloud configuration, runtime artifacts, and dataset privacy. No publishable secret or personal value was detected; the dataset remains synthetic-only.
- Expanded `.gitignore` for Streamlit secrets, credential/key formats, coverage/build output, runtime data, and internal planning files that should remain local.
- Added the verified Mermaid architecture documentation showing deterministic authority, one bounded Strands content-orchestrator role, three teacher gates, run-scoped persistence, audit records, provenance, and truthful `STRANDS_OFFLINE_TEST` provider status.
- Replaced the sprint-oriented README with the final judge-facing package: problem, end-to-end agent workflow, Strands tools, authority boundaries, local setup, tests, privacy, limitations, Bedrock blocker, architecture link, and MIT license.
- Verified clean-clone documentation statically; preflight passed **8/8**, and the offline terminal demo reached `REPORT_READY` with no external model or AWS calls.
- Marked the reviewed local package **PUBLICATION_READY = YES**. No repository was created and nothing was published.
- Verified regression result: **126 tests passed in 3.53s**.

### Sprint 8A — 2026-08-23

- Initialized a local Git repository on the `main` branch without configuring a remote.
- Reviewed the exact publication set: source, tests, synthetic data, judge-facing documentation, architecture, license, build journal, and offline demo/verification scripts are included; runtime data, environments, caches, secrets, credentials, build output, browser/session artifacts, and internal planning files remain ignored.
- Completed the final intended-tracked-content security and privacy review before staging; no secret value, account identifier, unnecessary personal value, local path, session identifier, or real student information was approved for the baseline.
- Verified README links, Mermaid structure, architecture accuracy, MIT license reference, provider disclosure, and canonical Grade 5 Fractions scenario consistency.
- Verified preflight result: **8/8 checks passed** with no network, AWS, Bedrock, or external model calls.
- Verified regression result: **126 tests passed in 6.99s**.
- Verified the offline CLI demo reached `REPORT_READY` with all three approval gates and no external model or AWS calls.
- Prepared the reviewed file set as the initial local publication baseline commit. No remote, push, deployment, or publication was performed.
- Replaced the final tracked references to the ignored historical architecture plan with `docs/architecture.md`, removing a clean-clone documentation/test dependency. Final regression result after this correction: **126 tests passed in 2.03s**.

### Sprint 8B — 2026-08-23

- Created the public GitHub repository at `https://github.com/lafryhi/gapbridge` with `main` as the default branch and pushed the reviewed local baseline without rewriting history.
- Retained the neutral Git identity `GapBridge Contributors <gapbridge@example.invalid>`; no history rewrite was performed for attribution.
- Verified the public README presentation, MIT License, architecture document, source, tests, requirements, and synthetic dataset from GitHub and a fresh public clone.
- GitHub initially reported `Could not find a suitable point for the given distance` for the Mermaid layout. Removed only three dashed-edge labels, committed the syntax-only correction normally, and visually verified the diagram rendered successfully afterward.
- Rechecked the 52-file public tree and fresh clone for secret-token patterns, personal emails, absolute local paths, runtime/environment data, private planning documents, and real student information; no publishable issue was found.
- Verified preflight result: **8/8 checks passed** with no AWS, Bedrock, or external model calls.
- Verified regression result: **126 tests passed in 3.64s**.
- Last verified publication-content commit before this append: `2e7d0a8837c8ae77cbc1803c796f829fb99b0e7b`. The subsequent journal-only commit is recorded by Git history and in the Sprint 8B report.

### Sprint 9 — 2026-08-23

- Prepared a final 4-minute-42-second demo-video strategy, shot sequence, and 559-word English narration focused on the teacher problem, live workflow, responsible architecture, and potential impact.
- Made the Strands Agents SDK role explicit: one bounded content agent, eight safe tools, strict structured output, deterministic revalidation, and three human approval gates.
- Prepared an accurate provider disclosure for `STRANDS_OFFLINE_TEST` and the future Bedrock provider boundary pending AWS account authorization, without attributing current output to Bedrock.
- Added recording-day privacy and quality checks, concise overlay captions, proposed public video metadata, and a fallback based only on persisted real runs, the generated report, and the public architecture page.
- Kept the detailed production blueprint in the existing ignored local rehearsal playbook. No product logic changed, and no video was recorded, uploaded, or published.
- Verified recording readiness with the local preflight at **8/8** and the canonical project test directory at **126 tests passed in 2.04s**; no AWS, Bedrock, or external model calls were made.
