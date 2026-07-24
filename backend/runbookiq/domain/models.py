from typing import Literal

from pydantic import BaseModel, Field


class Citation(BaseModel):
    number: int
    source_id: str
    title: str
    section_path: str
    excerpt: str
    source_url: str
    scores: dict[str, float] = Field(default_factory=dict)


class TraceStage(BaseModel):
    name: str
    duration_ms: int
    candidate_count: int


class RetrievalTrace(BaseModel):
    query_id: str
    stages: list[TraceStage] = Field(default_factory=list)


class Answer(BaseModel):
    text: str = Field(serialization_alias="answer")
    confidence: float = Field(ge=0, le=1)
    citations: list[Citation] = Field(default_factory=list)
    trace: RetrievalTrace


class KnowledgeBase(BaseModel):
    id: str
    name: str
    description: str = ""
    created_at: str


class IngestionJob(BaseModel):
    id: str
    knowledge_base_id: str
    filename: str
    status: Literal["queued", "processing", "completed", "failed"]
    progress: int = Field(ge=0, le=100)
    chunks_created: int = 0
    error: str | None = None


class EvaluationReport(BaseModel):
    run_id: str
    suite_id: str
    suite_total: int
    case_count: int
    evaluated_at: str
    duration_ms: int
    judge: str
    metrics: dict[str, float]
    metric_definitions: dict[str, str] = Field(default_factory=dict)
    cases: list["EvaluationCaseResult"] = Field(default_factory=list)


class EvaluationCaseResult(BaseModel):
    question: str
    expected_source_ids: list[str]
    retrieved_source_ids: list[str]
    first_relevant_rank: int | None
    metrics: dict[str, float]
