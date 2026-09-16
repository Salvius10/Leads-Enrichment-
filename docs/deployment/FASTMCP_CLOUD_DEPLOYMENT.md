# FastMCP Cloud Deployment Guide

This guide walks you through deploying the SignalHire MCP Server to FastMCP Cloud.

## Prerequisites

- GitHub account (required for FastMCP Cloud authentication)
- SignalHire API key
- External callback server (required for webhook handling)

## Important: Webhook Callback Architecture

The SignalHire API uses webhooks to deliver async results (search results, contact enrichment). This requires a **publicly accessible callback server**.

### Why You Need an External Callback Server

FastMCP Cloud deployments serve only the MCP protocol and cannot receive webhooks from SignalHire. You need a **separate callback server** deployed to a publicly accessible URL.

### Callback Server Deployment Options

1. **DigitalOcean App Platform** (recommended for production):
   ```bash
   # Use the provided deployment script
   chmod +x deploy-callback.sh
   ./deploy-callback.sh
   ```
   See [EXTERNAL_CALLBACK_SETUP.md](EXTERNAL_CALLBACK_SETUP.md) for detailed instructions.

2. **Railway, Render, or similar platform**:
   - Deploy `callback_server.py` as a standalone FastAPI app
   - Use `requirements.callback.txt` for dependencies
   - Expose on a public URL

3. **Webhook relay for development** (not recommended for production):
   - Use smee.io, ngrok, or similar service
   - Forward webhooks to local callback server

## Deployment Steps

### Step 1: Pre-Deployment Validation

Run validation scripts to ensure the server is ready:

```bash
cd servers/business-productivity/signalhire

# Run pre-deployment validation
../../../plugins/fastmcp/skills/fastmcp-cloud-deployment/scripts/validate-server.sh .
```

Expected output: All checks should pass.

### Step 2: Deploy External Callback Server

**IMPORTANT**: Deploy your callback server FIRST before deploying to FastMCP Cloud.

```bash
# Deploy to DigitalOcean (recommended)
chmod +x deploy-callback.sh
./deploy-callback.sh

# Or follow EXTERNAL_CALLBACK_SETUP.md for manual deployment
```

Save the callback server URL (e.g., `https://your-app.ondigitalocean.app/signalhire/callback`).

### Step 3: Create GitHub Repository

FastMCP Cloud requires a GitHub repository:

```bash
# Create a new directory for production deployment
mkdir -p ~/signalhire-mcp-production
cp -r . ~/signalhire-mcp-production/
cd ~/signalhire-mcp-production

# Initialize git repository
git init
git add .
git commit -m "Initial commit: SignalHire MCP Server for FastMCP Cloud"

# Create repository on GitHub (use GitHub CLI or web interface)
gh repo create signalhire-mcp --public --source=. --remote=origin

# Push to GitHub
git push -u origin main
```

### Step 4: Configure FastMCP Cloud

