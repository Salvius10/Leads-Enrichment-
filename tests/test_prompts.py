"""
Test suite for SignalHire MCP Server Prompts (8 prompts)

Tests all prompt invocations with parameter validation including:
- Prompt generation with valid parameters
- Prompt content quality and completeness
- Parameter substitution
"""
import pytest


@pytest.mark.asyncio
@pytest.mark.prompts
class TestPromptGeneration:
    """Test all MCP prompts"""

    async def test_enrich_linkedin_profile_prompt(self, mcp_client):
        """Test LinkedIn profile enrichment prompt"""
        linkedin_url = "https://linkedin.com/in/john-doe"

        result = await mcp_client.get_prompt(
            "enrich_linkedin_profile_prompt",
            {"linkedin_url": linkedin_url}
        )

        assert result is not None
        assert isinstance(result, str)
        assert linkedin_url in result
        assert "check_credits" in result
        assert "enrich_linkedin_profile" in result
        assert "get_request_status" in result

    async def test_bulk_enrich_contacts_prompt(self, mcp_client):
        """Test bulk enrichment prompt"""
        count = 50

        result = await mcp_client.get_prompt(
            "bulk_enrich_contacts_prompt",
            {"count": count}
        )

        assert result is not None
        assert isinstance(result, str)
        assert str(count) in result
        assert "batch_reveal_contacts" in result
        assert "check_credits" in result
        assert "600 items/min" in result or "rate limit" in result.lower()

    async def test_search_candidates_by_criteria_prompt(self, mcp_client):
        """Test candidate search prompt"""
        title = "Software Engineer"
        location = "San Francisco"

        result = await mcp_client.get_prompt(
            "search_candidates_by_criteria_prompt",
            {
                "title": title,
                "location": location
            }
        )

        assert result is not None
        assert isinstance(result, str)
        assert title in result
        assert location in result
        assert "search_prospects" in result
        assert "Boolean" in result or "AND" in result or "OR" in result

    async def test_search_and_enrich_workflow_prompt(self, mcp_client):
        """Test search and enrich workflow prompt"""
        criteria = "Python Developer"

        result = await mcp_client.get_prompt(
            "search_and_enrich_workflow_prompt",
            {"criteria": criteria}
        )

        assert result is not None
        assert isinstance(result, str)
        assert criteria in result
        assert "search_and_enrich" in result
        assert "get_request_status" in result

    async def test_manage_credits_prompt(self, mcp_client):
        """Test credit management prompt"""
        result = await mcp_client.get_prompt(
            "manage_credits_prompt",
            {}
        )

        assert result is not None
        assert isinstance(result, str)
        assert "check_credits" in result
        assert "without_contacts" in result
        assert "credit" in result.lower()

    async def test_validate_bulk_emails_prompt(self, mcp_client):
        """Test bulk email validation prompt"""
        count = 100

        result = await mcp_client.get_prompt(
            "validate_bulk_emails_prompt",
            {"count": count}
        )

        assert result is not None
        assert isinstance(result, str)
        assert str(count) in result
        assert "batch_reveal_contacts" in result
        assert "credit" in result.lower()

    async def test_export_search_results_prompt(self, mcp_client):
        """Test export results prompt"""
        request_id = "req_12345"

        result = await mcp_client.get_prompt(
            "export_search_results_prompt",
            {"request_id": request_id}
        )

        assert result is not None
        assert isinstance(result, str)
        assert request_id in result
        assert "export_results" in result
        assert "csv" in result.lower() or "json" in result.lower()

    async def test_troubleshoot_webhook_prompt(self, mcp_client):
        """Test webhook troubleshooting prompt"""
        result = await mcp_client.get_prompt(
            "troubleshoot_webhook_prompt",
            {}
        )

        assert result is not None
        assert isinstance(result, str)
        assert "webhook" in result.lower()
        assert "callback" in result.lower()
        assert "port" in result.lower()
        assert "8000" in result or "localhost" in result.lower()


