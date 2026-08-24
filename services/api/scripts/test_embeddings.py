from app.core.config import settings
from app.ingestion.embeddings import (
    get_embedding_service,
)


def main() -> None:
    service = get_embedding_service()

    text = (
        "ForgeOps is a production-oriented "
        "retrieval augmented generation platform."
    )

    passage = service.embed_passages(
        [text]
    )[0]

    query = service.embed_query(
        "What is ForgeOps?"
    )

    print(
        "Embedding model:",
        settings.embedding_model_name,
    )

    print(
        "Configured dimension:",
        settings.embedding_dimension,
    )

    print(
        "Passage dimension:",
        len(passage),
    )

    print(
        "Query dimension:",
        len(query),
    )

    assert (
        len(passage)
        == settings.embedding_dimension
    )

    assert (
        len(query)
        == settings.embedding_dimension
    )

    print(
        "Embedding smoke test passed."
    )


if __name__ == "__main__":
    main()