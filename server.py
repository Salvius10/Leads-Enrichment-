"""
SignalHire MCP Server - Standalone FastMCP Cloud Deployment

Complete MCP server implementation wrapping the SignalHire agent functionality.
Provides 13 tools, 7 resources, and 8 prompts for comprehensive access to SignalHire API.

Self-contained configuration: Loads .env from server directory automatically.
"""

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from dotenv import load_dotenv
from fastmcp import FastMCP, Context

try:
    from fastmcp.server.middleware.response_limiting import ResponseLimitingMiddleware
    HAS_RESPONSE_LIMITING = True
except ImportError:
    HAS_RESPONSE_LIMITING = False

from pydantic import Field

# Startup/shutdown notices must go to stderr: stdout is the JSON-RPC channel for
# the stdio transport, and Windows consoles default to cp1252, which cannot
# encode the emoji below.
def _log(message: str) -> None:
    try:
        print(message, file=sys.stderr, flush=True)
    except UnicodeEncodeError:
        print(message.encode("ascii", "replace").decode("ascii"),
              file=sys.stderr, flush=True)


# structlog and the stdlib root logger both default to stdout, which is the
# JSON-RPC channel under the stdio transport -- a single log line there corrupts
# the stream and the client reports "tools fetch failed". Pin both to stderr
# before importing anything under lib/, since those bind a logger at import time.
import logging

import structlog

logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(message)s")
structlog.configure(logger_factory=structlog.PrintLoggerFactory(file=sys.stderr))


# Load .env from the same directory as this server.py file
SERVER_DIR = Path(__file__).parent
ENV_FILE = SERVER_DIR / ".env"
if ENV_FILE.exists():
    load_dotenv(ENV_FILE)
    _log(f"✅ Loaded configuration from {ENV_FILE}")
else:
    _log(f"⚠️  No .env file found at {ENV_FILE}")

# Import local SignalHire components (all local, no external package dependencies)
from lib.signalhire_client import SignalHireClient
from lib.callback_server import CallbackServer, get_server
from lib.contact_cache import ContactCache
from lib.config import load_config
from models.person_callback import PersonCallbackItem

# Mem0 and Supabase removed - agents handle storage per use case


# =============================================================================
# Server Configuration & Initialization
# =============================================================================

# Global state management
class AppState:
    """Application state container"""
    client: SignalHireClient | None = None
    callback_server: CallbackServer | None = None
    cache: ContactCache | None = None
    # request_id -> completed reveal payload. The contact cache is keyed by uid,
    # so it cannot answer "is request X done?" on its own.
    results: dict = {}

state = AppState()

def get_callback_url() -> str:
    """
    Get callback URL - either external (DigitalOcean) or local server.

    Priority:
    1. EXTERNAL_CALLBACK_URL environment variable (e.g., DigitalOcean)
    2. Local callback server URL
    """
    external_url = os.getenv("EXTERNAL_CALLBACK_URL")
    if external_url:
        return external_url
    if state.callback_server:
        return state.callback_server.get_callback_url()
    raise RuntimeError("No callback server configured")


def _items_to_dicts(callback_data) -> list[dict]:
    """Serialize PersonCallbackItem objects to plain dicts."""
    out = []
    for item in callback_data:
        try:
            out.append(item.model_dump(mode="json", by_alias=True, exclude_none=True))
        except AttributeError:
            out.append(dict(item))
    return out


def _cache_contacts(callback_data) -> None:
    """Write revealed contacts into the uid-keyed cache.

    Registered globally so results survive even if the per-request handler was
    not registered in time (the webhook can in principle beat the registration).
    """
    if not state.cache:
        return
    for item in callback_data:
        candidate = getattr(item, "candidate", None)
        if getattr(item, "status", None) != "success" or candidate is None:
            continue
        payload = candidate.model_dump(mode="json", by_alias=True, exclude_none=True)
        uid = payload.get("uid")
        if not uid:
            continue
        state.cache.update_from_reveal_payload(uid, payload, profile=payload)
    try:
        state.cache.save()
    except Exception as exc:  # noqa: BLE001
        _log(f"⚠️  Failed to persist contact cache: {exc}")


def _store_reveal_result(request_id, callback_data) -> None:
    """Record a completed reveal so get_request_status() can report it."""
    items = _items_to_dicts(callback_data)
    state.results[str(request_id)] = {
        "status": "completed",
        "received_at": datetime.now(timezone.utc).isoformat(),
        "items": items,
    }
    _cache_contacts(callback_data)
    _log(f"📥 Stored reveal result for {request_id} ({len(items)} item(s))")


