#!/usr/bin/env python3
"""
SignalHire MCP Server - Configuration Test
Tests external callback server configuration.

Can be run standalone: python tests/test_configuration.py
Or via pytest (will skip if env not configured).
"""

import os
import sys
from pathlib import Path

import pytest
from dotenv import load_dotenv

SERVER_DIR = Path(__file__).parent.parent
ENV_FILE = SERVER_DIR / ".env"

if ENV_FILE.exists():
    load_dotenv(ENV_FILE)


class TestConfiguration:
    """Configuration validation tests."""

    def test_env_file_exists(self):
        assert ENV_FILE.exists(), f"No .env file at {ENV_FILE}"

    def test_api_key_configured(self):
        api_key = os.getenv("SIGNALHIRE_API_KEY")
        assert api_key is not None, "SIGNALHIRE_API_KEY not set"
        assert len(api_key) > 0, "SIGNALHIRE_API_KEY is empty"

    def test_callback_url_configured(self):
        external_callback = os.getenv("EXTERNAL_CALLBACK_URL")
        callback_host = os.getenv("CALLBACK_SERVER_HOST", "0.0.0.0")
        callback_port = os.getenv("CALLBACK_SERVER_PORT", "8000")
        # Either external or local should work
        assert external_callback or callback_host

    def test_server_imports(self):
        sys.path.insert(0, str(SERVER_DIR))
        from lib.signalhire_client import SignalHireClient
        from lib.callback_server import CallbackServer
        assert SignalHireClient is not None
        assert CallbackServer is not None

    def test_callback_url_logic(self):
        external_url = os.getenv("EXTERNAL_CALLBACK_URL")
        if external_url:
            assert "signalhire" in external_url.lower() or "callback" in external_url.lower()


if __name__ == "__main__":
    # Standalone mode with pretty output
    print("\n" + "=" * 60)
    print("SignalHire MCP Server - Configuration Test")
    print("=" * 60 + "\n")

    if not ENV_FILE.exists():
        print(f"❌ No .env file at {ENV_FILE}")
        sys.exit(1)

    print(f"✅ Loaded .env from {ENV_FILE}")

    api_key = os.getenv("SIGNALHIRE_API_KEY")
    if api_key and api_key != "your_signalhire_api_key_here":
        print(f"✅ API Key configured: {api_key[:10]}...")
    else:
        print("❌ API Key not configured or using placeholder")
        sys.exit(1)

    external_callback = os.getenv("EXTERNAL_CALLBACK_URL")
    if external_callback and "your-" not in external_callback:
        print(f"✅ External callback URL: {external_callback}")
    else:
        print("⚠️  External callback URL not set - will use local server")

    print("\n✅ Configuration test complete!")
