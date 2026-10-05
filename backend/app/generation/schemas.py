"""Pydantic schemas for all LLM output types, enforcing mandatory provenance fields."""

from typing import Literal
from pydantic import BaseModel, Field, model_validator

# ---------------------------------------------------------
# Shared Item Validator Helper
# ---------------------------------------------------------

def validate_item_provenance(objective_id: str, source_chunk_ids: list[str]):
    if not objective_id or not objective_id.strip():
        raise ValueError("objective_id cannot be empty or null.")
    if not source_chunk_ids or len(source_chunk_ids) == 0:
        raise ValueError("source_chunk_ids cannot be empty; every item must cite at least one source chunk.")


# ---------------------------------------------------------
# 1. Gap Check Schema
# ---------------------------------------------------------

class GapCheckOutput(BaseModel):
    objective_id: str = Field(..., description="Objective code or ID")
    status: Literal["supported", "partial", "unsupported"] = Field(..., description="Coverage status")
    evidence_chunk_ids: list[str] = Field(default_factory=list, description="Cited chunk labels")
    missing_concepts: list[str] = Field(default_factory=list, description="Missing concepts")
    reason: str = Field(..., description="Plain language explanation")


# ---------------------------------------------------------
# 2. Explanation Schema
# ---------------------------------------------------------

class ExplanationBlock(BaseModel):
    heading: str
    body: str
    objective_id: str
    source_chunk_ids: list[str]
    bloom_level: str = "understand"

    @model_validator(mode="after")
    def validate_provenance(self):
        validate_item_provenance(self.objective_id, self.source_chunk_ids)
        return self


class ExplanationAssetOutput(BaseModel):
    blocks: list[ExplanationBlock]
    key_terms: list[str] = Field(default_factory=list)
    notes: str | None = None


# ---------------------------------------------------------
# 3. Worked Example Schema
# ---------------------------------------------------------

class ExampleStep(BaseModel):
    step_number: int
    instruction: str
    working: str
    result: str
    objective_id: str
    source_chunk_ids: list[str]
    bloom_level: str = "apply"

    @model_validator(mode="after")
    def validate_provenance(self):
        validate_item_provenance(self.objective_id, self.source_chunk_ids)
        return self


class ExampleAssetOutput(BaseModel):
    title: str
    steps: list[ExampleStep]
    notes: str | None = None


# ---------------------------------------------------------
# 4. Quiz MCQ Schema
# ---------------------------------------------------------

class QuizOption(BaseModel):
    label: Literal["A", "B", "C", "D"]
    text: str


class QuizQuestion(BaseModel):
    stem: str
    options: list[QuizOption]
    correct_label: Literal["A", "B", "C", "D"]
    rationale: str
    objective_id: str
    source_chunk_ids: list[str]
    bloom_level: str = "remember"

    @model_validator(mode="after")
    def validate_question(self):
        validate_item_provenance(self.objective_id, self.source_chunk_ids)
        labels = [opt.label for opt in self.options]
        if len(self.options) != 4 or labels != ["A", "B", "C", "D"]:
            raise ValueError("Quiz question must have exactly 4 options labeled A, B, C, D in order.")
        if self.correct_label not in labels:
            raise ValueError(f"correct_label '{self.correct_label}' must be one of {labels}.")
        return self


class QuizAssetOutput(BaseModel):
    questions: list[QuizQuestion]
    notes: str | None = None


# ---------------------------------------------------------
# 5. Practice Schema (Easy & Advanced)
# ---------------------------------------------------------

class PracticeItem(BaseModel):
    prompt: str
    model_answer: str
    marking_points: list[str]
    objective_id: str
    source_chunk_ids: list[str]
    bloom_level: str = "apply"

    @model_validator(mode="after")
    def validate_practice(self):
        validate_item_provenance(self.objective_id, self.source_chunk_ids)
        if not self.marking_points or len(self.marking_points) == 0:
            raise ValueError("marking_points list cannot be empty.")
        return self


class PracticeAssetOutput(BaseModel):
    items: list[PracticeItem]
    notes: str | None = None


# ---------------------------------------------------------
# 6. Revision Sheet Schema
# ---------------------------------------------------------

class RevisionPoint(BaseModel):
    point: str
    objective_id: str
    source_chunk_ids: list[str]
    bloom_level: str = "remember"

    @model_validator(mode="after")
    def validate_provenance(self):
        validate_item_provenance(self.objective_id, self.source_chunk_ids)
        return self


class RevisionAssetOutput(BaseModel):
    points: list[RevisionPoint]
    notes: str | None = None