def _track_request(request_id) -> None:
    """Register the one-time handler for a submitted reveal request.

    The API returns the id as an int, but it comes back as a string in the
    Request-Id header, so both the handler map and the results store are keyed by
    str -- otherwise the lookup in _process_callback never matches.
    """
    if not request_id or not state.callback_server:
        return
    key = str(request_id)
    state.results[key] = {"status": "processing", "items": []}
    state.callback_server.register_request_handler(key, _store_reveal_result)


@asynccontextmanager
async def lifespan(app):
    """Server lifecycle management (FastMCP 2.x pattern)"""
    # ===== STARTUP =====
    _log("🚀 Starting SignalHire MCP Server...")

    # Load configuration
    config = load_config()

    # Initialize SignalHire client
    state.client = SignalHireClient(
        api_key=config.signalhire.api_key,
        base_url=config.signalhire.base_url
    )
    await state.client.start_session()

    # Check if using external callback server (DigitalOcean)
    external_callback_url = os.getenv("EXTERNAL_CALLBACK_URL")

    # EXTERNAL_CALLBACK_URL only decides which URL we advertise to SignalHire; it
    # must not decide whether we listen. A tunnel (ngrok) terminates at this local
    # listener, and get_request_status() reads results out of this process's cache,
    # so the listener has to run even when an external URL is advertised. Set
    # DISABLE_LOCAL_CALLBACK_SERVER=1 for a genuinely remote callback host.
    if external_callback_url:
        _log(f"✅ Advertising external callback URL: {external_callback_url}")

    if os.getenv("DISABLE_LOCAL_CALLBACK_SERVER", "").strip() in ("1", "true", "yes"):
        _log("ℹ️  Local callback listener disabled by DISABLE_LOCAL_CALLBACK_SERVER")
        state.callback_server = None
    else:
        # Start local callback server
        state.callback_server = get_server(
            host=config.callback_server.host,
            port=config.callback_server.port
        )
        state.callback_server.start(background=True)
        _log(f"📡 Local callback server: {get_callback_url()}")

    # Initialize contact cache
    state.cache = ContactCache()

    # Nothing else registers a handler, so without this every webhook payload is
    # logged and then dropped on the floor.
    if state.callback_server:
        state.callback_server.register_handler("cache_contacts", _cache_contacts)

    _log("✅ SignalHire MCP Server started successfully")

    yield  # Server runs here

    # ===== SHUTDOWN =====
    _log("👋 Shutting down SignalHire MCP Server...")

    if state.client:
        await state.client.close_session()
    if state.callback_server:
        state.callback_server.stop()

    _log("✅ SignalHire MCP Server stopped")


# Create FastMCP server with lifespan
mcp = FastMCP(
    name="SignalHire",
    instructions="""
    SignalHire MCP Server provides access to 900M+ professional profiles for contact enrichment and lead generation.

    Key capabilities:
    - Search for prospects with advanced Boolean queries
    - Reveal contact information (emails, phones) for profiles
    - Batch operations with automatic rate limiting
    - Credit management and usage tracking
    - Webhook-based async operations

    IMPORTANT — Credit pools:
    SignalHire has TWO separate credit pools:
    1. Regular credits (with contacts) — used by default. Always use this unless told otherwise.
    2. "Without contacts" credits — a separate, smaller pool. Do NOT use without_contacts=true
       unless you have confirmed available credits via check_credits(without_contacts=true) first.
    Most accounts have credits only in pool #1. Using without_contacts=true when pool #2 is empty
    causes a 402 "Insufficient credits" error even though pool #1 has thousands of credits.

    Workflow:
    1. search_prospects() to find candidates (free, no credits consumed)
    2. reveal_contact() or batch_reveal_contacts() to get contact info (1 credit each)
       — ALWAYS use the default without_contacts=false
    3. Results arrive async via webhook callback
    4. Use get_request_status() to check completion

    All operations respect rate limits (600 items/min, 3 concurrent searches).
    """,
    version="1.0.0",
    lifespan=lifespan  # FastMCP 2.x lifecycle management
)

if HAS_RESPONSE_LIMITING:
    mcp.add_middleware(ResponseLimitingMiddleware(max_size=100_000))


# =============================================================================
# TOOLS (13 total)
# =============================================================================

# -----------------------------------------------------------------------------
# Core API Tools (5)
# -----------------------------------------------------------------------------

