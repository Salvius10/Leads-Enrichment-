# SignalHire MCP → Claude Code Setup

Local stdio MCP server. No hosting, no public URL, no custom connector needed.

**Time:** ~20 minutes if nothing fights you.

---

## Prerequisites

- Python 3.10 or higher (`python3 --version`)
- Claude Code installed and working
- SignalHire API key (from your SignalHire account — API access is a paid tier, confirm your plan covers it)
- `ngrok` or similar tunnel — **only if you need contact reveals**, see Step 5

---

## Step 1 — Clone and read the code

```bash
git clone https://github.com/vanman2024/signalhire-mcp
cd signalhire-mcp
```

**Read these before running anything with a live key:**

- `server.py` — the 13 tool definitions
- `lib/signalhire_client.py` — the actual API calls
- `lib/config.py` — how your key is loaded and where it goes

This repo has 0 stars, 15 commits, and 6 open issues. It is one person's project, not a vetted library. You are about to hand it an API key that can spend credits and pull PII. Ten minutes of reading is cheap insurance.

Red flags to check for specifically:
- Any network call to a host that is not `signalhire.com`
- Your API key being logged, or written anywhere outside `.env`
- The `storage/` adapters (Supabase, Mem0) — confirm they are opt-in and not sending data anywhere by default

If anything looks off, skip to the Appendix and write your own.

---

## Step 2 — Install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Note the absolute path to the venv python — you need it in Step 7:

```bash
which python
# e.g. /home/you/signalhire-mcp/.venv/bin/python
```

---

## Step 3 — Configure your key

```bash
cp .env.example .env
```

Edit `.env`:

```
SIGNALHIRE_API_KEY=your_actual_key_here
EXTERNAL_CALLBACK_URL=
```

Leave `EXTERNAL_CALLBACK_URL` empty for now. Fill it in Step 5 if you need reveals.

**Confirm `.env` is gitignored before you commit anything:**

```bash
grep -n "^\.env$" .gitignore || echo ".env" >> .gitignore
```

The repo's README tells you to commit `.env` to your repo. Do not do that. It is wrong even for a private repo.

---

## Step 4 — Know which tools work without a callback

SignalHire splits into two kinds of calls:

| Works immediately | Needs a callback URL |
|---|---|
| `search_prospects` | `reveal_contact` |
| `scroll_search_results` | `batch_reveal_contacts` |
| `check_credits` | `search_and_enrich` |
| `get_search_suggestions` | `enrich_linkedin_profile` |
| `export_results` | `validate_email` |
| `list_requests`, `clear_cache` | |

Search is synchronous — you get results back in the response. **Reveal is asynchronous** — you submit a request, SignalHire processes it, then POSTs the results to a webhook URL you host. No reachable webhook means the results go nowhere and the credits are still spent.

If you only need search and credit checks, **skip Step 5 entirely.**

---

## Step 5 — Callback tunnel (only if you need reveals)

The repo bundles a FastAPI callback server in `lib/callback_server.py`, started automatically by `server.py` on port 8000. SignalHire's servers need to reach it from the public internet.

Terminal 1:
```bash
source .venv/bin/activate
python server.py
```

Terminal 2:
```bash
ngrok http 8000
```

Copy the `https://` forwarding URL ngrok prints, then update `.env`:

```
EXTERNAL_CALLBACK_URL=https://abc123.ngrok-free.app/signalhire/callback
```

Restart `server.py`.

**Caveat:** free ngrok URLs change every restart, so you will re-edit `.env` each session. If reveals become a routine thing, put the callback server on a small VPS with a fixed domain and point `EXTERNAL_CALLBACK_URL` there permanently — the MCP server itself can still stay local.

Health check:
```bash
curl http://localhost:8000/health
```

---

## Step 6 — Test before wiring it to Claude Code

```bash
fastmcp dev server.py
```

This opens the MCP Inspector in your browser. Test in this order:

1. **`check_credits`** — cheapest possible call, confirms your key authenticates
2. **`search_prospects`** — use a small limit (5–10) to confirm the search path
3. **`reveal_contact`** — one single contact, only after 1 and 2 pass, only if you set up Step 5

Do not run `batch_reveal_contacts` here. If the callback round-trip is broken, you burn credits on results that never arrive.

If `check_credits` fails, the problem is your key or the client code, not Claude Code. Fix it here before moving on.

---

## Step 7 — Register with Claude Code

Use absolute paths for both the python binary and the server script:

```bash
claude mcp add signalhire -- /absolute/path/to/signalhire-mcp/.venv/bin/python /absolute/path/to/signalhire-mcp/server.py
```

Scope options:
- `-s local` (default) — this project only
- `-s user` — available in every project on your machine

The repo also ships a `.mcp.json` and supports `fastmcp install claude-code .mcp.json`. Either works; the `claude mcp add` route is more transparent about what actually got registered.

Verify:
```bash
claude mcp list
```

---

## Step 8 — Confirm it works

Start Claude Code, then in-session:

```
/mcp
```

You should see `signalhire` connected with its tools listed. Then just ask:

```
Check my SignalHire credits
```

```
Search SignalHire for 10 fintech founders in Bangalore
```

---

## Troubleshooting

**Server shows as failed in `/mcp`**
Run the exact command from Step 7 directly in your shell. Claude Code launches it as a subprocess — if it crashes on startup you will see the traceback there, not in Claude Code.

**`ModuleNotFoundError`**
You registered the system python instead of the venv python. Re-check the path from Step 2.

**Key not found / 401**
`server.py` loads `.env` relative to its own directory. Confirm the file is beside `server.py` and has no quotes around the value.

**Reveal submits but nothing comes back**
Callback URL unreachable. Check ngrok is still running, the URL in `.env` matches the current tunnel, and the path ends in `/signalhire/callback`.

**Rate limits**
600 items/minute, 3 concurrent searches, 5,000 reveals/day, 5,000 search profiles/day. `scrollId` expires after 15 seconds, so paginate immediately or re-search.

---

## Before you pipe this into anything

Contact enrichment data is personal data. If results land in a database, the DPDP Act applies to Indian subjects and GDPR to EU ones — purpose limitation, retention limits, and deletion requests all attach to the stored copy, not just the lookup. Worth deciding the retention policy before the first bulk export rather than after.

Also keep an eye on credit spend: `batch_reveal_contacts` can clear a daily allowance in one call. Check `check_credits` first as a habit.

---

## Appendix — the DIY option

If the repo looks unmaintained or you just want less surface area, a minimal server covering the three tools you actually need (`search`, `reveal`, `credits`) is roughly 100 lines with FastMCP:

```python
from fastmcp import FastMCP
import httpx, os

mcp = FastMCP("signalhire")
KEY = os.environ["SIGNALHIRE_API_KEY"]

@mcp.tool()
async def search_prospects(query: str, size: int = 10) -> dict:
    """Search SignalHire profiles."""
    async with httpx.AsyncClient() as c:
        r = await c.post(
            "<search endpoint from the API docs>",
            headers={"apikey": KEY},
            json={"...": query, "size": size},
        )
        return r.json()

if __name__ == "__main__":
    mcp.run()
```

Confirm the exact endpoints, auth header name, and request shape at <https://www.signalhire.com/api-docs> — do not trust the skeleton above for those specifics. Register it the same way as Step 7.

This is genuinely less work than debugging someone else's 7,000 lines, and you own every line that touches your key.
