import asyncio
import os
import sys

from app.ai.gemini import GeminiService


async def main() -> None:
    if not os.getenv("GEMINI_API_KEY"):
        print("ERROR: GEMINI_API_KEY is not set.")
        sys.exit(1)

    service = GeminiService()

    print("=" * 60)
    print("ForgeOps Gemini smoke test")
    print("=" * 60)

    print(f"Configured model: {service.model}")
    print()

    print("Testing basic Gemini generation...")

    answer = await service.generate_answer(
        query="What is a health check endpoint?",
        context=(
            "A health check endpoint is an HTTP endpoint used by "
            "infrastructure to determine whether an application is "
            "running and able to serve requests."
        ),
    )

    if not answer:
        raise RuntimeError(
            "Gemini returned an empty answer."
        )

    print()
    print("Gemini response:")
    print("-" * 60)
    print(answer)
    print("-" * 60)

    print()
    print("SUCCESS: Gemini smoke test passed.")


if __name__ == "__main__":
    asyncio.run(main())