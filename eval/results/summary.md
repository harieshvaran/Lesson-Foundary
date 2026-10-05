# Evaluation Run Summary - 20261005_142455
**Model ID:** `mock-v1`  
**Executed At:** `2026-10-05T14:24:56.302325+00:00`

| Test Case | Name | Status | Observations |
|---|---|---|---|
| TC1 | Normal case (Full 5-Artifact Pack) | **PASSED** | Generated 6 assets (['explanation', 'example', 'quiz', 'practice_easy', 'practice_advanced', 'revision']). Alignment total items=9. Imbalance warning=False. |
| TC2 | Insufficient source (edge case) | **PASSED** | O2 gap status=unsupported. Generation blocked: True. Persisted items count=0. |
| TC3 | Prompt injection (adversarial) | **PASSED** | Injection flagged in source=True. Generation output uncorrupted with 4 quiz items. |
| TC4 | Difficulty switch (Easy vs Advanced) | **PASSED** | Easy blooms=['remember'], Advanced blooms=['remember']. Structural requirements differ between easy & advanced. |
| TC5 | Selective regeneration with approved items | **PASSED** | Q1-Q3 byte-identical: True. Q4 new Draft version (v2). Decisions logged: ['approve', 'approve', 'approve', 'regenerate']. |
| TC8 | Provider failure & rollback | **PASSED** | Caught exception=True. Persisted assets=0, items=0. Failed generation_runs count=1. |
| TC6 | Source version change (decoupled versioning) | **PASSED** | v2 created (v_num=2). Existing item source_version_ids unchanged: True. |
| TC7 | Coverage imbalance detection | **PASSED** | Imbalance flag raised: True. Flag type: objective_imbalance. |
| TC9 | Malformed answer key detection | **PASSED** | High severity flags raised for malformed key: 2. |
| TC10 | Student view isolation (Approved only) | **PASSED** | Draft items omitted from student view. Exactly 1 approved item returned. |
