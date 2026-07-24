import io
import re
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Protocol

import pypdfium2 as pdfium
import pytesseract
from docx import Document as open_docx
from docx.table import Table
from docx.text.paragraph import Paragraph
from PIL import Image
from pypdf import PdfReader


@dataclass(frozen=True)
class ParsedSection:
    title: str
    section_path: str
    text: str


class OcrEngine(Protocol):
    def extract_image(self, content: bytes) -> str: ...

    def extract_pdf(self, content: bytes) -> str: ...


class TesseractOcrEngine:
    def __init__(self, *, languages: str = "chi_sim+eng", timeout_seconds: int = 30) -> None:
        self._languages = languages
        self._timeout_seconds = timeout_seconds

    def extract_image(self, content: bytes) -> str:
        with Image.open(io.BytesIO(content)) as image:
            return pytesseract.image_to_string(
                image.convert("RGB"),
                lang=self._languages,
                timeout=self._timeout_seconds,
            ).strip()

    def extract_pdf(self, content: bytes) -> str:
        document = pdfium.PdfDocument(content)
        pages: list[str] = []
        try:
            for page in document:
                bitmap = page.render(scale=2)
                text = pytesseract.image_to_string(
                    bitmap.to_pil(),
                    lang=self._languages,
                    timeout=self._timeout_seconds,
                ).strip()
                if text:
                    pages.append(text)
        finally:
            document.close()
        return "\n\n".join(pages)


class DocumentParser:
    """Parses supported documents into heading-aware parent sections."""

    _IMAGE_SUFFIXES: ClassVar[set[str]] = {
        ".png",
        ".jpg",
        ".jpeg",
        ".webp",
        ".bmp",
        ".tif",
        ".tiff",
    }

    def __init__(self, *, ocr_engine: OcrEngine | None = None) -> None:
        self._ocr_engine = ocr_engine

    def parse(self, *, filename: str, content_type: str, content: bytes) -> list[ParsedSection]:
        suffix = Path(filename).suffix.lower()
        if suffix == ".docx" or content_type == (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ):
            return self._docx_sections(filename=filename, content=content)
        if content_type.startswith("image/") or suffix in self._IMAGE_SUFFIXES:
            if self._ocr_engine is None:
                raise ValueError("OCR is not configured for image documents")
            text = self._ocr_engine.extract_image(content)
        elif content_type == "application/pdf" or suffix == ".pdf":
            text = self._pdf_text(content)
            if not text.strip() and self._ocr_engine is not None:
                text = self._ocr_engine.extract_pdf(content)
        else:
            text = content.decode("utf-8", errors="replace")
        if suffix in {".md", ".markdown"} or content_type in {
            "text/markdown",
            "text/x-markdown",
        }:
            return self._markdown_sections(filename=filename, text=text)
        return self._plain_sections(filename=filename, text=text)

    @classmethod
    def _docx_sections(cls, *, filename: str, content: bytes) -> list[ParsedSection]:
        document = open_docx(io.BytesIO(content))
        lines: list[str] = []
        for block in document.iter_inner_content():
            if isinstance(block, Paragraph):
                text = block.text.strip()
                if not text:
                    continue
                match = re.match(r"Heading\s+([1-6])", block.style.name or "")
                lines.append(f"{'#' * int(match.group(1))} {text}" if match else text)
            elif isinstance(block, Table):
                for row in block.rows:
                    cells = [cell.text.strip() for cell in row.cells]
                    if any(cells):
                        lines.append(" | ".join(cells))
        return cls._markdown_sections(filename=filename, text="\n\n".join(lines))

    @staticmethod
    def _pdf_text(content: bytes) -> str:
        reader = PdfReader(io.BytesIO(content))
        return "\n\n".join(page.extract_text() or "" for page in reader.pages)

    @staticmethod
    def _plain_sections(*, filename: str, text: str) -> list[ParsedSection]:
        title = Path(filename).stem.replace("_", " ").replace("-", " ").strip() or "Untitled"
        paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
        if not paragraphs:
            return []
        return [
            ParsedSection(
                title=title,
                section_path=title,
                text="\n\n".join(paragraphs),
            )
        ]

    @staticmethod
    def _markdown_sections(*, filename: str, text: str) -> list[ParsedSection]:
        fallback_title = Path(filename).stem.replace("_", " ").replace("-", " ").strip()
        headings: list[str] = []
        document_title = fallback_title or "Untitled"
        current_lines: list[str] = []
        sections: list[ParsedSection] = []

        def flush() -> None:
            body = "\n".join(current_lines).strip()
            if not body:
                current_lines.clear()
                return
            path = " / ".join(headings) if headings else document_title
            sections.append(
                ParsedSection(
                    title=document_title,
                    section_path=path,
                    text=body,
                )
            )
            current_lines.clear()

        for line in text.splitlines():
            match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
            if not match:
                current_lines.append(line)
                continue
            flush()
            level = len(match.group(1))
            heading = match.group(2).strip().strip("#").strip()
            if level == 1:
                document_title = heading
            headings[level - 1 :] = [heading]

        flush()
        return sections
