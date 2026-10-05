"""Test Double for LLMProvider. Strictly residing inside tests/ directory."""

import json
from typing import Any
from backend.app.llm.base import LLMProvider
from backend.app.llm.schemas import LLMResponse
from backend.app.core.exceptions import LLMTimeoutError, LLMProviderError


class TestDoubleLLMProvider(LLMProvider):
    """Test double provider used for invariant tests and offline pytest runs.
    
    NEVER importable from production code paths.
    """
    __test__ = False

    def __init__(
        self,
        canned_response: str | None = None,
        should_timeout: bool = False,
        should_fail: bool = False,
        error_message: str = "Forced test failure",
    ):
        self.canned_response = canned_response
        self.should_timeout = should_timeout
        self.should_fail = should_fail
        self.error_message = error_message
        self.call_history: list[dict[str, Any]] = []

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        settings: dict[str, Any] | None = None,
    ) -> LLMResponse:
        self.call_history.append({"prompt": prompt, "system_prompt": system_prompt, "settings": settings})

        if self.should_timeout:
            raise LLMTimeoutError("Test double forced timeout after 30.0s")
        if self.should_fail:
            raise LLMProviderError(f"Test double forced error: {self.error_message}")

        if self.canned_response is not None:
            content = self.canned_response
        else:
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
                            "stem": "Which pigment absorbs light in photosynthesis?",
                            "options": [
                                {"label": "A", "text": "Chlorophyll"},
                                {"label": "B", "text": "Xanthophyll"},
                                {"label": "C", "text": "Carotene"},
                                {"label": "D", "text": "Anthocyanin"},
                            ],
                            "correct_label": "A",
                            "rationale": "Chlorophyll absorbs light energy.",
                            "objective_id": "O1",
                            "source_chunk_ids": ["S1"],
                            "bloom_level": "remember",
                        },
                        {
                            "stem": "What is the primary gaseous output of photosynthesis?",
                            "options": [
                                {"label": "A", "text": "Oxygen"},
                                {"label": "B", "text": "Carbon Dioxide"},
                                {"label": "C", "text": "Nitrogen"},
                                {"label": "D", "text": "Methane"},
                            ],
                            "correct_label": "A",
                            "rationale": "Oxygen gas is released.",
                            "objective_id": "O2",
                            "source_chunk_ids": ["S1"],
                            "bloom_level": "remember",
                        },
                        {
                            "stem": "Where are chlorophyll pigments located?",
                            "options": [
                                {"label": "A", "text": "Chloroplast thylakoids"},
                                {"label": "B", "text": "Cell wall"},
                                {"label": "C", "text": "Mitochondria"},
                                {"label": "D", "text": "Nucleus"},
                            ],
                            "correct_label": "A",
                            "rationale": "Chloroplasts contain thylakoid membranes.",
                            "objective_id": "O1",
                            "source_chunk_ids": ["S1"],
                            "bloom_level": "understand",
                        },
                        {
                            "stem": "What leaf structure absorbs CO2?",
                            "options": [
                                {"label": "A", "text": "Stomata"},
                                {"label": "B", "text": "Xylem"},
                                {"label": "C", "text": "Root hair"},
                                {"label": "D", "text": "Cuticle"},
                            ],
                            "correct_label": "A",
                            "rationale": "Stomata absorb carbon dioxide.",
                            "objective_id": "O2",
                            "source_chunk_ids": ["S1"],
                            "bloom_level": "remember",
                        },
                    ],
                    "notes": "Mock quiz",
                })
            elif "gap" in prompt_lower or "gapcheckoutput" in prompt_lower:
                content = json.dumps({
                    "objective_id": "O1",
                    "status": "supported",
                    "evidence_chunk_ids": ["S1"],
                    "missing_concepts": [],
                    "reason": "Source covers objective.",
                })
            elif "entailment" in prompt_lower or "support the claim" in prompt_lower or "claim" in prompt_lower:
                content = json.dumps({"supported": True, "reason": "Test double entailment supported."})
            elif "hello" in prompt_lower or "ping" in prompt_lower:
                content = "Hello! LessonFoundry LLM Provider is operational."
            else:
                content = json.dumps({"status": "ok", "message": "Test double default response"})

        return LLMResponse(
            content=content,
            raw_response={"test_double": True},
            model_id="test-double-v1",
            prompt_tokens=10,
            completion_tokens=20,
            latency_ms=1.5,
        )
