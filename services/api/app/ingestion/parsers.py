from __future__ import annotations

import re
from dataclasses import dataclass
from io import BytesIO

import pymupdf
from docx import Document as DocxDocument


@dataclass(frozen=True)
class ParsedBlock:
    text: str
    page_start: int | None
    page_end: int | None
    section_path: tuple[str, ...]


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    lines = [line.rstrip() for line in text.splitlines()]

    normalized = "\n".join(lines)

    normalized = re.sub(
        r"\n{3,}",
        "\n\n",
        normalized,
    )

    return normalized.strip()


def parse_pdf(data: bytes) -> list[ParsedBlock]:
    blocks: list[ParsedBlock] = []

    with pymupdf.open(
        stream=data,
        filetype="pdf",
    ) as document:
        for page_number, page in enumerate(
            document,
            start=1,
        ):
            text = normalize_text(
                page.get_text(
                    "text",
                    sort=True,
                )
            )

            if not text:
                continue

            blocks.append(
                ParsedBlock(
                    text=text,
                    page_start=page_number,
                    page_end=page_number,
                    section_path=(),
                )
            )

    if not blocks:
        raise ValueError(
            "The PDF contains no extractable text. "
            "OCR for image-only PDFs will be added "
            "as a later ingestion capability."
        )

    return blocks


def _heading_level(style_name: str) -> int | None:
    match = re.fullmatch(
        r"Heading ([1-9])",
        style_name.strip(),
    )

    if match is None:
        return None

    return int(match.group(1))


def parse_docx(data: bytes) -> list[ParsedBlock]:
    document = DocxDocument(BytesIO(data))

    blocks: list[ParsedBlock] = []
    section_stack: list[str] = []

    for paragraph in document.paragraphs:
        text = normalize_text(
            paragraph.text,
        )

        if not text:
            continue

        level = _heading_level(
            paragraph.style.name,
        )

        if level is not None:
            section_stack = section_stack[: level - 1]
            section_stack.append(text)

            blocks.append(
                ParsedBlock(
                    text=text,
                    page_start=None,
                    page_end=None,
                    section_path=tuple(section_stack),
                )
            )

            continue

        blocks.append(
            ParsedBlock(
                text=text,
                page_start=None,
                page_end=None,
                section_path=tuple(section_stack),
            )
        )

    if not blocks:
        raise ValueError("The DOCX contains no extractable text.")

    return blocks


def parse_markdown(data: bytes) -> list[ParsedBlock]:
    text = data.decode(
        "utf-8",
        errors="replace",
    )

    lines = (
        text.replace(
            "\r\n",
            "\n",
        )
        .replace(
            "\r",
            "\n",
        )
        .splitlines()
    )

    blocks: list[ParsedBlock] = []
    section_stack: list[str] = []
    buffer: list[str] = []

    def flush_buffer() -> None:
        if not buffer:
            return

        block_text = normalize_text("\n".join(buffer))

        if block_text:
            blocks.append(
                ParsedBlock(
                    text=block_text,
                    page_start=None,
                    page_end=None,
                    section_path=tuple(section_stack),
                )
            )

        buffer.clear()

    for line in lines:
        heading = re.match(
            r"^(#{1,6})\s+(.+?)\s*$",
            line,
        )

        if heading:
            flush_buffer()

            level = len(heading.group(1))
            title = heading.group(2).strip()

            section_stack = section_stack[: level - 1]
            section_stack.append(title)

            blocks.append(
                ParsedBlock(
                    text=title,
                    page_start=None,
                    page_end=None,
                    section_path=tuple(section_stack),
                )
            )

            continue

        if line.strip() == "":
            flush_buffer()
            continue

        buffer.append(line)

    flush_buffer()

    if not blocks:
        raise ValueError("The Markdown document contains no extractable text.")

    return blocks


def parse_text(data: bytes) -> list[ParsedBlock]:
    text = data.decode(
        "utf-8",
        errors="replace",
    )

    text = normalize_text(text)

    if not text:
        raise ValueError("The text document is empty.")

    return [
        ParsedBlock(
            text=text,
            page_start=None,
            page_end=None,
            section_path=(),
        )
    ]


class DocumentParser:
    def parse(
        self,
        *,
        filename: str,
        content_type: str,
        data: bytes,
    ) -> list[ParsedBlock]:
        filename_lower = filename.lower()

        if filename_lower.endswith(".pdf"):
            return parse_pdf(data)

        if filename_lower.endswith(".docx"):
            return parse_docx(data)

        if filename_lower.endswith(".md"):
            return parse_markdown(data)

        if filename_lower.endswith(".txt"):
            return parse_text(data)

        raise ValueError(f"Unsupported document format: {filename}")
