from __future__ import annotations

from typing import Any, TypedDict
from uuid import UUID

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from app.ai.gemini import ActionPlan, GeminiService
from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.ingestion.embeddings import get_embedding_service
from app.repositories.search_repository import SearchRepository
from app.agent.tools.github import GitHubTool
from app.agent.tools.incidents import IncidentTool


class AgentState(TypedDict, total=False):
    workspace_id: str
    user_id: str
    query: str
    query_type: str
    search_queries: list[str]
    sources: list[dict]
    context: str
    action_plan: dict | None
    action_result: dict | None
    approval: dict | None
    answer: str
    citations: list[int]
    error: str | None


def _is_write_action(plan: dict | None) -> bool:
    return bool(
        plan
        and plan.get("action_type") == "github_create_issue"
    )


def _is_action_request(query: str) -> bool:
    """
    Detect explicit requests to modify an external system.

    The classifier intentionally favors explicit write verbs and known
    external-system operations over broad incident-related keywords.

    Examples that should classify as action:
      - Create a GitHub issue for the payment incident
      - Create an issue for the outage
      - Open a GitHub issue for this bug
      - File a GitHub issue
      - Submit a GitHub issue
      - Please create an issue

    Examples that should remain investigation:
      - Investigate the payment incident
      - What happened during the outage?
      - Why did the deployment fail?
    """
    lowered = " ".join(query.lower().split())

    write_verbs = (
        "create",
        "open",
        "file",
        "submit",
        "raise",
        "make",
    )

    issue_terms = (
        "issue",
        "ticket",
    )

    external_systems = (
        "github",
        "git hub",
    )

    has_write_verb = any(
        verb in lowered.split()
        for verb in write_verbs
    )

    has_issue_term = any(
        term in lowered
        for term in issue_terms
    )

    has_external_system = any(
        system in lowered
        for system in external_systems
    )

    # Explicit GitHub issue creation is always an action.
    if (
        has_write_verb
        and has_issue_term
        and has_external_system
    ):
        return True

    # "Create an issue" / "open an issue" is also an explicit write
    # request even when the external system is not named.
    if (
        has_write_verb
        and has_issue_term
    ):
        return True

    # Preserve support for the common direct phrasing.
    explicit_phrases = (
        "create github issue",
        "create a github issue",
        "create an github issue",
        "open github issue",
        "open a github issue",
        "open an github issue",
        "file github issue",
        "file a github issue",
        "file an github issue",
        "submit github issue",
        "submit a github issue",
        "submit an github issue",
    )

    return any(
        phrase in lowered
        for phrase in explicit_phrases
    )


async def analyze_node(state: AgentState) -> dict:
    query = state["query"]

    if _is_action_request(query):
        query_type = "action"
    else:
        lowered = query.lower()

        if any(
            marker in lowered
            for marker in (
                "incident",
                "outage",
                "5xx",
                "error",
                "deployment",
            )
        ):
            query_type = "investigation"
        else:
            query_type = "knowledge"

    return {
        "query_type": query_type,
    }


async def retrieve_node(state: AgentState) -> dict:
    gemini = GeminiService()
    base_query = state["query"]

    try:
        expanded = await gemini.expand_query(base_query)
    except Exception:
        expanded = []

    queries = [base_query, *expanded]

    unique_queries = list(
        dict.fromkeys(
            q.strip()
            for q in queries
            if q.strip()
        )
    )[:4]

    embedding_service = get_embedding_service()
    merged: dict[UUID, dict] = {}

    async with AsyncSessionLocal() as session:
        repository = SearchRepository(session)

        for query in unique_queries:
            embedding = await _embed(
                embedding_service,
                query,
            )

            results = await repository.hybrid_search(
                workspace_id=UUID(state["workspace_id"]),
                query_embedding=embedding,
                query=query,
                top_k=settings.agent_max_context_chunks,
                candidate_k=settings.agent_max_retrieval_candidates,
            )

            for item in results:
                existing = merged.get(item["chunk_id"])

                if (
                    existing is None
                    or item["rerank_score"]
                    > existing["rerank_score"]
                ):
                    merged[item["chunk_id"]] = item

    sources = sorted(
        merged.values(),
        key=lambda item: item.get(
            "rerank_score",
            0.0,
        ),
        reverse=True,
    )[: settings.agent_max_context_chunks]

    context = "\n\n".join(
        f"""SOURCE {index}
Document: {item["document_name"]}
Section: {" > ".join(item.get("section_path") or [])}
Content:
{item["content"]}"""
        for index, item in enumerate(
            sources,
            start=1,
        )
    )

    return {
        "search_queries": unique_queries,
        "sources": sources,
        "context": context,
    }


