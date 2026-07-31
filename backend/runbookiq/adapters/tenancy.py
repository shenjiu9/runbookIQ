import hashlib
import re
import secrets
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from runbookiq.domain.tenancy import (
    Organization,
    TenantContext,
    TenantSession,
    TenantUser,
)

SLUG_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,30}[a-z0-9])?$")
PASSWORD_HASHER = PasswordHasher()


def _normalize_host(host: str) -> str:
    return host.partition(":")[0].strip().lower().rstrip(".")


def _password_hash(password: str) -> str:
    return PASSWORD_HASHER.hash(password)


def _password_matches(password: str, encoded: str) -> bool:
    try:
        return PASSWORD_HASHER.verify(encoded, password)
    except (InvalidHashError, VerifyMismatchError):
        return False


class OpenTenantAccess:
    """Development adapter that keeps existing local workflows frictionless."""

    authentication_required = False

    def __init__(self) -> None:
        self._context = TenantContext(
            user=TenantUser(id="development-user", email="developer@localhost"),
            organization=Organization(
                id="development",
                name="平台工程团队",
                slug="platform",
                url="http://localhost",
            ),
            role="owner",
        )

    async def register(
        self,
        *,
        email: str,
        password: str,
        organization_name: str,
        slug: str,
    ) -> TenantSession:
        raise ValueError("registration is disabled in open development mode")

    async def authenticate(self, *, email: str, password: str) -> TenantSession:
        raise ValueError("login is disabled in open development mode")

    async def resolve(self, *, session_token: str | None, host: str) -> TenantContext:
        return self._context

    async def revoke_session(self, session_token: str | None) -> None:
        return None

    async def validate_csrf(
        self,
        session_token: str | None,
        csrf_token: str | None,
    ) -> bool:
        return True

    async def grant_knowledge_base(
        self,
        context: TenantContext,
        knowledge_base_id: str,
    ) -> None:
        return None

    async def revoke_knowledge_base(
        self,
        context: TenantContext,
        knowledge_base_id: str,
    ) -> None:
        return None

    async def can_access_knowledge_base(
        self,
        context: TenantContext,
        knowledge_base_id: str,
    ) -> bool:
        return True

    async def allowed_knowledge_base_ids(
        self,
        context: TenantContext,
    ) -> set[str] | None:
        return None

    async def domain_allowed(self, host: str) -> bool:
        return True


