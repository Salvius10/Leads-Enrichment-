# DigitalOcean Droplet Deployment Guide

Complete guide for deploying SignalHire MCP Server to a DigitalOcean Droplet with proper secrets management using `doctl`.

## Overview

This deployment uses:
- ✅ **DigitalOcean Droplet** (VM) at `137.184.196.101`
- ✅ **Systemd service** for process management
- ✅ **Encrypted environment file** at `/etc/signalhire/.env`
- ✅ **doctl** for deployment automation
- ✅ **No app.yaml** (that's only for App Platform, not droplets)

## Prerequisites

### 1. Install doctl

```bash
# Install doctl
snap install doctl

# Authenticate
doctl auth init

# Verify
doctl account get
doctl compute droplet list
```

### 2. Get Your SignalHire API Key

1. Go to https://www.signalhire.com/settings/api
2. If you have an exposed key, **REVOKE IT IMMEDIATELY**
3. Generate a new API key
4. Copy it (you'll use it below)

---

## Quick Start: Deploy Everything

Deploy the entire application with one command:

```bash
cd servers/business-productivity/signalhire

# Set your API key (REQUIRED)
export SIGNALHIRE_API_KEY='your_signalhire_api_key_here'

# Deploy
bash deploy-to-droplet.sh
```

This script will:
1. ✅ Create secure environment file (`/etc/signalhire/.env`)
2. ✅ Upload secrets to droplet
3. ✅ Create systemd service
4. ✅ Deploy application code
5. ✅ Install dependencies
6. ✅ Start the service
7. ✅ Verify deployment

---

## Update Secrets Only

If you just need to rotate the API key without redeploying:

```bash
# Set your NEW API key
export SIGNALHIRE_API_KEY='your_new_api_key_here'

# Update secrets and restart
bash update-secrets.sh
```

This will:
1. Upload new environment file
2. Restart the service
3. Verify it's running

---

## How It Works

### Architecture

```
┌─────────────────────────────────────────┐
│   DigitalOcean Droplet (137.184.196.101)│
│                                         │
│  ┌───────────────────────────────────┐ │
│  │  Systemd Service                  │ │
│  │  signalhire-callback.service      │ │
│  │                                   │ │
│  │  Reads: /etc/signalhire/.env     │ │
│  │  ├─ SIGNALHIRE_API_KEY=••••••    │ │
│  │  ├─ HOST=0.0.0.0                 │ │
│  │  └─ PORT=8000                    │ │
│  │                                   │ │
│  │  Runs: /opt/signalhire-callback/ │ │
│  │        venv/bin/python            │ │
│  │        start-callback.py          │ │
│  └───────────────────────────────────┘ │
│                                         │
│  Listens on: 0.0.0.0:8000              │
└─────────────────────────────────────────┘
         │
         ├─ http://137.184.196.101:8000/health
         └─ http://137.184.196.101:8000/signalhire/callback
```

### File Locations on Droplet

| Path | Purpose | Permissions |
|------|---------|-------------|
| `/etc/signalhire/.env` | **Secrets** (API keys) | `600` (root only) |
| `/etc/systemd/system/signalhire-callback.service` | Systemd service | `644` |
| `/opt/signalhire-callback/` | Application code | `755` |
| `/opt/signalhire-callback/venv/` | Python virtual environment | `755` |

### Why This Approach?

**Secure:**
- ✅ Secrets stored in `/etc/signalhire/.env` with 600 permissions
- ✅ Only root can read the environment file
- ✅ Systemd loads secrets directly into process environment
- ✅ Secrets never stored in git or code

**Automated:**
- ✅ One command to deploy everything
- ✅ One command to update secrets
- ✅ Uses `doctl` for remote management

**Production-Ready:**
- ✅ Systemd ensures service restarts on failure
- ✅ Logs go to journald (centralized logging)
- ✅ Process isolation and security hardening

---

## Management Commands

### View Logs

```bash
# Follow logs in real-time
doctl compute ssh signalhire-callback --ssh-command 'sudo journalctl -u signalhire-callback -f'

# View last 100 lines
doctl compute ssh signalhire-callback --ssh-command 'sudo journalctl -u signalhire-callback -n 100'

# View logs from today
doctl compute ssh signalhire-callback --ssh-command 'sudo journalctl -u signalhire-callback --since today'
```

### Service Control

```bash
# Check status
doctl compute ssh signalhire-callback --ssh-command 'sudo systemctl status signalhire-callback'

# Restart service
doctl compute ssh signalhire-callback --ssh-command 'sudo systemctl restart signalhire-callback'

# Stop service
doctl compute ssh signalhire-callback --ssh-command 'sudo systemctl stop signalhire-callback'

# Start service
doctl compute ssh signalhire-callback --ssh-command 'sudo systemctl start signalhire-callback'

# Disable auto-start
doctl compute ssh signalhire-callback --ssh-command 'sudo systemctl disable signalhire-callback'
```

### Check Environment Variables

```bash
# View current environment (secrets will be hidden)
doctl compute ssh signalhire-callback --ssh-command 'sudo systemctl show signalhire-callback --property=Environment'

# View environment file (requires root)
doctl compute ssh signalhire-callback --ssh-command 'sudo cat /etc/signalhire/.env'
```

### Test Endpoints

```bash
# Health check
curl http://137.184.196.101:8000/health

# Should return:
# {
#   "status": "healthy",
#   "service": "signalhire-callback",
#   "timestamp": "2025-11-02T..."
# }
```

---

## Rotating API Keys

When you need to rotate your SignalHire API key:

### Step 1: Generate New Key

1. Go to https://www.signalhire.com/settings/api
2. Generate new API key
3. Copy it

### Step 2: Update on Droplet

```bash
# Set new key
export SIGNALHIRE_API_KEY='new_key_here'

# Update
bash update-secrets.sh
```

### Step 3: Revoke Old Key

1. Go back to SignalHire dashboard
2. Revoke the old key
3. Verify new key works

---

## Troubleshooting

### Service Won't Start

**Check logs:**
```bash
doctl compute ssh signalhire-callback --ssh-command 'sudo journalctl -u signalhire-callback -n 50'
```

**Common issues:**
- Missing API key → Check `/etc/signalhire/.env` exists
- Wrong permissions → Should be `600` owned by `root`
- Python errors → Check dependencies installed
- Port already in use → Check if another process uses port 8000

### Can't Connect to Endpoints

**Check firewall:**
```bash
doctl compute ssh signalhire-callback --ssh-command 'sudo ufw status'

# Allow port 8000 if needed
doctl compute ssh signalhire-callback --ssh-command 'sudo ufw allow 8000/tcp'
```

**Check service is running:**
```bash
doctl compute ssh signalhire-callback --ssh-command 'sudo systemctl is-active signalhire-callback'
```

### API Key Not Working

**Verify format:**
- SignalHire keys start with `202.`
- No extra spaces or quotes

**Test manually:**
```bash
doctl compute ssh signalhire-callback --ssh-command 'cat /etc/signalhire/.env | grep SIGNALHIRE_API_KEY'
```

---

## Security Best Practices

### 1. Environment File Permissions

```bash
# Verify secure permissions
doctl compute ssh signalhire-callback --ssh-command 'ls -la /etc/signalhire/.env'

# Should show: -rw------- 1 root root
```

### 2. Regular Key Rotation

- Rotate API keys every 90 days
- Immediately rotate if exposed
- Document rotation in change log

### 3. Firewall Configuration

```bash
# Only allow necessary ports
doctl compute ssh signalhire-callback --ssh-command 'sudo ufw default deny incoming'
doctl compute ssh signalhire-callback --ssh-command 'sudo ufw default allow outgoing'
doctl compute ssh signalhire-callback --ssh-command 'sudo ufw allow ssh'
doctl compute ssh signalhire-callback --ssh-command 'sudo ufw allow 8000/tcp'
doctl compute ssh signalhire-callback --ssh-command 'sudo ufw enable'
```

### 4. HTTPS Setup (Recommended)

For production, use nginx or Caddy as reverse proxy:

```bash
# Install Caddy (auto HTTPS)
doctl compute ssh signalhire-callback --ssh-command '
  sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https
  curl -1sLf "https://dl.cloudsmith.io/public/caddy/stable/gpg.key" | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  echo "deb [signed-by=/usr/share/keyrings/caddy-stable-archive-keyring.gpg] https://dl.cloudsmith.io/public/caddy/stable/deb/debian any-version main" | sudo tee /etc/apt/sources.list.d/caddy-stable.list
  sudo apt update
  sudo apt install caddy
'

# Configure Caddyfile
# Then your endpoint becomes: https://your-domain.com/signalhire/callback
```

---

## Manual Deployment (Advanced)

If you need to deploy manually without scripts:

### 1. Create Environment File

```bash
cat > /tmp/signalhire.env <<EOF
SIGNALHIRE_API_KEY=your_key_here
HOST=0.0.0.0
PORT=8000
EOF
```

### 2. Upload to Droplet

```bash
doctl compute scp /tmp/signalhire.env signalhire-callback:/tmp/
doctl compute ssh signalhire-callback --ssh-command '
  sudo mkdir -p /etc/signalhire
  sudo mv /tmp/signalhire.env /etc/signalhire/.env
  sudo chmod 600 /etc/signalhire/.env
  sudo chown root:root /etc/signalhire/.env
'
```

### 3. Create Systemd Service

```bash
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

[Install]
WantedBy=multi-user.target
EOF

doctl compute scp /tmp/signalhire-callback.service signalhire-callback:/tmp/
doctl compute ssh signalhire-callback --ssh-command '
  sudo mv /tmp/signalhire-callback.service /etc/systemd/system/
  sudo systemctl daemon-reload
  sudo systemctl enable signalhire-callback
  sudo systemctl start signalhire-callback
'
```

---

## Related Documentation

- [SECRETS_MANAGEMENT.md](./SECRETS_MANAGEMENT.md) - General secrets management guide
- [SECURITY_INCIDENT.md](./SECURITY_INCIDENT.md) - Security incident response
- [README.md](./README.md) - Main documentation

---

## Quick Reference

```bash
# Deploy everything
export SIGNALHIRE_API_KEY='your_key'
bash deploy-to-droplet.sh

# Update secrets only
export SIGNALHIRE_API_KEY='new_key'
bash update-secrets.sh

# View logs
doctl compute ssh signalhire-callback --ssh-command 'sudo journalctl -u signalhire-callback -f'

# Restart
doctl compute ssh signalhire-callback --ssh-command 'sudo systemctl restart signalhire-callback'

# Test
curl http://137.184.196.101:8000/health
```

---

**Remember:**
- ✅ Use `doctl` for all deployments
- ✅ Store secrets in `/etc/signalhire/.env`
- ✅ NEVER commit `.env` files to git
- ✅ Rotate API keys regularly
- ❌ Don't use `app.yaml` (that's for App Platform, not droplets)
