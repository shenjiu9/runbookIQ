from pydantic import BaseModel, Field, field_validator

from runbookiq.domain.tenancy import TenantRole


class RegistrationRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=12, max_length=200)
    organization_name: str = Field(min_length=2, max_length=120)
    slug: str | None = Field(default=None, min_length=2, max_length=32)
    turnstile_token: str | None = Field(default=None, max_length=2048)

    @field_validator("email", "organization_name")
    @classmethod
    def trim_registration_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("slug")
    @classmethod
    def trim_optional_slug(cls, value: str | None) -> str | None:
        return value.strip() if value else None

    @field_validator("email")
    @classmethod
    def email_must_be_plausible(cls, value: str) -> str:
        normalized = value.lower()
        if normalized.count("@") != 1 or normalized.startswith("@") or normalized.endswith("@"):
            raise ValueError("enter a valid email address")
        return normalized


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=200)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class InvitationCreateRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    role: TenantRole

    @field_validator("email")
    @classmethod
    def normalize_invitation_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized.count("@") != 1 or normalized.startswith("@") or normalized.endswith("@"):
            raise ValueError("enter a valid email address")
        return normalized

    @field_validator("role")
    @classmethod
    def invitation_role_must_not_be_owner(cls, value: TenantRole) -> TenantRole:
        if value == "owner":
            raise ValueError("owner role cannot be assigned by invitation")
        return value


class InvitationAcceptRequest(BaseModel):
    token: str = Field(min_length=20, max_length=200)
    password: str = Field(min_length=12, max_length=200)


class InvitationPreviewRequest(BaseModel):
    token: str = Field(min_length=20, max_length=200)


class OrganizationBrandingUpdate(BaseModel):
    display_name: str = Field(min_length=2, max_length=80)
    logo_url: str | None = Field(default=None, max_length=500)
    primary_color: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    welcome_title: str = Field(min_length=2, max_length=80)
    welcome_message: str = Field(min_length=2, max_length=240)

    @field_validator("display_name", "welcome_title", "welcome_message")
    @classmethod
    def trim_branding_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("logo_url")
    @classmethod
    def validate_logo_url(cls, value: str | None) -> str | None:
        normalized = value.strip() if value else None
        if not normalized:
            return None
        if not normalized.startswith(("https://", "/")):
            raise ValueError("logo_url must be an HTTPS URL or a site-relative path")
        return normalized


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


class RuntimeConfigResponse(BaseModel):
    mode: str
    chat_provider: str
    chat_base_url: str | None
    chat_model: str
    embedding_provider: str
    embedding_base_url: str | None
    embedding_model: str
    embedding_dimensions: int
    rerank_provider: str
    query_timeout_seconds: float
    ocr_languages: str
    max_document_mib: int = 20
    max_batch_files: int = 10
    max_knowledge_bases: int = 5
    max_organization_members: int = 25
    query_limit_per_day: int = 200
    upload_limit_per_day: int = 50
    evaluation_limit_per_hour: int = 10
    turnstile_enabled: bool = False


class SecurityConfigResponse(BaseModel):
    turnstile_enabled: bool
    turnstile_required: bool
    turnstile_site_key: str | None
    max_batch_files: int
    max_document_mib: int
