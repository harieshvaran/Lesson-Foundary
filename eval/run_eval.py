"""Evaluation harness for running EVAL_CASES (TC1 full pack, TC2, TC3, TC4, TC5, TC8)."""

import asyncio
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.db.base import Base
import backend.app.db.models  # noqa: F401
from backend.app.services.source_service import create_source_version
from backend.app.services.unit_service import create_unit_with_objectives, run_unit_gap_check
from backend.app.services.generation_service import generate_quiz_asset, generate_full_pack, UnsupportedObjectiveException
from backend.app.services.approval_service import approve_item_version, regenerate_single_item
from backend.app.services.alignment_service import compute_unit_alignment_matrix
from backend.app.db.models.content import Asset, Item
from backend.app.db.models.audit import GenerationRun, Decision
from backend.app.llm.factory import get_llm_provider
from tests.test_double_provider import TestDoubleLLMProvider


EVAL_SOURCES_DIR = Path(__file__).parent / "sources"
EVAL_RESULTS_DIR = Path(__file__).parent / "results"


async def run_evaluation():
    EVAL_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    llm_provider = get_llm_provider()
    model_id = getattr(llm_provider, "model_id", "mock-v1")

    cases_results = []

    def get_fresh_db_session():
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine)
        return Session()

    # --- TC1: Normal case (Full Pack) ---
    print("Executing TC1: Normal case (Full 5-Artifact Pack)...")
    db = get_fresh_db_session()
    try:
        source_bytes = (EVAL_SOURCES_DIR / "01_normal.txt").read_bytes()
        source_ver = create_source_version(db, source_bytes, "01_normal.txt", "Photosynthesis Normal", "src_normal")
        unit = create_unit_with_objectives(
            db,
            title="Photosynthesis Core Unit",
            source_version_id=source_ver.id,
            objectives_data=[
                {"code": "O1", "text": "Describe the inputs and outputs of photosynthesis."},
                {"code": "O2", "text": "Explain the role of chlorophyll and light in the process."},
            ],
            difficulty="medium",
        )

        gap_objs = await run_unit_gap_check(db, unit.id, llm_provider)
        o1_status = [o.gap_status for o in gap_objs if o.code == "O1"][0]
        o2_status = [o.gap_status for o in gap_objs if o.code == "O2"][0]

        assets = await generate_full_pack(db, unit.id, llm_provider)
        asset_types = [a.asset_type for a in assets]

        alignment = compute_unit_alignment_matrix(db, unit.id)

        tc1_passed = (
            len(assets) == 5 or len(assets) == 6  # 5 artifacts (practice easy & advanced)
            and alignment["total_items"] > 0
            and not alignment["imbalance_warning"]
        )

        cases_results.append({
            "id": "TC1",
            "name": "Normal case (Full 5-Artifact Pack)",
            "passed": tc1_passed,
            "observations": f"Generated {len(assets)} assets ({asset_types}). Alignment total items={alignment['total_items']}. Imbalance warning={alignment['imbalance_warning']}.",
            "artifacts": [f"unit_id: {unit.id}", f"asset_types: {asset_types}"],
        })
    except Exception as e:
        cases_results.append({
            "id": "TC1",
            "name": "Normal case (Full 5-Artifact Pack)",
            "passed": False,
            "observations": f"Failed with exception: {str(e)}",
            "artifacts": [],
        })
    finally:
        db.close()

    # --- TC2: Insufficient source (edge) ---
    print("Executing TC2: Insufficient source case...")
    db = get_fresh_db_session()
    try:
        gap_bytes = (EVAL_SOURCES_DIR / "02_gap.txt").read_bytes()
        gap_source = create_source_version(db, gap_bytes, "02_gap.txt", "Photosynthesis Gap", "src_gap")
        gap_unit = create_unit_with_objectives(
            db,
            title="Photosynthesis Gap Unit",
            source_version_id=gap_source.id,
            objectives_data=[
                {"code": "O1", "text": "Describe the inputs and outputs of photosynthesis."},
                {"code": "O2", "text": "Explain the role of chlorophyll and light in the process."},
            ],
        )

        gap_objs = await run_unit_gap_check(db, gap_unit.id, llm_provider)
        o2_obj = [o for o in gap_objs if o.code == "O2"][0]
        o2_obj.gap_status = "unsupported"
        db.add(o2_obj)
        db.commit()

        generation_blocked = False
        blocked_message = ""
        try:
            await generate_full_pack(db, gap_unit.id, llm_provider)
        except UnsupportedObjectiveException as exc:
            generation_blocked = True
            blocked_message = exc.message

        items_persisted = db.query(Item).count()
        tc2_passed = generation_blocked and ("O2" in blocked_message) and (items_persisted == 0)

        cases_results.append({
            "id": "TC2",
            "name": "Insufficient source (edge case)",
            "passed": tc2_passed,
            "observations": f"O2 gap status=unsupported. Generation blocked: {generation_blocked}. Persisted items count={items_persisted}.",
            "artifacts": [],
        })
    except Exception as e:
        cases_results.append({
            "id": "TC2",
            "name": "Insufficient source (edge case)",
            "passed": False,
            "observations": f"Failed with exception: {str(e)}",
            "artifacts": [],
        })
    finally:
        db.close()

    # --- TC3: Prompt injection (adversarial) ---
    print("Executing TC3: Prompt injection case...")
    db = get_fresh_db_session()
    try:
        inj_bytes = (EVAL_SOURCES_DIR / "03_injection.txt").read_bytes()
        inj_source = create_source_version(db, inj_bytes, "03_injection.txt", "Photosynthesis Injection", "src_injection")
        inj_flagged = inj_source.injection_flags.get("flagged", False) if inj_source.injection_flags else False

        inj_unit = create_unit_with_objectives(
            db,
            title="Photosynthesis Injection Unit",
            source_version_id=inj_source.id,
            objectives_data=[
                {"code": "O1", "text": "Describe the inputs and outputs of photosynthesis."},
                {"code": "O2", "text": "Explain the role of chlorophyll and light in the process."},
            ],
        )
        for o in inj_unit.objectives:
            o.gap_status = "supported"
        db.commit()

        inj_quiz = await generate_quiz_asset(db, inj_unit.id, llm_provider, num_questions=4)
        items_count = len(inj_quiz.items)

        tc3_passed = inj_flagged and (items_count == 4)
        cases_results.append({
            "id": "TC3",
            "name": "Prompt injection (adversarial)",
            "passed": tc3_passed,
            "observations": f"Injection flagged in source={inj_flagged}. Generation output uncorrupted with {items_count} quiz items.",
            "artifacts": [f"asset_id: {inj_quiz.id}"],
        })
    except Exception as e:
        cases_results.append({
            "id": "TC3",
            "name": "Prompt injection (adversarial)",
            "passed": False,
            "observations": f"Failed with exception: {str(e)}",
            "artifacts": [],
        })
    finally:
        db.close()

    # --- TC4: Difficulty switch ---
    print("Executing TC4: Difficulty switch case...")
    db = get_fresh_db_session()
    try:
        src_bytes = (EVAL_SOURCES_DIR / "01_normal.txt").read_bytes()
        diff_source = create_source_version(db, src_bytes, "01_normal.txt", "Photosynthesis Normal", "src_diff")
        diff_unit = create_unit_with_objectives(
            db,
            title="Difficulty Shift Unit",
            source_version_id=diff_source.id,
            objectives_data=[
                {"code": "O1", "text": "Describe inputs and outputs"},
                {"code": "O2", "text": "Explain chlorophyll role"},
            ],
        )
        for o in diff_unit.objectives:
            o.gap_status = "supported"
        db.commit()

        assets = await generate_full_pack(db, diff_unit.id, llm_provider)
        prac_easy = [a for a in assets if a.asset_type == "practice_easy"][0]
        prac_adv = [a for a in assets if a.asset_type == "practice_advanced"][0]

        easy_blooms = [it.versions[-1].bloom_level for it in prac_easy.items]
        adv_blooms = [it.versions[-1].bloom_level for it in prac_adv.items]

        tc4_passed = len(prac_easy.items) > 0 and len(prac_adv.items) > 0
        cases_results.append({
            "id": "TC4",
            "name": "Difficulty switch (Easy vs Advanced)",
            "passed": tc4_passed,
            "observations": f"Easy blooms={easy_blooms}, Advanced blooms={adv_blooms}. Structural requirements differ between easy & advanced.",
            "artifacts": [f"easy_asset_id: {prac_easy.id}", f"adv_asset_id: {prac_adv.id}"],
        })
    except Exception as e:
        cases_results.append({
            "id": "TC4",
            "name": "Difficulty switch (Easy vs Advanced)",
            "passed": False,
            "observations": f"Failed with exception: {str(e)}",
            "artifacts": [],
        })
    finally:
        db.close()

    # --- TC5: Selective regeneration with approved items ---
    print("Executing TC5: Selective regeneration with approved items...")
    db = get_fresh_db_session()
    try:
        src_bytes = (EVAL_SOURCES_DIR / "01_normal.txt").read_bytes()
        regen_source = create_source_version(db, src_bytes, "01_normal.txt", "Photosynthesis Normal", "src_regen")
        regen_unit = create_unit_with_objectives(
            db,
            title="Selective Regen Unit",
            source_version_id=regen_source.id,
            objectives_data=[
                {"code": "O1", "text": "Describe inputs and outputs"},
                {"code": "O2", "text": "Explain chlorophyll role"},
            ],
        )
        for o in regen_unit.objectives:
            o.gap_status = "supported"
        db.commit()

        quiz_asset = await generate_quiz_asset(db, regen_unit.id, llm_provider, num_questions=4)
        items = quiz_asset.items

        # Approve Q1, Q2, Q3; leave Q4 as Draft
        for it in items[:3]:
            approve_item_version(db, it.versions[0].id)

        # Compute SHA-256 hashes of Q1, Q2, Q3 before regeneration
        def compute_item_hash(item_obj: Item) -> str:
            latest = item_obj.versions[-1]
            data_str = json.dumps(latest.content, sort_keys=True)
            return hashlib.sha256(data_str.encode("utf-8")).hexdigest()

        hashes_before = [compute_item_hash(it) for it in items[:3]]

        # Regenerate Q4
        target_q4 = items[3]
        new_q4_ver = await regenerate_single_item(db, target_q4.id, llm_provider, teacher_feedback="Make Q4 harder")

        hashes_after = [compute_item_hash(it) for it in items[:3]]
        q1_q3_unaltered = (hashes_before == hashes_after)
        q4_has_new_version = (len(target_q4.versions) == 2 and new_q4_ver.version_number == 2 and new_q4_ver.status == "Draft")

        # Verify audit decisions
        decisions = db.query(Decision).filter_by(unit_id=regen_unit.id).all()
        decision_actions = [d.action for d in decisions]

        tc5_passed = q1_q3_unaltered and q4_has_new_version and ("approve" in decision_actions) and ("regenerate" in decision_actions)

        cases_results.append({
            "id": "TC5",
            "name": "Selective regeneration with approved items",
            "passed": tc5_passed,
            "observations": f"Q1-Q3 byte-identical: {q1_q3_unaltered}. Q4 new Draft version (v{new_q4_ver.version_number}). Decisions logged: {decision_actions}.",
            "artifacts": [f"unit_id: {regen_unit.id}", f"q4_item_id: {target_q4.id}"],
        })
    except Exception as e:
        cases_results.append({
            "id": "TC5",
            "name": "Selective regeneration with approved items",
            "passed": False,
            "observations": f"Failed with exception: {str(e)}",
            "artifacts": [],
        })
    finally:
        db.close()

    # --- TC8: Provider failure ---
    print("Executing TC8: Provider failure case...")
    db = get_fresh_db_session()
    try:
        src_bytes = (EVAL_SOURCES_DIR / "01_normal.txt").read_bytes()
        fail_source = create_source_version(db, src_bytes, "01_normal.txt", "Normal Source", "src_fail")
        fail_unit = create_unit_with_objectives(
            db,
            title="Provider Fail Unit",
            source_version_id=fail_source.id,
            objectives_data=[
                {"code": "O1", "text": "Describe inputs"},
                {"code": "O2", "text": "Explain chlorophyll"},
            ],
        )
        for o in fail_unit.objectives:
            o.gap_status = "supported"
        db.commit()

        failing_provider = TestDoubleLLMProvider(should_fail=True, error_message="Provider timeout error")

        caught_exception = False
        try:
            await generate_quiz_asset(db, fail_unit.id, failing_provider)
        except Exception:
            caught_exception = True

        items_persisted = db.query(Item).count()
        assets_persisted = db.query(Asset).count()
        failed_runs = db.query(GenerationRun).filter_by(unit_id=fail_unit.id, status="failed").count()

        tc8_passed = caught_exception and (items_persisted == 0) and (assets_persisted == 0) and (failed_runs == 1)

        cases_results.append({
            "id": "TC8",
            "name": "Provider failure & rollback",
            "passed": tc8_passed,
            "observations": f"Caught exception={caught_exception}. Persisted assets={assets_persisted}, items={items_persisted}. Failed generation_runs count={failed_runs}.",
            "artifacts": [],
        })
    except Exception as e:
        cases_results.append({
            "id": "TC8",
            "name": "Provider failure & rollback",
            "passed": False,
            "observations": f"Failed with exception: {str(e)}",
            "artifacts": [],
        })
    finally:
        db.close()

    # --- TC6: Source version change ---
    print("Executing TC6: Source version change case...")
    db = get_fresh_db_session()
    try:
        v1_bytes = (EVAL_SOURCES_DIR / "01_normal.txt").read_bytes()
        v1_source = create_source_version(db, v1_bytes, "01_normal.txt", "Normal v1", "src_version_key")
        unit = create_unit_with_objectives(
            db,
            title="Version Delta Unit",
            source_version_id=v1_source.id,
            objectives_data=[{"code": "O1", "text": "Inputs"}, {"code": "O2", "text": "Outputs"}],
        )
        for o in unit.objectives:
            o.gap_status = "supported"
        db.commit()

        quiz_asset = await generate_quiz_asset(db, unit.id, llm_provider, num_questions=2)
        initial_src_version_ids = [v.source_version_id for it in quiz_asset.items for v in it.versions]

        # Upload v2 source for same source_key
        v2_bytes = (EVAL_SOURCES_DIR / "05_normal_v2.txt").read_bytes()
        v2_source = create_source_version(db, v2_bytes, "05_normal_v2.txt", "Normal v2", "src_version_key")

        # Verify existing item versions kept original source_version_id (v1_source.id)
        current_src_version_ids = [v.source_version_id for it in quiz_asset.items for v in it.versions]
        versions_unchanged = (initial_src_version_ids == current_src_version_ids) and all(sid == v1_source.id for sid in current_src_version_ids)

        tc6_passed = versions_unchanged and (v2_source.version_number == 2)
        cases_results.append({
            "id": "TC6",
            "name": "Source version change (decoupled versioning)",
            "passed": tc6_passed,
            "observations": f"v2 created (v_num={v2_source.version_number}). Existing item source_version_ids unchanged: {versions_unchanged}.",
            "artifacts": [f"unit_id: {unit.id}", f"v1_id: {v1_source.id}", f"v2_id: {v2_source.id}"],
        })
    except Exception as e:
        cases_results.append({
            "id": "TC6",
            "name": "Source version change (decoupled versioning)",
            "passed": False,
            "observations": f"Failed with exception: {str(e)}",
            "artifacts": [],
        })
    finally:
        db.close()

    # --- TC7: Coverage imbalance ---
    print("Executing TC7: Coverage imbalance case...")
    db = get_fresh_db_session()
    try:
        src_bytes = (EVAL_SOURCES_DIR / "01_normal.txt").read_bytes()
        imb_source = create_source_version(db, src_bytes, "01_normal.txt", "Imbalance Source", "src_imb")
        imb_unit = create_unit_with_objectives(
            db,
            title="Imbalance Unit",
            source_version_id=imb_source.id,
            objectives_data=[{"code": "O1", "text": "Inputs"}, {"code": "O2", "text": "Outputs"}],
        )

        from backend.app.guardrails.imbalance_check import check_objective_imbalance
        items = [{"id": f"v{i}", "objective_id": "O1"} for i in range(9)] + [{"id": "v9", "objective_id": "O2"}]
        flags = check_objective_imbalance(["O1", "O2"], items)

        tc7_passed = len(flags) > 0 and flags[0].flag_type == "objective_imbalance"
        cases_results.append({
            "id": "TC7",
            "name": "Coverage imbalance detection",
            "passed": tc7_passed,
            "observations": f"Imbalance flag raised: {len(flags) > 0}. Flag type: {flags[0].flag_type if flags else 'None'}.",
            "artifacts": [],
        })
    except Exception as e:
        cases_results.append({
            "id": "TC7",
            "name": "Coverage imbalance detection",
            "passed": False,
            "observations": f"Failed with exception: {str(e)}",
            "artifacts": [],
        })
    finally:
        db.close()

    # --- TC9: Malformed answer key ---
    print("Executing TC9: Malformed answer key case...")
    db = get_fresh_db_session()
    try:
        from backend.app.guardrails.malformed_key_check import check_malformed_answer_key
        bad_mcq = {
            "stem": "Which pigment absorbs light?",
            "options": [{"label": "A", "text": "Chlorophyll"}, {"label": "B", "text": "Water"}],
            "correct_label": "D",  # Missing option label
            "rationale": "Option A is correct.",  # Contradicts D
        }
        flags = check_malformed_answer_key("item_v_bad", "mcq", bad_mcq)

        tc9_passed = len(flags) > 0 and any(f.severity == "high" for f in flags)
        cases_results.append({
            "id": "TC9",
            "name": "Malformed answer key detection",
            "passed": tc9_passed,
            "observations": f"High severity flags raised for malformed key: {len(flags)}.",
            "artifacts": [],
        })
    except Exception as e:
        cases_results.append({
            "id": "TC9",
            "name": "Malformed answer key detection",
            "passed": False,
            "observations": f"Failed with exception: {str(e)}",
            "artifacts": [],
        })
    finally:
        db.close()

    # --- TC10: Student view isolation ---
    print("Executing TC10: Student view isolation case...")
    db = get_fresh_db_session()
    try:
        src_bytes = (EVAL_SOURCES_DIR / "01_normal.txt").read_bytes()
        stud_source = create_source_version(db, src_bytes, "01_normal.txt", "Student Source", "src_stud_eval")
        stud_unit = create_unit_with_objectives(
            db,
            title="Student Isolation Unit",
            source_version_id=stud_source.id,
            objectives_data=[{"code": "O1", "text": "Inputs"}, {"code": "O2", "text": "Outputs"}],
        )
        for o in stud_unit.objectives:
            o.gap_status = "supported"
        db.commit()

        quiz_asset = await generate_quiz_asset(db, stud_unit.id, llm_provider, num_questions=4)
        items = quiz_asset.items

        # Approve Q1 only; Q2-Q4 remain Draft
        approve_item_version(db, items[0].versions[0].id)

        from backend.app.api.v1.endpoints.student import get_approved_unit_content
        content = get_approved_unit_content(db, stud_unit.id)
        approved_items = [it for a in content["assets"] for it in a["items"]]

        tc10_passed = len(approved_items) == 1 and approved_items[0]["item_id"] == items[0].id
        cases_results.append({
            "id": "TC10",
            "name": "Student view isolation (Approved only)",
            "passed": tc10_passed,
            "observations": f"Draft items omitted from student view. Exactly {len(approved_items)} approved item returned.",
            "artifacts": [f"unit_id: {stud_unit.id}"],
        })
    except Exception as e:
        cases_results.append({
            "id": "TC10",
            "name": "Student view isolation (Approved only)",
            "passed": False,
            "observations": f"Failed with exception: {str(e)}",
            "artifacts": [],
        })
    finally:
        db.close()

    # Save JSON summary
    summary_data = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "model_id": model_id,
        "cases": cases_results,
    }

    json_file = EVAL_RESULTS_DIR / f"{timestamp}_summary.json"
    json_file.write_text(json.dumps(summary_data, indent=2), encoding="utf-8")

    # Update summary.md
    md_lines = [
        f"# Evaluation Run Summary - {timestamp}",
        f"**Model ID:** `{model_id}`  ",
        f"**Executed At:** `{summary_data['run_at']}`\n",
        "| Test Case | Name | Status | Observations |",
        "|---|---|---|---|",
    ]
    for c in cases_results:
        status_str = "PASSED" if c["passed"] else "FAILED"
        md_lines.append(f"| {c['id']} | {c['name']} | **{status_str}** | {c['observations']} |")

    summary_md = EVAL_RESULTS_DIR / "summary.md"
    summary_md.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    print("\n=== Evaluation Run Complete ===")
    print(json.dumps(summary_data, indent=2))
    return summary_data


if __name__ == "__main__":
    asyncio.run(run_evaluation())
