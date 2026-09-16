# SignalHire MCP Server - FastMCP Cloud Deployment Checklist

**Deployment Target**: FastMCP Cloud
**Server**: SignalHire MCP Server v1.0.0
**Date Prepared**: 2025-11-02
**Status**: Ready for deployment

## Pre-Deployment Checklist

### Code Quality & Validation

- [x] All code changes committed to git (commit: 0f85f75)
- [x] Python syntax validated
- [x] FastMCP dependency declared (fastmcp>=2.10.0)
- [x] No hardcoded secrets detected
- [ ] Review localhost references (server.py has internal callback server references)

### Dependencies

- [x] requirements.txt up to date with all dependencies
- [ ] **TODO**: Pin dependency versions for production (currently using >= ranges)
  - Recommendation: Create `requirements-pinned.txt` with exact versions
  - Run: `pip freeze > requirements-pinned.txt` after testing
- [x] FastMCP 2.10.0+ included
- [x] All production dependencies listed

### Configuration Files

- [x] fastmcp.json created and validated
  - [x] Server name: SignalHire MCP Server
  - [x] Version: 1.0.0
  - [x] Entry point: server.py:mcp
  - [x] Environment variables documented (7 vars)
  - [x] Deployment configuration specified
- [x] .env.example documents all required variables
- [x] .env.production template created
- [x] .gitignore includes .env and .env.* files

### Environment Variables

**Required Variables**:
- [ ] SIGNALHIRE_API_KEY - Set in FastMCP Cloud dashboard
- [ ] EXTERNAL_CALLBACK_URL - Deploy callback server first!

**Optional Variables**:
- [ ] MEM0_API_KEY (for semantic memory)
- [ ] SUPABASE_URL (for persistent storage)
- [ ] SUPABASE_KEY (for persistent storage)

