from uuid import uuid4

from app.ingestion.chunker import chunk_blocks
from app.ingestion.parsers import (
    ParsedBlock,
    parse_markdown,
    parse_text,
)
from app.ingestion.pipeline import (
    IngestionPipeline,
)


def test_markdown_parser_preserves_sections():
    data = b"""
# Architecture

ForgeOps is a RAG platform.

## Authentication

Clerk authenticates users.

## Storage

MinIO stores documents.
"""

    blocks = parse_markdown(data)

    assert len(blocks) >= 3

    architecture = blocks[0]
    authentication = next(block for block in blocks if block.text == "Authentication")

    assert architecture.section_path == ("Architecture",)

    assert authentication.section_path == (
        "Architecture",
        "Authentication",
    )


def test_text_parser_extracts_content():
    blocks = parse_text(b"Hello ForgeOps.\n\nThis is a test document.")

    assert len(blocks) == 1
    assert "Hello ForgeOps." in blocks[0].text


def test_chunker_creates_overlapping_chunks():
    blocks = [
        ParsedBlock(
            text=("word " * 500),
            page_start=1,
            page_end=1,
            section_path=("Architecture",),
        ),
    ]

    chunks = chunk_blocks(blocks)

    assert len(chunks) > 1

    assert all(chunk.section_path == ["Architecture"] for chunk in chunks)


class FakeEmbeddingService:
    def embed_passages(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        return [[0.0] * 384 for _ in texts]

    def token_counts(
        self,
        texts: list[str],
    ) -> list[int]:
        return [len(text.split()) for text in texts]


def test_pipeline_builds_vector_chunks():
    parser = __import__(
        "app.ingestion.parsers",
        fromlist=["DocumentParser"],
    ).DocumentParser()

    pipeline = IngestionPipeline(
        parser=parser,
        embedding_service=FakeEmbeddingService(),
    )

    chunks = pipeline.build_chunks(
        filename="test.md",
        content_type="text/markdown",
        data=(b"# Test\n\nForgeOps is a production-grade RAG system."),
        document_version_id=uuid4(),
    )

    assert chunks
    assert chunks[0].embedding
    assert len(chunks[0].embedding) == 384
    assert chunks[0].content_hash
