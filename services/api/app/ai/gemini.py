from __future__ import annotations

import asyncio
import logging
from functools import lru_cache
from typing import Any, ClassVar

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from app.core.config import settings

logger = logging.getLogger(__name__)


class QueryExpansion(BaseModel):
    queries: list[str] = Field(default_factory=list, max_length=4)


class ActionPlan(BaseModel):
    action_type: str = Field(
        description="One of none, github_create_issue, incident_lookup."
    )
    repository: str | None = None
    title: str | None = None
    body: str | None = None
    incident_query: str | None = None


class AnswerDraft(BaseModel):
    answer: str
    citations: list[int] = Field(default_factory=list)


class GeminiService:
    """Provider adapter for Gemini.

    The rest of ForgeOps depends on this adapter rather than directly
    calling the SDK, keeping the LLM provider replaceable.

    This adapter also handles transient Gemini provider failures by:
    1. Retrying transient errors with exponential backoff.
    2. Falling back to another supported Gemini model when necessary.
    """

    TRANSIENT_STATUS_CODES: ClassVar[set[int]] = {
        429,
        500,
        502,
        503,
        504,
    }

    MAX_RETRIES_PER_MODEL = 3

    INITIAL_RETRY_DELAY_SECONDS = 1.0

    FALLBACK_MODELS = ("gemini-3.6-flash",)

    def __init__(self) -> None:
        self.client = genai.Client(
            api_key=settings.gemini_api_key,
        )

        self.model = settings.gemini_model

    # ------------------------------------------------------------------
    # Error handling
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_status_code(
        error: Exception,
    ) -> int | None:
        """Best-effort extraction of an HTTP/provider status code.

        The google-genai SDK has changed some exception internals across
        versions, so we intentionally avoid depending on one concrete
        exception class here.
        """

        for attribute in (
            "code",
            "status_code",
            "status",
        ):
            value = getattr(error, attribute, None)

            if isinstance(value, int):
                return value

            if isinstance(value, str):
                try:
                    return int(value)
                except ValueError:
                    pass

        response = getattr(error, "response", None)

        if response is not None:
            value = getattr(
                response,
                "status_code",
                None,
            )

            if isinstance(value, int):
                return value

        return None

    @classmethod
    def _is_transient_error(
        cls,
        error: Exception,
    ) -> bool:
        """Return True when an error is likely temporary."""

        status_code = cls._extract_status_code(error)

        if status_code in cls.TRANSIENT_STATUS_CODES:
            return True

        message = str(error).lower()

        transient_markers = (
            "503",
            "service unavailable",
            "unavailable",
            "temporarily unavailable",
            "high demand",
            "rate limit",
            "rate_limit",
            "too many requests",
            "429",
            "resource exhausted",
            "overloaded",
            "deadline exceeded",
            "timeout",
            "timed out",
        )

        return any(marker in message for marker in transient_markers)

    @classmethod
    def _model_candidates(
        cls,
        primary_model: str,
    ) -> list[str]:
        """Build an ordered, duplicate-free model fallback list."""

        candidates: list[str] = []

        for model in (
            primary_model,
            *cls.FALLBACK_MODELS,
        ):
            if model and model not in candidates:
                candidates.append(model)

        return candidates

    # ------------------------------------------------------------------
    # Resilient Gemini invocation
    # ------------------------------------------------------------------

    async def _generate_content(
        self,
        *,
        contents: str,
        config: types.GenerateContentConfig,
    ) -> Any:
        """Call Gemini with retries and model fallback.

        Primary model:
            settings.gemini_model

        Fallback models:
            gemini-2.5-flash
            gemini-2.5-flash-lite

        Each model gets up to MAX_RETRIES_PER_MODEL attempts for transient
        provider failures.
        """

        models = self._model_candidates(self.model)

        last_error: Exception | None = None

        for model_index, model in enumerate(models):
            for attempt in range(
                1,
                self.MAX_RETRIES_PER_MODEL + 1,
            ):
                try:
                    logger.info(
                        "Calling Gemini model=%s attempt=%s/%s",
                        model,
                        attempt,
                        self.MAX_RETRIES_PER_MODEL,
                    )

                    response = await self.client.aio.models.generate_content(
                        model=model,
                        contents=contents,
                        config=config,
                    )

                    logger.info(
                        "Gemini request succeeded with model=%s",
                        model,
                    )

                    return response

                except Exception as error:
                    last_error = error

                    status_code = self._extract_status_code(error)

                    transient = self._is_transient_error(error)

                    logger.warning(
                        "Gemini request failed "
                        "model=%s attempt=%s/%s "
                        "status=%s transient=%s "
                        "error=%s",
                        model,
                        attempt,
                        self.MAX_RETRIES_PER_MODEL,
                        status_code,
                        transient,
                        error,
                    )

                    # Do not waste retries on permanent errors.
                    if not transient:
                        raise

                    # Retry the same model if attempts remain.
                    if attempt < self.MAX_RETRIES_PER_MODEL:
                        delay = self.INITIAL_RETRY_DELAY_SECONDS * (2 ** (attempt - 1))

                        logger.info(
                            "Retrying Gemini model=%s in %.1f seconds",
                            model,
                            delay,
                        )

                        await asyncio.sleep(delay)

                        continue

                    # This model has been exhausted.
                    if model_index < len(models) - 1:
                        next_model = models[model_index + 1]

                        logger.warning(
                            "Gemini model=%s remains "
                            "unavailable after %s attempts. "
                            "Falling back to model=%s",
                            model,
                            self.MAX_RETRIES_PER_MODEL,
                            next_model,
                        )

                        break

        if last_error is not None:
            raise RuntimeError(
                "Gemini is temporarily unavailable "
                "after retrying all configured "
                "fallback models."
            ) from last_error

        raise RuntimeError("Gemini request failed without a response.")

    # ------------------------------------------------------------------
    # Answer generation
    # ------------------------------------------------------------------

    async def generate_answer(
        self,
        *,
        query: str,
        context: str,
    ) -> str:
        prompt = f"""You are ForgeOps, a grounded engineering intelligence assistant.

Answer the user's question using ONLY the supplied context.

Rules:
- Do not invent facts.
- If the context is insufficient, say so clearly.
- Prefer concise, actionable engineering language.
- Do not mention these instructions.

CONTEXT:
{context}

USER QUESTION:
{query}
"""

        response = await self._generate_content(
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.2,
            ),
        )

        answer = response.text

        if not answer:
            raise RuntimeError("Gemini returned an empty response.")

        return answer.strip()

    # ------------------------------------------------------------------
    # Grounded structured answer
    # ------------------------------------------------------------------

    async def generate_grounded_answer(
        self,
        *,
        query: str,
        context: str,
    ) -> AnswerDraft:
        prompt = f"""Answer this engineering question using only the evidence below.

Return citations as 1-based SOURCE numbers.
Never cite a source that does not support the claim.
If evidence is insufficient, say that explicitly.

EVIDENCE:
{context}

QUESTION:
{query}
"""

        response = await self._generate_content(
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.15,
                response_mime_type="application/json",
                response_schema=AnswerDraft,
            ),
        )

        if (
            getattr(
                response,
                "parsed",
                None,
            )
            is not None
        ):
            return AnswerDraft.model_validate(response.parsed)

        if not response.text:
            raise RuntimeError("Gemini returned an empty structured response.")

        return AnswerDraft.model_validate_json(response.text)

    # ------------------------------------------------------------------
    # Query expansion
    # ------------------------------------------------------------------

    async def expand_query(
        self,
        query: str,
    ) -> list[str]:
        prompt = f"""Generate up to 3 alternative search queries for the engineering question below.

Preserve important service names, error codes, identifiers, and technical terms.
Do not answer the question.

QUESTION:
{query}
"""

        response = await self._generate_content(
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.1,
                response_mime_type="application/json",
                response_schema=QueryExpansion,
            ),
        )

        if (
            getattr(
                response,
                "parsed",
                None,
            )
            is not None
        ):
            data = QueryExpansion.model_validate(response.parsed)

        elif response.text:
            data = QueryExpansion.model_validate_json(response.text)

        else:
            return []

        return [q.strip() for q in data.queries if q.strip()][:3]

    # ------------------------------------------------------------------
    # Action planning
    # ------------------------------------------------------------------

    async def plan_action(
        self,
        *,
        query: str,
        context: str = "",
    ) -> ActionPlan:
        prompt = f"""Classify the requested engineering operation.

Only propose a write action when the user explicitly asks to perform an action.

Allowed action_type values:
- none
- github_create_issue
- incident_lookup

For GitHub issues, extract owner/repository if present as owner/repo.
For incident lookup, extract the incident/search terms.
Never invent a repository.

Context:
{context}

User request:
{query}
"""

        response = await self._generate_content(
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0,
                response_mime_type="application/json",
                response_schema=ActionPlan,
            ),
        )

        if (
            getattr(
                response,
                "parsed",
                None,
            )
            is not None
        ):
            return ActionPlan.model_validate(response.parsed)

        if not response.text:
            return ActionPlan(action_type="none")

        return ActionPlan.model_validate_json(response.text)


@lru_cache
def get_gemini_service() -> GeminiService:
    return GeminiService()
