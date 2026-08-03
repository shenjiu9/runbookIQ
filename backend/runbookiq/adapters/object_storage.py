import asyncio
from pathlib import Path


class InMemoryDocumentStore:
    def __init__(self) -> None:
        self._objects: dict[str, tuple[bytes, str]] = {}

    async def put(self, key: str, content: bytes, content_type: str) -> None:
        self._objects[key] = (bytes(content), content_type)

    async def get(self, key: str) -> bytes:
        return self._objects[key][0]

    async def delete(self, key: str) -> None:
        self._objects.pop(key, None)


class FileSystemDocumentStore:
    """Durable single-server object store behind the document-storage seam."""

    def __init__(self, root: str | Path) -> None:
        self._root = Path(root).resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        target = (self._root / key).resolve()
        if target != self._root and self._root not in target.parents:
            raise ValueError("invalid document object key")
        return target

    async def put(self, key: str, content: bytes, content_type: str) -> None:
        del content_type
        target = self._path(key)

        def write() -> None:
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_suffix(f"{target.suffix}.tmp")
            temporary.write_bytes(content)
            temporary.replace(target)

        await asyncio.to_thread(write)

    async def get(self, key: str) -> bytes:
        return await asyncio.to_thread(self._path(key).read_bytes)

    async def delete(self, key: str) -> None:
        target = self._path(key)

        def remove() -> None:
            target.unlink(missing_ok=True)
            parent = target.parent
            while parent != self._root:
                try:
                    parent.rmdir()
                except OSError:
                    break
                parent = parent.parent

        await asyncio.to_thread(remove)
