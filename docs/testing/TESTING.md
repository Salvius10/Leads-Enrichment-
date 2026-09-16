# SignalHire MCP Server - Testing Guide

Quick reference for running and understanding the test suite.

---

## Quick Start

```bash
# Navigate to server directory
cd /home/gotime2022/Projects/Mcp-Servers/signalhire

# Install test dependencies (if not already installed)
pip install pytest pytest-asyncio pytest-cov

# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_tools.py -v

# Run with coverage report
pytest tests/ --cov=server --cov-report=html
```

---

## Test Suite Overview

### 127 Total Test Cases

| Test File | Tests | Description |
|-----------|-------|-------------|
| `test_tools.py` | 47 | All 13 MCP tools with various scenarios |
| `test_resources.py` | 27 | All 7 MCP resources and URI patterns |
| `test_prompts.py` | 32 | All 8 MCP prompts and parameter substitution |
| `test_protocol_compliance.py` | 21 | MCP protocol adherence verification |
| `test_deployment.py` | 33 | Deployment readiness and configuration |

---

## Running Specific Test Categories

### Tool Tests (13 tools)

```bash
# Run all tool tests
pytest tests/test_tools.py -v

# Run specific tool category
pytest tests/test_tools.py::TestCoreAPITools -v
pytest tests/test_tools.py::TestWorkflowTools -v
pytest tests/test_tools.py::TestManagementTools -v

# Run single tool test
pytest tests/test_tools.py::TestCoreAPITools::test_search_prospects_basic -v
```

**Tools Tested:**
- Core API: search_prospects, reveal_contact, batch_reveal_contacts, check_credits, scroll_search_results
- Workflow: search_and_enrich, enrich_linkedin_profile, validate_email, export_results, get_search_suggestions
- Management: get_request_status, list_requests, clear_cache

### Resource Tests (7 resources)

```bash
# Run all resource tests
pytest tests/test_resources.py -v

# Run specific resource category
pytest tests/test_resources.py::TestResourceAccess -v
pytest tests/test_resources.py::TestResourceURIPatterns -v
pytest tests/test_resources.py::TestResourceDataFormats -v
```

**Resources Tested:**
- signalhire://contacts/{uid}
- signalhire://cache/stats
- signalhire://recent-searches
- signalhire://credits
- signalhire://rate-limits
- signalhire://requests/history
- signalhire://account

### Prompt Tests (8 prompts)

```bash
# Run all prompt tests
pytest tests/test_prompts.py -v

# Run specific prompt category
pytest tests/test_prompts.py::TestPromptGeneration -v
pytest tests/test_prompts.py::TestPromptContentQuality -v
pytest tests/test_prompts.py::TestPromptParameterSubstitution -v
```

**Prompts Tested:**
- enrich_linkedin_profile_prompt
- bulk_enrich_contacts_prompt
- search_candidates_by_criteria_prompt
- search_and_enrich_workflow_prompt
- manage_credits_prompt
- validate_bulk_emails_prompt
- export_search_results_prompt
- troubleshoot_webhook_prompt

### Protocol Compliance Tests

```bash
# Run all protocol tests
pytest tests/test_protocol_compliance.py -v

# Run specific compliance category
pytest tests/test_protocol_compliance.py::TestServerInitialization -v
pytest tests/test_protocol_compliance.py::TestToolDiscovery -v
pytest tests/test_protocol_compliance.py::TestResourceDiscovery -v
pytest tests/test_protocol_compliance.py::TestPromptDiscovery -v
```

### Deployment Tests

```bash
# Run all deployment tests
pytest tests/test_deployment.py -v

# Run specific deployment category
pytest tests/test_deployment.py::TestEnvironmentConfiguration -v
pytest tests/test_deployment.py::TestDependencies -v
pytest tests/test_deployment.py::TestCallbackServerIntegration -v
```

---

## Test Markers

Tests are organized with pytest markers for selective execution:

```bash
# Run only unit tests
pytest tests/ -m unit -v

# Run only integration tests
pytest tests/ -m integration -v

# Run only protocol tests
pytest tests/ -m protocol -v

# Run only tool tests
pytest tests/ -m tools -v

# Run only resource tests
pytest tests/ -m resources -v

# Run only prompt tests
pytest tests/ -m prompts -v

# Run only error handling tests
pytest tests/ -m error_handling -v

# Exclude slow tests
pytest tests/ -m "not slow" -v
```

---

## Understanding Test Output

### Successful Test

```
tests/test_tools.py::TestCoreAPITools::test_check_credits_default PASSED [25%]
```

- ✅ Test passed successfully
- Tool executed correctly with expected response

### Failed Test

```
tests/test_tools.py::TestCoreAPITools::test_search_prospects_basic FAILED [10%]
AssertionError: assert 'profiles' in result
```

- ❌ Test failed - check assertion
- Review test logic or server implementation

### Test Error

```
tests/test_tools.py::TestCoreAPITools::test_reveal_contact ERROR [20%]
ImportError: cannot import name 'Education'
```

- ⚠️ Test couldn't run due to import/setup error
- Fix import issues before test can execute

---

## Test Configuration

### pytest.ini Settings

```ini
[pytest]
asyncio_mode = auto                # Enable async test support
python_files = test_*.py           # Discover test files
python_classes = Test*             # Discover test classes
python_functions = test_*          # Discover test functions
testpaths = tests                  # Test directory
minversion = 3.10                  # Minimum Python version
```

### conftest.py Fixtures

```python
@pytest.fixture
async def mcp_client():
    """In-memory MCP client for testing"""
    # Creates test client without HTTP server
    # Mocks external API calls
    # Provides isolated test environment
```

