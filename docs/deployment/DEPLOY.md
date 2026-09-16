# FastMCP Cloud Deployment - Quick Reference

**Server**: SignalHire MCP Server v1.0.0
**Status**: ✅ Ready for deployment

---

## Prerequisites

Before starting:

- [ ] SignalHire API key (get from https://www.signalhire.com/settings/api)
- [ ] GitHub account
- [ ] FastMCP Cloud account (sign up at https://cloud.fastmcp.com)

---

## 5-Step Deployment

### Step 1: Verify Callback Server (Required)

**⚠️ Check if already deployed**: If you previously deployed the callback server to DigitalOcean, verify it's still running:

```bash
# Check if callback server is running
curl https://your-callback.ondigitalocean.app/health

# If it returns {"status":"healthy"}, you can skip to Step 2
# If it fails, redeploy:
chmod +x deploy-callback.sh
./deploy-callback.sh
```

**If not deployed yet**:
```bash
# Option A: DigitalOcean (Recommended)
chmod +x deploy-callback.sh
./deploy-callback.sh
# Follow prompts and save the callback URL

# Option B: See ../setup/EXTERNAL_CALLBACK_SETUP.md for other platforms
```

**Save your callback URL**: `https://your-callback.ondigitalocean.app/signalhire/callback`

---

### Step 2: Create GitHub Repository

```bash
# Create deployment directory
mkdir -p ~/signalhire-mcp-production
cp -r . ~/signalhire-mcp-production/
cd ~/signalhire-mcp-production

# Push to GitHub
git init
git add .
git commit -m "feat: SignalHire MCP Server"
gh repo create signalhire-mcp --public --source=. --remote=origin
git push -u origin main
```

---

### Step 3: Configure FastMCP Cloud

1. Go to https://cloud.fastmcp.com
2. Sign in with GitHub
3. Click **"New Project"**
4. Select repository: `your-username/signalhire-mcp`
5. Project name: `signalhire-mcp`
6. Set environment variables:

```
SIGNALHIRE_API_KEY=<your-signalhire-api-key>
EXTERNAL_CALLBACK_URL=<your-callback-server-url>/signalhire/callback
```

7. Click **"Deploy"**

---

### Step 4: Wait for Deployment

Watch build logs (30-60 seconds):
- ✓ Cloning repository
- ✓ Installing dependencies
- ✓ Starting server
- ✓ Health check passed

**Deployment URL**: `https://signalhire-mcp.fastmcp.app/mcp`

---

### Step 5: Verify & Connect

**Test deployment**:
```bash
curl https://signalhire-mcp.fastmcp.app/health
# Should return: {"status":"healthy","version":"1.0.0"}
```

**Add to your IDE**:

Claude Desktop (`claude_desktop_config.json`):
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

Restart IDE and start using!

---

## Quick Troubleshooting

**Build fails?**
- Check environment variables are set in FastMCP Cloud
- Verify callback server is accessible: `curl https://your-callback.com/health`
- Review build logs for specific errors

**Server not responding?**
- Verify deployment status in FastMCP Cloud dashboard
- Check health endpoint: `curl https://signalhire-mcp.fastmcp.app/health`
- Review server logs in dashboard

**Webhooks not working?**
- Verify callback server is running
- Check EXTERNAL_CALLBACK_URL is correct
- Test callback endpoint: `curl https://your-callback.com/signalhire/callback -X POST`

---

## Full Documentation

For detailed information, see:

- **Complete Guide**: [FASTMCP_CLOUD_DEPLOYMENT.md](FASTMCP_CLOUD_DEPLOYMENT.md)
- **Detailed Checklist**: [DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md)
- **Configuration Summary**: [DEPLOYMENT_SUMMARY.md](DEPLOYMENT_SUMMARY.md)
- **Callback Server Setup**: [../setup/EXTERNAL_CALLBACK_SETUP.md](../setup/EXTERNAL_CALLBACK_SETUP.md)

---

## Need Help?

- FastMCP Cloud: https://cloud.fastmcp.com/support
- SignalHire API: https://www.signalhire.com/help
- Issues: Open GitHub issue in your repository

---

**Total Time**: ~10 minutes (callback server + FastMCP Cloud deployment)
