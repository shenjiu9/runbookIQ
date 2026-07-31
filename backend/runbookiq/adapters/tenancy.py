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
    CreatedTenantInvitation,
    Organization,
    OrganizationBranding,
    OrganizationMember,
    TenantContext,
    TenantInvitation,
    TenantInvitationPreview,
    TenantRole,
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


def _internal_slug(organization_name: str, requested_slug: str | None) -> str:
    if requested_slug:
        normalized = requested_slug.strip().lower()
        if not SLUG_PATTERN.fullmatch(normalized):
            raise ValueError(
                "enterprise slug must contain lowercase letters, numbers or hyphens"
            )
        return normalized
    ascii_name = organization_name.casefold().encode("ascii", "ignore").decode()
    base = re.sub(r"[^a-z0-9]+", "-", ascii_name).strip("-") or "org"
    base = base[:22].rstrip("-") or "org"
    return f"{base}-{uuid4().hex[:8]}"


def _default_branding(organization_name: str) -> OrganizationBranding:
    return OrganizationBranding(
        display_name=organization_name.strip(),
        welcome_title=f"欢迎来到{organization_name.strip()}知识空间",
        welcome_message="从企业资料中检索答案，并通过原文证据核验每一项结论。",
    )


def _public_url(root_domain: str) -> str:
    return f"https://{root_domain}"


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
                branding=_default_branding("平台工程团队"),
            ),
            role="owner",
        )

    async def register(
        self,
        *,
        email: str,
        password: str,
        organization_name: str,
        slug: str | None,
    ) -> TenantSession:
        raise ValueError("registration is disabled in open development mode")

    async def authenticate(self, *, email: str, password: str) -> TenantSession:
        raise ValueError("login is disabled in open development mode")

    async def create_invitation(
        self,
        context: TenantContext,
        *,
        email: str,
        role: TenantRole,
    ) -> CreatedTenantInvitation:
        raise ValueError("invitations are disabled in open development mode")

    async def preview_invitation(self, token: str) -> TenantInvitationPreview:
        raise ValueError("invitation is invalid or expired")

    async def accept_invitation(self, *, token: str, password: str) -> TenantSession:
        raise ValueError("invitations are disabled in open development mode")

    async def list_members(self, context: TenantContext) -> list[OrganizationMember]:
        return [
            OrganizationMember(
                user_id=context.user.id,
                email=context.user.email,
                role=context.role,
                joined_at=datetime.now(UTC),
            )
        ]

    async def get_branding(
        self,
        context: TenantContext,
    ) -> OrganizationBranding:
        return context.organization.branding

    async def update_branding(
        self,
        context: TenantContext,
        branding: OrganizationBranding,
    ) -> OrganizationBranding:
        context.organization.branding = branding
        return branding

    async def list_invitations(
        self,
        context: TenantContext,
    ) -> list[TenantInvitation]:
        return []

    async def revoke_invitation(
        self,
        context: TenantContext,
        invitation_id: str,
    ) -> None:
        raise KeyError(invitation_id)

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
        self._membership_created_at: dict[str, datetime] = {}
        self._invitations_by_hash: dict[str, dict[str, object]] = {}

    async def register(
        self,
        *,
        email: str,
        password: str,
        organization_name: str,
        slug: str | None,
    ) -> TenantSession:
        normalized_email = email.strip().lower()
        normalized_slug = _internal_slug(organization_name, slug)
        if normalized_email in self._users_by_email:
            raise ValueError("email is already registered")
        if normalized_slug in self._organization_ids_by_slug:
            raise ValueError("enterprise slug is already in use")
        user_id = f"user-{uuid4().hex}"
        organization_id = f"org-{uuid4().hex}"
        organization = Organization(
            id=organization_id,
            name=organization_name.strip(),
            slug=normalized_slug,
            url=_public_url(self._root_domain),
            branding=_default_branding(organization_name),
        )
        self._users_by_email[normalized_email] = {
            "id": user_id,
            "email": normalized_email,
            "password_hash": _password_hash(password),
        }
        self._organizations_by_id[organization_id] = organization
        self._organization_ids_by_slug[normalized_slug] = organization_id
        self._memberships[user_id] = (organization_id, "owner")
        self._membership_created_at[user_id] = datetime.now(UTC)
        return self._new_session(user_id)

    async def authenticate(self, *, email: str, password: str) -> TenantSession:
        user = self._users_by_email.get(email.strip().lower())
        if user is None or not _password_matches(password, user["password_hash"]):
            raise ValueError("email or password is incorrect")
        return self._new_session(user["id"])

    async def create_invitation(
        self,
        context: TenantContext,
        *,
        email: str,
        role: TenantRole,
    ) -> CreatedTenantInvitation:
        normalized_email = email.strip().lower()
        if normalized_email in self._users_by_email:
            raise ValueError("该邮箱已经是系统用户")
        now = datetime.now(UTC)
        for invitation in self._invitations_by_hash.values():
            if (
                invitation["organization_id"] == context.organization.id
                and invitation["email"] == normalized_email
                and invitation["expires_at"] > now
            ):
                raise ValueError("该邮箱已有待接受邀请")
        token = secrets.token_urlsafe(32)
        invitation_id = f"invite-{uuid4().hex}"
        expires_at = now + timedelta(days=7)
        invitation = {
            "id": invitation_id,
            "organization_id": context.organization.id,
            "email": normalized_email,
            "role": role,
            "expires_at": expires_at,
            "created_at": now,
        }
        self._invitations_by_hash[self._token_hash(token)] = invitation
        return CreatedTenantInvitation(
            id=invitation_id,
            email=normalized_email,
            role=role,
            expires_at=expires_at,
            created_at=now,
            token=token,
            accept_url=f"{context.organization.url}/#invite={token}",
        )

    async def preview_invitation(self, token: str) -> TenantInvitationPreview:
        invitation = self._active_invitation(token)
        organization = self._organizations_by_id[str(invitation["organization_id"])]
        return TenantInvitationPreview(
            email=str(invitation["email"]),
            role=invitation["role"],
            organization_name=organization.name,
            organization_url=organization.url,
            expires_at=invitation["expires_at"],
        )

    async def accept_invitation(self, *, token: str, password: str) -> TenantSession:
        token_hash = self._token_hash(token)
        invitation = self._active_invitation(token)
        normalized_email = str(invitation["email"])
        if normalized_email in self._users_by_email:
            raise ValueError("该邮箱已经是系统用户")
        user_id = f"user-{uuid4().hex}"
        self._users_by_email[normalized_email] = {
            "id": user_id,
            "email": normalized_email,
            "password_hash": _password_hash(password),
        }
        self._memberships[user_id] = (
            str(invitation["organization_id"]),
            str(invitation["role"]),
        )
        self._membership_created_at[user_id] = datetime.now(UTC)
        self._invitations_by_hash.pop(token_hash, None)
        return self._new_session(user_id)

    async def list_members(self, context: TenantContext) -> list[OrganizationMember]:
        members = []
        for user_id, (organization_id, role) in self._memberships.items():
            if organization_id != context.organization.id:
                continue
            user = next(
                item for item in self._users_by_email.values() if item["id"] == user_id
            )
            members.append(
                OrganizationMember(
                    user_id=user_id,
                    email=user["email"],
                    role=role,
                    joined_at=self._membership_created_at[user_id],
                )
            )
        return sorted(members, key=lambda member: member.joined_at)

    async def get_branding(
        self,
        context: TenantContext,
    ) -> OrganizationBranding:
        return self._organizations_by_id[context.organization.id].branding

    async def update_branding(
        self,
        context: TenantContext,
        branding: OrganizationBranding,
    ) -> OrganizationBranding:
        self._organizations_by_id[context.organization.id].branding = branding
        return branding

    async def list_invitations(
        self,
        context: TenantContext,
    ) -> list[TenantInvitation]:
        now = datetime.now(UTC)
        return sorted(
            [
                TenantInvitation(
                    id=str(item["id"]),
                    email=str(item["email"]),
                    role=item["role"],
                    expires_at=item["expires_at"],
                    created_at=item["created_at"],
                )
                for item in self._invitations_by_hash.values()
                if item["organization_id"] == context.organization.id
                and item["expires_at"] > now
            ],
            key=lambda invitation: invitation.created_at,
        )

    async def revoke_invitation(
        self,
        context: TenantContext,
        invitation_id: str,
    ) -> None:
        for token_hash, invitation in list(self._invitations_by_hash.items()):
            if (
                invitation["id"] == invitation_id
                and invitation["organization_id"] == context.organization.id
            ):
                self._invitations_by_hash.pop(token_hash)
                return
        raise KeyError(invitation_id)

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

    def _active_invitation(self, token: str) -> dict[str, object]:
        invitation = self._invitations_by_hash.get(self._token_hash(token))
        if invitation is None or invitation["expires_at"] <= datetime.now(UTC):
            raise ValueError("邀请链接无效或已过期")
        return invitation

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
        slug: str | None,
    ) -> TenantSession:
        normalized_email = email.strip().lower()
        normalized_slug = _internal_slug(organization_name, slug)
        branding = _default_branding(organization_name)

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
                        INSERT INTO organizations (
                            id, name, slug, display_name, primary_color,
                            welcome_title, welcome_message
                        )
                        VALUES (
                            :id, :name, :slug, :display_name, :primary_color,
                            :welcome_title, :welcome_message
                        )
                        """
                    ),
                    {
                        "id": organization_id,
                        "name": organization_name.strip(),
                        "slug": normalized_slug,
                        "display_name": branding.display_name,
                        "primary_color": branding.primary_color,
                        "welcome_title": branding.welcome_title,
                        "welcome_message": branding.welcome_message,
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
                    url=_public_url(self._root_domain),
                    branding=branding,
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
                COALESCE(o.display_name, o.name) AS display_name,
                o.logo_url,
                o.primary_color,
                o.welcome_title,
                o.welcome_message,
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

    async def create_invitation(
        self,
        context: TenantContext,
        *,
        email: str,
        role: TenantRole,
    ) -> CreatedTenantInvitation:
        normalized_email = email.strip().lower()
        token = secrets.token_urlsafe(32)
        invitation_id = f"invite-{uuid4().hex}"
        expires_at = datetime.now(UTC) + timedelta(days=7)
        try:
            async with self._engine.begin() as connection:
                existing_user = await connection.scalar(
                    text("SELECT EXISTS (SELECT 1 FROM users WHERE email = :email)"),
                    {"email": normalized_email},
                )
                if existing_user:
                    raise ValueError("该邮箱已经是系统用户")
                await connection.execute(
                    text(
                        """
                        DELETE FROM organization_invitations
                        WHERE organization_id = :organization_id
                          AND accepted_at IS NULL
                          AND revoked_at IS NULL
                          AND expires_at <= now()
                        """
                    ),
                    {"organization_id": context.organization.id},
                )
                await connection.execute(
                    text(
                        """
                        INSERT INTO organization_invitations (
                            id, organization_id, email, role, token_hash,
                            invited_by, expires_at
                        )
                        VALUES (
                            :id, :organization_id, :email, :role, :token_hash,
                            :invited_by, :expires_at
                        )
                        """
                    ),
                    {
                        "id": invitation_id,
                        "organization_id": context.organization.id,
                        "email": normalized_email,
                        "role": role,
                        "token_hash": self._token_hash(token),
                        "invited_by": context.user.id,
                        "expires_at": expires_at,
                    },
                )
        except IntegrityError as exc:
            raise ValueError("该邮箱已有待接受邀请") from exc
        return CreatedTenantInvitation(
            id=invitation_id,
            email=normalized_email,
            role=role,
            expires_at=expires_at,
            created_at=datetime.now(UTC),
            token=token,
            accept_url=f"{context.organization.url}/#invite={token}",
        )

    async def preview_invitation(self, token: str) -> TenantInvitationPreview:
        async with self._engine.connect() as connection:
            row = (
                await connection.execute(
                    text(
                        """
                        SELECT
                            i.email,
                            i.role,
                            i.expires_at,
                            o.name AS organization_name,
                            o.slug
                        FROM organization_invitations i
                        JOIN organizations o ON o.id = i.organization_id
                        WHERE i.token_hash = :token_hash
                          AND i.accepted_at IS NULL
                          AND i.revoked_at IS NULL
                          AND i.expires_at > now()
                        """
                    ),
                    {"token_hash": self._token_hash(token)},
                )
            ).mappings().one_or_none()
        if row is None:
            raise ValueError("邀请链接无效或已过期")
        return TenantInvitationPreview(
            email=row["email"],
            role=row["role"],
            organization_name=row["organization_name"],
            organization_url=_public_url(self._root_domain),
            expires_at=row["expires_at"],
        )

    async def accept_invitation(self, *, token: str, password: str) -> TenantSession:
        token_hash = self._token_hash(token)
        user_id = f"user-{uuid4().hex}"
        session_token = secrets.token_urlsafe(32)
        csrf_token = secrets.token_urlsafe(32)
        try:
            async with self._engine.begin() as connection:
                row = (
                    await connection.execute(
                        text(
                            """
                            SELECT
                                i.id,
                                i.organization_id,
                                i.email,
                                i.role,
                                o.name AS organization_name,
                                o.slug,
                                COALESCE(o.display_name, o.name) AS display_name,
                                o.logo_url,
                                o.primary_color,
                                o.welcome_title,
                                o.welcome_message
                            FROM organization_invitations i
                            JOIN organizations o ON o.id = i.organization_id
                            WHERE i.token_hash = :token_hash
                              AND i.accepted_at IS NULL
                              AND i.revoked_at IS NULL
                              AND i.expires_at > now()
                            FOR UPDATE
                            """
                        ),
                        {"token_hash": token_hash},
                    )
                ).mappings().one_or_none()
                if row is None:
                    raise ValueError("邀请链接无效或已过期")
                await connection.execute(
                    text(
                        """
                        INSERT INTO users (id, email, password_hash)
                        VALUES (:id, :email, :password_hash)
                        """
                    ),
                    {
                        "id": user_id,
                        "email": row["email"],
                        "password_hash": _password_hash(password),
                    },
                )
                await connection.execute(
                    text(
                        """
                        INSERT INTO organization_memberships
                            (organization_id, user_id, role)
                        VALUES (:organization_id, :user_id, :role)
                        """
                    ),
                    {
                        "organization_id": row["organization_id"],
                        "user_id": user_id,
                        "role": row["role"],
                    },
                )
                await connection.execute(
                    text(
                        """
                        UPDATE organization_invitations
                        SET accepted_at = now()
                        WHERE id = :id
                        """
                    ),
                    {"id": row["id"]},
                )
                await self._insert_session(
                    connection,
                    token=session_token,
                    csrf_token=csrf_token,
                    user_id=user_id,
                    expires_at=datetime.now(UTC) + self._session_lifetime,
                )
        except IntegrityError as exc:
            raise ValueError("该邮箱已经是系统用户") from exc
        context = TenantContext(
            user=TenantUser(id=user_id, email=row["email"]),
            organization=Organization(
                id=row["organization_id"],
                name=row["organization_name"],
                slug=row["slug"],
                url=_public_url(self._root_domain),
                branding=self._row_to_branding(row, row["organization_name"]),
            ),
            role=row["role"],
        )
        return TenantSession(
            context=context,
            token=session_token,
            csrf_token=csrf_token,
        )

    async def list_members(self, context: TenantContext) -> list[OrganizationMember]:
        async with self._engine.connect() as connection:
            rows = (
                await connection.execute(
                    text(
                        """
                        SELECT
                            u.id AS user_id,
                            u.email,
                            m.role,
                            m.created_at AS joined_at
                        FROM organization_memberships m
                        JOIN users u ON u.id = m.user_id
                        WHERE m.organization_id = :organization_id
                          AND u.is_active = true
                        ORDER BY m.created_at
                        """
                    ),
                    {"organization_id": context.organization.id},
                )
            ).mappings().all()
        return [OrganizationMember.model_validate(row) for row in rows]

    async def get_branding(
        self,
        context: TenantContext,
    ) -> OrganizationBranding:
        async with self._engine.connect() as connection:
            row = (
                await connection.execute(
                    text(
                        """
                        SELECT
                            COALESCE(display_name, name) AS display_name,
                            logo_url,
                            primary_color,
                            welcome_title,
                            welcome_message
                        FROM organizations
                        WHERE id = :organization_id
                        """
                    ),
                    {"organization_id": context.organization.id},
                )
            ).mappings().one()
        return self._row_to_branding(row, context.organization.name)

    async def update_branding(
        self,
        context: TenantContext,
        branding: OrganizationBranding,
    ) -> OrganizationBranding:
        async with self._engine.begin() as connection:
            await connection.execute(
                text(
                    """
                    UPDATE organizations
                    SET display_name = :display_name,
                        logo_url = :logo_url,
                        primary_color = :primary_color,
                        welcome_title = :welcome_title,
                        welcome_message = :welcome_message
                    WHERE id = :organization_id
                    """
                ),
                {
                    "organization_id": context.organization.id,
                    **branding.model_dump(),
                },
            )
        return branding

    async def list_invitations(
        self,
        context: TenantContext,
    ) -> list[TenantInvitation]:
        async with self._engine.connect() as connection:
            rows = (
                await connection.execute(
                    text(
                        """
                        SELECT id, email, role, expires_at, created_at
                        FROM organization_invitations
                        WHERE organization_id = :organization_id
                          AND accepted_at IS NULL
                          AND revoked_at IS NULL
                          AND expires_at > now()
                        ORDER BY created_at
                        """
                    ),
                    {"organization_id": context.organization.id},
                )
            ).mappings().all()
        return [TenantInvitation.model_validate(row) for row in rows]

    async def revoke_invitation(
        self,
        context: TenantContext,
        invitation_id: str,
    ) -> None:
        async with self._engine.begin() as connection:
            result = await connection.execute(
                text(
                    """
                    UPDATE organization_invitations
                    SET revoked_at = now()
                    WHERE id = :id
                      AND organization_id = :organization_id
                      AND accepted_at IS NULL
                      AND revoked_at IS NULL
                    """
                ),
                {
                    "id": invitation_id,
                    "organization_id": context.organization.id,
                },
            )
        if result.rowcount == 0:
            raise KeyError(invitation_id)

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
                COALESCE(o.display_name, o.name) AS display_name,
                o.logo_url,
                o.primary_color,
                o.welcome_title,
                o.welcome_message,
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
                url=_public_url(self._root_domain),
                branding=self._row_to_branding(row, row["organization_name"]),
            ),
            role=row["role"],
        )

    @staticmethod
    def _row_to_branding(row, organization_name: str) -> OrganizationBranding:
        defaults = _default_branding(organization_name)
        return OrganizationBranding(
            display_name=row.get("display_name") or defaults.display_name,
            logo_url=row.get("logo_url"),
            primary_color=row.get("primary_color") or defaults.primary_color,
            welcome_title=row.get("welcome_title") or defaults.welcome_title,
            welcome_message=row.get("welcome_message") or defaults.welcome_message,
        )

    @staticmethod
    def _token_hash(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()