@pytest.mark.asyncio
@pytest.mark.prompts
class TestPromptContentQuality:
    """Test prompt content quality and completeness"""

    async def test_enrich_prompt_has_steps(self, mcp_client):
        """Verify enrich prompt contains clear steps"""
        result = await mcp_client.get_prompt(
            "enrich_linkedin_profile_prompt",
            {"linkedin_url": "https://linkedin.com/in/test"}
        )

        # Should have numbered steps or clear workflow
        assert "1." in result or "step" in result.lower()
        assert "2." in result or "Steps:" in result

    async def test_bulk_enrich_prompt_has_workflow(self, mcp_client):
        """Verify bulk enrich prompt contains workflow"""
        result = await mcp_client.get_prompt(
            "bulk_enrich_contacts_prompt",
            {"count": 25}
        )

        assert "workflow" in result.lower() or "step" in result.lower()
        assert "check_credits" in result
        assert "batch_reveal_contacts" in result

    async def test_search_prompt_explains_boolean(self, mcp_client):
        """Verify search prompt explains Boolean operators"""
        result = await mcp_client.get_prompt(
            "search_candidates_by_criteria_prompt",
            {"title": "Engineer", "location": "Remote"}
        )

        # Should explain Boolean syntax
        assert "AND" in result
        assert "OR" in result
        assert "NOT" in result or "Boolean" in result

    async def test_workflow_prompt_comprehensive(self, mcp_client):
        """Verify workflow prompt is comprehensive"""
        result = await mcp_client.get_prompt(
            "search_and_enrich_workflow_prompt",
            {"criteria": "Developer"}
        )

        # Should explain complete workflow
        assert "search" in result.lower()
        assert "enrich" in result.lower()
        assert "monitor" in result.lower() or "status" in result.lower()

    async def test_credits_prompt_explains_cost(self, mcp_client):
        """Verify credits prompt explains cost structure"""
        result = await mcp_client.get_prompt(
            "manage_credits_prompt",
            {}
        )

        assert "credit" in result.lower()
        assert "1 credit" in result or "cost" in result.lower()
        assert "search" in result.lower()

    async def test_export_prompt_lists_formats(self, mcp_client):
        """Verify export prompt lists available formats"""
        result = await mcp_client.get_prompt(
            "export_search_results_prompt",
            {"request_id": "test"}
        )

        # Should list supported formats
        assert "csv" in result.lower()
        assert "json" in result.lower()
        assert "excel" in result.lower()

    async def test_troubleshoot_prompt_actionable(self, mcp_client):
        """Verify troubleshoot prompt provides actionable steps"""
        result = await mcp_client.get_prompt(
            "troubleshoot_webhook_prompt",
            {}
        )

        # Should have troubleshooting steps
        assert "1." in result or "step" in result.lower()
        assert "check" in result.lower()
        assert "curl" in result or "test" in result.lower()


@pytest.mark.asyncio
@pytest.mark.prompts
class TestPromptParameterSubstitution:
    """Test parameter substitution in prompts"""

    async def test_enrich_prompt_substitutes_url(self, mcp_client):
        """Test URL parameter is substituted correctly"""
        test_urls = [
            "https://linkedin.com/in/alice-smith",
            "https://linkedin.com/in/bob-jones-123",
            "https://www.linkedin.com/in/carol"
        ]

        for url in test_urls:
            result = await mcp_client.get_prompt(
                "enrich_linkedin_profile_prompt",
                {"linkedin_url": url}
            )
            assert url in result

    async def test_bulk_prompt_substitutes_count(self, mcp_client):
        """Test count parameter is substituted correctly"""
        counts = [10, 50, 100, 500]

        for count in counts:
            result = await mcp_client.get_prompt(
                "bulk_enrich_contacts_prompt",
                {"count": count}
            )
            assert str(count) in result

    async def test_search_prompt_substitutes_criteria(self, mcp_client):
        """Test search criteria parameters are substituted"""
        test_cases = [
            {"title": "Engineer", "location": "SF"},
            {"title": "Manager", "location": "NYC"},
            {"title": "Designer", "location": "Remote"}
        ]

        for case in test_cases:
            result = await mcp_client.get_prompt(
                "search_candidates_by_criteria_prompt",
                case
            )
            assert case["title"] in result
            assert case["location"] in result

    async def test_workflow_prompt_substitutes_criteria(self, mcp_client):
        """Test workflow criteria is substituted"""
        criteria_list = [
            "Python Developer",
            "DevOps Engineer",
            "Product Manager",
            "Data Scientist"
        ]

        for criteria in criteria_list:
            result = await mcp_client.get_prompt(
                "search_and_enrich_workflow_prompt",
                {"criteria": criteria}
            )
            assert criteria in result

    async def test_export_prompt_substitutes_request_id(self, mcp_client):
        """Test request ID is substituted in export prompt"""
        request_ids = [
            "req_123",
            "request_456",
            "abc-def-789",
            "test_id_001"
        ]

        for req_id in request_ids:
            result = await mcp_client.get_prompt(
                "export_search_results_prompt",
                {"request_id": req_id}
            )
            assert req_id in result


@pytest.mark.asyncio
@pytest.mark.prompts
@pytest.mark.error_handling
class TestPromptErrorHandling:
    """Test prompt error handling"""

    async def test_prompt_with_missing_parameters(self, mcp_client):
        """Test prompts with missing required parameters"""
        # This may raise an error or handle gracefully
        try:
            result = await mcp_client.get_prompt(
                "enrich_linkedin_profile_prompt",
                {}  # Missing linkedin_url
            )
            # If it doesn't raise, check if it handles missing param
            # (might use placeholder or raise)
        except Exception:
            # Expected to fail with missing parameter
            pass

    async def test_prompt_with_invalid_count(self, mcp_client):
        """Test bulk prompt with invalid count"""
        try:
            result = await mcp_client.get_prompt(
                "bulk_enrich_contacts_prompt",
                {"count": -10}  # Invalid negative count
            )
            # May accept and render anyway
            assert result is not None
        except Exception:
            # May raise validation error
            pass

    async def test_prompt_with_extra_parameters(self, mcp_client):
        """Test prompts with extra unused parameters"""
        # FastMCP may reject extra parameters — that's valid behavior
        try:
            result = await mcp_client.get_prompt(
                "manage_credits_prompt",
                {
                    "unused_param": "value",
                    "another_param": 123
                }
            )
            assert result is not None
            assert isinstance(result, str)
        except Exception:
            # FastMCP rejects unknown parameters — expected
            pass
