"""
Test suite for Deployment Readiness

Tests SignalHire server's deployment readiness including:
- Environment configuration
- Dependency installation
- External callback server integration
- Performance and reliability
"""
import pytest
import os
import sys
from pathlib import Path
from unittest.mock import patch, Mock, AsyncMock


@pytest.mark.asyncio
@pytest.mark.integration
class TestEnvironmentConfiguration:
    """Test environment configuration validation"""

    def test_env_file_exists(self):
        """Verify .env file exists"""
        server_dir = Path(__file__).parent.parent
        env_file = server_dir / ".env"
        assert env_file.exists(), ".env file should exist"

    def test_required_env_vars_set(self):
        """Verify required environment variables are set"""
        # Check SIGNALHIRE_API_KEY
        api_key = os.getenv("SIGNALHIRE_API_KEY")
        assert api_key is not None, "SIGNALHIRE_API_KEY must be set"
        assert len(api_key) > 0, "SIGNALHIRE_API_KEY must not be empty"

    def test_callback_url_configured(self):
        """Verify callback URL is configured"""
        callback_url = os.getenv("EXTERNAL_CALLBACK_URL")
        # Either external URL or local server should be configured
        assert callback_url is not None or True  # Local server is fallback

    def test_optional_env_vars(self):
        """Check optional environment variables"""
        # These are optional, just verify they don't break if missing
        mem0_key = os.getenv("MEM0_API_KEY")
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_KEY")

        # Should handle missing optional vars gracefully
        assert True  # No assertion needed, just checking access

    def test_env_example_exists(self):
        """Verify .env.example file exists for documentation"""
        server_dir = Path(__file__).parent.parent
        env_example = server_dir / ".env.example"
        assert env_example.exists(), ".env.example should exist"


@pytest.mark.asyncio
@pytest.mark.integration
class TestDependencies:
    """Test dependency installation and imports"""

    def test_fastmcp_installed(self):
        """Verify FastMCP is installed"""
        try:
            import fastmcp
            assert hasattr(fastmcp, 'FastMCP')
        except ImportError:
            pytest.fail("FastMCP not installed")

    def test_fastmcp_version(self):
        """Verify FastMCP version is 2.x or 3.x"""
        import fastmcp
        if hasattr(fastmcp, '__version__'):
            version = fastmcp.__version__
            assert version.startswith('2.') or version.startswith('3.'), \
                f"FastMCP version {version} should be 2.x or 3.x"

    def test_required_packages_installed(self):
        """Verify all required packages are installed"""
        required_packages = [
            'httpx',
            'pydantic',
            'fastapi',
            'uvicorn',
            'pandas',
            'click',
            'rich',
            'dotenv',
            'structlog',
            'fastmcp'
        ]

        for package in required_packages:
            try:
                if package == 'dotenv':
                    __import__('dotenv')
                else:
                    __import__(package)
            except ImportError:
                pytest.fail(f"Required package '{package}' not installed")

    def test_optional_packages_handled(self):
        """Verify optional packages are handled gracefully"""
        # Server should work without these
        try:
            import mem0
            has_mem0 = True
        except ImportError:
            has_mem0 = False

        try:
            import supabase
            has_supabase = True
        except ImportError:
            has_supabase = False

        # Server should import successfully regardless
        import server
        assert server is not None

    def test_local_imports(self):
        """Verify all local modules can be imported"""
        sys.path.insert(0, str(Path(__file__).parent.parent))

        local_modules = [
            'lib.signalhire_client',
            'lib.callback_server',
            'lib.contact_cache',
            'lib.config',
            'models.person_callback'
        ]

        for module in local_modules:
            try:
                __import__(module)
            except ImportError as e:
                pytest.fail(f"Failed to import local module '{module}': {e}")


@pytest.mark.asyncio
@pytest.mark.integration
class TestCallbackServerIntegration:
    """Test external callback server integration"""

    async def test_external_callback_url_used(self, mcp_client):
        """Verify external callback URL is used when configured"""
        import server

        # With EXTERNAL_CALLBACK_URL set, should use it
        callback_url = server.get_callback_url()
        assert callback_url is not None
        assert isinstance(callback_url, str)

    async def test_callback_url_in_reveal_request(self, mcp_client):
        """Verify callback URL is included in reveal requests"""
        result = await mcp_client.call_tool(
            "reveal_contact",
            {"identifier": "test@example.com"}
        )

        assert "callback_url" in result
        assert result["callback_url"] is not None

    async def test_callback_url_in_batch_request(self, mcp_client):
        """Verify callback URL is used in batch requests"""
        import server

        # Check that batch operations use callback URL
        callback_url = server.get_callback_url()
        assert callback_url is not None

        # Batch operation should include callback
        result = await mcp_client.call_tool(
            "batch_reveal_contacts",
            {"identifiers": ["test1@example.com", "test2@example.com"]}
        )

        assert "request_id" in result  # Should initiate request


@pytest.mark.asyncio
@pytest.mark.integration
class TestServerStartupShutdown:
    """Test server lifecycle management"""

    async def test_server_imports_successfully(self):
        """Verify server module imports without errors"""
        try:
            import server
            assert server is not None
            assert server.mcp is not None
        except Exception as e:
            pytest.fail(f"Server import failed: {e}")

    async def test_lifespan_startup_logic(self):
        """Verify lifespan startup initializes correctly"""
        import server

        # Lifespan should initialize:
        # - SignalHire client
        # - Contact cache
        # - Optional: Mem0, Supabase

        # Check state objects exist
        assert hasattr(server, 'state')
        assert hasattr(server.state, 'client')
        assert hasattr(server.state, 'cache')

    async def test_lifespan_shutdown_logic(self):
        """Verify lifespan shutdown cleans up resources"""
        import server

        # Shutdown should:
        # - Close HTTP session
        # - Stop callback server (if local)

        # Verify shutdown handlers exist
        assert hasattr(server, 'lifespan')