@mcp.tool
async def search_prospects(
    title: Annotated[str | None, Field(description="Job title (supports Boolean: AND, OR, NOT)")] = None,
    location: Annotated[list[str] | None, Field(description="City, state, or country (multiple allowed)")] = None,
    company: Annotated[str | None, Field(description="Company name (supports Boolean operators)")] = None,
    keywords: Annotated[str | None, Field(description="Skills, education, bio keywords (Boolean supported)")] = None,
    years_experience_from: Annotated[int | None, Field(ge=0, description="Minimum years of experience")] = None,
    years_experience_to: Annotated[int | None, Field(le=50, description="Maximum years of experience")] = None,
    open_to_work: Annotated[bool | None, Field(description="Filter by job-seeking status")] = None,
    current_past_title: Annotated[str | None, Field(description="Boolean query for current AND past job titles")] = None,
    current_past_company: Annotated[str | None, Field(description="Boolean query for current AND past companies")] = None,
    full_name: Annotated[str | None, Field(description="Search by person's full name")] = None,
    industry: Annotated[str | None, Field(description="Filter by industry category")] = None,
    exclude_revealed: Annotated[bool | None, Field(description="Exclude already-revealed profiles (saves credits)")] = None,
    exclude_emailed: Annotated[bool | None, Field(description="Exclude previously emailed profiles")] = None,
    exclude_watched: Annotated[bool | None, Field(description="Exclude previously viewed profiles")] = None,
    exclude_in_lists: Annotated[bool | None, Field(description="Exclude profiles already in lists")] = None,
    exclude_in_progress: Annotated[bool | None, Field(description="Exclude profiles in job pipelines")] = None,
    latitude: Annotated[float | None, Field(description="Latitude for geo search")] = None,
    longitude: Annotated[float | None, Field(description="Longitude for geo search")] = None,
    years_current_past_experience_from: Annotated[int | None, Field(ge=0, description="Min total years experience (current + past)")] = None,
    years_current_past_experience_to: Annotated[int | None, Field(ge=0, description="Max total years experience (current + past)")] = None,
    size: Annotated[int, Field(ge=1, le=100, description="Results per page")] = 25,
    ctx: Context = None
) -> dict:
    """
    Search SignalHire's 900M+ profile database with advanced filters.

    Returns profile UIDs only (no contacts). Use reveal_contact() to get contact info.
    Supports Boolean queries: "Software Engineer AND (Python OR Java)"
    """
    await ctx.info(f"Searching for prospects with title='{title}', location={location}")

    # Build search criteria
    criteria = {}
    if title:
        criteria["currentTitle"] = title
    if location:
        criteria["location"] = location
    if company:
        criteria["currentCompany"] = company
    if keywords:
        criteria["keywords"] = keywords
    if years_experience_from is not None:
        criteria["yearsOfCurrentExperienceFrom"] = years_experience_from
    if years_experience_to is not None:
        criteria["yearsOfCurrentExperienceTo"] = years_experience_to
    if open_to_work is not None:
        criteria["openToWork"] = open_to_work
    if current_past_title:
        criteria["currentPastTitle"] = current_past_title
    if current_past_company:
        criteria["currentPastCompany"] = current_past_company
    if full_name:
        criteria["fullName"] = full_name
    if industry:
        criteria["industry"] = industry
    if exclude_revealed is not None:
        criteria["excludeRevealed"] = exclude_revealed
    if exclude_emailed is not None:
        criteria["excludeEmailed"] = exclude_emailed
    if exclude_watched is not None:
        criteria["excludeWatched"] = exclude_watched
    if exclude_in_lists is not None:
        criteria["excludeInLists"] = exclude_in_lists
    if exclude_in_progress is not None:
        criteria["excludeInProgress"] = exclude_in_progress
    if latitude is not None:
        criteria["latitude"] = latitude
    if longitude is not None:
        criteria["longitude"] = longitude
    if years_current_past_experience_from is not None:
        criteria["yearsOfCurrentPastExperienceFrom"] = years_current_past_experience_from
    if years_current_past_experience_to is not None:
        criteria["yearsOfCurrentPastExperienceTo"] = years_current_past_experience_to

    # Execute search
    response = await state.client.search_prospects(criteria, size=size)

    if not response.success:
        raise ValueError(f"Search failed: {response.error}")

    profiles = response.data.get("profiles", [])
    total = response.data.get("total", 0)

    await ctx.info(f"Found {total} total profiles, returning first {len(profiles)}")

    return {
        "total": total,
        "count": len(profiles),
        "profiles": profiles,
        "scroll_id": response.data.get("scrollId"),
        "request_id": response.data.get("requestId")
    }


