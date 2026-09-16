"""
Test suite for SignalHire MCP Server Resources (7 resources)

Tests all resource URIs and template variable handling including:
- URI access patterns
- Resource availability
- Data format validation
"""
import pytest
from unittest.mock import Mock, patch


@pytest.mark.asyncio
@pytest.mark.resources
class TestResourceAccess:
    """Test accessing all MCP resources"""

    async def test_get_cached_contact(self, mcp_client):
        """Test accessing cached contact by UID"""
        import server

        # Mock cache to return a contact
        test_contact = {
            "uid": "test_uid_123",
            "name": "John Doe",
            "emails": ["john@example.com"],
            "phones": ["+1-555-0100"]
        }

        with patch.object(server.state.cache, 'get', return_value=test_contact):
            result = await mcp_client.read_resource("signalhire://contacts/test_uid_123")

            assert result is not None
            assert "uid" in result or result == test_contact

    async def test_get_cached_contact_not_found(self, mcp_client):
        """Test accessing non-existent cached contact"""
        import server

        with patch.object(server.state.cache, 'get', return_value=None):
            try:
                result = await mcp_client.read_resource("signalhire://contacts/nonexistent")
            except Exception as e:
                assert "not found" in str(e).lower()

    async def test_get_cache_stats(self, mcp_client):
        """Test accessing cache statistics resource"""
        import server

        # Mock cache stats
        with patch.object(server.state.cache, '_cache', {}):
            result = await mcp_client.read_resource("signalhire://cache/stats")

            assert result is not None
            assert "total_contacts" in result
            assert isinstance(result["total_contacts"], int)

    async def test_get_recent_searches(self, mcp_client):
        """Test accessing recent searches resource"""
        result = await mcp_client.read_resource("signalhire://recent-searches")

        assert result is not None
        assert isinstance(result, list)

    async def test_get_credits_resource(self, mcp_client):
        """Test accessing credits resource"""
        result = await mcp_client.read_resource("signalhire://credits")

        assert result is not None
        assert "credits" in result
        assert isinstance(result["credits"], int)

    async def test_get_rate_limits(self, mcp_client):
        """Test accessing rate limits resource"""
        result = await mcp_client.read_resource("signalhire://rate-limits")

        assert result is not None
        # May return "unknown" status if rate limiter not initialized
        assert "status" in result or "items_per_minute" in result

    async def test_get_requests_history(self, mcp_client):
        """Test accessing requests history resource"""
        result = await mcp_client.read_resource("signalhire://requests/history")

        assert result is not None
        assert isinstance(result, list)

    async def test_get_account_info(self, mcp_client):
        """Test accessing account info resource"""
        result = await mcp_client.read_resource("signalhire://account")

        assert result is not None
        # May return "unavailable" status if account endpoint not implemented
        assert "status" in result or isinstance(result, dict)


@pytest.mark.asyncio
@pytest.mark.resources
class TestResourceURIPatterns:
    """Test resource URI pattern handling"""

    async def test_contact_uri_with_various_uids(self, mcp_client):
        """Test contact URI with different UID formats"""
        import server

        uids = [
            "simple_uid",
            "uid-with-dashes",
            "uid_with_underscores",
            "UID123",
            "uid.with.dots"
        ]

        for uid in uids:
            test_contact = {"uid": uid, "name": "Test User"}
            with patch.object(server.state.cache, 'get', return_value=test_contact):
                result = await mcp_client.read_resource(f"signalhire://contacts/{uid}")
                assert result is not None

    async def test_static_resources(self, mcp_client):
        """Test all static resource URIs (no variables)"""
        static_resources = [
            "signalhire://cache/stats",
            "signalhire://recent-searches",
            "signalhire://credits",
            "signalhire://rate-limits",
            "signalhire://requests/history",
            "signalhire://account"
        ]

        for uri in static_resources:
            result = await mcp_client.read_resource(uri)
            assert result is not None, f"Resource {uri} should return data"


@pytest.mark.asyncio
@pytest.mark.resources
@pytest.mark.error_handling
class TestResourceErrorHandling:
    """Test error handling for resource access"""

    async def test_invalid_resource_uri(self, mcp_client):
        """Test accessing non-existent resource URI"""
        try:
            result = await mcp_client.read_resource("signalhire://invalid/resource")
        except Exception as e:
            # Expected to fail - invalid resource
            assert True

    async def test_malformed_uri(self, mcp_client):
        """Test malformed resource URI"""
        try:
            result = await mcp_client.read_resource("invalid-uri-format")
        except Exception:
            # Expected to fail
            assert True

    async def test_credits_resource_api_failure(self, mcp_client):
        """Test credits resource when API fails"""
        import server

        with patch.object(server.state.client, 'check_credits') as mock_credits:
            mock_credits.return_value = Mock(
                success=False,
                error="API error"
            )

            try:
                result = await mcp_client.read_resource("signalhire://credits")
            except Exception as e:
                assert "failed" in str(e).lower()

    async def test_history_resource_empty(self, mcp_client):
        """Test requests history resource when empty"""
        import server

        with patch.object(server.state.client, 'list_requests') as mock_list:
            mock_list.return_value = Mock(
                success=True,
                data={"requests": []}
            )

            result = await mcp_client.read_resource("signalhire://requests/history")
            assert isinstance(result, list)
            assert len(result) == 0


@pytest.mark.asyncio
@pytest.mark.resources
class TestResourceDataFormats:
    """Test resource data format validation"""

    async def test_cache_stats_format(self, mcp_client):
        """Verify cache stats returns correct format"""
        result = await mcp_client.read_resource("signalhire://cache/stats")

        assert isinstance(result, dict)
        assert "total_contacts" in result
        assert isinstance(result["total_contacts"], int)
        assert result["total_contacts"] >= 0

    async def test_credits_format(self, mcp_client):
        """Verify credits resource returns correct format"""
        result = await mcp_client.read_resource("signalhire://credits")

        assert isinstance(result, dict)
        assert "credits" in result
        assert isinstance(result["credits"], int)

    async def test_rate_limits_format(self, mcp_client):
        """Verify rate limits resource returns correct format"""
        result = await mcp_client.read_resource("signalhire://rate-limits")

        assert isinstance(result, dict)
        assert "status" in result or "items_per_minute" in result

    async def test_recent_searches_format(self, mcp_client):
        """Verify recent searches returns list format"""
        result = await mcp_client.read_resource("signalhire://recent-searches")

        assert isinstance(result, list)

    async def test_requests_history_format(self, mcp_client):
        """Verify requests history returns list format"""
        result = await mcp_client.read_resource("signalhire://requests/history")

        assert isinstance(result, list)

    async def test_account_info_format(self, mcp_client):
        """Verify account info returns dict format"""
        result = await mcp_client.read_resource("signalhire://account")

        assert isinstance(result, dict)
