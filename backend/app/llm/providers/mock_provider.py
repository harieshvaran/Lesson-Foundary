"""Mock LLM Provider for local development and deterministic execution."""

import json
import time
from typing import Any
from backend.app.llm.base import LLMProvider
from backend.app.llm.schemas import LLMResponse


class MockLLMProvider(LLMProvider):
    """Production mock provider used when LLM_PROVIDER=mock in development."""

    def __init__(self, model_id: str = "mock-v1", latency_ms: float = 10.0):
        self.model_id = model_id
        self.latency_ms = latency_ms

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        settings: dict[str, Any] | None = None,
    ) -> LLMResponse:
        start_time = time.perf_counter()
        prompt_lower = prompt.lower()

        if "regenerate one item" in prompt_lower or "single item" in prompt_lower:
            content = json.dumps({
                "stem": "Which pigment absorbs light in photosynthesis (Regenerated)?",
                "options": [
                    {"label": "A", "text": "Chlorophyll (Regenerated)"},
                    {"label": "B", "text": "Xanthophyll"},
                    {"label": "C", "text": "Carotene"},
                    {"label": "D", "text": "Anthocyanin"},
                ],
                "correct_label": "A",
                "rationale": "Regenerated rationale.",
                "objective_id": "O1",
                "source_chunk_ids": ["S1"],
                "bloom_level": "understand",
                "heading": "Regenerated Heading",
                "body": "Regenerated Body",
                "title": "Regenerated Example",
                "step_number": 1,
                "instruction": "Regenerated Instruction",
                "working": "Regenerated Working",
                "result": "Regenerated Result",
                "prompt": "Regenerated Practice Prompt?",
                "model_answer": "Regenerated Model Answer",
                "marking_points": ["Point 1"],
                "point": "Regenerated Revision Point",
            })
        elif "exampleassetoutput" in prompt_lower or "worked example" in prompt_lower:
            content = json.dumps({
                "title": "Photosynthesis Step-by-Step",
                "steps": [
                    {
                        "step_number": 1,
                        "instruction": "Absorb light energy via chlorophyll",
                        "working": "Photons excite chlorophyll electrons",
                        "result": "Water photolysis releases oxygen",
                        "objective_id": "O2",
                        "source_chunk_ids": ["S1"],
                        "bloom_level": "apply",
                    }
                ],
                "notes": "Mock example",
            })
        elif "explanationassetoutput" in prompt_lower or "concept explanation" in prompt_lower:
            content = json.dumps({
                "blocks": [
                    {
                        "heading": "Inputs of Photosynthesis",
                        "body": "Plants absorb water through roots and carbon dioxide through leaf stomata.",
                        "objective_id": "O1",
                        "source_chunk_ids": ["S1"],
                        "bloom_level": "understand",
                    }
                ],
                "key_terms": ["Photosynthesis", "Stomata"],
                "notes": "Mock explanation",
            })
        elif "practiceassetoutput" in prompt_lower or "practice items" in prompt_lower:
            content = json.dumps({
                "items": [
                    {
                        "prompt": "State the two primary raw material inputs required for photosynthesis.",
                        "model_answer": "Water (H2O) and Carbon Dioxide (CO2).",
                        "marking_points": ["Mentions Water", "Mentions Carbon Dioxide"],
                        "objective_id": "O1",
                        "source_chunk_ids": ["S1"],
                        "bloom_level": "remember" if "easy" in prompt_lower else "analyze",
                    }
                ],
                "notes": "Mock practice",
            })
        elif "revisionassetoutput" in prompt_lower or "revision sheet" in prompt_lower:
            content = json.dumps({
                "points": [
                    {
                        "point": "Photosynthesis converts water and carbon dioxide into glucose and oxygen.",
                        "objective_id": "O1",
                        "source_chunk_ids": ["S1"],
                        "bloom_level": "remember",
                    }
                ],
                "notes": "Mock revision",
            })
        elif "quiz" in prompt_lower or "quizassetoutput" in prompt_lower or "multiple-choice" in prompt_lower:
            content = json.dumps({
                "questions": [
                    {
                        "stem": "Which pigment absorbs light energy during photosynthesis?",
                        "options": [
                            {"label": "A", "text": "Chlorophyll"},
                            {"label": "B", "text": "Xanthophyll"},
                            {"label": "C", "text": "Carotene"},
                            {"label": "D", "text": "Anthocyanin"},
                        ],
                        "correct_label": "A",
                        "rationale": "Chlorophyll in thylakoids absorbs red and blue light to excite electrons.",
                        "objective_id": "O1",
                        "source_chunk_ids": ["S1"],
                        "bloom_level": "remember",
                    },
                    {
                        "stem": "What are the primary chemical outputs of photosynthesis?",
                        "options": [
                            {"label": "A", "text": "Glucose and Oxygen"},
                            {"label": "B", "text": "Water and Carbon Dioxide"},
                            {"label": "C", "text": "Starch and Nitrogen"},
                            {"label": "D", "text": "ATP and Water"},
                        ],
                        "correct_label": "A",
                        "rationale": "Photosynthesis produces glucose (C6H12O6) and oxygen gas (O2).",
                        "objective_id": "O2",
                        "source_chunk_ids": ["S1"],
                        "bloom_level": "remember",
                    },
                    {
                        "stem": "Where inside plant cells does photosynthesis take place?",
                        "options": [
                            {"label": "A", "text": "Chloroplasts"},
                            {"label": "B", "text": "Mitochondria"},
                            {"label": "C", "text": "Ribosomes"},
                            {"label": "D", "text": "Vacuoles"},
                        ],
                        "correct_label": "A",
                        "rationale": "Chloroplasts contain chlorophyll and thylakoid membranes.",
                        "objective_id": "O1",
                        "source_chunk_ids": ["S1"],
                        "bloom_level": "understand",
                    },
                    {
                        "stem": "Through which specialized pores do leaves absorb carbon dioxide?",
                        "options": [
                            {"label": "A", "text": "Stomata"},
                            {"label": "B", "text": "Xylem"},
                            {"label": "C", "text": "Phloem"},
                            {"label": "D", "text": "Epidermis"},
                        ],
                        "correct_label": "A",
                        "rationale": "Stomata are microscopic leaf pores that absorb CO2.",
                        "objective_id": "O2",
                        "source_chunk_ids": ["S1"],
                        "bloom_level": "remember",
                    },
                ],
                "notes": "Generated 4 mock quiz questions.",
            })
        elif "gap" in prompt_lower or "gapcheckoutput" in prompt_lower:
            content = json.dumps({
                "objective_id": "O1",
                "status": "supported",
                "evidence_chunk_ids": ["S1"],
                "missing_concepts": [],
                "reason": "Source chunk S1 covers the objective.",
            })
        elif "hello" in prompt_lower or "ping" in prompt_lower:
            content = "Hello! LessonFoundry LLM Provider is operational."
        else:
            content = json.dumps({"status": "ok", "message": "Mock provider default response"})

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0 + self.latency_ms

        return LLMResponse(
            content=content,
            raw_response={"mock": True, "prompt": prompt},
            model_id=self.model_id,
            prompt_tokens=len(prompt.split()),
            completion_tokens=len(content.split()),
            latency_ms=elapsed_ms,
        )
