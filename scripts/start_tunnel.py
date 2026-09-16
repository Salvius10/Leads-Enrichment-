"""Start the ngrok tunnel and point .env at it.

Free ngrok mints a new URL on every restart, and a stale EXTERNAL_CALLBACK_URL
fails silently: the reveal submits, credits are spent, and the results are
POSTed to a URL that no longer exists. This script makes that one command.

    .venv\\Scripts\\python.exe scripts\\start_tunnel.py

Reuses an already-running tunnel instead of starting a second one. Restart
Claude Code afterwards so the MCP server re-reads .env.
"""

import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ENV_FILE = REPO / ".env"
NGROK_API = "http://127.0.0.1:4040/api/tunnels"
CALLBACK_PATH = "/signalhire/callback"
PORT = 8000


def find_tunnel(timeout: float = 0.0) -> str | None:
    """Return the public https URL of a running tunnel, if any."""
    deadline = time.time() + timeout
    while True:
        try:
            with urllib.request.urlopen(NGROK_API, timeout=3) as resp:
                data = json.load(resp)
            for tunnel in data.get("tunnels", []):
                if tunnel.get("proto") == "https":
                    return tunnel["public_url"]
        except (urllib.error.URLError, OSError, json.JSONDecodeError):
            pass
        if time.time() >= deadline:
            return None
        time.sleep(1)


def start_ngrok() -> None:
    """Launch ngrok detached so it outlives this script."""
    flags = 0
    kwargs = {}
    if sys.platform == "win32":
        flags = subprocess.CREATE_NEW_CONSOLE
        kwargs["creationflags"] = flags
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen(
        ["ngrok", "http", str(PORT)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        **kwargs,
    )


def update_env(callback_url: str) -> bool:
    """Rewrite EXTERNAL_CALLBACK_URL in .env. Returns True if it changed."""
    if not ENV_FILE.exists():
        sys.exit(f"No .env at {ENV_FILE} - copy .env.example and add your API key.")

    text = ENV_FILE.read_text(encoding="utf-8")
    line = f"EXTERNAL_CALLBACK_URL={callback_url}"
    pattern = re.compile(r"(?m)^EXTERNAL_CALLBACK_URL=.*$")

    if pattern.search(text):
        current = pattern.search(text).group(0)
        if current == line:
            return False
        text = pattern.sub(line, text, count=1)
    else:
        text = text.rstrip("\n") + f"\n{line}\n"

    ENV_FILE.write_text(text, encoding="utf-8")
    return True


def main() -> None:
    public_url = find_tunnel()
    if public_url:
        print(f"Reusing running tunnel: {public_url}")
    else:
        print(f"Starting ngrok on port {PORT}...")
        start_ngrok()
        public_url = find_tunnel(timeout=20)
        if not public_url:
            sys.exit(
                "ngrok did not come up within 20s.\n"
                "Run 'ngrok http 8000' manually and check for an auth error."
            )
        print(f"Tunnel up: {public_url}")

    callback_url = public_url.rstrip("/") + CALLBACK_PATH
    changed = update_env(callback_url)
    print(f"{'Updated' if changed else 'Already correct'}: EXTERNAL_CALLBACK_URL={callback_url}")

    # The listener only runs inside the MCP server, so a failure here is expected
    # when Claude Code is not currently running the server.
    try:
        req = urllib.request.Request(
            public_url.rstrip("/") + "/health",
            headers={"ngrok-skip-browser-warning": "1"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            print(f"Callback listener reachable through tunnel: HTTP {resp.status}")
    except Exception:
        print("Callback listener not up yet (expected - it starts with the MCP server).")

    if changed:
        print("\nRestart Claude Code so the MCP server re-reads .env.")


if __name__ == "__main__":
    main()
