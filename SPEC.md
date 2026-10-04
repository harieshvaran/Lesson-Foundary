# SPEC.md: LessonFoundry Technical Specification

## 1. Purpose

LessonFoundry is a teacher-facing studio that converts one trusted teaching source plus explicit learning objectives into a connected learning pack (explanation, worked example, quiz with key, two-level practice, revision sheet). The teacher controls generation, regeneration, review and approval. Students see approved content only.

**Primary user:** teacher. **Secondary user:** student (read-only, approved content).

## 2. Architecture

```
React client  --->  FastAPI backend  --->  SQLite (SQLAlchemy)
                        |
                        +--> ingestion/   (upload, parse, chunk, version)
                        +--> generation/  (pipeline, prompt rendering, validation)
                        +--> guardrails/  (deterministic checks + LLM backup)
                        +--> services/    (approval, versioning, alignment, export)
                        +--> llm/         (LLMProvider interface + concrete provider)
```

- Client holds no secrets and no business rules.
- The model is called only from `llm/` and only via the pipeline.
- Source, teacher intent, prompts/config, generated output and teacher decisions live in separate tables.

## 3. Data model

All tables have `id` (UUID or integer PK) and `created_at`. Types are indicative.

### 3.1 Source
**source_versions**: `id`, `source_key` (groups versions of the same source), `version_number`, `title`, `raw_text`, `content_hash`, `file_type`, `injection_flags` (JSON), `created_at`

**source_chunks**: `id`, `source_version_id`, `chunk_label` (S1, S2, ...), `position`, `text`

### 3.2 Teacher intent
**units**: `id`, `title`, `source_version_id`, `target_level`, `difficulty` (easy | medium | advanced), `created_at`

**objectives**: `id`, `unit_id`, `code` (O1, O2, ...), `text`, `target_bloom` (nullable), `gap_status` (supported | partial | unsupported | unchecked), `gap_evidence_chunk_ids` (JSON)

**constraints**: `id`, `unit_id`, `vocabulary_level`, `max_length_words`, `answer_reveal_policy` (never_in_stem | hints_allowed | show_after_attempt), `style_notes`

### 3.3 Generated content
**assets**: `id`, `unit_id`, `asset_type` (explanation | example | quiz | practice_easy | practice_advanced | revision)

**items**: `id`, `asset_id`, `position`, `item_type` (explanation_block | example_step | mcq | short_answer | revision_point), `current_approved_version_id` (nullable), `latest_version_id`

**item_versions**: `id`, `item_id`, `version_number`, `content` (JSON), `status` (Draft | Approved | Needs Revision), `objective_id` (NOT NULL), `source_chunk_ids` (JSON, non-empty), `bloom_level`, `bloom_overridden` (bool), `source_version_id`, `model_id`, `prompt_template_version`, `generation_settings` (JSON), `generation_run_id`, `created_at`, `approved_at`

Constraints: `objective_id` NOT NULL; `source_chunk_ids` non-empty (validated in schema and service layer); approved rows immutable.

### 3.4 Quality and audit
**quality_flags**: `id`, `item_version_id`, `flag_type`, `severity` (low | medium | high), `message`, `suggested_fix`, `detected_by` (deterministic | llm), `resolved` (bool), `resolution_note`, `created_at`

**generation_runs**: `id`, `unit_id`, `asset_type`, `target_item_id` (nullable), `status` (success | failed | invalid_output), `attempts`, `error_message`, `model_id`, `prompt_template_version`, `settings` (JSON), `started_at`, `finished_at`

**decisions**: `id`, `unit_id`, `item_version_id` (nullable), `action` (approve | reject | regenerate | flag_override | bloom_override | flag_resolve | source_update), `actor` (teacher), `note`, `created_at`

## 4. Status state machine

```
Draft ---approve---> Approved           (blocked if unresolved high-severity flags, unless override logged)
Draft ---reject----> Needs Revision
Needs Revision ---regenerate---> new item_version in Draft
Approved ---regenerate---> new item_version in Draft (old Approved version stays student-visible)
New Draft ---approve---> Approved       (previous Approved version becomes superseded, never edited)
```

Rules:
- No transition may edit an Approved row's content.
- "Student-ready" means the latest Approved version of an item.
- Superseded versions remain in history.

## 5. Generation pipeline

1. **Ingest**: parse text/PDF, normalize, hash, chunk (S1..Sn), run injection scan, create `source_version`.
2. **Unit setup**: teacher defines at least 2 objectives, level, difficulty, constraints.
3. **Gap check**: per objective, retrieve relevant chunks and ask the model for `supported | partial | unsupported` with chunk IDs. Any `unsupported` objective blocks generation with a message naming the objective. `partial` warns and requires teacher confirmation.
4. **Generate in order**: explanation, then example, then quiz, then practice (easy, advanced), then revision. Each step receives prior output as context for terminology stability.
5. **Validate**: Pydantic schema; bounded retries; log every attempt in `generation_runs`.
6. **Persist** in a transaction as Draft `item_versions` with alignment and provenance.
7. **Guardrails** run automatically after persistence and write `quality_flags`.
8. **Review**: teacher approves, rejects or regenerates per item.

### 5.1 Retrieval
Keep it simple and explainable: lexical (BM25 or TF-IDF) retrieval over chunks, optionally embeddings. Retrieved chunk IDs are passed to the prompt and must be cited back in output. Items citing chunk IDs not in the source version are rejected.

