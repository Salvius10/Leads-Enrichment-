# SignalHire MCP Server - Quick Start Guide

## Self-Contained Setup (3 Steps)

### 1. Create Your `.env` File

```bash
cd /home/gotime2022/Projects/Mcp-Servers/signalhire
cp .env.example .env
nano .env
```

Add your SignalHire API key:
```bash
SIGNALHIRE_API_KEY=your_actual_api_key_here
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

Or use the automated installer:
```bash
./install.sh
```

### 3. Install in Claude Code

```bash
fastmcp install claude-code .mcp.json
```

**That's it!** Restart Claude Code and you're ready to go.

## Usage

Just ask Claude:
- "Search SignalHire for Python engineers in San Francisco"
- "Enrich these LinkedIn profiles"
- "Check my SignalHire credits"

## What Makes It Self-Contained?

✅ **No global environment variables** - `.env` lives with the server
✅ **No external packages** - All code included (~7,000 lines)
✅ **Portable** - Copy directory anywhere, it works
✅ **Simple .mcp.json** - No env vars to configure

## Deploy to FastMCP Cloud

```bash
# Commit your .env file (safe in private repo)
git add .env
git commit -m "Add configuration"
git push origin main

# Deploy at fastmcp.cloud
# No additional environment variables needed!
```

## Files in This Directory

- `server.py` - Main MCP server (auto-loads `.env`)
- `.env` - Your configuration (create from `.env.example`)
- `.mcp.json` - Claude Code integration (no env vars!)
- `lib/` - All SignalHire client code
- `models/` - Pydantic data models
- `storage/` - Mem0/Supabase adapters
- `requirements.txt` - Python dependencies

## Troubleshooting

**Server won't start:**
```bash
# Check Python version
python3 --version  # Need 3.10+

# Test syntax
python3 -m py_compile server.py

# Check .env exists
ls -la .env
```

**Missing dependencies:**
```bash
pip install -r requirements.txt
```

For more details, see [README.md](README.md)