async def _embed(
    embedding_service,
    query: str,
) -> list[float]:
    # fastembed is CPU-bound; keep the event loop responsive.
    import asyncio

    return await asyncio.to_thread(
        embedding_service.embed_query,
        query,
    )


async def plan_node(state: AgentState) -> dict:
    gemini = GeminiService()

    plan: ActionPlan = await gemini.plan_action(
        query=state["query"],
        context=state.get("context", ""),
    )

    if plan.action_type == "github_create_issue":
        repository = (
            plan.repository
            or settings.github_default_repository
        )

        if not repository:
            # Keep the proposal explicit rather than inventing a repo.
            plan = ActionPlan(
                action_type="none",
            )

    if plan.action_type == "incident_lookup":
        results = await IncidentTool().search(
            plan.incident_query
            or state["query"]
        )

        return {
            "action_plan": plan.model_dump(),
            "action_result": {
                "incidents": results,
            },
        }

    return {
        "action_plan": plan.model_dump(),
    }


async def approval_node(state: AgentState) -> dict:
    plan = state.get("action_plan")

    if not _is_write_action(plan):
        return {}

    approval = interrupt(
        {
            "type": "approval_required",
            "action_type": plan["action_type"],
            "payload": plan,
            "message": (
                "This action will modify an external system. "
                "Approve, edit, or reject it."
            ),
        }
    )

    return {
        "approval": (
            approval
            if isinstance(approval, dict)
            else {
                "decision": str(approval),
            }
        ),
    }


async def execute_node(state: AgentState) -> dict:
    plan = state.get("action_plan")

    if not _is_write_action(plan):
        return {}

    approval = state.get("approval") or {}
    decision = approval.get(
        "decision",
        "reject",
    )

    if decision == "reject":
        return {
            "action_result": {
                "status": "rejected",
            }
        }

    edited = (
        approval.get("payload")
        if decision == "edit"
        else None
    )

    payload = edited or plan

    result = await GitHubTool().create_issue(
        repository=payload["repository"],
        title=(
            payload["title"]
            or "ForgeOps incident"
        ),
        body=payload.get("body") or "",
    )

    return {
        "action_result": {
            "status": "executed",
            "github": result,
        }
    }


async def generate_node(state: AgentState) -> dict:
    if (
        state.get("action_result", {}).get("status")
        == "rejected"
    ):
        return {
            "answer": (
                "The proposed external action was rejected."
            ),
            "citations": [],
        }

    context = state.get(
        "context",
        "",
    )

    if not context:
        context = "No document evidence was found."

    if state.get("action_result", {}).get(
        "incidents"
    ):
        context += (
            "\n\nINCIDENT TOOL RESULTS:\n"
            + str(
                state["action_result"]["incidents"]
            )
        )

    gemini = GeminiService()

    draft = await gemini.generate_grounded_answer(
        query=state["query"],
        context=context,
    )

    citations = [
        index
        for index in draft.citations
        if 1 <= index <= len(
            state.get("sources", [])
        )
    ]

    return {
        "answer": draft.answer,
        "citations": citations,
    }


async def validate_node(state: AgentState) -> dict:
    answer = state.get(
        "answer",
        "",
    ).strip()

    citations = state.get(
        "citations",
        [],
    )

    if not answer:
        answer = (
            "I could not produce an answer "
            "from the available evidence."
        )

    if state.get("sources") and citations:
        citation_text = (
            " Sources: "
            + ", ".join(
                f"[{index}] "
                f"{state['sources'][index - 1]['document_name']}"
                for index in citations
            )
        )

        if citation_text not in answer:
            answer += citation_text

    return {
        "answer": answer,
    }


def build_graph(checkpointer):
    builder = StateGraph(AgentState)

    builder.add_node(
        "analyze",
        analyze_node,
    )

    builder.add_node(
        "retrieve",
        retrieve_node,
    )

    builder.add_node(
        "plan",
        plan_node,
    )

    builder.add_node(
        "approval",
        approval_node,
    )

    builder.add_node(
        "execute",
        execute_node,
    )

    builder.add_node(
        "generate",
        generate_node,
    )

    builder.add_node(
        "validate",
        validate_node,
    )

    builder.add_edge(
        START,
        "analyze",
    )

    builder.add_edge(
        "analyze",
        "retrieve",
    )

    builder.add_edge(
        "retrieve",
        "plan",
    )

    builder.add_edge(
        "plan",
        "approval",
    )

    builder.add_edge(
        "approval",
        "execute",
    )

    builder.add_edge(
        "execute",
        "generate",
    )

    builder.add_edge(
        "generate",
        "validate",
    )

    builder.add_edge(
        "validate",
        END,
    )

    return builder.compile(
        checkpointer=checkpointer,
    )