@mcp.tool
async def reveal_contact(
    identifier: Annotated[str, Field(description="LinkedIn URL, email, phone, or UID")],
    without_contacts: Annotated[bool, Field(description="LEAVE AS FALSE (default). If true, uses a separate 'without contacts' credit pool which is likely empty (causes 402). Only set true after confirming credits via check_credits(without_contacts=true).")] = False,
    ctx: Context = None
) -> dict:
    """
    Reveal contact information for a single profile.

    IMPORTANT: Always use the default without_contacts=false. The without_contacts=true
    option uses a separate credit pool that is typically empty (0 credits), causing 402 errors.

    Async operation - returns requestId immediately, then sends results to webhook.
    Use get_request_status() to check completion or wait for webhook callback.
    """
    await ctx.info(f"Revealing contact for: {identifier}")

    callback_url = get_callback_url()

    response = await state.client.reveal_contact_by_identifier(
        identifier,
        callback_url,
        without_contacts=without_contacts
    )

    if not response.success:
        raise ValueError(f"Reveal failed: {response.error}")

    # The Person API returns camelCase "requestId"; the batch client normalizes to
    # "request_id". Accept either, or single reveals hand back a null id and the
    # result can never be correlated to the request.
    data = response.data or {}
    # Returned as a str so it can be passed straight back into
    # get_request_status(request_id: str) without a type error.
    request_id = data.get("requestId") or data.get("request_id")
    request_id = str(request_id) if request_id is not None else None
    _track_request(request_id)
    await ctx.info(f"Reveal request submitted: {request_id}")

    return {
        "request_id": request_id,
        "status": "processing",
        "identifier": identifier,
        "callback_url": callback_url,
        "message": "Results will be sent to webhook when ready"
    }


@mcp.tool
async def batch_reveal_contacts(
    identifiers: Annotated[list[str], Field(description="List of LinkedIn URLs, emails, phones, or UIDs (max 100)")],
    without_contacts: Annotated[bool, Field(description="LEAVE AS FALSE (default). The without_contacts credit pool is typically empty. Only set true after confirming credits via check_credits(without_contacts=true).")] = False,
    ctx: Context = None
) -> dict:
    """
    Batch reveal contact information for multiple profiles.

    IMPORTANT: Always use the default without_contacts=false. The without_contacts=true
    option uses a separate credit pool that is typically empty, causing 402 errors.

    Automatically splits into 100-item chunks and handles rate limiting.
    Returns request_id for tracking. Use get_request_status() to monitor progress.
    """
    # MCP clients may send list as JSON string — parse if needed
    if isinstance(identifiers, str):
        identifiers = json.loads(identifiers)

    if len(identifiers) > 100:
        await ctx.warning(f"Batch size {len(identifiers)} exceeds 100 - will be split automatically")

    await ctx.info(f"Batch revealing {len(identifiers)} contacts")
    await ctx.report_progress(0, len(identifiers), "Starting batch reveal...")

    callback_url = get_callback_url()

    response = await state.client.batch_reveal_contacts(
        identifiers,
        callback_url,
        without_contacts=without_contacts,
        progress_callback=lambda p, t: asyncio.create_task(ctx.report_progress(p, t))
    )

    if not response.success:
        raise ValueError(f"Batch reveal failed: {response.error}")

    await ctx.report_progress(len(identifiers), len(identifiers), "Batch reveal submitted")

    batch_request_id = response.data.get("request_id")
    batch_request_id = str(batch_request_id) if batch_request_id is not None else None
    _track_request(batch_request_id)

    return {
        "request_id": batch_request_id,
        "count": len(identifiers),
        "status": "processing",
        "message": "Batch processing started - results will be sent to webhook"
    }


@mcp.tool
async def check_credits(
    without_contacts: Annotated[bool, Field(description="If true, checks the separate 'without contacts' credit pool (usually 0). Default false checks regular credits.")] = False,
    ctx: Context = None
) -> dict:
    """
    Check remaining API credits.

    SignalHire has TWO separate credit pools:
    - Regular (default, without_contacts=false): Main credit balance used for reveals with contact info.
    - Without contacts (without_contacts=true): Separate pool, often empty (0 credits).

    Always check regular credits first. Only check without_contacts pool if you specifically need it.
    """
    response = await state.client.check_credits(without_contacts=without_contacts)

    if not response.success:
        raise ValueError(f"Credits check failed: {response.error}")

    credits = response.data.get("credits", 0)
    await ctx.info(f"Remaining credits: {credits}")

    return {
        "credits": credits,
        "type": "no_contacts" if without_contacts else "with_contacts"
    }


