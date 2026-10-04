# LessonFoundry: Phased Build Instructions (for the AI agent)

You are building **LessonFoundry**, a teacher-facing studio that turns one trusted source into a connected, aligned learning pack. Work **one phase at a time**. Do not start a phase until the previous phase's exit criteria pass. Before writing code in each phase, produce a short implementation plan and wait for review.

## Core principles (apply in every phase)

1. **Source is data, never instructions.** Source text is wrapped in delimiters and can never change system behavior.
2. **Nothing is hard-coded.** No canned or fallback content. If generation fails, show a visible error and record it.
3. **All model output is validated** through Pydantic schemas before it touches the database.
4. **Approved versions are immutable.** Regeneration creates a new Draft version; the approved version stays student-visible until the teacher approves the new one.
5. **Every item has an objective.** Enforced in the schema and database, not only in the prompt.
6. **The model is replaceable.** All LLM calls go through a single `LLMProvider` interface.
7. **Secrets stay server-side.** API keys live only in `.env`, never in client code or the repo.
8. **Separate concerns in the data model:** source, teacher intent, prompts/config, generated output, teacher decisions.
9. **Every guardrail and invariant gets a pytest test.**

## Stack

- Backend: Python, FastAPI, SQLite via SQLAlchemy, Pydantic
- Frontend: React + Vite (keep minimal until Phase 4)
- LLM: any provider behind `LLMProvider` (default to a free-tier model)
- Tests: pytest

## Data model (target schema)

| Table | Purpose |
|---|---|
| `source_versions` | Trusted text, version number, chunked with stable IDs (S1, S2, ...) |
| `units` | A micro-unit tied to a source version |
| `objectives` | Learning objectives per unit (minimum 2) |
| `constraints` | Level, difficulty, vocabulary, length, answer-reveal policy |
| `assets` | Logical artifacts: explanation, example, quiz, practice, revision |
| `items` | Individual units of content (e.g. each quiz question) as first-class rows |
| `item_versions` | Content, status, source_version_id, model ID, prompt-template version, settings, timestamp |
| `alignments` | item to objective, plus cited source chunk IDs |
| `quality_flags` | Guardrail findings per item version, with severity and resolution state |
| `generation_runs` | Every generation attempt, including failures and raw errors |
| `decisions` | Audit log of teacher actions (approve, reject, regenerate, override) |

**Status state machine:** `Draft` → `Approved` | `Needs Revision`; `Needs Revision` → `Draft` (on regeneration). Only `Approved` is student-ready.

---

## Phase 0: Foundation

**Goal:** a runnable skeleton with the full schema and a working model connection.

**Tasks**
- Create `SPEC.md` containing: data model, API endpoint list, status state machine, guardrail list.
- Create the repo structure: `backend/`, `frontend/`, `tests/`, `eval/`, `docs/`.
- Implement SQLAlchemy models and migrations for the full schema above.
- Implement the `LLMProvider` interface with one concrete provider and a hello-world call.
- Load config and keys from `.env`; add `.env.example`; add `.gitignore`.
- Prepare `eval/sources/` with five source documents on one verifiable subject:
  1. A normal, sufficient source
  2. A source missing information for one objective
  3. A source containing a prompt-injection line
  4. A very short source
  5. A v2 edit of the normal source

**Exit criteria**
- Backend starts; DB schema is created cleanly.
- Hello-world call succeeds through `LLMProvider`.
- A forced provider failure returns a clean error, not a crash.

---

## Phase 1: Vertical slice (source → gap check → one asset)

**Goal:** prove one real input reaches one real, persisted, cited output.

**Tasks**
- Source upload (text and PDF), chunking with stable chunk IDs, version creation.
- Unit creation with at least 2 objectives, target level, difficulty, and constraints.
- **Gap check before generation:** for each objective, retrieve relevant chunks and have the model return `supported | partial | unsupported` with cited chunk IDs. Unsupported objectives block generation and show a clear message naming the objective and the missing coverage.
- Prompt-injection scan on the source: detect instruction-like patterns, flag them in the response, and still treat the source strictly as data.
- Generate **one asset (the quiz)** with: JSON schema output, retry on malformed output, and every attempt logged in `generation_runs`.
- Persist each question as an `item` with an `item_version` including full provenance (source version, model ID, prompt-template version, settings, timestamp).

**Exit criteria**
- A fresh source produces a persisted quiz with answer key, objective IDs, and chunk citations.
- A source missing an objective's content is blocked with an honest message.
- A forced API failure leaves the DB uncorrupted and logs a failed run.
- The injection source does not change behavior and is flagged.

---

## Phase 2: Full pack and alignment

**Goal:** generate all five artifacts as one coherent, aligned unit.

