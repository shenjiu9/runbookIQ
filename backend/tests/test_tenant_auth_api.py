import httpx
import pytest

from runbookiq.adapters.tenancy import InMemoryTenantAccess
from runbookiq.app import create_local_app


async def _register(
    client: httpx.AsyncClient,
    *,
    email: str,
    organization_name: str,
    slug: str,
) -> httpx.Response:
    response = await client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": "Strong-password-2026",
            "organization_name": organization_name,
            "slug": slug,
        },
    )
    assert response.status_code == 201
    client.headers["X-CSRF-Token"] = client.cookies["runbookiq_csrf"]
    return response


@pytest.mark.asyncio
async def test_registration_creates_an_authenticated_enterprise_session() -> None:
    app = create_local_app(
        tenant_access=InMemoryTenantAccess(
            authentication_required=True,
            root_domain="knowledge.test",
        )
    )
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(
        transport=transport,
        base_url="https://app.knowledge.test",
    ) as client:
        registration = await _register(
            client,
            email="owner@alpha.example",
            organization_name="Alpha Manufacturing",
            slug="alpha",
        )
        current = await client.get("/api/auth/me")
        logged_out = await client.post("/api/auth/logout")
        after_logout = await client.get("/api/auth/me")

    registered = registration.json()
    assert registered["user"]["email"] == "owner@alpha.example"
    assert registered["organization"]["name"] == "Alpha Manufacturing"
    assert registered["organization"]["slug"] == "alpha"
    assert registered["organization"]["url"] == "https://alpha.knowledge.test"
    assert registered["role"] == "owner"
    assert "HttpOnly" in registration.headers["set-cookie"]
    assert "runbookiq_csrf=" in registration.headers["set-cookie"]
    assert current.status_code == 200
    assert current.json()["organization"]["slug"] == "alpha"
    assert logged_out.status_code == 204
    assert after_logout.status_code == 401
@pytest.mark.asyncio
async def test_enterprises_cannot_access_each_others_knowledge_bases() -> None:
    app = create_local_app(
        tenant_access=InMemoryTenantAccess(
            authentication_required=True,
            root_domain="knowledge.test",
        )
    )
    transport = httpx.ASGITransport(app=app)

    async with (
        httpx.AsyncClient(
            transport=transport,
            base_url="https://app.knowledge.test",
        ) as alpha,
        httpx.AsyncClient(
            transport=transport,
            base_url="https://app.knowledge.test",
        ) as beta,
    ):
        await _register(
            alpha,
            email="owner@alpha.example",
            organization_name="Alpha Manufacturing",
            slug="alpha",
        )
        await _register(
            beta,
            email="owner@beta.example",
            organization_name="Beta Retail",
            slug="beta",
        )
        alpha_knowledge_base = await alpha.post(
            "/api/knowledge-bases",
            json={"name": "Alpha procedures", "description": "Private operations"},
        )
        beta_knowledge_base = await beta.post(
            "/api/knowledge-bases",
            json={"name": "Beta handbook", "description": "Private retail policies"},
        )

        alpha_list = await alpha.get("/api/knowledge-bases")
        beta_list = await beta.get("/api/knowledge-bases")
        cross_tenant_query = await alpha.post(
            "/api/query",
            json={
                "knowledge_base_id": beta_knowledge_base.json()["id"],
                "question": "What are Beta's private policies?",
            },
        )
        cross_tenant_delete = await alpha.delete(
            f"/api/knowledge-bases/{beta_knowledge_base.json()['id']}"
        )

    assert alpha_knowledge_base.status_code == 201
    assert beta_knowledge_base.status_code == 201
    assert {item["id"] for item in alpha_list.json()} == {
        alpha_knowledge_base.json()["id"]
    }
    assert {item["id"] for item in beta_list.json()} == {
        beta_knowledge_base.json()["id"]
    }
    assert cross_tenant_query.status_code == 404
    assert cross_tenant_delete.status_code == 404


@pytest.mark.asyncio
async def test_tls_is_only_authorized_for_registered_enterprise_domains() -> None:
    app = create_local_app(
        tenant_access=InMemoryTenantAccess(
            authentication_required=True,
            root_domain="knowledge.test",
        )
    )
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(
        transport=transport,
        base_url="https://app.knowledge.test",
    ) as client:
        await _register(
            client,
            email="owner@alpha.example",
            organization_name="Alpha Manufacturing",
            slug="alpha",
        )
        registered = await client.get(
            "/api/internal/tls/allow",
            params={"domain": "alpha.knowledge.test"},
        )
        unknown = await client.get(
            "/api/internal/tls/allow",
            params={"domain": "attacker.knowledge.test"},
        )

    assert registered.status_code == 200
    assert unknown.status_code == 403


@pytest.mark.asyncio
async def test_cookie_authenticated_writes_require_the_csrf_token() -> None:
    app = create_local_app(
        tenant_access=InMemoryTenantAccess(
            authentication_required=True,
            root_domain="knowledge.test",
        )
    )
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(
        transport=transport,
        base_url="https://app.knowledge.test",
    ) as client:
        await _register(
            client,
            email="owner@alpha.example",
            organization_name="Alpha Manufacturing",
            slug="alpha",
        )
        client.headers.pop("X-CSRF-Token")
        rejected = await client.post(
            "/api/knowledge-bases",
            json={"name": "Blocked write", "description": "Missing CSRF token"},
        )

    assert rejected.status_code == 403
    assert rejected.json()["detail"] == "CSRF 校验失败"


@pytest.mark.asyncio
async def test_cross_origin_registration_is_rejected() -> None:
    app = create_local_app(
        tenant_access=InMemoryTenantAccess(
            authentication_required=True,
            root_domain="knowledge.test",
        )
    )
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(
        transport=transport,
        base_url="https://app.knowledge.test",
    ) as client:
        rejected = await client.post(
            "/api/auth/register",
            headers={"Origin": "https://attacker.example"},
            json={
                "email": "owner@alpha.example",
                "password": "Strong-password-2026",
                "organization_name": "Alpha Manufacturing",
                "slug": "alpha",
            },
        )

    assert rejected.status_code == 403
    assert rejected.json()["detail"] == "跨站请求已拒绝"