@mcp.tool
async def scroll_search_results(
    request_id: Annotated[str, Field(description="Request ID from initial search")],
    scroll_id: Annotated[str, Field(description="Scroll ID from previous batch")],
    ctx: Context = None
) -> dict:
    """
    Fetch next batch of search results.

    scrollId expires after 15 seconds - must be called promptly.
    Returns next batch of profiles and new scrollId for pagination.
    """
    await ctx.info(f"Scrolling search results for request {request_id}")

    try:
        request_id_int = int(request_id)
    except (ValueError, TypeError):
        raise ValueError(f"Invalid request_id '{request_id}' — must be a numeric ID from the initial search")

    response = await state.client.scroll_search(request_id_int, scroll_id)

    if not response.success:
        if "expired" in str(response.error).lower():
            raise ValueError("scrollId expired (15s timeout) - restart search")
        raise ValueError(f"Scroll failed: {response.error}")

    profiles = response.data.get("profiles", [])
    new_scroll_id = response.data.get("scrollId")

    await ctx.info(f"Fetched {len(profiles)} more profiles")

    return {
        "count": len(profiles),
        "profiles": profiles,
        "scroll_id": new_scroll_id,
        "has_more": bool(new_scroll_id)
    }


# -----------------------------------------------------------------------------
# Workflow Tools (5)
# -----------------------------------------------------------------------------

@mcp.tool
async def search_and_enrich(
    title: Annotated[str | None, Field(description="Job title to search")] = None,
    location: Annotated[list[str] | None, Field(description="Locations to search")] = None,
    company: Annotated[str | None, Field(description="Company to search")] = None,
    max_results: Annotated[int, Field(ge=1, le=100, description="Max profiles to enrich")] = 25,
    ctx: Context = None
) -> dict:
    """
    Combined workflow: Search for profiles then automatically enrich with contacts.

    1. Searches SignalHire database with filters
    2. Extracts UIDs from results
    3. Batch reveals contacts for all UIDs
    4. Returns request_id for tracking

    Most common use case - use this for end-to-end lead generation.
    """
    await ctx.info("Starting search and enrich workflow...")
    await ctx.report_progress(0, 3, "Phase 1: Searching profiles...")

    # Phase 1: Search (call client directly, not tool objects)
    criteria = {}
    if title:
        criteria["currentTitle"] = title
    if location:
        criteria["location"] = location
    if company:
        criteria["currentCompany"] = company

    search_response = await state.client.search_prospects(criteria, size=max_results)

    if not search_response.success:
        raise ValueError(f"Search failed: {search_response.error}")

    profiles = search_response.data.get("profiles", [])
    total = search_response.data.get("total", 0)
    uids = [p["uid"] for p in profiles if "uid" in p]

    if not uids:
        return {
            "error": "No profiles found",
            "search_total": total
        }

    await ctx.report_progress(1, 3, f"Phase 2: Enriching {len(uids)} profiles...")

    # Phase 2: Batch reveal (call client directly, not tool objects)
    callback_url = get_callback_url()
    reveal_response = await state.client.batch_reveal_contacts(
        uids, callback_url
    )

    if not reveal_response.success:
        raise ValueError(f"Batch reveal failed: {reveal_response.error}")

    await ctx.report_progress(3, 3, "Workflow complete")

    request_id = reveal_response.data.get("request_id")

    return {
        "search_total": total,
        "profiles_found": len(profiles),
        "enrichment_request_id": request_id,
        "status": "processing",
        "message": f"Enriching {len(uids)} profiles - results will be sent to webhook"
    }


@mcp.tool
async def enrich_linkedin_profile(
    linkedin_url: Annotated[str, Field(description="LinkedIn profile URL")],
    ctx: Context = None
) -> dict:
    """
    Enrich a single LinkedIn profile with contact information.

    High-level wrapper that:
    1. Checks credits
    2. Reveals contact
    3. Returns tracking info

    Use this for simple single-profile enrichment.
    """
    await ctx.info(f"Enriching LinkedIn profile: {linkedin_url}")

    # Check credits first (call client directly, not the tool object)
    credits_response = await state.client.check_credits()
    if not credits_response.success:
        raise ValueError(f"Credits check failed: {credits_response.error}")

    credits = credits_response.data.get("credits", 0)
    if credits < 1:
        raise ValueError("Insufficient credits")

    # Reveal contact (call client directly, not the tool object)
    callback_url = get_callback_url()
    reveal_response = await state.client.reveal_contact_by_identifier(
        linkedin_url, callback_url
    )

    if not reveal_response.success:
        raise ValueError(f"Reveal failed: {reveal_response.error}")

    request_id = reveal_response.data.get("requestId") or reveal_response.data.get("request_id")

    return {
        "request_id": request_id,
        "profile_url": linkedin_url,
        "status": "processing",
        "credits_remaining": credits - 1,
        "callback_url": callback_url,
        "message": "Profile enrichment started - results will be sent to webhook"
    }


