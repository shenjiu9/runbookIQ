import hashlib
import re

from runbookiq.domain.retrieval import DocumentChunk
from runbookiq.ingestion.parser import ParsedSection


class ParentChildChunker:
    def __init__(self, *, child_tokens: int = 180, overlap_tokens: int = 30) -> None:
        if overlap_tokens >= child_tokens:
            raise ValueError("overlap_tokens must be smaller than child_tokens")
        self._child_tokens = child_tokens
        self._overlap_tokens = overlap_tokens

    def chunk(
        self,
        *,
        source_id: str,
        source_url: str,
        sections: list[ParsedSection],
    ) -> list[DocumentChunk]:
        chunks: list[DocumentChunk] = []
        for section_index, section in enumerate(sections):
            tokens = re.findall(r"\S+", section.text)
            if not tokens:
                continue
            step = self._child_tokens - self._overlap_tokens
            for child_index, start in enumerate(range(0, len(tokens), step)):
                child_tokens = tokens[start : start + self._child_tokens]
                if not child_tokens:
                    continue
                text = " ".join(child_tokens)
                digest = hashlib.sha1(
                    f"{source_id}:{section_index}:{child_index}:{text}".encode()
                ).hexdigest()[:16]
                chunks.append(
                    DocumentChunk(
                        id=f"chunk-{digest}",
                        source_id=source_id,
                        title=section.title,
                        section_path=section.section_path,
                        text=text,
                        parent_text=section.text,
                        source_url=source_url,
                    )
                )
                if start + self._child_tokens >= len(tokens):
                    break
        return chunks

