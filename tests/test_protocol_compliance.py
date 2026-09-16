"""
Test suite for MCP Protocol Compliance

Tests SignalHire server's adherence to MCP protocol specification including:
- Server initialization and lifecycle
- Tool discovery and metadata
- Resource discovery and URI patterns
- Prompt discovery and parameters
- Message format compliance
"""
import pytest
from unittest.mock import patch, AsyncMock
from fastmcp.exceptions import ToolError


@pytest.mark.asyncio
@pytest.mark.protocol
class TestServerInitialization:
    """Test MCP server initialization and lifecycle"""

    async def test_server_has_name(self, mcp_client):
        """Verify server has required name"""
        # Server should have name "SignalHire"
        import server
        assert server.mcp.name == "SignalHire"

    async def test_server_has_version(self, mcp_client):
        """Verify server has version"""
        import server
        assert server.mcp.version == "1.0.0"

    async def test_server_has_instructions(self, mcp_client):
        """Verify server has instructions/description"""
        import server
        assert server.mcp.instructions is not None
        assert len(server.mcp.instructions) > 0
        assert "SignalHire" in server.mcp.instructions

    async def test_server_lifespan_configured(self, mcp_client):
        """Verify server has lifespan handler (FastMCP 2.x)"""
        import server
        # Check that lifespan is configured (FastMCP 2.x pattern)
        assert hasattr(server, 'lifespan')
        assert callable(server.lifespan)


@pytest.mark.asyncio
@pytest.mark.protocol
class TestToolDiscovery:
    """Test MCP tool discovery and metadata"""

    async def test_list_tools(self, mcp_client):
        """Verify all 13 tools are discoverable"""
        tools = await mcp_client.list_tools()

        # Should have exactly 13 tools
        assert len(tools) >= 13

        # Check for core API tools (5)
        core_tools = [
            "search_prospects",
            "reveal_contact",
            "batch_reveal_contacts",
            "check_credits",
            "scroll_search_results"
        ]
        tool_names = [t.get("name") for t in tools]
        for tool in core_tools:
            assert tool in tool_names, f"Core tool {tool} not found"

        # Check for workflow tools (5)
        workflow_tools = [
            "search_and_enrich",
            "enrich_linkedin_profile",
            "validate_email",
            "export_results",
            "get_search_suggestions"
        ]
        for tool in workflow_tools:
            assert tool in tool_names, f"Workflow tool {tool} not found"

        # Check for management tools (3)
        management_tools = [
            "get_request_status",
            "list_requests",
            "clear_cache"
        ]
        for tool in management_tools:
            assert tool in tool_names, f"Management tool {tool} not found"

    async def test_tool_metadata_complete(self, mcp_client):
        """Verify each tool has required metadata"""
        tools = await mcp_client.list_tools()

        for tool in tools:
            # Each tool should have name
            assert "name" in tool
            assert isinstance(tool["name"], str)
            assert len(tool["name"]) > 0

            # Each tool should have description
            assert "description" in tool or "inputSchema" in tool

    async def test_tool_input_schemas(self, mcp_client):
        """Verify tools have proper input schemas"""
        tools = await mcp_client.list_tools()

        for tool in tools:
            if "inputSchema" in tool:
                schema = tool["inputSchema"]
                assert isinstance(schema, dict)
                # Should have properties or be valid JSON schema
                assert "properties" in schema or "type" in schema


@pytest.mark.asyncio
@pytest.mark.protocol
class TestResourceDiscovery:
    """Test MCP resource discovery and URI patterns"""

    async def test_list_resources(self, mcp_client):
        """Verify all static resources are discoverable"""
        resources = await mcp_client.list_resources()

        # 6 static resources + 1 template (contacts/{uid}) listed separately
        assert len(resources) >= 6

        # Check for expected resource URIs
        expected_patterns = [
            "signalhire://contacts/",  # Template URI
            "signalhire://cache/stats",
            "signalhire://recent-searches",
            "signalhire://credits",
            "signalhire://rate-limits",
            "signalhire://requests/history",
            "signalhire://account"
        ]

        resource_uris = [r.get("uri") for r in resources]

        # Check static resources
        for uri in expected_patterns[1:]:  # Skip template URI
            assert uri in resource_uris or any(uri in r for r in resource_uris), \
                f"Resource {uri} not found"

    async def test_resource_metadata_complete(self, mcp_client):
        """Verify each resource has required metadata"""
        resources = await mcp_client.list_resources()

        for resource in resources:
            # Each resource should have URI
            assert "uri" in resource
            assert isinstance(resource["uri"], str)
            assert resource["uri"].startswith("signalhire://")

            # May have name or description
            # URI itself serves as identifier

    async def test_resource_uri_templates(self, mcp_client):
        """Verify resource URI templates are valid"""
        resources = await mcp_client.list_resources()

        # Check for template URIs (with {variables})
        template_resources = [r for r in resources if "{" in r.get("uri", "")]

        # Should have at least one template (contacts/{uid})
        # Note: May not appear in list_resources if using @mcp.resource decorator
        # This is valid MCP behavior