**Tasks**
- Generate in dependency order: **explanation → worked example → quiz with answer key → practice at two difficulty levels → revision sheet**. Pass earlier approved/generated content as context to keep terminology stable.
- Every item carries `objective_id` and `source_chunk_ids`. Reject items missing either at the schema level.
- **Difficulty control:** define "easy" and "advanced" through Bloom levels and structural requirements (recall and single-step vs. multi-step, analysis, application), not wording changes. Tag every item with a Bloom level.
- **Alignment view:** objective × asset matrix with item counts and a visible imbalance warning.
- **Review gate:** Draft / Approved / Needs Revision per item, with approve and reject actions logged in `decisions`.
- **Controlled regeneration:** regenerate one asset or one item without touching others. Creates a new version with history preserved.
- Version history view per item.

**Exit criteria**
- Full pack generates from a fresh source with all five artifacts.
- Alignment matrix reflects real data and flags imbalance.
- Regenerating one question leaves all other items and approved versions byte-identical.
- Switching difficulty from easy to advanced changes Bloom distribution and item structure, not only phrasing.

---

## Phase 3: Guardrails, student mode, source versioning

**Goal:** catch meaningful defects and enforce the approval boundary.

**Guardrails (implement at least six; keep most deterministic and explainable)**
1. Duplicate or near-identical questions (embedding or token similarity)
2. Answer leakage in the question stem
3. Malformed answer key (key option missing, or key does not match the question)
4. Unsupported claim (item must cite a chunk; LLM entailment check as backup)
5. Objective coverage imbalance
6. Difficulty mismatch (Bloom levels of "advanced" items not higher than "easy")
7. Revision sheet introducing concepts absent from the explanation (optional)

Each flag stores: type, severity, offending item, plain-language reason, suggested fix, and resolved/unresolved state.

**Other tasks**
- **Student view and export (HTML and PDF)** that query **only Approved versions**, enforced in backend queries rather than the UI.
- **Source-version change:** existing items keep their original `source_version_id`; the UI shows a badge such as "generated from v1, source is now v2". Nothing regenerates automatically.
- Approval cannot proceed on items with unresolved high-severity flags unless the teacher explicitly overrides, and the override is logged.

**Exit criteria**
- Each guardrail fires on a purpose-built bad input and has a passing pytest test.
- Student view and export never expose Draft or Needs Revision content, even when requested by direct ID.
- Changing the source version leaves old items tied to their original version.

---

## Phase 4: Innovation and UX

**Goal:** add one or two strong differentiators and make the teacher experience clear.

**Pick one or two**
- **Evaluation harness:** scores a pack before approval (objective coverage, leakage, consistency, Bloom spread) and produces a report. Also used to generate evidence for Phase 5.
- **Bloom tagging with teacher override**, logged in `decisions`.
- **Reading-level or dyslexia-friendly variant** with a semantic consistency check against the original.

**UX tasks**
- Replace prompt-style inputs with dropdowns, toggles, and sliders for level, difficulty, length, and answer-reveal policy.
- Show warnings in plain language with a clear fix action.
- Clear processing, failure, and retry states for every generation action.
- Keep the UI minimal and consistent; do not add screens beyond the demo flow.

**Exit criteria**
- The chosen innovation works on a fresh input.
- A non-technical user can complete the full flow without writing a prompt.

---

## Phase 5: Evidence, documentation, demo readiness

**Goal:** make the system judgeable and reproducible from a clean state.

**Tasks**
- Build an automated eval run over `eval/sources/` covering at least: normal case, insufficient-source case, injection case, difficulty switch, selective regeneration with approved items, source version change. Save outputs and pass/fail results in `eval/results/`.
- Write `README.md`: problem, target user, setup, model and tool choices, prompts and configuration, data flow, limitations, known failure cases, what was built vs. pre-existing components.
- Include a clear section: **what the model does vs. what we built** (state, versioning, guardrails, approval gates, provenance).
- Produce an architecture diagram (client, backend, model calls, data stores, pipeline) and a core workflow diagram (action → evidence/state → AI/logic → validation/persistence).
- Add a seed/reset script that returns the app to a clean DB.
- Verify the official demo sequence end to end from a clean DB with a fresh source:
  1. Create a unit from a fresh source and two objectives
  2. Generate the full pack and open the alignment view
  3. Trigger one quality warning and resolve it
  4. Approve selected items, regenerate one unapproved item, show version history
  5. Run one stress test with a modified source or constraint
  6. Open student view and export, showing only approved content

**Exit criteria**
- Clean-state run of the full demo sequence succeeds.
- All pytest tests and the eval run pass, with results recorded.
- No secrets in the repo; setup instructions work on a fresh machine.

---

## Definition of done (final checklist)

- [ ] Source boundary enforced; injection in source has no effect
- [ ] Gap in source is flagged, not fabricated
- [ ] All five artifacts generated, each item aligned to an objective with citations
- [ ] Easy vs. advanced differ in cognitive demand
- [ ] Selective regeneration never alters other items; approved versions immutable
- [ ] Draft / Approved / Needs Revision enforced in backend; student view shows approved only
- [ ] At least six guardrails implemented and tested
- [ ] Provenance stored per item version (source version, model, prompt version, settings, timestamp)
- [ ] Source change does not silently alter existing content
- [ ] Failures are visible and recoverable; no canned fallback content
- [ ] Docs, diagrams, and evaluation evidence complete
