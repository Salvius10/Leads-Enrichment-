"""
Test fixtures for SignalHire MCP Server
Provides mcp_client fixture using FastMCP v3 Client testing pattern
"""
import json
import os
import sys
import pytest
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Set up test environment variables before any imports
os.environ["SIGNALHIRE_API_KEY"] = "test_fake_api_key_for_testing_only"
os.environ["EXTERNAL_CALLBACK_URL"] = "https://test-callback.example.com/webhook"

from fastmcp import Client


class MCPClientWrapper:
    """Wrapper around FastMCP v3 Client that provides a test-friendly interface.

    Normalizes FastMCP v3 return types into simple Python types
    (dicts, lists, strings) that tests can assert against easily.
    """

    def __init__(self, client: Client):
        self._client = client

    async def call_tool(self, name: str, arguments: dict) -> dict:
        """Call a tool and return the result as a dict."""
        result = await self._client.call_tool(name, arguments)
        if result.is_error:
            raise ValueError(f"Tool error: {result.data}")
        data = result.data
        if isinstance(data, str):
            try:
                return json.loads(data)
            except json.JSONDecodeError:
                return {"result": data}
        if isinstance(data, dict):
            return data
        if isinstance(data, list):
            return {"items": data}
        return {"result": data}

    async def read_resource(self, uri: str):
        """Read a resource and return parsed JSON (dict or list)."""
        result = await self._client.read_resource(uri)
        # FastMCP v3 returns list[TextResourceContents | BlobResourceContents]
        if isinstance(result, list) and len(result) > 0:
            item = result[0]
            text = getattr(item, "text", None)
            if text is not None:
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    return {"content": text}
        if isinstance(result, str):
            try:
                return json.loads(result)
            except json.JSONDecodeError:
                return {"content": result}
        return result

    async def list_tools(self) -> list[dict]:
        """List all tools and return as list of dicts."""
        tools = await self._client.list_tools()
        return [
            {
                "name": t.name,
                "description": t.description,
                "inputSchema": t.inputSchema,
            }
            for t in tools
        ]

    async def list_resources(self) -> list[dict]:
        """List all resources and return as list of dicts."""
        resources = await self._client.list_resources()
        return [
            {
                "uri": str(r.uri),
                "name": r.name,
                "description": r.description,
                "mimeType": r.mimeType,
            }
            for r in resources
        ]

    async def list_prompts(self) -> list[dict]:
        """List all prompts and return as list of dicts."""
        prompts = await self._client.list_prompts()
        return [
            {
                "name": p.name,
                "description": p.description,
                "arguments": [
                    {"name": a.name, "required": a.required}
                    for a in (p.arguments or [])
                ],
            }
            for p in prompts
        ]

    async def get_prompt(self, name: str, arguments: dict) -> str:
        """Get a prompt and return the rendered text as a string."""
        result = await self._client.get_prompt(name, arguments)
        # GetPromptResult has .messages list of PromptMessage
        texts = []
        for msg in result.messages:
            if hasattr(msg.content, "text"):
                texts.append(msg.content.text)
            elif isinstance(msg.content, str):
                texts.append(msg.content)
        return "\n".join(texts)


def _create_mock_client():
    """Create a fully configured mock SignalHire client."""
    mock_client = Mock()
    mock_client.search_prospects = AsyncMock(return_value=Mock(
        success=True,
        data={"profiles": [], "total": 0, "scrollId": "test_scroll", "requestId": "test_req"}
    ))
    mock_client.reveal_contact_by_identifier = AsyncMock(return_value=Mock(
        success=True,
        data={"request_id": "test_reveal_req", "requestId": "test_reveal_req"}
    ))
    mock_client.batch_reveal_contacts = AsyncMock(return_value=Mock(
        success=True,
        data={"request_id": "test_batch_req"}
    ))
    mock_client.check_credits = AsyncMock(return_value=Mock(
        success=True,
        data={"credits": 1000}
    ))
    mock_client.scroll_search = AsyncMock(return_value=Mock(
        success=True,
        data={"profiles": [], "scrollId": "next_scroll"}
    ))
    mock_client.rate_limiter = Mock(
        daily_limit=5000,
        daily_usage={"credits_used": 0, "reveals": 0, "search_profiles": 0, "last_reset": "2024-01-01"},
    )
    mock_client.start_session = AsyncMock()
    mock_client.close_session = AsyncMock()
    return mock_client


@pytest.fixture
async def mcp_client():
    """
    Create in-memory MCP client for testing.

    Uses FastMCP v3 Client to create a test client
    without starting an actual HTTP server.
    Patches state AFTER lifespan runs to override real client.
    """
    # Import server after env vars are set
    import server

    # Create test client using FastMCP v3 Client
    # The lifespan will run and create real state objects
    async with Client(server.mcp) as client:
        # Now patch state AFTER lifespan has run
        mock_client = _create_mock_client()
        original_client = server.state.client
        server.state.client = mock_client

        # Mock cache
        mock_cache = Mock()
        mock_cache.get = Mock(return_value=None)
        mock_cache.clear = Mock()
        mock_cache._cache = {}
        mock_cache.get_stats = Mock(return_value={})
        original_cache = server.state.cache
        server.state.cache = mock_cache

        # Mock callback_server
        mock_cb = Mock()
        mock_cb._request_handlers = {}
        original_cb = server.state.callback_server
        server.state.callback_server = mock_cb

        try:
            yield MCPClientWrapper(client)
        finally:
            # Restore original state for clean teardown
            server.state.client = original_client
            server.state.cache = original_cache
            server.state.callback_server = original_cb


@pytest.fixture
def mock_signalhire_api():
    """
    Mock SignalHire API responses for testing actual API integration.
    Use this fixture when you need to simulate different API responses.
    """
    return {
        "search_success": {
            "profiles": [
                {
                    "uid": "test_uid_1",
                    "name": "John Doe",
                    "title": "Software Engineer",
                    "company": "Tech Corp"
                }
            ],
            "total": 1,
            "scrollId": "scroll_123",
            "requestId": "req_123"
        },
        "reveal_success": {
            "request_id": "reveal_123",
            "status": "processing"
        },
        "credits_response": {
            "credits": 500
        },
        "error_response": {
            "error": "API Error",
            "message": "Invalid request"
        }
    }


@pytest.fixture
def sample_profiles():
    """Sample profile data for testing"""
    return [
        {
            "uid": "uid_001",
            "name": "Alice Smith",
            "title": "Senior Software Engineer",
            "company": "Tech Inc",
            "location": "San Francisco, CA",
            "linkedin_url": "https://linkedin.com/in/alice-smith"
        },
        {
            "uid": "uid_002",
            "name": "Bob Johnson",
            "title": "Engineering Manager",
            "company": "StartupCo",
            "location": "New York, NY",
            "linkedin_url": "https://linkedin.com/in/bob-johnson"
        },
        {
            "uid": "uid_003",
            "name": "Carol White",
            "title": "DevOps Engineer",
            "company": "CloudTech",
            "location": "Remote",
            "linkedin_url": "https://linkedin.com/in/carol-white"
        }
    ]


@pytest.fixture
def sample_identifiers():
    """Sample identifiers for batch operations"""
    return [
        "https://linkedin.com/in/test-user-1",
        "https://linkedin.com/in/test-user-2",
        "test@example.com",
        "uid_12345"
    ]
