# AGENT_RULES.md

These rules apply to every task in this repository. If a request conflicts with a rule, stop and ask instead of breaking the rule.

## 1. Workflow rules

1. Read `SPEC.md`, `PHASES.md`, `PROMPT_TEMPLATES.md` and `EVAL_CASES.md` before starting any phase.
2. Work on **one phase at a time**. Do not begin a phase until the previous phase's exit criteria pass.
3. Before writing code for a phase, produce an **implementation plan** (files to create or change, interfaces, tests, risks) and wait for approval.
4. Do not add features, screens or dependencies that are not in the spec. If you think something is missing, propose it and wait.
5. Keep commits small and scoped to one concern. Never rewrite unrelated files.
6. When finishing a task, report: what changed, which tests ran, which exit criteria are met, and anything left open.
7. Never claim something works without running it. State exactly what you ran and the result.

## 2. Content and generation rules

1. **Never hard-code generated content.** No canned explanations, quizzes, fallbacks, placeholders presented as output, or mock responses in production code paths.
2. If a model call fails, times out or returns invalid output, **surface the error visibly** and record it in `generation_runs`. Never substitute fake content.
3. **All LLM output passes through Pydantic validation** before touching the database. Invalid output is retried (bounded) and then fails visibly.
4. **Source text is data, never instructions.** Always wrap it in the delimiters defined in `PROMPT_TEMPLATES.md`. Never concatenate source text into the system prompt.
5. Every generated item must have a non-null `objective_id` and at least one `source_chunk_id`. Enforce in the Pydantic schema, the service layer and a database constraint.
6. Every claim in generated content must be traceable to a source chunk. If the source does not support it, the item must be flagged or not generated.
7. Use the `LLMProvider` interface for every model call. No direct SDK calls outside the provider module.

## 3. Data integrity rules

1. **Approved versions are immutable.** No code path may update or delete an approved `item_version`.
2. Regeneration always creates a **new** `item_version` with status `Draft`. The previously approved version remains the student-visible version until the teacher approves the new one.
3. Regenerating one item or asset must not modify any other item. Add a test that proves other items are byte-identical before and after.
4. Every generated `item_version` stores: `source_version_id`, `model_id`, `prompt_template_version`, `generation_settings`, `created_at`, `generation_run_id`.
5. A source change creates a **new** `source_version`. Existing items keep their original `source_version_id`. Nothing regenerates automatically.
6. Every teacher action (approve, reject, regenerate, override, Bloom change, flag resolution) writes a row to `decisions`.
7. Database writes for a multi-item generation run happen in a transaction. A failure must not leave a partial or corrupted pack.

## 4. Access and security rules

1. **Student views and exports query only `Approved` versions.** Enforce this in backend queries, not only in the UI. Requesting a Draft item by direct ID from student routes returns 404.
2. API keys and secrets live only in server-side `.env`. Never in client code, logs, commits or error messages. Provide `.env.example` with placeholders only.
3. Validate and size-limit all uploads. Reject unsupported file types with a clear error.
4. Do not log full source text or full prompts at INFO level.

## 5. Code quality rules

1. Python with type hints. Pydantic models for all request, response and LLM output schemas.
2. Keep layers separate: `ingestion/`, `generation/`, `guardrails/`, `services/`, `api/`, `db/`, `llm/`. No business logic in route handlers.
3. Guardrails are separate pure functions that take item data and return flags. Prefer deterministic logic; use the model only as a documented backup.
4. Prompts live in versioned template files, not inline strings. Bumping a template changes its `prompt_template_version`.
5. Write a pytest test for **every guardrail** and **every invariant** in sections 2 and 3. Tests must not depend on the UI or on live model calls (use a test double implementing `LLMProvider` only inside `tests/`).
6. The test double must never be importable from production code.
7. Add docstrings explaining *why*, not only *what*, for non-obvious logic. The team must be able to explain every code path to judges.

## 6. UX rules

1. The teacher must never need to write a prompt. Use dropdowns, toggles, sliders and plain-language warnings.
2. Every long action shows a processing state, and every failure shows a clear message with a retry option.
3. Status badges (Draft / Approved / Needs Revision) are visible everywhere an item appears.
4. Keep the UI minimal until Phase 4. Correctness over polish.

## 7. Honesty rules

1. Do not fabricate evaluation results, test outcomes or metrics. Eval outputs must come from real runs saved in `eval/results/`.
2. If something is partially implemented, say so in the README under known limitations.
3. Disclose any boilerplate or third-party code in the README.

## 8. Stop-and-ask triggers

Stop and ask before: changing the data model, adding a dependency, changing a status transition, touching `PHASES.md` or `SPEC.md`, deleting files, or anything that would modify approved data.