---

## Troubleshooting

### Common Issues

#### 1. Import Errors

**Problem:**
```
ImportError: cannot import name 'Education' from 'models.education'
```

**Solution:**
Already fixed in `models/__init__.py` with import aliases:
```python
from .education import EducationEntry as Education
from .experience import ExperienceEntry as Experience
```

#### 2. Server Won't Start

**Problem:**
```
RuntimeError: SIGNALHIRE_API_KEY not set
```

**Solution:**
```bash
# Ensure .env file exists with API key
echo "SIGNALHIRE_API_KEY=your_key_here" > .env
```

#### 3. Tests Hang

**Problem:**
Tests timeout waiting for async operations

**Solution:**
```bash
# Run with timeout
pytest tests/ --timeout=30

# Or kill hanging tests
killall pytest
```

#### 4. Fixture Errors

**Problem:**
```
ERROR at setup of test_*
```

**Solution:**
- Check conftest.py fixture definitions
- Ensure mcp_client fixture can import server
- Verify environment variables are set

---

## Test Development

### Adding New Tests

#### 1. Tool Test

```python
# tests/test_tools.py

@pytest.mark.asyncio
@pytest.mark.tools
async def test_my_new_tool(mcp_client):
    """Test my new tool functionality"""
    result = await mcp_client.call_tool(
        "my_new_tool",
        {"param": "value"}
    )

    assert "expected_field" in result
    assert result["expected_field"] == "expected_value"
```

#### 2. Resource Test

```python
# tests/test_resources.py

@pytest.mark.asyncio
@pytest.mark.resources
async def test_my_new_resource(mcp_client):
    """Test my new resource access"""
    result = await mcp_client.read_resource(
        "signalhire://my/resource"
    )

    assert result is not None
    assert isinstance(result, dict)
```

#### 3. Prompt Test

```python
# tests/test_prompts.py

@pytest.mark.asyncio
@pytest.mark.prompts
async def test_my_new_prompt(mcp_client):
    """Test my new prompt generation"""
    result = await mcp_client.get_prompt(
        "my_new_prompt",
        {"param": "value"}
    )

    assert isinstance(result, str)
    assert "value" in result
```

### Test Best Practices

1. **Use descriptive test names**
   - ✅ `test_search_prospects_with_boolean_query`
   - ❌ `test_search_1`

2. **Test one thing per test**
   - Each test should verify a single behavior
   - Makes failures easier to diagnose

3. **Use fixtures for setup**
   - Avoid repeating setup code
   - Keep tests focused on assertions

4. **Mock external dependencies**
   - Don't call real APIs in tests
   - Use `unittest.mock.patch` or `pytest-mock`

5. **Document edge cases**
   - Add docstrings explaining unusual test cases
   - Helps future maintainers understand intent

---

## Coverage Analysis

### Generate Coverage Report

```bash
# Run tests with coverage
pytest tests/ --cov=server --cov-report=html --cov-report=term

# Open HTML report
xdg-open htmlcov/index.html  # Linux
open htmlcov/index.html      # Mac
```

### Coverage Interpretation

```
Name                           Stmts   Miss  Cover
--------------------------------------------------
server.py                        250     50    80%
lib/signalhire_client.py        150     30    80%
lib/callback_server.py           80     20    75%
--------------------------------------------------
TOTAL                           480    100    79%
```

- **Stmts:** Total statements
- **Miss:** Statements not executed by tests
- **Cover:** Percentage covered

**Target:** 80%+ coverage for production code

---

## Continuous Integration

### GitHub Actions Example

```yaml
# .github/workflows/test.yml
name: Run Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.12'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
      - name: Run tests
        run: |
          pytest tests/ --cov=server --cov-report=xml
      - name: Upload coverage
        uses: codecov/codecov-action@v2
```

---

## Performance Testing

### Load Testing Example

```python
# tests/test_performance.py

@pytest.mark.asyncio
@pytest.mark.slow
async def test_concurrent_tool_calls(mcp_client):
    """Test 50 concurrent tool calls"""
    import asyncio

    async def call_tool():
        return await mcp_client.call_tool("check_credits", {})

    # Run 50 concurrent calls
    tasks = [call_tool() for _ in range(50)]
    results = await asyncio.gather(*tasks)

    assert len(results) == 50
    assert all("credits" in r for r in results)
```

---

## Resources

### Documentation

- **FastMCP Docs:** https://github.com/jlowin/fastmcp
- **MCP Specification:** https://modelcontextprotocol.io/docs
- **Pytest Docs:** https://docs.pytest.org/
- **Pytest-Asyncio:** https://pytest-asyncio.readthedocs.io/

### Test Files Location

```
/home/gotime2022/Projects/Mcp-Servers/signalhire/
├── tests/
│   ├── conftest.py              # Test fixtures
│   ├── pytest.ini               # Pytest config
│   ├── test_tools.py            # 47 tool tests
│   ├── test_resources.py        # 27 resource tests
│   ├── test_prompts.py          # 32 prompt tests
│   ├── test_protocol_compliance.py  # 21 protocol tests
│   └── test_deployment.py       # 33 deployment tests
├── TESTING.md                   # This guide
└── TESTING_REPORT.md           # Comprehensive test report
```

---

## Support

For questions or issues with testing:

1. Check `TESTING_REPORT.md` for detailed test results
2. Review test file docstrings for test descriptions
3. Run specific failing test with `-v` for verbose output
4. Check server logs for error details

---

**Last Updated:** October 29, 2025
**Test Suite Version:** 1.0
**Total Tests:** 127
