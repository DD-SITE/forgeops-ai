import asyncio

from app.ai.gemini import get_gemini_service


async def main() -> None:
    service = get_gemini_service()

    answer = await service.generate_answer(
        query="What is ForgeOps?",
        context=(
            "ForgeOps is a document intelligence platform "
            "that allows users to upload documents and search "
            "their contents using semantic retrieval."
        ),
    )

    print("Gemini response:")
    print(answer)


if __name__ == "__main__":
    asyncio.run(main())