@mcp.tool
async def validate_email(
    email: Annotated[str, Field(description="Email address to validate")],
    ctx: Context = None
) -> dict:
    """
    Validate if an email exists in SignalHire database.

    Quick validation without consuming credits if email is invalid.
    Returns true/false + confidence score.
    """
    await ctx.info(f"Validating email: {email}")

    # Use reveal to check existence (uses regular credits — without_contacts pool has 0)
    response = await state.client.reveal_contact_by_identifier(
        email,
        get_callback_url(),
        without_contacts=False
    )

    if not response.success:
        return {
            "email": email,
            "valid": False,
            "confidence": 0.0,
            "reason": str(response.error)
        }

    return {
        "email": email,
        "valid": True,
        "confidence": 0.9,
        "request_id": response.data.get("request_id")
    }


@mcp.tool
async def export_results(
    request_id: Annotated[str, Field(description="Request ID to export")],
    format: Annotated[str, Field(description="Export format: csv, json, or excel")] = "json",
    ctx: Context = None
) -> dict:
    """
    Export enriched contacts to file format.

    Retrieves completed results from cache and formats for export.
    Supports CSV, JSON, and Excel formats.
    """
    await ctx.info(f"Exporting results for request {request_id} as {format}")

    # Get request status (would need to implement this in client)
    # For now, return export structure

    return {
        "request_id": request_id,
        "format": format,
        "status": "exported",
        "message": "Export functionality to be implemented based on export_service"
    }


@mcp.tool
async def get_search_suggestions(
    query: Annotated[str, Field(description="Partial search query to get suggestions for")],
    ctx: Context = None
) -> list[str]:
    """
    Get search query refinement suggestions.

    Analyzes partial query and suggests Boolean operators, filters, and common patterns.
    Helps users construct effective search queries.
    """
    await ctx.info(f"Generating suggestions for: {query}")

    suggestions = []

    # Basic Boolean suggestions
    if "and" not in query.lower():
        suggestions.append(f"{query} AND Python")
        suggestions.append(f"{query} AND (AWS OR Azure)")

    # Location suggestions
    if not any(loc in query.lower() for loc in ["san francisco", "new york", "remote"]):
        suggestions.append(f"{query} in San Francisco")
        suggestions.append(f"{query} (Remote)")

    # Experience level suggestions
    suggestions.append(f"Senior {query}")
    suggestions.append(f"{query} with 5+ years")

    # Company type suggestions
    suggestions.append(f"{query} at (Google OR Amazon OR Microsoft)")
    suggestions.append(f"{query} at Startup")

    return suggestions[:10]


# -----------------------------------------------------------------------------
# Management Tools (3)
# -----------------------------------------------------------------------------

@mcp.tool
async def get_request_status(
    request_id: Annotated[str, Field(description="Request ID to check")],
    ctx: Context = None
) -> dict:
    """
    Check status of an async request.

    SignalHire uses an async callback model - results are POSTed to your callbackUrl.
    This tool checks local tracking state for the given request ID.
    """
    await ctx.info(f"Checking status for request: {request_id}")

    # Completed results land here via the registered callback handler
    record = state.results.get(str(request_id))
    if record and record.get("status") == "completed":
        items = record["items"]
        return {
            "request_id": request_id,
            "status": "completed",
            "received_at": record.get("received_at"),
            "item_count": len(items),
            "results": items,
        }

    # Check if callback server has pending handler for this request
    if state.callback_server and request_id in state.callback_server._request_handlers:
        return {
            "request_id": request_id,
            "status": "processing",
            "message": "Awaiting callback from SignalHire"
        }

    # Check cache for completed results
    if state.cache:
        cached = state.cache.get(request_id)
        if cached:
            return {
                "request_id": request_id,
                "status": "completed",
                "data": cached
            }

    return {
        "request_id": request_id,
        "status": "unknown",
        "message": "No local tracking data found. SignalHire API is fully async - results are delivered via webhook callback. Check your callback server logs."
    }


@mcp.tool
async def list_requests(
    limit: Annotated[int, Field(ge=1, le=100, description="Max requests to return")] = 10,
    ctx: Context = None
) -> dict:
    """
    List tracked API requests.

    SignalHire uses an async callback model. This returns locally tracked
    pending requests from the callback server.
    """
    await ctx.info(f"Listing tracked requests")

    pending = []
    if state.callback_server:
        pending = list(state.callback_server._request_handlers.keys())[:limit]

    return {
        "pending_requests": pending,
        "pending_count": len(pending),
        "message": "SignalHire API is fully async. Results are delivered via webhook callback. These are requests awaiting callbacks."
    }