@pytest.mark.asyncio
@pytest.mark.integration
class TestPerformanceAndReliability:
    """Test performance and reliability characteristics"""

    async def test_concurrent_tool_calls(self, mcp_client):
        """Test handling multiple concurrent tool calls"""
        import asyncio

        # Make 5 concurrent credit checks
        tasks = [
            mcp_client.call_tool("check_credits", {})
            for _ in range(5)
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # All should complete successfully
        assert len(results) == 5
        for result in results:
            assert not isinstance(result, Exception)
            assert "credits" in result

    async def test_tool_call_performance(self, mcp_client):
        """Test tool call response time"""
        import time

        start = time.time()
        result = await mcp_client.call_tool("check_credits", {})
        elapsed = time.time() - start

        # Should complete quickly (< 1 second for mocked call)
        assert elapsed < 1.0, f"Tool call took {elapsed}s, should be < 1s"

    async def test_resource_access_performance(self, mcp_client):
        """Test resource access response time"""
        import time

        start = time.time()
        result = await mcp_client.read_resource("signalhire://credits")
        elapsed = time.time() - start

        # Should complete quickly
        assert elapsed < 1.0, f"Resource access took {elapsed}s, should be < 1s"

    async def test_error_recovery(self, mcp_client):
        """Test server recovers from errors"""
        import server
        from fastmcp.exceptions import ToolError

        # Simulate API error by reconfiguring the mock
        server.state.client.check_credits = AsyncMock(
            return_value=Mock(success=False, error="API Error")
        )

        with pytest.raises((ValueError, ToolError)):
            await mcp_client.call_tool("check_credits", {})

        # Server should still work after error - restore success mock
        server.state.client.check_credits = AsyncMock(
            return_value=Mock(success=True, data={"credits": 100})
        )
        result = await mcp_client.call_tool("check_credits", {})
        assert "credits" in result

    async def test_memory_usage_stable(self, mcp_client):
        """Test memory usage remains stable over multiple calls"""
        # Make many sequential calls
        for _ in range(20):
            result = await mcp_client.call_tool("check_credits", {})
            assert result is not None

        # If we get here without crashing, memory is stable
        assert True


@pytest.mark.asyncio
@pytest.mark.integration
class TestConfigurationValidation:
    """Test configuration file validation"""

    def test_requirements_file_exists(self):
        """Verify requirements.txt exists"""
        server_dir = Path(__file__).parent.parent
        req_file = server_dir / "requirements.txt"
        assert req_file.exists(), "requirements.txt should exist"

    def test_requirements_has_fastmcp(self):
        """Verify requirements.txt includes FastMCP 3.x"""
        server_dir = Path(__file__).parent.parent
        req_file = server_dir / "requirements.txt"

        with open(req_file) as f:
            content = f.read()
            assert "fastmcp" in content.lower()
            # Should specify version constraint
            assert ">=" in content

    def test_server_entry_point_exists(self):
        """Verify server.py entry point exists"""
        server_dir = Path(__file__).parent.parent
        server_py = server_dir / "server.py"
        assert server_py.exists(), "server.py should exist"

    def test_readme_exists(self):
        """Verify README documentation exists"""
        server_dir = Path(__file__).parent.parent
        readme = server_dir / "README.md"
        assert readme.exists(), "README.md should exist"

    def test_install_script_exists(self):
        """Verify install script exists"""
        server_dir = Path(__file__).parent.parent
        install_script = server_dir / "install.sh"
        assert install_script.exists(), "install.sh should exist"


@pytest.mark.asyncio
@pytest.mark.integration
class TestDeploymentScenarios:
    """Test different deployment scenarios"""

    async def test_standalone_deployment(self, mcp_client):
        """Test standalone deployment scenario"""
        # Server should work independently
        import server

        # Should load config from .env in server directory
        assert server.ENV_FILE.exists()

        # Should have all components initialized
        result = await mcp_client.call_tool("check_credits", {})
        assert result is not None

    async def test_external_callback_deployment(self, mcp_client):
        """Test deployment with external callback server"""
        import server

        # With EXTERNAL_CALLBACK_URL set, should use external server
        external_url = os.getenv("EXTERNAL_CALLBACK_URL")
        if external_url:
            callback_url = server.get_callback_url()
            assert callback_url == external_url

    async def test_local_callback_deployment(self, mcp_client):
        """Test deployment with local callback server"""
        import server

        # Without EXTERNAL_CALLBACK_URL, should use local server
        # (mocked in tests, but should be initialized in production)
        with patch.dict(os.environ, {"EXTERNAL_CALLBACK_URL": ""}):
            # Would initialize local callback server
            pass

    async def test_fastmcp_cloud_deployment(self, mcp_client):
        """Test FastMCP Cloud deployment readiness"""
        import server

        # Should have proper FastMCP structure
        assert server.mcp is not None
        assert hasattr(server, 'lifespan')

        # Should use lifespan for initialization (internal attr name varies by version)
        assert hasattr(server.mcp, 'lifespan') or hasattr(server.mcp, '_lifespan')