class InMemoryTenantAccess:
    authentication_required = True

    def __init__(
        self,
        *,
        authentication_required: bool = True,
        root_domain: str = "localhost",
        session_hours: int = 24 * 7,
    ) -> None:
        self.authentication_required = authentication_required
        self._root_domain = _normalize_host(root_domain)
        self._session_lifetime = timedelta(hours=session_hours)
        self._users_by_email: dict[str, dict[str, str]] = {}
        self._organizations_by_id: dict[str, Organization] = {}
        self._organization_ids_by_slug: dict[str, str] = {}
        self._memberships: dict[str, tuple[str, str]] = {}
        self._sessions: dict[str, tuple[str, str, datetime]] = {}
        self._knowledge_base_owners: dict[str, str] = {}

    async def register(
        self,
        *,
        email: str,
        password: str,
        organization_name: str,
        slug: str,
    ) -> TenantSession:
        normalized_email = email.strip().lower()
        normalized_slug = slug.strip().lower()
        if normalized_email in self._users_by_email:
            raise ValueError("email is already registered")
        if normalized_slug in self._organization_ids_by_slug:
            raise ValueError("enterprise slug is already in use")
        if not SLUG_PATTERN.fullmatch(normalized_slug):
            raise ValueError("enterprise slug must contain lowercase letters, numbers or hyphens")

        user_id = f"user-{uuid4().hex}"
        organization_id = f"org-{uuid4().hex}"
        organization = Organization(
            id=organization_id,
            name=organization_name.strip(),
            slug=normalized_slug,
            url=f"https://{normalized_slug}.{self._root_domain}",
        )
        self._users_by_email[normalized_email] = {
            "id": user_id,
            "email": normalized_email,
            "password_hash": _password_hash(password),
        }
        self._organizations_by_id[organization_id] = organization
        self._organization_ids_by_slug[normalized_slug] = organization_id
        self._memberships[user_id] = (organization_id, "owner")
        return self._new_session(user_id)

    async def authenticate(self, *, email: str, password: str) -> TenantSession:
        user = self._users_by_email.get(email.strip().lower())
        if user is None or not _password_matches(password, user["password_hash"]):
            raise ValueError("email or password is incorrect")
        return self._new_session(user["id"])

    async def resolve(
        self,
        *,
        session_token: str | None,
        host: str,
    ) -> TenantContext | None:
        if not session_token:
            return None
        session = self._sessions.get(session_token)
        if session is None:
            return None
        user_id, _csrf_hash, expires_at = session
        if expires_at <= datetime.now(UTC):
            self._sessions.pop(session_token, None)
            return None
        context = self._context_for_user(user_id)
        requested_organization_id = self._organization_for_host(host)
        if (
            requested_organization_id is not None
            and requested_organization_id != context.organization.id
        ):
            return None
        return context

    async def revoke_session(self, session_token: str | None) -> None:
        if session_token:
            self._sessions.pop(session_token, None)

    async def validate_csrf(
        self,
        session_token: str | None,
        csrf_token: str | None,
    ) -> bool:
        if not session_token or not csrf_token:
            return False
        session = self._sessions.get(session_token)
        if session is None:
            return False
        return secrets.compare_digest(session[1], self._token_hash(csrf_token))

    async def grant_knowledge_base(
        self,
        context: TenantContext,
        knowledge_base_id: str,
    ) -> None:
        self._knowledge_base_owners[knowledge_base_id] = context.organization.id

    async def revoke_knowledge_base(
        self,
        context: TenantContext,
        knowledge_base_id: str,
    ) -> None:
        if self._knowledge_base_owners.get(knowledge_base_id) == context.organization.id:
            self._knowledge_base_owners.pop(knowledge_base_id, None)

    async def can_access_knowledge_base(
        self,
        context: TenantContext,
        knowledge_base_id: str,
    ) -> bool:
        return self._knowledge_base_owners.get(knowledge_base_id) == context.organization.id

    async def allowed_knowledge_base_ids(
        self,
        context: TenantContext,
    ) -> set[str]:
        return {
            knowledge_base_id
            for knowledge_base_id, organization_id in self._knowledge_base_owners.items()
            if organization_id == context.organization.id
        }

    async def domain_allowed(self, host: str) -> bool:
        normalized = _normalize_host(host)
        if normalized in {self._root_domain, f"app.{self._root_domain}"}:
            return True
        return self._organization_for_host(normalized) is not None

    def _new_session(self, user_id: str) -> TenantSession:
        token = secrets.token_urlsafe(32)
        csrf_token = secrets.token_urlsafe(32)
        self._sessions[token] = (
            user_id,
            self._token_hash(csrf_token),
            datetime.now(UTC) + self._session_lifetime,
        )
        return TenantSession(
            context=self._context_for_user(user_id),
            token=token,
            csrf_token=csrf_token,
        )

    def _context_for_user(self, user_id: str) -> TenantContext:
        user = next(item for item in self._users_by_email.values() if item["id"] == user_id)
        organization_id, role = self._memberships[user_id]
        return TenantContext(
            user=TenantUser(id=user_id, email=user["email"]),
            organization=self._organizations_by_id[organization_id],
            role=role,
        )

    def _organization_for_host(self, host: str) -> str | None:
        normalized = _normalize_host(host)
        suffix = f".{self._root_domain}"
        if not normalized.endswith(suffix):
            return None
        slug = normalized[: -len(suffix)]
        if "." in slug:
            return None
        return self._organization_ids_by_slug.get(slug)

    @staticmethod
    def _token_hash(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()


class PostgresTenantAccess:
    authentication_required = True

    def __init__(
        self,
        engine: AsyncEngine,
        *,
        root_domain: str,
        session_hours: int = 24 * 7,
    ) -> None:
        self._engine = engine
        self._root_domain = _normalize_host(root_domain)
        self._session_lifetime = timedelta(hours=session_hours)

    async def register(
        self,
        *,
        email: str,
        password: str,
        organization_name: str,
        slug: str,
    ) -> TenantSession:
        normalized_email = email.strip().lower()
        normalized_slug = slug.strip().lower()
        if not SLUG_PATTERN.fullmatch(normalized_slug):
            raise ValueError("enterprise slug must contain lowercase letters, numbers or hyphens")

        user_id = f"user-{uuid4().hex}"
        organization_id = f"org-{uuid4().hex}"
        token = secrets.token_urlsafe(32)
        csrf_token = secrets.token_urlsafe(32)
        expires_at = datetime.now(UTC) + self._session_lifetime
        try:
            async with self._engine.begin() as connection:
                await connection.execute(
                    text(
                        """
                        INSERT INTO organizations (id, name, slug)
                        VALUES (:id, :name, :slug)
                        """
                    ),
                    {
                        "id": organization_id,
                        "name": organization_name.strip(),
                        "slug": normalized_slug,
                    },
                )
                await connection.execute(
                    text(
                        """
                        INSERT INTO users (id, email, password_hash)
                        VALUES (:id, :email, :password_hash)
                        """
                    ),
                    {
                        "id": user_id,
                        "email": normalized_email,
                        "password_hash": _password_hash(password),
                    },
                )
                await connection.execute(
                    text(
                        """
                        INSERT INTO organization_memberships
                            (organization_id, user_id, role)
                        VALUES (:organization_id, :user_id, 'owner')
                        """
                    ),
                    {"organization_id": organization_id, "user_id": user_id},
                )
                await connection.execute(
                    text(
                        """
                        INSERT INTO tenant_domains (domain, organization_id, is_primary)
                        VALUES (:domain, :organization_id, true)
                        """
                    ),
                    {
                        "domain": f"{normalized_slug}.{self._root_domain}",
                        "organization_id": organization_id,
                    },
                )
                await self._insert_session(
                    connection,
                    token=token,
                    csrf_token=csrf_token,
                    user_id=user_id,
                    expires_at=expires_at,
                )
        except IntegrityError as exc:
            message = str(exc.orig).lower()
            if "email" in message:
                raise ValueError("email is already registered") from exc
            if "slug" in message or "domain" in message:
                raise ValueError("enterprise slug is already in use") from exc
            raise ValueError("enterprise registration conflicts with existing data") from exc

        return TenantSession(
            context=TenantContext(
                user=TenantUser(id=user_id, email=normalized_email),
                organization=Organization(
                    id=organization_id,
                    name=organization_name.strip(),
                    slug=normalized_slug,
                    url=f"https://{normalized_slug}.{self._root_domain}",
                ),
                role="owner",
            ),
            token=token,
            csrf_token=csrf_token,
        )

    async def authenticate(self, *, email: str, password: str) -> TenantSession:
        statement = text(
            """
            SELECT
                u.id AS user_id,
                u.email,
                u.password_hash,
                o.id AS organization_id,
                o.name AS organization_name,
                o.slug,
                m.role
            FROM users u
            JOIN organization_memberships m ON m.user_id = u.id
            JOIN organizations o ON o.id = m.organization_id
            WHERE u.email = :email AND u.is_active = true
            ORDER BY m.created_at
            LIMIT 1
            """
        )
        async with self._engine.begin() as connection:
            row = (
                await connection.execute(statement, {"email": email.strip().lower()})
            ).mappings().one_or_none()
            if row is None or not _password_matches(password, row["password_hash"]):
                raise ValueError("email or password is incorrect")
            token = secrets.token_urlsafe(32)
            csrf_token = secrets.token_urlsafe(32)
            await self._insert_session(
                connection,
                token=token,
                csrf_token=csrf_token,
                user_id=row["user_id"],
                expires_at=datetime.now(UTC) + self._session_lifetime,
            )
        return TenantSession(
            context=self._row_to_context(row),
            token=token,
            csrf_token=csrf_token,
        )

    async def resolve(
        self,
        *,
        session_token: str | None,
        host: str,
    ) -> TenantContext | None:
        if not session_token:
            return None
        statement = text(
            """
            SELECT
                u.id AS user_id,
                u.email,
                o.id AS organization_id,
                o.name AS organization_name,
                o.slug,
                m.role
            FROM auth_sessions s
            JOIN users u ON u.id = s.user_id
            JOIN organization_memberships m ON m.user_id = u.id
            JOIN organizations o ON o.id = m.organization_id
            WHERE s.token_hash = :token_hash
              AND s.expires_at > now()
              AND u.is_active = true
            ORDER BY m.created_at
            LIMIT 1
            """
        )
        async with self._engine.connect() as connection:
            row = (
                await connection.execute(
                    statement,
                    {"token_hash": self._token_hash(session_token)},
                )
            ).mappings().one_or_none()
            if row is None:
                return None
            requested_organization_id = await self._organization_for_host(
                connection,
                host,
            )
        if (
            requested_organization_id is not None
            and requested_organization_id != row["organization_id"]
        ):
            return None
        return self._row_to_context(row)

    async def revoke_session(self, session_token: str | None) -> None:
        if not session_token:
            return
        async with self._engine.begin() as connection:
            await connection.execute(
                text("DELETE FROM auth_sessions WHERE token_hash = :token_hash"),
                {"token_hash": self._token_hash(session_token)},
            )

    async def validate_csrf(
        self,
        session_token: str | None,
        csrf_token: str | None,
    ) -> bool:
        if not session_token or not csrf_token:
            return False
        async with self._engine.connect() as connection:
            stored_hash = await connection.scalar(
                text(
                    """
                    SELECT csrf_hash
                    FROM auth_sessions
                    WHERE token_hash = :token_hash
                      AND expires_at > now()
                    """
                ),
                {"token_hash": self._token_hash(session_token)},
            )
        return bool(
            stored_hash
            and secrets.compare_digest(stored_hash, self._token_hash(csrf_token))
        )

    async def grant_knowledge_base(
        self,
        context: TenantContext,
        knowledge_base_id: str,
    ) -> None:
        async with self._engine.begin() as connection:
            await connection.execute(
                text(
                    """
                    INSERT INTO tenant_knowledge_bases
                        (organization_id, knowledge_base_id)
                    VALUES (:organization_id, :knowledge_base_id)
                    ON CONFLICT (knowledge_base_id) DO NOTHING
                    """
                ),
                {
                    "organization_id": context.organization.id,
                    "knowledge_base_id": knowledge_base_id,
                },
            )

    async def revoke_knowledge_base(
        self,
        context: TenantContext,
        knowledge_base_id: str,
    ) -> None:
        async with self._engine.begin() as connection:
            await connection.execute(
                text(
                    """
                    DELETE FROM tenant_knowledge_bases
                    WHERE organization_id = :organization_id
                      AND knowledge_base_id = :knowledge_base_id
                    """
                ),
                {
                    "organization_id": context.organization.id,
                    "knowledge_base_id": knowledge_base_id,
                },
            )

    async def can_access_knowledge_base(
        self,
        context: TenantContext,
        knowledge_base_id: str,
    ) -> bool:
        async with self._engine.connect() as connection:
            allowed = await connection.scalar(
                text(
                    """
                    SELECT EXISTS (
                        SELECT 1
                        FROM tenant_knowledge_bases
                        WHERE organization_id = :organization_id
                          AND knowledge_base_id = :knowledge_base_id
                    )
                    """
                ),
                {
                    "organization_id": context.organization.id,
                    "knowledge_base_id": knowledge_base_id,
                },
            )
        return bool(allowed)

    async def allowed_knowledge_base_ids(
        self,
        context: TenantContext,
    ) -> set[str]:
        async with self._engine.connect() as connection:
            rows = (
                await connection.execute(
                    text(
                        """
                        SELECT knowledge_base_id
                        FROM tenant_knowledge_bases
                        WHERE organization_id = :organization_id
                        """
                    ),
                    {"organization_id": context.organization.id},
                )
            ).scalars()
        return set(rows)

    async def domain_allowed(self, host: str) -> bool:
        normalized = _normalize_host(host)
        if normalized in {self._root_domain, f"app.{self._root_domain}"}:
            return True
        async with self._engine.connect() as connection:
            organization_id = await self._organization_for_host(connection, normalized)
        return organization_id is not None

    async def _organization_for_host(self, connection, host: str) -> str | None:
        normalized = _normalize_host(host)
        if normalized in {self._root_domain, f"app.{self._root_domain}"}:
            return None
        return await connection.scalar(
            text("SELECT organization_id FROM tenant_domains WHERE domain = :domain"),
            {"domain": normalized},
        )

    @staticmethod
    async def _insert_session(
        connection,
        *,
        token: str,
        csrf_token: str,
        user_id: str,
        expires_at: datetime,
    ) -> None:
        await connection.execute(
            text(
                """
                INSERT INTO auth_sessions
                    (token_hash, csrf_hash, user_id, expires_at)
                VALUES (:token_hash, :csrf_hash, :user_id, :expires_at)
                """
            ),
            {
                "token_hash": PostgresTenantAccess._token_hash(token),
                "csrf_hash": PostgresTenantAccess._token_hash(csrf_token),
                "user_id": user_id,
                "expires_at": expires_at,
            },
        )

    def _row_to_context(self, row) -> TenantContext:
        return TenantContext(
            user=TenantUser(id=row["user_id"], email=row["email"]),
            organization=Organization(
                id=row["organization_id"],
                name=row["organization_name"],
                slug=row["slug"],
                url=f"https://{row['slug']}.{self._root_domain}",
            ),
            role=row["role"],
        )

    @staticmethod
    def _token_hash(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()
