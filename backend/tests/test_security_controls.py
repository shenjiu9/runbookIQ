import httpx
import pytest

from runbookiq.adapters.tenancy import InMemoryTenantAccess
from runbookiq.app import create_local_app
from runbookiq.security import InMemoryAbuseGuard, RateLimitExceeded, UsageLimits


class RecordingTurnstileVerifier:
    enabled = True
    required = True

    def __init__(self) -> None:
        self.tokens: list[str | None] = []

    async def verify(
        self,
        *,
        token: str | None,
        remote_ip: str | None,
        action: str,
    ) -> bool:
        self.tokens.append(token)
        return token == "valid-turnstile-token" and action == "register"


def tenant_access() -> InMemoryTenantAccess:
    return InMemoryTenantAccess(
        authentication_required=True,
        root_domain="knowledge.test",
    )


async def register(client: httpx.AsyncClient, *, email: str = "owner@example.com"):
    response = await client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": "Strong-password-2026",
            "organization_name": "Example Enterprise",
        },
    )
    if response.status_code == 201:
        client.headers["X-CSRF-Token"] = client.cookies["runbookiq_csrf"]
    return response


@pytest.mark.asyncio
async def test_in_memory_guard_enforces_a_sliding_window() -> None:
    guard = InMemoryAbuseGuard()
    await guard.enforce(action="login", scope="client", limit=1, window_seconds=60)

    with pytest.raises(RateLimitExceeded):
        await guard.enforce(action="login", scope="client", limit=1, window_seconds=60)


@pytest.mark.asyncio
async def test_registration_requires_server_verified_turnstile_when_enabled() -> None:
    verifier = RecordingTurnstileVerifier()
    app = create_local_app(
        tenant_access=tenant_access(),
        turnstile_verifier=verifier,
        turnstile_site_key="public-site-key",
    )
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="https://knowledge.test") as client:
        config = await client.get("/api/security-config")
        rejected = await register(client)
        accepted = await client.post(
            "/api/auth/register",
            json={
                "email": "verified@example.com",
                "password": "Strong-password-2026",
                "organization_name": "Verified Enterprise",
                "turnstile_token": "valid-turnstile-token",
            },
        )

    assert config.json() == {
        "turnstile_enabled": True,
        "turnstile_required": True,
        "turnstile_site_key": "public-site-key",
        "max_batch_files": 10,
        "max_document_mib": 20,
    }
    assert rejected.status_code == 400
    assert accepted.status_code == 201
    assert verifier.tokens == [None, "valid-turnstile-token"]


@pytest.mark.asyncio
async def test_registration_rate_limit_returns_retry_after() -> None:
    app = create_local_app(
        tenant_access=tenant_access(),
        usage_limits=UsageLimits(
            registration_per_hour=1,
            registration_global_per_hour=10,
        ),
    )
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="https://knowledge.test") as client:
        first = await register(client, email="first@example.com")
        second = await register(client, email="second@example.com")

    assert first.status_code == 201
    assert second.status_code == 429
    assert int(second.headers["Retry-After"]) > 0


@pytest.mark.asyncio
async def test_free_plan_caps_knowledge_bases() -> None:
    app = create_local_app(
        tenant_access=tenant_access(),
        usage_limits=UsageLimits(max_knowledge_bases=1),
    )
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="https://knowledge.test") as client:
        assert (await register(client)).status_code == 201
        rejected = await client.post(
            "/api/knowledge-bases",
            json={"name": "Extra knowledge base", "description": "Over the free limit"},
        )

    assert rejected.status_code == 409
    assert "最多创建 1 个知识库" in rejected.json()["detail"]


@pytest.mark.asyncio
async def test_upload_rejects_spoofed_and_oversized_files() -> None:
    app = create_local_app(
        tenant_access=tenant_access(),
        usage_limits=UsageLimits(max_document_mib=1),
    )
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="https://knowledge.test") as client:
        registered = await register(client)
        knowledge_base_id = (
            await client.get("/api/knowledge-bases")
        ).json()[0]["id"]
        spoofed = await client.post(
            "/api/documents",
            data={"knowledge_base_id": knowledge_base_id},
            files={"file": ("manual.pdf", b"not a pdf", "application/pdf")},
        )
        oversized = await client.post(
            "/api/documents",
            data={"knowledge_base_id": knowledge_base_id},
            files={"file": ("manual.txt", b"x" * (1024 * 1024 + 1), "text/plain")},
        )

    assert registered.status_code == 201
    assert spoofed.status_code == 422
    assert spoofed.json()["detail"] == "文件内容与扩展名不匹配"
    assert oversized.status_code == 413