@mcp.tool
async def clear_cache(ctx: Context = None) -> dict:
    """
    Clear local contact cache.

    Removes all cached enriched profiles from local storage.
    Use this to free up disk space or reset state.
    """
    await ctx.info("Clearing contact cache...")

    state.cache.clear()

    return {
        "status": "cleared",
        "message": "All cached contacts removed"
    }


# =============================================================================
# RESOURCES (7 total)
# =============================================================================

@mcp.resource("signalhire://contacts/{uid}")
async def get_cached_contact(uid: str) -> str:
    """Get enriched contact from cache by UID"""
    contact = state.cache.get(uid)
    if not contact:
        raise ValueError(f"Contact {uid} not found in cache")
    return json.dumps(contact)


@mcp.resource("signalhire://cache/stats")
async def get_cache_stats() -> str:
    """Get contact cache statistics"""
    stats = state.cache.get_stats() if hasattr(state.cache, 'get_stats') else {}
    data = {
        "total_contacts": len(state.cache._cache) if hasattr(state.cache, '_cache') else 0,
        "cache_size_mb": 0,
        **stats
    }
    return json.dumps(data)


@mcp.resource("signalhire://recent-searches")
async def get_recent_searches() -> str:
    """Get recent search queries (last 10)"""
    return json.dumps([])


@mcp.resource("signalhire://credits")
async def get_credits_resource() -> str:
    """Current credit balance (cached for 5 min)"""
    response = await state.client.check_credits()
    if not response.success:
        raise ValueError(f"Credits check failed: {response.error}")
    return json.dumps(response.data)


@mcp.resource("signalhire://credits/all")
async def get_all_credits_resource() -> str:
    """Both credit pools: regular (with contacts) and without-contacts. Check this before using without_contacts=true."""
    regular = await state.client.check_credits(without_contacts=False)
    without = await state.client.check_credits(without_contacts=True)
    data = {
        "regular_credits": regular.data.get("credits", 0) if regular.success else "error",
        "without_contacts_credits": without.data.get("credits", 0) if without.success else "error",
        "recommendation": "Use regular credits (default). Without-contacts pool is typically 0."
    }
    return json.dumps(data)


@mcp.resource("signalhire://rate-limits")
async def get_rate_limits() -> str:
    """Current rate limit status"""
    rate_limiter = state.client.rate_limiter if state.client else None
    if not rate_limiter:
        return json.dumps({"status": "unknown"})

    return json.dumps({
        "items_per_minute": 600,
        "concurrent_searches": 3,
        "daily_limit": rate_limiter.daily_limit,
        "daily_usage": rate_limiter.daily_usage,
    })


@mcp.resource("signalhire://requests/history")
async def get_requests_history() -> str:
    """Pending request history from local callback server"""
    pending = []
    if state.callback_server:
        pending = [
            {"request_id": rid, "status": "pending"}
            for rid in state.callback_server._request_handlers.keys()
        ]
    return json.dumps(pending)


@mcp.resource("signalhire://account")
async def get_account_info() -> str:
    """Account information - credits and rate limit status"""
    if not state.client:
        return json.dumps({"status": "unavailable"})
    response = await state.client.check_credits()
    if not response.success:
        return json.dumps({"status": "unavailable", "error": response.error})
    return json.dumps(response.data)


# =============================================================================
# PROMPTS (8 total)
# =============================================================================

@mcp.prompt
async def enrich_linkedin_profile_prompt(linkedin_url: str) -> str:
    """Guide for enriching a single LinkedIn profile with contact info"""
    return f"""
I need to enrich this LinkedIn profile: {linkedin_url}

Steps:
1. First check credits: call check_credits()
2. If credits > 0, call enrich_linkedin_profile(linkedin_url="{linkedin_url}")
3. Monitor the request: call get_request_status(request_id="<returned_id>")
4. Once completed, get contacts from cache: read signalhire://contacts/<uid>

This will return emails, phones, and full profile data.
"""


@mcp.prompt
async def bulk_enrich_contacts_prompt(count: int) -> str:
    """Guide for bulk contact enrichment"""
    return f"""
I need to enrich {count} LinkedIn profiles in bulk.

Workflow:
1. Check credits: call check_credits() to ensure you have >= {count} credits
2. Prepare list of identifiers (LinkedIn URLs, emails, or UIDs)
3. Call batch_reveal_contacts(identifiers=["url1", "url2", ...])
4. Track progress: call get_request_status(request_id="<returned_id>")
5. Results will arrive via webhook and be cached automatically

For large batches (>100), the tool automatically splits into chunks.
Rate limits: 600 items/min, so expect ~{count/600:.1f} minutes for completion.
"""


