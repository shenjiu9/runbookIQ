from pydantic import BaseModel, Field


class DocumentChunk(BaseModel):
    id: str
    source_id: str
    title: str
    section_path: str
    text: str
    source_url: str
    parent_text: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)


class RankedChunk(BaseModel):
    chunk: DocumentChunk
    rank: int
    score: float
    component_scores: dict[str, float] = Field(default_factory=dict)

