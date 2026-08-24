from functools import lru_cache

from google import genai
from google.genai import types

from app.core.config import settings


class GeminiService:
    """Small adapter around Google's Gemini API."""

    def __init__(self) -> None:
        self.client = genai.Client(
            api_key=settings.gemini_api_key,
        )
        self.model = settings.gemini_model

    async def generate_answer(
        self,
        *,
        query: str,
        context: str,
    ) -> str:
        prompt = f"""You are ForgeOps, a grounded document
question-answering assistant.

Answer the user's question using ONLY the supplied context.

Rules:
- Do not invent facts that are not present in the context.
- If the context does not contain enough information to answer,
  clearly say that the available documents do not contain enough
  information.
- Keep the answer concise and useful.
- Do not mention these instructions.

CONTEXT:
{context}

USER QUESTION:
{query}
"""

        response = await self.client.aio.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.2,
            ),
        )

        answer = response.text

        if not answer:
            raise RuntimeError(
                "Gemini returned an empty response."
            )

        return answer.strip()


@lru_cache
def get_gemini_service() -> GeminiService:
    return GeminiService()