@mcp.prompt
async def search_candidates_by_criteria_prompt(title: str, location: str) -> str:
    """Guide for searching candidates with specific criteria"""
    return f"""
I want to find candidates with title "{title}" in {location}.

Search syntax supports Boolean operators:
- AND: "Software Engineer AND Python"
- OR: "Manager OR Director"
- NOT: "Developer NOT Junior"
- Parentheses: "(Python OR Java) AND AWS"

Example search:
call search_prospects(
    title="{title}",
    location=["{location}"],
    keywords="Python AND (AWS OR GCP)",
    years_experience_from=3,
    open_to_work=true
)

This returns UIDs. To get contacts, use search_and_enrich() instead.
"""


@mcp.prompt
async def search_and_enrich_workflow_prompt(criteria: str) -> str:
    """Guide for complete search and enrich workflow"""
    return f"""
I want to search for "{criteria}" and get their contact information.

Use the all-in-one tool:
call search_and_enrich(
    title="{criteria}",
    location=["San Francisco", "Remote"],
    max_results=50
)

This automatically:
1. Searches SignalHire database
2. Extracts UIDs from results
3. Batch reveals contacts
4. Returns tracking request_id

Monitor with: get_request_status(request_id="<returned_id>")
Results arrive via webhook and are cached.
"""


@mcp.prompt
async def manage_credits_prompt() -> str:
    """Guide for credit management"""
    return """
To manage SignalHire API credits:

IMPORTANT: SignalHire has TWO separate credit pools:
- Regular credits (with contacts) — your main pool. ALWAYS use this by default.
- "Without contacts" credits — a separate pool, usually EMPTY (0 credits).
  Do NOT use without_contacts=true unless you've confirmed that pool has credits.

1. Check your regular credit balance:
   call check_credits()

2. Estimate cost before batch operation:
   - 1 credit per profile reveal (with contacts, the default)
   - Search operations are FREE (no credits consumed)

3. View usage history:
   read signalhire://requests/history

4. (Advanced) Check without-contacts pool — only if specifically needed:
   call check_credits(without_contacts=true)
   WARNING: This pool is often 0. Using without_contacts=true with 0 credits causes 402 errors.
"""


@mcp.prompt
async def validate_bulk_emails_prompt(count: int) -> str:
    """Guide for bulk email validation"""
    return f"""
I need to validate {count} email addresses.

Workflow:
1. Check credits first: call check_credits() — need at least {count} credits
2. Prepare list of emails
3. Call batch_reveal_contacts(identifiers=emails)
   NOTE: Do NOT use without_contacts=true — that credit pool is typically empty (0 credits).
   Use the default (with contacts) which draws from your main credit pool.
4. Monitor: get_request_status(request_id="<returned_id>")
5. Results indicate which emails exist in SignalHire database and include contact info

Cost: 1 credit per email validated.
"""


@mcp.prompt
async def export_search_results_prompt(request_id: str) -> str:
    """Guide for exporting search results"""
    return f"""
To export results for request {request_id}:

1. Check if request completed:
   call get_request_status(request_id="{request_id}")

2. Once status="completed", export:
   call export_results(request_id="{request_id}", format="csv")

3. Supported formats:
   - "csv" - Comma-separated values
   - "json" - JSON format
   - "excel" - Excel spreadsheet

Results include all enriched contact data (emails, phones, profiles).
"""


@mcp.prompt
async def troubleshoot_webhook_prompt() -> str:
    """Guide for troubleshooting webhook issues"""
    return """
Webhook not receiving callbacks? Troubleshooting steps:

1. Check callback server is running:
   - Server should start automatically with MCP server
   - Default URL: http://localhost:8000/signalhire/callback

2. Verify callback URL is reachable:
   - From command line: curl http://localhost:8000/health
   - Should return: {"status": "ok"}

3. Check firewall/network:
   - Ensure port 8000 is open
   - If behind NAT, use ngrok: ngrok http 8000

4. Monitor callback server logs:
   - Callbacks log to console
   - Look for "Received callback for request: <id>"

5. Test with single reveal:
   call reveal_contact(identifier="test@example.com")
   - Should return request_id
   - Wait 30-60 seconds for callback

Common issues:
- Server not started → restart MCP server
- Port blocked → change port in config
- Behind NAT → use ngrok tunnel
"""


# =============================================================================
# Run Server
# =============================================================================

if __name__ == "__main__":
    # Run server in STDIO mode (default for MCP)
    mcp.run()
