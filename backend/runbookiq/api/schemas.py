from pydantic import BaseModel, Field, field_validator


class KnowledgeBaseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=500)

    @field_validator("name", "description")
    @classmethod
    def trim_text(cls, value: str) -> str:
        return value.strip()


class QueryRequest(BaseModel):
    knowledge_base_id: str = Field(min_length=1, max_length=100)
    question: str = Field(min_length=1, max_length=4000)

    @field_validator("question")
    @classmethod
    def question_must_contain_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("question must contain non-whitespace text")
        return value


class EvaluationCaseRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    expected_source_ids: list[str] = Field(min_length=1)
    reference_answer: str | None = None


class EvaluationRunRequest(BaseModel):
    knowledge_base_id: str = Field(min_length=1, max_length=100)
    suite_id: str | None = Field(default=None, min_length=1, max_length=100)
    max_cases: int | None = Field(default=None, ge=1, le=500)
    cases: list[EvaluationCaseRequest] | None = Field(default=None, min_length=1, max_length=500)

    @field_validator("cases")
    @classmethod
    def suite_or_cases_must_be_selected(
        cls,
        value: list[EvaluationCaseRequest] | None,
        info,
    ) -> list[EvaluationCaseRequest] | None:
        if value is None and not info.data.get("suite_id"):
            raise ValueError("suite_id or cases is required")
        return value
