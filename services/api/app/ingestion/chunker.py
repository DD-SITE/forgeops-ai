from __future__ import annotations

from dataclasses import dataclass

from app.ingestion.parsers import ParsedBlock


TARGET_CHARS = 1800
OVERLAP_CHARS = 250


@dataclass(frozen=True)
class ChunkDraft:
    chunk_index: int
    text: str
    page_start: int | None
    page_end: int | None
    section_path: list[str]


def _split_long_text(
    text: str,
    max_chars: int,
) -> list[str]:
    if len(text) <= max_chars:
        return [text]

    words = text.split()
    parts: list[str] = []
    current: list[str] = []
    current_length = 0

    for word in words:
        extra = len(word)
        if current:
            extra += 1

        if (
            current_length + extra > max_chars
            and current
        ):
            parts.append(" ".join(current))
            current = [word]
            current_length = len(word)
        else:
            current.append(word)
            current_length += extra

    if current:
        parts.append(" ".join(current))

    return parts


def chunk_blocks(
    blocks: list[ParsedBlock],
) -> list[ChunkDraft]:
    chunks: list[ChunkDraft] = []

    current_parts: list[str] = []
    current_page_start: int | None = None
    current_page_end: int | None = None
    current_section: tuple[str, ...] = ()

    def current_text() -> str:
        return "\n\n".join(
            current_parts
        ).strip()

    def flush() -> None:
        if not current_parts:
            return

        text = current_text()

        chunks.append(
            ChunkDraft(
                chunk_index=len(chunks),
                text=text,
                page_start=current_page_start,
                page_end=current_page_end,
                section_path=list(
                    current_section
                ),
            )
        )

    for block in blocks:
        section_changed = (
            current_parts
            and block.section_path
            != current_section
        )

        if section_changed:
            flush()

            overlap = (
                current_text()[-OVERLAP_CHARS:]
                if current_text()
                else ""
            )

            current_parts = (
                [overlap]
                if overlap
                else []
            )

            current_page_start = None
            current_page_end = None

        if not current_section:
            current_section = block.section_path

        pieces = _split_long_text(
            block.text,
            TARGET_CHARS,
        )

        for piece in pieces:
            candidate_parts = (
                current_parts + [piece]
            )

            candidate_text = "\n\n".join(
                candidate_parts
            ).strip()

            if (
                current_parts
                and len(candidate_text)
                > TARGET_CHARS
            ):
                flush()

                overlap = (
                    current_text()[-OVERLAP_CHARS:]
                    if current_text()
                    else ""
                )

                current_parts = (
                    [overlap, piece]
                    if overlap
                    else [piece]
                )

                current_page_start = (
                    block.page_start
                )
                current_page_end = (
                    block.page_end
                )

            else:
                current_parts = (
                    candidate_parts
                )

            if current_page_start is None:
                current_page_start = (
                    block.page_start
                )

            if block.page_end is not None:
                current_page_end = (
                    block.page_end
                )

    flush()

    return chunks