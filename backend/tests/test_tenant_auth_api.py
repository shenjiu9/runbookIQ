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
        knowledge_bases = await client.get("/api/knowledge-bases")
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
    assert knowledge_bases.status_code == 200
    assert [(item["name"], item["description"]) for item in knowledge_bases.json()] == [
        ("Alpha Manufacturing 企业知识库", "企业制度、手册与业务资料")
    ]
    assert logged_out.status_code == 204
    assert after_logout.status_code == 401


@pytest.mark.asyncio
async def test_owner_can_invite_a_colleague_into_the_same_enterprise() -> None:
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
    ) as owner:
        await _register(
            owner,
            email="owner@alpha.example",
            organization_name="Alpha Manufacturing",
            slug="alpha",
        )
        created = await owner.post(
            "/api/organization/invitations",
            json={"email": "analyst@alpha.example", "role": "viewer"},
        )
        assert created.status_code == 201
        invitation = created.json()
        assert invitation["email"] == "analyst@alpha.example"
        assert invitation["role"] == "viewer"
        assert invitation["accept_url"].startswith(
            "https://alpha.knowledge.test/#invite="
        )

        members_before_acceptance = await owner.get("/api/organization/members")
        pending_before_acceptance = await owner.get(
            "/api/organization/invitations"
        )

    async with httpx.AsyncClient(
        transport=transport,
        base_url="https://alpha.knowledge.test",
    ) as invited:
        preview = await invited.post(
            "/api/auth/invitations/preview",
            json={"token": invitation["token"]},
        )
        accepted = await invited.post(
            "/api/auth/invitations/accept",
            json={
                "token": invitation["token"],
                "password": "Invited-password-2026",
            },
        )
        invited.headers["X-CSRF-Token"] = invited.cookies["runbookiq_csrf"]
        current = await invited.get("/api/auth/me")
        knowledge_bases = await invited.get("/api/knowledge-bases")
        rejected_write = await invited.post(
            "/api/knowledge-bases",
            json={"name": "Viewer cannot create", "description": ""},
        )

    assert members_before_acceptance.status_code == 200
    assert [member["email"] for member in members_before_acceptance.json()] == [
        "owner@alpha.example"
    ]
    assert pending_before_acceptance.status_code == 200
    assert [item["email"] for item in pending_before_acceptance.json()] == [
        "analyst@alpha.example"
    ]
    assert preview.status_code == 200
    assert preview.json()["organization_name"] == "Alpha Manufacturing"
    assert accepted.status_code == 200
    assert accepted.json()["role"] == "viewer"
    assert current.status_code == 200
    assert current.json()["organization"]["slug"] == "alpha"
    assert len(knowledge_bases.json()) == 1
    assert rejected_write.status_code == 403
    assert rejected_write.json()["detail"] == "当前角色无权执行此操作"


@pytest.mark.asyncio
async def test_invitation_is_one_time_and_disappears_after_acceptance() -> None:
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
    ) as owner:
        await _register(
            owner,
            email="owner@alpha.example",
            organization_name="Alpha Manufacturing",
            slug="alpha",
        )
        invitation = (
            await owner.post(
                "/api/organization/invitations",
                json={"email": "editor@alpha.example", "role": "editor"},
            )
        ).json()

    async with httpx.AsyncClient(
        transport=transport,
        base_url="https://alpha.knowledge.test",
    ) as invited:
        first = await invited.post(
            "/api/auth/invitations/accept",
            json={
                "token": invitation["token"],
                "password": "Invited-password-2026",
            },
        )
        invited.cookies.clear()
        second = await invited.post(
            "/api/auth/invitations/accept",
            json={
                "token": invitation["token"],
                "password": "Another-password-2026",
            },
        )

    async with httpx.AsyncClient(
        transport=transport,
        base_url="https://app.knowledge.test",
    ) as owner_again:
        logged_in = await owner_again.post(
            "/api/auth/login",
            json={
                "email": "owner@alpha.example",
                "password": "Strong-password-2026",
            },
        )
        assert logged_in.status_code == 200
        owner_again.headers["X-CSRF-Token"] = owner_again.cookies["runbookiq_csrf"]
        pending_after_acceptance = await owner_again.get(
            "/api/organization/invitations"
        )

    assert first.status_code == 200
    assert second.status_code == 409
    assert pending_after_acceptance.status_code == 200
    assert pending_after_acceptance.json() == []
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
    assert {item["name"] for item in alpha_list.json()} == {
        "Alpha Manufacturing 企业知识库",
        "Alpha procedures",
    }
    assert {item["name"] for item in beta_list.json()} == {
        "Beta Retail 企业知识库",
        "Beta handbook",
    }
    assert {item["id"] for item in alpha_list.json()}.isdisjoint(
        {item["id"] for item in beta_list.json()}
    )
    assert cross_tenant_query.status_code == 404
    assert cross_tenant_delete.status_code == 404


@pytest.mark.asyncio
async def test_user_cannot_log_in_through_another_enterprises_domain() -> None:
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
    ) as registration_client:
        await _register(
            registration_client,
            email="owner@alpha.example",
            organization_name="Alpha Manufacturing",
            slug="alpha",
        )
        registration_client.cookies.clear()
        await _register(
            registration_client,
            email="owner@beta.example",
            organization_name="Beta Retail",
            slug="beta",
        )

    async with httpx.AsyncClient(
        transport=transport,
        base_url="https://alpha.knowledge.test",
    ) as wrong_domain:
        rejected = await wrong_domain.post(
            "/api/auth/login",
            json={
                "email": "owner@beta.example",
                "password": "Strong-password-2026",
            },
        )

    assert rejected.status_code == 403
    assert rejected.json()["detail"] == "该账号不属于当前企业网址"


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
