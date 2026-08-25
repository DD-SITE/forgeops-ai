import pytest

from app.agent.graph import analyze_node


@pytest.mark.asyncio
async def test_agent_classifies_knowledge_query():
    result = await analyze_node(
        {
            "query": "What database stores our vector embeddings?",
        }
    )
    assert result["query_type"] == "knowledge"


@pytest.mark.asyncio
async def test_agent_classifies_write_request():
    result = await analyze_node(
        {
            "query": "Create a GitHub issue for the payment incident",
        }
    )
    assert result["query_type"] == "action"


@pytest.mark.asyncio
async def test_agent_classifies_incident_investigation():
    result = await analyze_node(
        {
            "query": "Why did payment-service start returning 5xx errors?",
        }
    )
    assert result["query_type"] == "investigation"
