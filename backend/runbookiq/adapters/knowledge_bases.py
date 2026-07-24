from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from runbookiq.domain.models import KnowledgeBase


def _now() -> str:
    return datetime.now(UTC).isoformat()


class InMemoryKnowledgeBaseCatalog:
    def __init__(self) -> None:
        platform = KnowledgeBase(
            id="platform",
            name="平台工程知识库",
            description="Kubernetes、运行手册与事故复盘",
            created_at=_now(),
        )
        self._items: dict[str, KnowledgeBase] = {platform.id: platform}

    async def create(self, *, name: str, description: str) -> KnowledgeBase:
        knowledge_base = KnowledgeBase(
            id=f"kb-{uuid4().hex[:12]}",
            name=name,
            description=description,
            created_at=_now(),
        )
        self._items[knowledge_base.id] = knowledge_base
        return knowledge_base

    async def list(self) -> list[KnowledgeBase]:
        return sorted(self._items.values(), key=lambda item: (item.created_at, item.id))

    async def get(self, knowledge_base_id: str) -> KnowledgeBase:
        return self._items[knowledge_base_id]

    async def delete(self, knowledge_base_id: str) -> None:
        if knowledge_base_id == "platform":
            raise ValueError("默认知识库不能删除")
        del self._items[knowledge_base_id]


class PostgresKnowledgeBaseCatalog:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def create(self, *, name: str, description: str) -> KnowledgeBase:
        knowledge_base_id = f"kb-{uuid4().hex[:12]}"
        statement = text(
            """
            INSERT INTO knowledge_bases (id, name, description)
            VALUES (:id, :name, :description)
            RETURNING id, name, description, created_at
            """
        )
        async with self._engine.begin() as connection:
            row = (
                await connection.execute(
                    statement,
                    {
                        "id": knowledge_base_id,
                        "name": name,
                        "description": description,
                    },
                )
            ).mappings().one()
        return self._to_model(row)

    async def list(self) -> list[KnowledgeBase]:
        statement = text(
            """
            SELECT id, name, description, created_at
            FROM knowledge_bases
            ORDER BY created_at, id
            """
        )
        async with self._engine.connect() as connection:
            rows = (await connection.execute(statement)).mappings().all()
        return [self._to_model(row) for row in rows]

    async def get(self, knowledge_base_id: str) -> KnowledgeBase:
        statement = text(
            """
            SELECT id, name, description, created_at
            FROM knowledge_bases
            WHERE id = :id
            """
        )
        async with self._engine.connect() as connection:
            row = (
                await connection.execute(statement, {"id": knowledge_base_id})
            ).mappings().one_or_none()
        if row is None:
            raise KeyError(knowledge_base_id)
        return self._to_model(row)

    async def delete(self, knowledge_base_id: str) -> None:
        if knowledge_base_id == "platform":
            raise ValueError("默认知识库不能删除")
        statement = text(
            "DELETE FROM knowledge_bases WHERE id = :id RETURNING id"
        )
        async with self._engine.begin() as connection:
            deleted = (
                await connection.execute(statement, {"id": knowledge_base_id})
            ).scalar_one_or_none()
        if deleted is None:
            raise KeyError(knowledge_base_id)

    @staticmethod
    def _to_model(row: dict) -> KnowledgeBase:
        created_at = row["created_at"]
        return KnowledgeBase(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            created_at=(
                created_at.isoformat()
                if hasattr(created_at, "isoformat")
                else str(created_at)
            ),
        )
