#!/bin/bash
# Deploy SignalHire MCP Server to DigitalOcean Droplet
# This script properly manages secrets using environment files

set -e

# Configuration
DROPLET_NAME="signalhire-callback"
DROPLET_IP="137.184.196.101"
DEPLOY_DIR="/opt/signalhire-callback"
SERVICE_NAME="signalhire-callback"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 SignalHire Droplet Deployment${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check if API key is provided
if [ -z "$SIGNALHIRE_API_KEY" ]; then
    echo -e "${RED}❌ ERROR: SIGNALHIRE_API_KEY environment variable not set${NC}"
    echo ""
    echo "Usage:"
    echo "  export SIGNALHIRE_API_KEY='your_api_key_here'"
    echo "  bash $0"
    echo ""
    echo "Or run in one line:"
    echo "  SIGNALHIRE_API_KEY='your_key' bash $0"
    exit 1
fi

# Validate API key format
if [[ ! "$SIGNALHIRE_API_KEY" =~ ^202\. ]]; then
    echo -e "${YELLOW}⚠️  WARNING: API key doesn't match expected format (should start with '202.')${NC}"
    read -p "Continue anyway? (y/N): " confirm
    if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
        exit 1
    fi
fi

echo -e "${GREEN}✓${NC} API key validated"

# Step 1: Create secure environment file
echo ""
echo "📝 Step 1: Creating secure environment file..."

cat > /tmp/signalhire.env <<EOF
# SignalHire MCP Server Environment Configuration
# SECURITY: This file contains sensitive credentials
# File permissions: 600 (owner read/write only)

# REQUIRED: SignalHire API Key
SIGNALHIRE_API_KEY=${SIGNALHIRE_API_KEY}

# OPTIONAL: External callback server (if different from this droplet)
# EXTERNAL_CALLBACK_URL=https://your-callback-server.com/signalhire/callback

# OPTIONAL: Mem0 integration
# MEM0_API_KEY=your_mem0_key

# OPTIONAL: Supabase integration
# SUPABASE_URL=https://your-project.supabase.co
# SUPABASE_KEY=your_supabase_key

# Server configuration
HOST=0.0.0.0
PORT=8000
EOF

echo -e "${GREEN}✓${NC} Environment file created at /tmp/signalhire.env"

# Step 2: Upload environment file to droplet
echo ""
echo "📤 Step 2: Uploading environment file to droplet..."

doctl compute ssh $DROPLET_NAME --ssh-command "sudo mkdir -p /etc/signalhire"
doctl compute scp /tmp/signalhire.env $DROPLET_NAME:/tmp/signalhire.env
doctl compute ssh $DROPLET_NAME --ssh-command "sudo mv /tmp/signalhire.env /etc/signalhire/.env && sudo chmod 600 /etc/signalhire/.env && sudo chown root:root /etc/signalhire/.env"

echo -e "${GREEN}✓${NC} Environment file uploaded to /etc/signalhire/.env"

# Clean up local temp file
trash-put /tmp/signalhire.env 2>/dev/null || rm -f /tmp/signalhire.env

# Step 3: Create systemd service
echo ""
echo "⚙️  Step 3: Creating systemd service..."

cat > /tmp/signalhire-callback.service <<'EOF'
[Unit]
Description=SignalHire MCP Callback Server
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/signalhire-callback
EnvironmentFile=/etc/signalhire/.env
ExecStart=/opt/signalhire-callback/venv/bin/python start-callback.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=signalhire-callback

# Security settings
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/signalhire-callback

[Install]
WantedBy=multi-user.target
EOF

doctl compute scp /tmp/signalhire-callback.service $DROPLET_NAME:/tmp/signalhire-callback.service
doctl compute ssh $DROPLET_NAME --ssh-command "sudo mv /tmp/signalhire-callback.service /etc/systemd/system/signalhire-callback.service && sudo chmod 644 /etc/systemd/system/signalhire-callback.service"

echo -e "${GREEN}✓${NC} Systemd service created"

# Clean up local temp file
trash-put /tmp/signalhire-callback.service 2>/dev/null || rm -f /tmp/signalhire-callback.service

# Step 4: Deploy application code
echo ""
echo "📦 Step 4: Deploying application code..."

# Sync code to droplet (excluding sensitive files)
rsync -avz --progress \
    --exclude='.git' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.env' \
    --exclude='.env.*' \
    --exclude='venv' \
    --exclude='node_modules' \
    -e "ssh" \
    ./ root@$DROPLET_IP:$DEPLOY_DIR/

echo -e "${GREEN}✓${NC} Code deployed to $DEPLOY_DIR"

# Step 5: Install dependencies
echo ""
echo "📚 Step 5: Installing dependencies..."

doctl compute ssh $DROPLET_NAME --ssh-command "cd $DEPLOY_DIR && python3 -m venv venv && venv/bin/pip install -r requirements.callback.txt"

echo -e "${GREEN}✓${NC} Dependencies installed"

# Step 6: Restart service
echo ""
echo "🔄 Step 6: Restarting service..."

doctl compute ssh $DROPLET_NAME --ssh-command "sudo systemctl daemon-reload"
doctl compute ssh $DROPLET_NAME --ssh-command "sudo systemctl enable signalhire-callback"
doctl compute ssh $DROPLET_NAME --ssh-command "sudo systemctl restart signalhire-callback"

# Wait for service to start
sleep 3

# Step 7: Verify deployment
echo ""
echo "✅ Step 7: Verifying deployment..."

# Check service status
if doctl compute ssh $DROPLET_NAME --ssh-command "sudo systemctl is-active --quiet signalhire-callback"; then
    echo -e "${GREEN}✓${NC} Service is running"
else
    echo -e "${RED}✗${NC} Service failed to start"
    echo ""
    echo "View logs with:"
    echo "  doctl compute ssh $DROPLET_NAME --ssh-command 'sudo journalctl -u signalhire-callback -n 50'"
    exit 1
fi

# Check health endpoint
echo ""
echo "Testing health endpoint..."
sleep 2

if curl -sf http://$DROPLET_IP:8000/health > /dev/null; then
    echo -e "${GREEN}✓${NC} Health check passed: http://$DROPLET_IP:8000/health"
else
    echo -e "${YELLOW}⚠${NC}  Health check failed (service might still be starting)"
fi

# Display service info
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}✅ Deployment Complete!${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📡 Endpoints:"
echo "   Health:    http://$DROPLET_IP:8000/health"
echo "   Callback:  http://$DROPLET_IP:8000/signalhire/callback"
echo ""
echo "🔧 Management Commands:"
echo "   View logs:    doctl compute ssh $DROPLET_NAME --ssh-command 'sudo journalctl -u signalhire-callback -f'"
echo "   Restart:      doctl compute ssh $DROPLET_NAME --ssh-command 'sudo systemctl restart signalhire-callback'"
echo "   Stop:         doctl compute ssh $DROPLET_NAME --ssh-command 'sudo systemctl stop signalhire-callback'"
echo "   Status:       doctl compute ssh $DROPLET_NAME --ssh-command 'sudo systemctl status signalhire-callback'"
echo ""
echo "🔒 Security:"
echo "   Environment: /etc/signalhire/.env (permissions: 600)"
echo "   Service:     /etc/systemd/system/signalhire-callback.service"
echo ""
echo "⚠️  Remember to:"
echo "   1. Configure firewall to allow port 8000 (if not already)"
echo "   2. Set up HTTPS with nginx/caddy reverse proxy"
echo "   3. Monitor logs regularly"
echo ""
