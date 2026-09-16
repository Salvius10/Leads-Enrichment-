#!/usr/bin/env bash
#
# SignalHire MCP Server - Standalone Installation Script
#
# This script installs the standalone SignalHire MCP server and its dependencies.

set -euo pipefail

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 SignalHire MCP Server - Standalone Installation${NC}"
echo "=========================================="
echo ""

# Get paths
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo "📂 Installation directory: $SCRIPT_DIR"
echo ""

# Step 1: Check Python version
echo "1️⃣  Checking Python version..."
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
REQUIRED_VERSION="3.10"

if python3 -c "import sys; exit(0 if sys.version_info >= (3, 10) else 1)"; then
    echo -e "${GREEN}✅ Python $PYTHON_VERSION (>= $REQUIRED_VERSION)${NC}"
else
    echo -e "${RED}❌ Python $PYTHON_VERSION is too old. Requires >= $REQUIRED_VERSION${NC}"
    exit 1
fi
echo ""

# Step 2: Install MCP server dependencies
echo "2️⃣  Installing dependencies..."
cd "$SCRIPT_DIR"
pip install -r requirements.txt --quiet
echo -e "${GREEN}✅ Dependencies installed${NC}"
echo ""

# Step 3: Check environment variables
echo "3️⃣  Checking environment configuration..."
ENV_FILE="$SCRIPT_DIR/.env"

if [ ! -f "$ENV_FILE" ]; then
    echo -e "${YELLOW}⚠️  .env file not found. Creating template...${NC}"
    cat > "$ENV_FILE" << 'EOF'
# SignalHire API Credentials (required)
SIGNALHIRE_API_KEY=your_api_key_here

# Callback Server Configuration
CALLBACK_SERVER_HOST=0.0.0.0
CALLBACK_SERVER_PORT=8000

# Optional: Mem0 for semantic memory
# MEM0_API_KEY=your_mem0_key

# Optional: Supabase for persistent storage
# SUPABASE_URL=https://your-project.supabase.co
# SUPABASE_KEY=your_supabase_key
EOF
    echo -e "${YELLOW}⚠️  Please edit .env and add your API keys${NC}"
else
    echo -e "${GREEN}✅ .env file exists${NC}"

    # Check if API key is set
    if grep -q "SIGNALHIRE_API_KEY=your_api_key_here" "$ENV_FILE"; then
        echo -e "${YELLOW}⚠️  SIGNALHIRE_API_KEY not configured in .env${NC}"
    else
        echo -e "${GREEN}✅ SIGNALHIRE_API_KEY configured${NC}"
    fi
fi
echo ""

# Step 4: Test server startup
echo "4️⃣  Testing server..."
cd "$SCRIPT_DIR"

# Test syntax
python3 -m py_compile server.py
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Server syntax valid${NC}"
else
    echo -e "${RED}❌ Server syntax error${NC}"
    exit 1
fi

# Test lib imports
python3 -c "from lib.signalhire_client import SignalHireClient; from lib.callback_server import CallbackServer" 2>/dev/null
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Library imports valid${NC}"
else
    echo -e "${RED}❌ Library import error${NC}"
    exit 1
fi
echo ""

# Step 5: Installation summary
echo "=========================================="
echo -e "${GREEN}🎉 Installation Complete!${NC}"
echo ""
echo "Next steps:"
echo ""
echo "1. Configure your API key:"
echo "   nano $SCRIPT_DIR/.env"
echo ""
echo "2. Test the server:"
echo "   cd $SCRIPT_DIR"
echo "   python server.py"
echo ""
echo "3. Install in Claude Code:"
echo "   fastmcp install claude-code $SCRIPT_DIR/.mcp.json"
echo ""
echo "4. Or deploy to FastMCP Cloud:"
echo "   - Push to GitHub"
echo "   - Connect to FastMCP Cloud dashboard"
echo "   - Deploy!"
echo ""
echo "5. Restart Claude Code and try:"
echo "   'Search SignalHire for Python engineers'"
echo ""
echo "For help, see README.md"
echo ""
