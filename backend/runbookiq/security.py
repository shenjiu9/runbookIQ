from __future__ import annotations

import asyncio
import hashlib
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Protocol

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


class RateLimitExceeded(RuntimeError):
    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__("rate limit exceeded")
        self.retry_after_seconds = max(1, retry_after_seconds)


class AbuseGuard(Protocol):
    async def enforce(
        self,
        *,
        action: str,
        scope: str,
        limit: int,
        window_seconds: int,
    ) -> None: ...


class TurnstileVerifier(Protocol):
    @property
    def enabled(self) -> bool: ...

    @property
    def required(self) -> bool: ...

    async def verify(
        self,
        *,
        token: str | None,
        remote_ip: str | None,
        action: str,
    ) -> bool: ...


@dataclass(frozen=True)
class UsageLimits:
    registration_per_hour: int = 3
    registration_global_per_hour: int = 30
    login_per_15_minutes: int = 10
    login_ip_per_15_minutes: int = 40
    invitation_preview_per_15_minutes: int = 30
    query_per_minute: int = 20
    query_per_day: int = 200
    upload_per_hour: int = 20
    upload_per_day: int = 50
    evaluation_per_hour: int = 10
    invitation_per_day: int = 20
    max_knowledge_bases: int = 5
    max_organization_members: int = 25
    max_batch_files: int = 10
    max_document_mib: int = 20

    def public_dict(self) -> dict[str, int]:
        return {
            "query_per_day": self.query_per_day,
            "upload_per_day": self.upload_per_day,
            "evaluation_per_hour": self.evaluation_per_hour,
            "max_knowledge_bases": self.max_knowledge_bases,
            "max_organization_members": self.max_organization_members,
            "max_batch_files": self.max_batch_files,
            "max_document_mib": self.max_document_mib,
        }


class InMemoryAbuseGuard:
    """Process-local sliding-window limiter for development and tests."""

    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def enforce(
        self,
        *,
        action: str,
        scope: str,
        limit: int,
        window_seconds: int,
    ) -> None:
        bucket = _bucket_key(action, scope)
        now = time.monotonic()
        cutoff = now - window_seconds
        async with self._lock:
            events = self._events[bucket]
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= limit:
                retry_after = int(max(1, window_seconds - (now - events[0])))
                raise RateLimitExceeded(retry_after)
            events.append(now)


class PostgresAbuseGuard:
    """Persistent limiter shared by every API process on the production database."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def enforce(
        self,
        *,
        action: str,
        scope: str,
        limit: int,
        window_seconds: int,
    ) -> None:
        bucket = _bucket_key(action, scope)
        lock_id = int.from_bytes(
            hashlib.sha256(bucket.encode("utf-8")).digest()[:8],
            byteorder="big",
            signed=True,
        )
        async with self._engine.begin() as connection:
            await connection.execute(
                text("SELECT pg_advisory_xact_lock(:lock_id)"),
                {"lock_id": lock_id},
            )
            await connection.execute(
                text(
                    """
                    DELETE FROM security_usage_events
                    WHERE bucket_key = :bucket
                      AND created_at <= CURRENT_TIMESTAMP
                          - (:window_seconds * INTERVAL '1 second')
                    """
                ),
                {
                    "bucket": bucket,
                    "window_seconds": window_seconds,
                },
            )
            count = (
                await connection.execute(
                    text(
                        """
                        SELECT count(*)
                        FROM security_usage_events
                        WHERE bucket_key = :bucket
                          AND created_at > CURRENT_TIMESTAMP
                              - (:window_seconds * INTERVAL '1 second')
                        """
                    ),
                    {
                        "bucket": bucket,
                        "window_seconds": window_seconds,
                    },
                )
            ).scalar_one()
            if count >= limit:
                raise RateLimitExceeded(window_seconds)
            await connection.execute(
                text(
                    """
                    INSERT INTO security_usage_events (bucket_key, action)
                    VALUES (:bucket, :action)
                    """
                ),
                {"bucket": bucket, "action": action},
            )


class DisabledTurnstileVerifier:
    enabled = False
    required = False

    async def verify(
        self,
        *,
        token: str | None,
        remote_ip: str | None,
        action: str,
    ) -> bool:
        return True


class CloudflareTurnstileVerifier:
    SITEVERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"

    def __init__(
        self,
        *,
        secret_key: str,
        expected_hostname: str,
        required: bool,
        timeout_seconds: float = 5,
    ) -> None:
        self._secret_key = secret_key
        self._expected_hostname = expected_hostname.lower().rstrip(".")
        self._required = required
        self._timeout_seconds = timeout_seconds

    @property
    def enabled(self) -> bool:
        return bool(self._secret_key)

    @property
    def required(self) -> bool:
        return self._required

    async def verify(
        self,
        *,
        token: str | None,
        remote_ip: str | None,
        action: str,
    ) -> bool:
        if not self.enabled:
            return not self.required
        if not token or len(token) > 2048:
            return False
        payload = {
            "secret": self._secret_key,
            "response": token,
        }
        if remote_ip:
            payload["remoteip"] = remote_ip
        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                response = await client.post(self.SITEVERIFY_URL, data=payload)
                response.raise_for_status()
                result = response.json()
        except (httpx.HTTPError, ValueError):
            return False
        if not result.get("success"):
            return False
        verified_action = result.get("action")
        if verified_action and verified_action != action:
            return False
        hostname = str(result.get("hostname") or "").lower().rstrip(".")
        return not (
            self._expected_hostname
            and hostname
            and hostname != self._expected_hostname
        )


def _bucket_key(action: str, scope: str) -> str:
    digest = hashlib.sha256(scope.encode("utf-8")).hexdigest()
    return f"{action}:{digest}"