1. Visit [FastMCP Cloud](https://cloud.fastmcp.com) and sign in with GitHub
2. Click "New Project"
3. Configure your project:
   - **Name**: `signalhire-mcp` (or your preferred name)
   - **Repository**: Select your `signalhire-mcp` repository
   - **Entrypoint**: `server.py:mcp` (detected automatically from `fastmcp.json`)
   - **Authentication**: Organization-only (recommended) or Public

4. Set environment variables in FastMCP Cloud dashboard:
   ```
   SIGNALHIRE_API_KEY=your_actual_signalhire_api_key
   EXTERNAL_CALLBACK_URL=https://your-callback-server.com/signalhire/callback
   ```

   Optional environment variables:
   ```
   MEM0_API_KEY=your_mem0_api_key (if using Mem0)
   SUPABASE_URL=https://your-project.supabase.co (if using Supabase)
   SUPABASE_KEY=your_supabase_anon_key (if using Supabase)
   ```

5. Click "Deploy"

### Step 5: Monitor Deployment

Watch the build logs in the FastMCP Cloud dashboard:

- Dependencies installation
- Server initialization
- Health check validation
- Deployment URL generation

Expected deployment time: 30-60 seconds.

### Step 6: Verify Deployment

Once deployed, your server will be available at:
```
https://signalhire-mcp.fastmcp.app/mcp
```

Test the deployment:

```bash
# Run post-deployment verification
../../../plugins/fastmcp/skills/fastmcp-cloud-deployment/scripts/verify-deployment.sh https://signalhire-mcp.fastmcp.app/mcp
```

Expected output:
- DNS resolution successful
- Server reachable
- Health endpoint responding
- MCP endpoint returning tools
- SSL/TLS certificate valid

### Step 7: Connect to Claude/Cursor

Add the server to your IDE configuration:

#### Claude Desktop

Add to `claude_desktop_config.json`:
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

#### Cursor

Add to `.cursor/mcp_config.json`:
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

#### Claude Code

Add to `.claude/mcp.json`:
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

Restart your IDE to load the new configuration.

## Troubleshooting

### Deployment Fails

1. **Check build logs** in FastMCP Cloud dashboard for errors
2. **Verify environment variables** are set correctly
3. **Check requirements.txt** has all dependencies with pinned versions
4. **Validate fastmcp.json** syntax using the JSON schema

### Server Not Responding

1. **Check server status** in FastMCP Cloud dashboard
2. **Verify callback server** is running and accessible
3. **Test health endpoint**: `curl https://signalhire-mcp.fastmcp.app/health`
4. **Review server logs** in FastMCP Cloud dashboard

### Webhooks Not Working

1. **Verify callback server** is deployed and accessible:
   ```bash
   curl https://your-callback-server.com/health
   ```

2. **Check EXTERNAL_CALLBACK_URL** is set correctly in FastMCP Cloud

3. **Test callback endpoint**:
   ```bash
   curl -X POST https://your-callback-server.com/signalhire/callback \
     -H "Content-Type: application/json" \
     -d '{"test": "data"}'
   ```

4. **Review callback server logs** for incoming webhooks

### Tools Not Available

1. **Verify server initialization** in logs
2. **Check FastMCP version** matches requirements (>=2.10.0)
3. **Test MCP endpoint**:
   ```bash
   curl -X POST https://signalhire-mcp.fastmcp.app/mcp \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","method":"tools/list","id":1}'
   ```

## Continuous Deployment

FastMCP Cloud automatically deploys changes pushed to the `main` branch:

```bash
# Make changes locally
git add .
git commit -m "Update server configuration"
git push origin main

# FastMCP Cloud will automatically:
# 1. Detect the push
# 2. Build the server
# 3. Run health checks
# 4. Deploy if successful
```

## Production Checklist

Before going to production:

- [ ] Callback server deployed and tested
- [ ] All environment variables set in FastMCP Cloud
- [ ] Health endpoint responding
- [ ] MCP endpoint returns all tools
- [ ] Test search_prospects tool
- [ ] Test reveal_contact tool (verify webhook callbacks work)
- [ ] Verify credits are displayed correctly
- [ ] Test error handling (invalid API key, etc.)
- [ ] Monitor logs for first 24 hours
- [ ] Set up alerts for failures

## Monitoring

### Health Checks

FastMCP Cloud automatically monitors your server:
- Health endpoint checks every 30 seconds
- Auto-restart if server becomes unresponsive
- Email alerts for deployment failures

### Manual Monitoring

```bash
# Check server status
curl https://signalhire-mcp.fastmcp.app/health

# List available tools
curl -X POST https://signalhire-mcp.fastmcp.app/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/list","id":1}'

# Check callback server
curl https://your-callback-server.com/health
```

### Logs

View logs in FastMCP Cloud dashboard:
- Real-time logs during deployment
- Historical logs for debugging
- Error tracking and alerts

## Support

- **FastMCP Cloud**: https://cloud.fastmcp.com/support
- **SignalHire API**: https://www.signalhire.com/help
- **MCP Protocol**: https://modelcontextprotocol.io

## Next Steps

After successful deployment:

1. **Test all tools** with real data
2. **Monitor webhook callbacks** to ensure async operations work
3. **Set up alerts** for failures or rate limit issues
4. **Document custom workflows** for your team
5. **Consider Mem0/Supabase** for enhanced memory and storage

## Architecture Diagram

```
┌─────────────────┐
│  Claude/Cursor  │
│      IDE        │
└────────┬────────┘
         │ MCP Protocol
         │
         ▼
┌─────────────────────────┐
│  FastMCP Cloud          │
│  signalhire-mcp.        │
│  fastmcp.app/mcp        │
└────────┬────────────────┘
         │ HTTPS API Calls
         │
         ▼
┌─────────────────────────┐      ┌──────────────────────┐
│  SignalHire API         │◄─────┤  External Callback   │
│  www.signalhire.com     │      │  Server              │
│                         │      │  (DigitalOcean)      │
│  Webhooks ──────────────┼─────►│                      │
└─────────────────────────┘      └──────────────────────┘
```

## Security Considerations

1. **Never commit `.env` files** to git
2. **Use organization-only auth** in FastMCP Cloud for private servers
3. **Rotate API keys** regularly
4. **Monitor rate limits** to avoid API quota exhaustion
5. **Secure callback server** with authentication if handling sensitive data

## Cost Considerations

- **FastMCP Cloud**: Free during beta
- **SignalHire API**: Pay-per-use credits (check pricing at signalhire.com)
- **Callback Server**:
  - DigitalOcean: $5-10/month for basic app
  - Railway/Render: Similar pricing tiers
- **Optional Services**:
  - Mem0: Check pricing at mem0.ai
  - Supabase: Free tier available, paid for production

---

**Questions?** See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) or open an issue in the GitHub repository.
