# External Callback Server Setup (DigitalOcean)

This guide explains how to configure the SignalHire MCP Server to use your existing DigitalOcean callback server instead of starting a local one.

## Why Use an External Callback Server?

SignalHire's API is **async** - when you request contact enrichment, it returns immediately with a `requestId` and sends results to a **webhook callback URL** when ready.

**Benefits of external callback server:**
- ✅ Already hosted and running 24/7
- ✅ Public URL accessible to SignalHire API
- ✅ Can integrate with Mem0, Supabase, Airtable, etc.
- ✅ Handles webhooks for multiple MCP server instances
- ✅ No need to expose local server or use ngrok

## Configuration

### Step 1: Get Your DigitalOcean Callback URL

Your callback server should be hosted at a public URL, for example:
```
https://callback.yourdomain.com/signalhire/callback
```

Or if using DigitalOcean App Platform:
```
https://signalhire-callback-xxxxx.ondigitalocean.app/signalhire/callback
```

### Step 2: Update `.env` File

Edit `/home/gotime2022/Projects/Mcp-Servers/signalhire/.env`:

```bash
# Your SignalHire API Key (GET THIS FROM YOUR SIGNALHIRE DASHBOARD)
SIGNALHIRE_API_KEY=your_actual_api_key_here

# Your DigitalOcean callback server URL
EXTERNAL_CALLBACK_URL=https://your-actual-callback-server.com/signalhire/callback
```

**That's it!** The MCP server will now send all webhook URLs to your external server.

### Step 3: Verify Configuration

Run the configuration test:

```bash
cd /home/gotime2022/Projects/Mcp-Servers/signalhire
python3 test_configuration.py
```

You should see:
```
✅ API Key configured: ••••••••••...
✅ External callback URL configured:
   https://your-actual-callback-server.com/signalhire/callback
ℹ️  Local callback server will NOT be started
```

## How It Works

### Without External URL (Local Mode)

```python
# .env
# EXTERNAL_CALLBACK_URL not set

# Server behavior:
- Starts local FastAPI callback server on port 8000
- Uses http://localhost:8000/signalhire/callback
- Only works for local testing (not accessible to SignalHire API)
```

### With External URL (Production Mode)

```python
# .env
EXTERNAL_CALLBACK_URL=https://callback.yourdomain.com/signalhire/callback

# Server behavior:
- Does NOT start local callback server
- Uses your DigitalOcean URL for all API requests
- Works in production (SignalHire can reach it)
```

## Integration with Mem0 and Supabase

Your DigitalOcean callback server can store webhook results in:

### Mem0 (Semantic Memory)
```python
# In your callback server
@app.post("/signalhire/callback")
async def handle_callback(data: dict):
    # Store in Mem0
    mem0.add(
        messages=[{
            "role": "user",
            "content": f"Contact: {data['fullName']}, {data['email']}"
        }],
        user_id=data['uid']
    )
```

### Supabase (PostgreSQL + pgvector)
```python
# In your callback server
@app.post("/signalhire/callback")
async def handle_callback(data: dict):
    # Store in Supabase
    supabase.table('signalhire_contacts').insert({
        'uid': data['uid'],
        'full_name': data['fullName'],
        'email': data['email'],
        'phone': data['phone'],
        'raw_data': data
    }).execute()
```

## Callback Server Requirements

Your DigitalOcean callback server should:

1. **Accept POST requests** at `/signalhire/callback`
2. **Validate** the request contains valid SignalHire data
3. **Store results** in Mem0, Supabase, or your database
4. **Return 200 OK** to acknowledge receipt

### Example Callback Handler

```python
from fastapi import FastAPI, Request
from pydantic import BaseModel

app = FastAPI()

class SignalHireCallback(BaseModel):
    item: str  # LinkedIn URL or identifier
    status: str  # "success" or "failed"
    candidate: dict | None  # Profile data if successful

@app.post("/signalhire/callback")
async def signalhire_webhook(request: Request):
    """Handle SignalHire webhook callbacks"""
    data = await request.json()

    # Parse callback data
    for item in data:
        if item['status'] == 'success' and item['candidate']:
            # Store in your database
            await store_contact(item['candidate'])

    return {"status": "accepted"}
```

## Testing the Integration

### 1. Test from MCP Server

```bash
cd /home/gotime2022/Projects/Mcp-Servers/signalhire
python server.py
```

### 2. Make a Test Request

In Claude Code:
```
Search SignalHire for a Python engineer and enrich their profile
```

### 3. Verify Webhook Received

Check your DigitalOcean callback server logs:
```bash
# Should see POST requests from SignalHire
POST /signalhire/callback - 200 OK
```

## Troubleshooting

### Server Still Starting Local Callback

**Problem:** Local callback server starts even though EXTERNAL_CALLBACK_URL is set

**Solution:**
1. Check `.env` file has EXTERNAL_CALLBACK_URL uncommented
2. Verify no placeholder text like "your-digitalocean-server"
3. Restart the MCP server

### SignalHire Not Sending Webhooks

**Problem:** No callbacks received at DigitalOcean server

**Check:**
1. URL is publicly accessible: `curl https://your-callback-server.com/health`
2. SSL certificate is valid (SignalHire requires HTTPS)
3. Server is running and healthy
4. Check SignalHire dashboard for failed webhook attempts

### Multiple MCP Instances

**Question:** Can multiple MCP servers use the same callback URL?

**Answer:** Yes! Your callback server can handle webhooks from multiple MCP server instances. Just make sure to:
- Include request tracking (request_id) in your database
- Handle concurrent requests properly
- Use async processing for heavy operations

## Environment Variables Reference

```bash
# REQUIRED
SIGNALHIRE_API_KEY=your_api_key

# RECOMMENDED: Use external callback server
EXTERNAL_CALLBACK_URL=https://callback.yourdomain.com/signalhire/callback

# FALLBACK: Local callback server (only if EXTERNAL_CALLBACK_URL not set)
CALLBACK_SERVER_HOST=0.0.0.0
CALLBACK_SERVER_PORT=8000

# OPTIONAL: Enhanced storage
MEM0_API_KEY=your_mem0_key
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_supabase_key
```

## Next Steps

1. **Get your DigitalOcean callback URL**
2. **Update `.env`** with EXTERNAL_CALLBACK_URL
3. **Test the configuration** with `python3 test_configuration.py`
4. **Deploy** and test with real SignalHire API requests
5. **Integrate with Mem0/Supabase** for storing enriched contacts

---

**Ready to deploy?** See [README.md](README.md) for deployment instructions.