### 5.2 Difficulty definition
Difficulty is defined by Bloom level and structure, not wording.

| Level | Bloom levels | Structural requirements |
|---|---|---|
| easy | Remember, Understand | single-step, recall or direct restatement, one concept |
| medium | Understand, Apply | one to two steps, apply a rule to a new case |
| advanced | Apply, Analyze, Evaluate | multi-step, combines concepts, requires justification or comparison |

Practice items at two levels must differ in Bloom distribution and structure. The difficulty-mismatch guardrail checks this.

### 5.3 Injection handling
- Source is wrapped in delimiters and labeled untrusted data in the system prompt.
- A regex/heuristic scan flags phrases like "ignore previous instructions", "reveal the answer", "you are now", "system prompt". Flags are stored in `source_versions.injection_flags` and shown in the UI.
- Output schema validation and the answer-leakage check act as a second defense.
- Flagged sources are still usable; the flagged text is treated as ordinary content.

## 6. LLM output schemas (Pydantic, summarized)

Every generated item shares:
```
objective_id: str (required)
source_chunk_ids: list[str] (min length 1)
bloom_level: enum[remember, understand, apply, analyze, evaluate, create]
```

- **explanation_block**: `heading`, `body`, shared fields
- **example_step**: `step_number`, `instruction`, `working`, `result`, shared fields
- **mcq**: `stem`, `options` (list of 4 with `label` and `text`), `correct_label`, `rationale`, shared fields. `correct_label` must match an option label.
- **short_answer**: `prompt`, `model_answer`, `marking_points`, shared fields
- **revision_point**: `point`, shared fields. Every point must cite chunks that also support the explanation.

## 7. Guardrails

Each returns zero or more `quality_flags`.

| # | Flag | Method | Default severity |
|---|---|---|---|
| 1 | Duplicate / near-identical question | token Jaccard or embedding cosine over stems | medium |
| 2 | Answer leakage in stem | answer text or key phrase appears in stem; other options contain stem phrases | high |
| 3 | Malformed answer key | `correct_label` not in options; duplicate options; rationale contradicts key | high |
| 4 | Unsupported claim | missing/invalid chunk IDs; lexical overlap below threshold; LLM entailment as backup | high |
| 5 | Objective coverage imbalance | item count per objective deviates beyond threshold | medium |
| 6 | Difficulty mismatch | advanced Bloom mean not above easy Bloom mean; or items outside allowed Bloom band | medium |
| 7 | Revision introduces new concept | key terms in revision absent from explanation/example | medium |
| 8 | Constraint violation | length, vocabulary or reveal-policy breach | low to medium |

Thresholds live in configuration, not code constants.

## 8. API (REST, JSON)

**Source**
- `POST /sources` upload text/PDF, returns `source_version`
- `POST /sources/{source_key}/versions` new version
- `GET /sources/{id}` and `/chunks`

**Units**
- `POST /units` with objectives and constraints
- `GET /units/{id}`
- `POST /units/{id}/gap-check`
- `POST /units/{id}/generate` full pack (blocked by gap status)
- `GET /units/{id}/alignment` objective x asset matrix, coverage counts, imbalance warning
- `GET /units/{id}/flags`
- `GET /units/{id}/evaluation` pack score report (Phase 4)

**Items**
- `GET /items/{id}/versions`
- `POST /items/{id}/regenerate` creates new Draft version only
- `POST /item-versions/{id}/approve`
- `POST /item-versions/{id}/reject`
- `POST /item-versions/{id}/bloom-override`
- `POST /quality-flags/{id}/resolve`

**Student (read-only, approved only)**
- `GET /student/units/{id}` approved items only
- `GET /student/units/{id}/export?format=html|pdf`

**Audit**
- `GET /units/{id}/decisions`
- `GET /units/{id}/generation-runs`

Errors return structured JSON: `{error_code, message, recoverable, details}`.

## 9. Student mode rules

- Student routes join only on `item_versions.status = 'Approved'` and use the latest approved version per item.
- Direct-ID requests for non-approved versions return 404.
- Exports use the same query path as the student view.
- An item with no approved version is omitted, not shown as empty.

## 10. Source versioning behavior

- Updating the source creates a new `source_version`; units keep a pointer to the version they were generated from.
- Items show "generated from vN, source is now vM" when versions differ.
- No automatic regeneration. Teacher chooses to re-run the gap check and regenerate per item.

## 11. Failure handling

| Failure | Behavior |
|---|---|
| Provider timeout / outage | run marked `failed`, clear message, pack unchanged, retry available |
| Malformed model output | bounded retry, then `invalid_output`, nothing persisted |
| Unsupported objective | generation blocked, message names objective and missing coverage |
| Partial pack failure | transaction rolled back, previous state intact |
| Missing API key | startup/health endpoint reports configuration error clearly |

## 12. Provenance

Each `item_version` stores source version, chunk IDs, model ID, prompt template version, generation settings, run ID and timestamp. The UI exposes this in an item detail drawer.

## 13. Out of scope

Automatic grading, autonomous publishing, model training, scraping copyrighted material, subjects where correctness cannot be checked, multi-tenant auth beyond a simple teacher/student role split.

## 14. Tech choices

Python 3.11+, FastAPI, SQLAlchemy, SQLite, Pydantic v2, pytest, React + Vite. Concrete LLM provider selected in Phase 0 behind `LLMProvider`.