**Auto-configured** (defaults in fastmcp.json):
- [x] SIGNALHIRE_API_BASE_URL (default: https://www.signalhire.com)
- [x] SIGNALHIRE_API_PREFIX (default: /api/v1)

### Critical Pre-Deployment Steps

#### 1. Deploy External Callback Server FIRST

**IMPORTANT**: SignalHire MCP Server requires a publicly accessible callback server for webhooks.

Options:
- [ ] **Option A**: Deploy to DigitalOcean using `deploy-callback.sh`
  ```bash
  chmod +x deploy-callback.sh
  ./deploy-callback.sh
  # Save the callback URL for FastMCP Cloud configuration
  ```

- [ ] **Option B**: Deploy to Railway/Render manually
  - Deploy lib/callback_server.py as standalone app
  - Use requirements.callback.txt for dependencies
  - Expose /signalhire/callback endpoint

- [ ] **Option C**: Use webhook relay (development only, not production)
  - Configure smee.io or ngrok
  - Forward to local callback server

- [ ] Verify callback server is accessible:
  ```bash
  curl https://your-callback-server.com/health
  # Should return: {"status":"ok"}
  ```

- [ ] Save callback URL for next step

#### 2. Create GitHub Repository

- [ ] Create new repository: `signalhire-mcp` (or preferred name)
- [ ] Extract server to clean directory:
  ```bash
  mkdir -p ~/signalhire-mcp-production
  cp -r . ~/signalhire-mcp-production/
  cd ~/signalhire-mcp-production
  ```

- [ ] Initialize and push to GitHub:
  ```bash
  git init
  git add .
  git commit -m "feat: SignalHire MCP Server for FastMCP Cloud deployment"
  gh repo create signalhire-mcp --public --source=. --remote=origin
  git push -u origin main
  ```

### Testing

- [ ] Local STDIO testing completed
  ```bash
  python server.py
  # Verify: Server starts, loads configuration, no errors
  ```

- [ ] HTTP transport testing (if available)
  ```bash
  TRANSPORT=http python server.py
  # Verify: Server responds on http://localhost:8000
  ```

- [ ] Environment variables tested locally
  - [ ] Create .env with test credentials
  - [ ] Test with real SignalHire API key
  - [ ] Verify callback server connection

- [ ] Tools tested manually:
  - [ ] search_prospects - Basic search query
  - [ ] reveal_contact - Single contact enrichment
  - [ ] check_credits - API key validation
  - [ ] get_request_status - Webhook callback verification

### Security

- [x] No secrets in code or git repository
- [x] .env file not tracked by git
- [x] .env.production template provided (without actual secrets)
- [ ] SignalHire API key stored securely (to be set in FastMCP Cloud)
- [ ] Callback server URL documented (to be set in FastMCP Cloud)

## Deployment Checklist - FastMCP Cloud

### Step 1: Prepare Environment Variables

Gather these values before starting deployment:

```
SIGNALHIRE_API_KEY=<your-actual-api-key>
EXTERNAL_CALLBACK_URL=<your-callback-server-url>/signalhire/callback
```

Optional (if using):
```
MEM0_API_KEY=<your-mem0-key>
SUPABASE_URL=<your-supabase-project-url>
SUPABASE_KEY=<your-supabase-anon-key>
```

### Step 2: FastMCP Cloud Configuration

- [ ] Visit https://cloud.fastmcp.com
- [ ] Sign in with GitHub account
- [ ] Click "New Project"
- [ ] Select repository: `your-username/signalhire-mcp`
- [ ] Configure project:
  - [ ] Name: `signalhire-mcp` (will generate URL: signalhire-mcp.fastmcp.app)
  - [ ] Entrypoint: `server.py:mcp` (auto-detected from fastmcp.json)
  - [ ] Authentication: Organization-only (recommended) or Public

### Step 3: Set Environment Variables in Dashboard

In FastMCP Cloud project settings:

- [ ] Add SIGNALHIRE_API_KEY
- [ ] Add EXTERNAL_CALLBACK_URL (from Step 1 - callback server deployment)
- [ ] Add optional variables (Mem0, Supabase) if configured

### Step 4: Deploy

- [ ] Click "Deploy" button in FastMCP Cloud
- [ ] Monitor build logs for:
  - [ ] Repository cloning
  - [ ] Dependencies installation
  - [ ] Server initialization
  - [ ] Health check passing
- [ ] Wait for "Deployment successful" message
- [ ] Note deployment URL: `https://signalhire-mcp.fastmcp.app/mcp`

Expected deployment time: 30-90 seconds

### Step 5: Verify Build Logs

Check for:
- [x] Python version: >=3.10
- [ ] All dependencies installed successfully
- [ ] No import errors
- [ ] FastMCP server initialization successful
- [ ] Health endpoint responding

## Post-Deployment Verification

### Automated Verification

- [ ] Run post-deployment verification script:
  ```bash
  ../../../plugins/fastmcp/skills/fastmcp-cloud-deployment/scripts/verify-deployment.sh https://signalhire-mcp.fastmcp.app/mcp
  ```

Expected checks:
- [ ] DNS resolution successful
- [ ] Server reachable
- [ ] Health endpoint returns 200 OK
- [ ] MCP endpoint responds to JSON-RPC
- [ ] Tools are listed (13 expected)
- [ ] SSL/TLS certificate valid
- [ ] Response time acceptable (<3s)

### Manual Verification

#### 1. Health Endpoint Test

```bash
curl https://signalhire-mcp.fastmcp.app/health
```

Expected response:
```json
{"status":"healthy","version":"1.0.0"}
```

#### 2. MCP Endpoint Test

```bash
curl -X POST https://signalhire-mcp.fastmcp.app/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/list","id":1}'
```

Expected: JSON response with 13 tools

#### 3. Callback Server Test

```bash
curl https://your-callback-server.com/health
```

Expected: Callback server is accessible

#### 4. End-to-End Tool Test

Using Claude/Cursor IDE:

- [ ] Connect to server in IDE
- [ ] Test `check_credits` tool (should return available credits)
- [ ] Test `search_prospects` tool (basic search)
- [ ] Monitor callback server for webhook delivery
- [ ] Verify results are returned correctly

### Functional Tests

- [ ] Server lists all 13 tools via tools/list
- [ ] Test tool execution:
  - [ ] check_credits - Returns credit balance
  - [ ] search_prospects - Initiates search (returns request_id)
  - [ ] get_request_status - Monitors async request
  - [ ] Webhook callback received (check callback server logs)
- [ ] Resources accessible:
  - [ ] signalhire://credits
  - [ ] signalhire://cache/stats
- [ ] Prompts available (8 expected)

### Performance Tests

- [ ] Response time < 3 seconds for health check
- [ ] Response time < 5 seconds for MCP tool listing
- [ ] Server handles multiple concurrent requests
- [ ] Webhook callbacks processed within 30 seconds

### Monitoring & Logging

- [ ] FastMCP Cloud dashboard shows "Active" status
- [ ] Logs accessible in FastMCP Cloud dashboard
- [ ] No error messages in recent logs
- [ ] Callback server logs show webhook deliveries

## IDE Integration

### Claude Desktop

- [ ] Add to claude_desktop_config.json:
  ```json
  {
    "mcpServers": {
      "signalhire": {
        "url": "https://signalhire-mcp.fastmcp.app/mcp",
        "transport": "http"
      }
    }
  }
  ```
- [ ] Restart Claude Desktop
- [ ] Verify server appears in MCP servers list

### Cursor

- [ ] Add to .cursor/mcp_config.json:
  ```json
  {
    "mcpServers": {
      "signalhire": {
        "url": "https://signalhire-mcp.fastmcp.app/mcp",
        "transport": "http"
      }
    }
  }
  ```
- [ ] Restart Cursor
- [ ] Verify tools are available

### Claude Code

- [ ] Add to .claude/mcp.json:
  ```json
  {
    "mcpServers": {
      "signalhire": {
        "url": "https://signalhire-mcp.fastmcp.app/mcp",
        "transport": "http"
      }
    }
  }
  ```
- [ ] Restart Claude Code
- [ ] Test server connectivity

## Deployment Tracking

- [ ] Update .fastmcp-deployments.json with:
  - [ ] Actual deployment timestamp
  - [ ] Deployment URL
  - [ ] Environment variables status
  - [ ] Post-deployment verification results
  - [ ] Any issues encountered

## Rollback Plan

If deployment fails:

1. [ ] Review FastMCP Cloud build logs for errors
2. [ ] Check environment variables are set correctly
3. [ ] Verify callback server is accessible
4. [ ] Test health endpoint manually
5. [ ] Review server logs for runtime errors
6. [ ] If critical: Revert to previous working version
7. [ ] Document issue in deployment tracking
8. [ ] Fix locally and redeploy

## Post-Deployment Tasks

### Immediate (First 24 hours)

- [ ] Monitor logs every 2-4 hours
- [ ] Test all 13 tools with real data
- [ ] Verify webhook callbacks are working
- [ ] Check error rate (should be <1%)
- [ ] Monitor credit usage
- [ ] Document any issues or unexpected behavior

### First Week

- [ ] Set up automated monitoring alerts
- [ ] Review performance metrics
- [ ] Gather user feedback
- [ ] Document common workflows
- [ ] Update troubleshooting guide with any new issues

### Documentation

- [ ] Update README.md with:
  - [ ] Production deployment URL
  - [ ] Environment setup instructions
  - [ ] Common troubleshooting steps
- [ ] Update FASTMCP_CLOUD_DEPLOYMENT.md if needed
- [ ] Document any deployment issues encountered
- [ ] Share deployment guide with team

## Known Issues & Warnings

1. **Unpinned Dependencies**:
   - Current: Using >= ranges (e.g., httpx>=0.25.0)
   - Risk: May install incompatible future versions
   - Recommendation: Create requirements-pinned.txt with exact versions
   - Priority: Medium (address before production scale)

2. **Localhost References**:
   - Location: server.py callback server initialization
   - Impact: Local callback server won't work in FastMCP Cloud
   - Solution: MUST use EXTERNAL_CALLBACK_URL (already configured in fastmcp.json)
   - Status: Resolved by configuration

3. **Callback Server Dependency**:
   - SignalHire requires webhook callbacks for async operations
   - MUST deploy separate callback server before FastMCP Cloud deployment
   - No fallback if callback server is down
   - Recommendation: Use managed platform with high uptime (DigitalOcean/Railway)

## Success Criteria

Deployment is successful when:

- [x] Pre-deployment validation passed
- [ ] FastMCP Cloud build completed without errors
- [ ] Server status shows "Active"
- [ ] Health endpoint returns 200 OK
- [ ] MCP endpoint responds with 13 tools
- [ ] All tools listed correctly
- [ ] Callback server is accessible
- [ ] End-to-end tool test successful (search + webhook callback)
- [ ] No errors in first 24 hours of logs
- [ ] IDE integration working
- [ ] Deployment tracked in .fastmcp-deployments.json

## Sign-Off

- **Prepared by**: fastmcp-deployment-agent
- **Date Prepared**: 2025-11-02
- **Server Version**: 1.0.0
- **Git Commit**: 0f85f75
- **Environment**: Production
- **Deployment Target**: FastMCP Cloud
- **Status**: ⏳ Ready for deployment (callback server required first)

**Next Action**: Deploy external callback server, then proceed with FastMCP Cloud deployment.

---

**Questions?** See [FASTMCP_CLOUD_DEPLOYMENT.md](FASTMCP_CLOUD_DEPLOYMENT.md) or [EXTERNAL_CALLBACK_SETUP.md](EXTERNAL_CALLBACK_SETUP.md)
