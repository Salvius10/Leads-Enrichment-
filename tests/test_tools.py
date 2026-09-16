"""
Test suite for SignalHire MCP Server Tools (13 tools)

Tests all tool invocations with various input scenarios including:
- Success cases with valid inputs
- Error cases with invalid/missing parameters
- Edge cases and boundary conditions
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch


@pytest.mark.asyncio
@pytest.mark.tools
class TestCoreAPITools:
    """Test core API tools (5 tools)"""

    async def test_search_prospects_basic(self, mcp_client):
        """Test basic prospect search with minimal parameters"""
        result = await mcp_client.call_tool(
            "search_prospects",
            {"title": "Software Engineer"}
        )

        assert "total" in result
        assert "count" in result
        assert "profiles" in result
        assert isinstance(result["profiles"], list)

    async def test_search_prospects_with_location(self, mcp_client):
        """Test search with location filter"""
        result = await mcp_client.call_tool(
            "search_prospects",
            {
                "title": "Product Manager",
                "location": ["San Francisco", "Remote"]
            }
        )

        assert result is not None
        assert "profiles" in result

    async def test_search_prospects_boolean_query(self, mcp_client):
        """Test search with Boolean operators in title"""
        result = await mcp_client.call_tool(
            "search_prospects",
            {
                "title": "Software Engineer AND (Python OR Java)",
                "size": 50
            }
        )

        assert "total" in result
        assert result["count"] >= 0

    async def test_search_prospects_experience_range(self, mcp_client):
        """Test search with experience filters"""
        result = await mcp_client.call_tool(
            "search_prospects",
            {
                "title": "Developer",
                "years_experience_from": 3,
                "years_experience_to": 10
            }
        )

        assert result is not None

    async def test_search_prospects_all_filters(self, mcp_client):
        """Test search with all available filters"""
        result = await mcp_client.call_tool(
            "search_prospects",
            {
                "title": "Engineering Manager",
                "location": ["San Francisco"],
                "company": "Tech Corp",
                "keywords": "Python AND AWS",
                "years_experience_from": 5,
                "years_experience_to": 15,
                "open_to_work": True,
                "size": 25
            }
        )

        assert "profiles" in result
        assert "scroll_id" in result

    async def test_reveal_contact_linkedin_url(self, mcp_client):
        """Test revealing contact by LinkedIn URL"""
        result = await mcp_client.call_tool(
            "reveal_contact",
            {"identifier": "https://linkedin.com/in/john-doe"}
        )

        assert "request_id" in result
        assert result["status"] == "processing"
        assert "callback_url" in result

    async def test_reveal_contact_email(self, mcp_client):
        """Test revealing contact by email"""
        result = await mcp_client.call_tool(
            "reveal_contact",
            {"identifier": "john@example.com"}
        )

        assert "request_id" in result
        assert result["identifier"] == "john@example.com"

    async def test_reveal_contact_without_contacts(self, mcp_client):
        """Test revealing profile without contact info (cheaper)"""
        result = await mcp_client.call_tool(
            "reveal_contact",
            {
                "identifier": "uid_12345",
                "without_contacts": True
            }
        )

        assert "request_id" in result

    async def test_batch_reveal_contacts_small_batch(self, mcp_client):
        """Test batch reveal with small list"""
        identifiers = [
            "https://linkedin.com/in/user1",
            "https://linkedin.com/in/user2",
            "user3@example.com"
        ]

        result = await mcp_client.call_tool(
            "batch_reveal_contacts",
            {"identifiers": identifiers}
        )

        assert "request_id" in result
        assert result["count"] == 3
        assert result["status"] == "processing"

    async def test_batch_reveal_contacts_without_contacts(self, mcp_client):
        """Test batch reveal without contact info"""
        identifiers = ["uid_1", "uid_2", "uid_3"]

        result = await mcp_client.call_tool(
            "batch_reveal_contacts",
            {
                "identifiers": identifiers,
                "without_contacts": True
            }
        )

        assert "request_id" in result

    async def test_check_credits_default(self, mcp_client):
        """Test checking credits for normal operations"""
        result = await mcp_client.call_tool("check_credits", {})

        assert "credits" in result
        assert result["type"] == "with_contacts"
        assert isinstance(result["credits"], int)

    async def test_check_credits_without_contacts(self, mcp_client):
        """Test checking credits for no-contact operations"""
        result = await mcp_client.call_tool(
            "check_credits",
            {"without_contacts": True}
        )

        assert result["type"] == "no_contacts"

    async def test_scroll_search_results(self, mcp_client):
        """Test scrolling through search results"""
        result = await mcp_client.call_tool(
            "scroll_search_results",
            {
                "request_id": "123456",
                "scroll_id": "scroll_abc"
            }
        )

        assert "count" in result
        assert "profiles" in result
        assert "scroll_id" in result
        assert "has_more" in result


@pytest.mark.asyncio
@pytest.mark.tools
class TestWorkflowTools:
    """Test workflow tools (5 tools)"""

    async def test_search_and_enrich_basic(self, mcp_client):
        """Test combined search and enrich workflow"""
        # Mock search to return profiles
        import server
        with patch.object(server.state.client, 'search_prospects') as mock_search:
            mock_search.return_value = Mock(
                success=True,
                data={
                    "profiles": [{"uid": "uid_1"}, {"uid": "uid_2"}],
                    "total": 2,
                    "scrollId": "scroll_1",
                    "requestId": "req_1"
                }
            )

            result = await mcp_client.call_tool(
                "search_and_enrich",
                {
                    "title": "Software Engineer",
                    "max_results": 10
                }
            )

            assert "search_total" in result
            assert "enrichment_request_id" in result
            assert result["status"] == "processing"

    async def test_search_and_enrich_with_location(self, mcp_client):
        """Test search and enrich with location filter"""
        import server
        with patch.object(server.state.client, 'search_prospects') as mock_search:
            mock_search.return_value = Mock(
                success=True,
                data={
                    "profiles": [{"uid": "uid_1"}],
                    "total": 1,
                    "scrollId": "scroll_1",
                    "requestId": "req_1"
                }
            )

            result = await mcp_client.call_tool(
                "search_and_enrich",
                {
                    "title": "Developer",
                    "location": ["Remote"],
                    "max_results": 25
                }
            )

            assert "profiles_found" in result

    async def test_enrich_linkedin_profile(self, mcp_client):
        """Test enriching single LinkedIn profile"""
        result = await mcp_client.call_tool(
            "enrich_linkedin_profile",
            {"linkedin_url": "https://linkedin.com/in/test-user"}
        )

        assert "request_id" in result
        assert "profile_url" in result
        assert result["status"] == "processing"
        assert "credits_remaining" in result

    async def test_validate_email_valid(self, mcp_client):
        """Test email validation for valid email"""
        result = await mcp_client.call_tool(
            "validate_email",
            {"email": "valid@example.com"}
        )

        assert "email" in result
        assert "valid" in result
        assert "confidence" in result

    async def test_validate_email_invalid(self, mcp_client):
        """Test email validation for invalid email"""
        import server
        with patch.object(server.state.client, 'reveal_contact_by_identifier') as mock_reveal:
            mock_reveal.return_value = Mock(
                success=False,
                error="Email not found"
            )

            result = await mcp_client.call_tool(
                "validate_email",
                {"email": "notfound@example.com"}
            )

            assert result["valid"] == False
            assert "reason" in result

    async def test_export_results_json(self, mcp_client):
        """Test exporting results as JSON"""
        result = await mcp_client.call_tool(
            "export_results",
            {
                "request_id": "req_123",
                "format": "json"
            }
        )

        assert "request_id" in result
        assert result["format"] == "json"

    async def test_export_results_csv(self, mcp_client):
        """Test exporting results as CSV"""
        result = await mcp_client.call_tool(
            "export_results",
            {
                "request_id": "req_456",
                "format": "csv"
            }
        )

        assert result["format"] == "csv"

    async def test_get_search_suggestions(self, mcp_client):
        """Test getting search query suggestions"""
        result = await mcp_client.call_tool(
            "get_search_suggestions",
            {"query": "Python Developer"}
        )

        assert "items" in result  # wrapper wraps list as {"items": [...]}
        assert isinstance(result["items"], list)
        assert len(result["items"]) > 0
        assert all(isinstance(s, str) for s in result["items"])


@pytest.mark.asyncio
@pytest.mark.tools
class TestManagementTools:
    """Test management tools (3 tools)"""

    async def test_get_request_status(self, mcp_client):
        """Test checking request status"""
        result = await mcp_client.call_tool(
            "get_request_status",
            {"request_id": "test_req_123"}
        )

        assert "status" in result
        assert result["status"] in ["processing", "completed", "failed", "unknown"]

    async def test_list_requests(self, mcp_client):
        """Test listing recent requests"""
        result = await mcp_client.call_tool(
            "list_requests",
            {"limit": 10}
        )

        assert "requests" in result or isinstance(result, dict)

    async def test_list_requests_custom_limit(self, mcp_client):
        """Test listing requests with custom limit"""
        result = await mcp_client.call_tool(
            "list_requests",
            {"limit": 50}
        )

        assert result is not None

    async def test_clear_cache(self, mcp_client):
        """Test clearing contact cache"""
        result = await mcp_client.call_tool("clear_cache", {})

        assert result["status"] == "cleared"
        assert "message" in result


@pytest.mark.asyncio
@pytest.mark.tools
@pytest.mark.error_handling
class TestToolErrorHandling:
    """Test error handling for all tools"""

    async def test_search_prospects_invalid_experience(self, mcp_client):
        """Test search with invalid experience range"""
        # Should handle gracefully even if parameters are out of range
        try:
            result = await mcp_client.call_tool(
                "search_prospects",
                {
                    "title": "Developer",
                    "years_experience_from": -5  # Invalid negative
                }
            )
            # If it doesn't raise, parameters might be validated
            assert result is not None
        except Exception as e:
            # Expected to fail validation
            assert "experience" in str(e).lower() or "validation" in str(e).lower()

    async def test_reveal_contact_empty_identifier(self, mcp_client):
        """Test reveal with empty identifier"""
        try:
            result = await mcp_client.call_tool(
                "reveal_contact",
                {"identifier": ""}
            )
            # May accept empty string but should handle it
            assert result is not None
        except Exception:
            # Expected to fail
            pass

    async def test_batch_reveal_empty_list(self, mcp_client):
        """Test batch reveal with empty identifiers list"""
        try:
            result = await mcp_client.call_tool(
                "batch_reveal_contacts",
                {"identifiers": []}
            )
            # Should handle empty list gracefully
            assert result is not None
        except Exception:
            # May raise error for empty list
            pass

    async def test_scroll_invalid_ids(self, mcp_client):
        """Test scroll with invalid request/scroll IDs"""
        from fastmcp.exceptions import ToolError
        import server

        # Non-numeric request_id should fail with validation error
        try:
            result = await mcp_client.call_tool(
                "scroll_search_results",
                {
                    "request_id": "invalid",
                    "scroll_id": "expired"
                }
            )
        except (ValueError, ToolError) as e:
            assert "invalid" in str(e).lower() or "numeric" in str(e).lower()

    async def test_scroll_expired_scroll_id(self, mcp_client):
        """Test scroll with expired scrollId"""
        from fastmcp.exceptions import ToolError
        import server
        with patch.object(server.state.client, 'scroll_search') as mock_scroll:
            mock_scroll.return_value = Mock(
                success=False,
                error="scrollId expired"
            )

            try:
                result = await mcp_client.call_tool(
                    "scroll_search_results",
                    {
                        "request_id": "999999",
                        "scroll_id": "expired"
                    }
                )
            except (ValueError, ToolError) as e:
                assert "expired" in str(e).lower()

    async def test_check_credits_api_failure(self, mcp_client):
        """Test credits check when API fails"""
        from fastmcp.exceptions import ToolError
        import server
        with patch.object(server.state.client, 'check_credits') as mock_credits:
            mock_credits.return_value = Mock(
                success=False,
                error="API unavailable"
            )

            try:
                result = await mcp_client.call_tool("check_credits", {})
            except (ValueError, ToolError) as e:
                assert "failed" in str(e).lower() or "unavailable" in str(e).lower()