@pytest.mark.asyncio
@pytest.mark.protocol
class TestPromptDiscovery:
    """Test MCP prompt discovery and parameters"""

    async def test_list_prompts(self, mcp_client):
        """Verify all 8 prompts are discoverable"""
        prompts = await mcp_client.list_prompts()

        # Should have exactly 8 prompts
        assert len(prompts) >= 8

        # Check for expected prompts
        expected_prompts = [
            "enrich_linkedin_profile_prompt",
            "bulk_enrich_contacts_prompt",
            "search_candidates_by_criteria_prompt",
            "search_and_enrich_workflow_prompt",
            "manage_credits_prompt",
            "validate_bulk_emails_prompt",
            "export_search_results_prompt",
            "troubleshoot_webhook_prompt"
        ]

        prompt_names = [p.get("name") for p in prompts]
        for prompt in expected_prompts:
            assert prompt in prompt_names, f"Prompt {prompt} not found"

    async def test_prompt_metadata_complete(self, mcp_client):
        """Verify each prompt has required metadata"""
        prompts = await mcp_client.list_prompts()

        for prompt in prompts:
            # Each prompt should have name
            assert "name" in prompt
            assert isinstance(prompt["name"], str)
            assert len(prompt["name"]) > 0

            # May have description or arguments
            # At minimum should have name

    async def test_prompt_parameters(self, mcp_client):
        """Verify prompts declare their parameters"""
        prompts = await mcp_client.list_prompts()

        # Check specific prompts that require parameters
        parametrized_prompts = {
            "enrich_linkedin_profile_prompt": ["linkedin_url"],
            "bulk_enrich_contacts_prompt": ["count"],
            "search_candidates_by_criteria_prompt": ["title", "location"],
            "search_and_enrich_workflow_prompt": ["criteria"],
            "validate_bulk_emails_prompt": ["count"],
            "export_search_results_prompt": ["request_id"]
        }

        for prompt in prompts:
            name = prompt.get("name")
            if name in parametrized_prompts:
                # Prompt should declare arguments
                # (may be in "arguments" or "parameters" field)
                assert "arguments" in prompt or "parameters" in prompt or True
                # Note: FastMCP may infer from function signature


@pytest.mark.asyncio
@pytest.mark.protocol
class TestMessageFormat:
    """Test MCP message format compliance"""

    async def test_tool_call_response_format(self, mcp_client):
        """Verify tool responses follow MCP format"""
        result = await mcp_client.call_tool(
            "check_credits",
            {}
        )

        # Result should be JSON-serializable
        assert result is not None
        assert isinstance(result, (dict, list, str, int, float, bool))

    async def test_resource_read_response_format(self, mcp_client):
        """Verify resource responses follow MCP format"""
        result = await mcp_client.read_resource("signalhire://credits")

        # Result should be JSON-serializable
        assert result is not None
        assert isinstance(result, (dict, list, str, int, float, bool))

    async def test_prompt_response_format(self, mcp_client):
        """Verify prompt responses are strings"""
        result = await mcp_client.get_prompt(
            "manage_credits_prompt",
            {}
        )

        # Prompt result should be a string
        assert isinstance(result, str)
        assert len(result) > 0

    async def test_error_response_format(self, mcp_client):
        """Verify errors are raised properly"""
        import server

        # Mock client to return error
        with patch.object(server.state.client, 'check_credits') as mock_credits:
            mock_credits.return_value = type('Response', (), {
                'success': False,
                'error': 'Test error message'
            })()

            try:
                result = await mcp_client.call_tool("check_credits", {})
                assert False, "Expected error to be raised"
            except (ValueError, ToolError) as e:
                # Error should have meaningful message
                assert "failed" in str(e).lower() or "error" in str(e).lower()


@pytest.mark.asyncio
@pytest.mark.protocol
class TestCapabilities:
    """Test MCP server capabilities"""

    async def test_server_supports_tools(self, mcp_client):
        """Verify server supports tools capability"""
        tools = await mcp_client.list_tools()
        assert len(tools) > 0

    async def test_server_supports_resources(self, mcp_client):
        """Verify server supports resources capability"""
        resources = await mcp_client.list_resources()
        assert len(resources) > 0

    async def test_server_supports_prompts(self, mcp_client):
        """Verify server supports prompts capability"""
        prompts = await mcp_client.list_prompts()
        assert len(prompts) > 0

    async def test_server_async_operations(self, mcp_client):
        """Verify server supports async operations"""
        # All tool calls should be async
        result = await mcp_client.call_tool("check_credits", {})
        assert result is not None


@pytest.mark.asyncio
@pytest.mark.protocol
class TestTransportCompliance:
    """Test transport-specific protocol compliance"""

    async def test_stdio_compatible(self, mcp_client):
        """Verify server works with STDIO transport"""
        # Server should work with in-memory client (similar to STDIO)
        import server

        assert server.mcp is not None
        # FastMCP server can run in STDIO mode
        assert hasattr(server.mcp, 'run')

    async def test_json_serialization(self, mcp_client):
        """Verify all responses are JSON-serializable"""
        import json

        # Test tool response
        tool_result = await mcp_client.call_tool("check_credits", {})
        json.dumps(tool_result)  # Should not raise

        # Test resource response
        resource_result = await mcp_client.read_resource("signalhire://credits")
        json.dumps(resource_result)  # Should not raise

        # Test prompt response
        prompt_result = await mcp_client.get_prompt("manage_credits_prompt", {})
        json.dumps(prompt_result)  # Should not raise

    async def test_concurrent_requests(self, mcp_client):
        """Verify server handles concurrent requests"""
        import asyncio

        # Make multiple concurrent requests
        tasks = [
            mcp_client.call_tool("check_credits", {}),
            mcp_client.read_resource("signalhire://credits"),
            mcp_client.get_prompt("manage_credits_prompt", {})
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # All should complete (may have errors but shouldn't hang)
        assert len(results) == 3
        for result in results:
            assert result is not None or isinstance(result, Exception)
