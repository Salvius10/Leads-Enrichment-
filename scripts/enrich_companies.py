"""Find and reveal senior contacts at a list of companies.

Reads company names from a text file, searches SignalHire for senior roles at
each, filters to people who genuinely hold one of those roles *at that company
right now*, and reveals up to N of them per company.

    # see who would be revealed - costs nothing
    .venv\\Scripts\\python.exe scripts\\enrich_companies.py companies.txt --dry-run

    # actually reveal (1 credit per person) and write the CSV
    .venv\\Scripts\\python.exe scripts\\enrich_companies.py companies.txt --reveal

Why the local filter: SignalHire's search matches *past* employers and matches
titles loosely, so a raw search for "Zerodha" returns founders of other
companies and a search for senior titles returns "Lead Executive Assistant".
Reveals cost a credit whether the pick was right or wrong, so the query casts a
wide net for recall and every precision decision is made here, where it is free
and you can inspect it with --dry-run first.

Results are collected from the on-disk contact cache rather than from
get_request_status, because a batch's results can arrive across several webhook
calls sharing one request id and the per-request handler only fires once.
"""

import argparse
import csv
import json
import re
import subprocess
import sys
import time
import unicodedata
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from lib.contact_cache import ContactCache  # noqa: E402

PYTHON = REPO / ".venv" / "Scripts" / "python.exe"
if not PYTHON.exists():  # non-Windows layout
    PYTHON = REPO / ".venv" / "bin" / "python"
SERVER = REPO / "server.py"

# Ordered most senior first; the tier index is the ranking key. Patterns match
# against the person's current title, already lowercased.
ROLES: list[tuple[str, str]] = [
    ("Founder/CEO", r"\b(co[\s-]?founder|founder|chief executive|ceo)\b"),
    ("CTO", r"\b(cto|chief technology officer|chief technical officer)\b"),
    (
        "VP/Head of Engineering",
        r"\b(vp|v\.p\.|vice president|head|director)\s+(of\s+)?(engineering|technology)\b"
        r"|\bengineering\s+(vp|head|director)\b",
    ),
    (
        "VP/Head of Product",
        r"\b(vp|v\.p\.|vice president|head|director)\s+(of\s+)?product\b"
        r"|\bproduct\s+(vp|head)\b|\bchief product officer\b|\bcpo\b",
    ),
    (
        "VP/Head of Infrastructure",
        r"\b(vp|v\.p\.|vice president|head|director)\s+(of\s+)?"
        r"(infrastructure|infra|platform|sre)\b",
    ),
    # "Lead" alone matches "Lead Executive Assistant" and "Lead Generation
    # Specialist", so it is constrained to engineering-flavoured leads.
    (
        "Engineering Lead",
        r"\b(engineering|technical|tech|platform|infrastructure|software|architecture)\s+lead\b"
        r"|\blead\s+(engineer|architect|developer)\b",
    ),
]

# Cast wide for recall; precision happens in classify_title(). The API's title
# filter is exact-phrase sensitive ("VP Engineering" and "VP of Engineering" are
# different queries), hence the spelled-out variants.
TITLE_QUERY = " OR ".join(
    f'"{t}"'
    for t in [
        "Founder", "Co-Founder", "Cofounder", "Co Founder",
        "CEO", "Chief Executive Officer",
        "CTO", "Chief Technology Officer",
        "VP Engineering", "VP of Engineering", "Vice President of Engineering",
        "Head of Engineering", "Director of Engineering",
        "VP Product", "VP of Product", "Vice President of Product",
        "Head of Product", "Chief Product Officer",
        "VP Infrastructure", "VP of Infrastructure", "Head of Infrastructure",
        "Head of Platform", "VP Platform",
        "Engineering Lead", "Technical Lead", "Tech Lead",
    ]
)

# Titles that contain a senior keyword but do NOT belong to the senior person:
# assistants, chiefs of staff, and campus/student roles. Without this, "Executive
# Assistant - Founder's office" and "CoS to CEO" are scored as founders.
EXCLUDE_TITLE = re.compile(
    r"\b(assistant|secretary|chief of staff|cos|apprentice|intern|trainee|"
    r"student|campus|ambassador|aspiring|recruiter|former)\b"
    r"|\b(ea|pa)\s+to\b"
    r"|\btalent acquisition\b"
    r"|\bto\s+(the\s+)?(ceo|founder|cto|md|gceo)\b"
    r"|\boffice of\b"
    r"|\bfounder'?s?\s+office\b"
    r"|\bex[\s-]",
    re.I,
)

# Dropped before comparing company names.
LEGAL_SUFFIXES = re.compile(
    r"\b(private|pvt|public|limited|ltd|llp|llc|inc|incorporated|corp|corporation|"
    r"co|company|gmbh|bv|plc|sa|ag|technologies|technology|tech|labs|software|"
    r"solutions|systems|services|group|holdings|india|global)\b",
    re.I,
)


def is_latin_name(name: str) -> bool:
    """True if every letter in the name is written in Latin script.

    Search returns some profiles under their native spelling ("Tomonaga
    Tejima ..."), which are not the leads these lists are after. Accented
    Latin names ("Jose Garcia" with its real diacritics) are kept -- only
    other scripts (CJK, Cyrillic, Devanagari, Arabic) are dropped.
    """
    return all(
        unicodedata.name(char, "").startswith("LATIN")
        for char in name
        if char.isalpha()
    )


def normalize_company(name: str) -> str:
    """Reduce a company name to a comparable core token string."""
    cleaned = re.sub(r"[^\w\s]", " ", name or "").lower()
    cleaned = LEGAL_SUFFIXES.sub(" ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def company_matches(candidate: str, target: str, loose: bool = False) -> bool:
    """True if the candidate's employer really is the target company.

    Exact (normalised) equality by default. Substring matching is tempting but
    lets "Cred My Practice" and "Meesho lucky draw" through as CRED and Meesho,
    and a wrong pick costs the same credit as a right one. --loose-company opts
    into prefix matching, which recovers things like "Razorpay Singapore" at the
    cost of those false positives.
    """
    c, t = normalize_company(candidate), normalize_company(target)
    if not c or not t:
        return False
    if c == t:
        return True
    if not loose or len(t) < 3:
        return False
    c_tokens, t_tokens = c.split(), t.split()
    # Prefix match with a short remainder: "razorpay singapore", not "cred books".
    return c_tokens[:len(t_tokens)] == t_tokens and len(c_tokens) - len(t_tokens) <= 2


def classify_title(title: str) -> tuple[int, str] | None:
    """Return (tier, role label) for a matching senior title, else None."""
    text = (title or "").lower()
    if EXCLUDE_TITLE.search(text):
        return None
    for tier, (label, pattern) in enumerate(ROLES):
        if re.search(pattern, text):
            return tier, label
    return None


class MCPClient:
    """Minimal stdio MCP client for the local SignalHire server."""

    def __init__(self) -> None:
        self.proc = subprocess.Popen(
            [str(PYTHON), str(SERVER)],
            cwd=str(REPO),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        self._id = 0
        self._request({"method": "initialize", "params": {
            "protocolVersion": "2024-11-05", "capabilities": {},
            "clientInfo": {"name": "enrich-companies", "version": "1.0"}}})
        self._notify({"method": "notifications/initialized"})
        time.sleep(3)  # let the callback listener bind before any reveal

    def _notify(self, msg: dict) -> None:
        self.proc.stdin.write(json.dumps({"jsonrpc": "2.0", **msg}) + "\n")
        self.proc.stdin.flush()

    def _request(self, msg: dict) -> dict | None:
        self._id += 1
        want = self._id
        self.proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": want, **msg}) + "\n")
        self.proc.stdin.flush()
        while True:
            line = self.proc.stdout.readline()
            if not line:
                raise RuntimeError("MCP server exited unexpectedly")
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                continue  # notification or stray output
            if parsed.get("id") == want:
                return parsed

    def call(self, tool: str, args: dict) -> dict:
        resp = self._request({"method": "tools/call",
                              "params": {"name": tool, "arguments": args}})
        if "error" in resp:
            return {"_error": resp["error"]}
        result = resp.get("result", {})
        for chunk in result.get("content", []):
            if chunk.get("type") == "text":
                try:
                    return json.loads(chunk["text"])
                except json.JSONDecodeError:
                    return {"_text": chunk["text"]}
        return result

    def close(self) -> None:
        try:
            self.proc.stdin.close()
        except Exception:
            pass
        self.proc.kill()


def pick_for_company(profiles: list[dict], company: str, limit: int,
                     loose: bool = False) -> list[dict]:
    """Filter search hits to real senior staff at this company, best first."""
    picks, seen = [], set()
    target_tokens = set(normalize_company(company).split())
    for prof in profiles:
        experience = prof.get("experience") or []
        if not experience:
            continue
        if not is_latin_name(prof.get("fullName", "")):
            continue
        # Spam listings name themselves after the company ("Meesho Lucky Draw
        # Head Office"); a real person's name does not contain their employer.
        name_tokens = set(normalize_company(prof.get("fullName", "")).split())
        if target_tokens and target_tokens <= name_tokens:
            continue
        current = experience[0]  # no current-flag in search results; [0] is current
        if not company_matches(current.get("company", ""), company, loose):
            continue
        classified = classify_title(current.get("title", ""))
        if not classified:
            continue
        uid = prof.get("uid")
        if not uid or uid in seen:
            continue
        seen.add(uid)
        tier, role = classified
        picks.append({
            "company": company,
            "matched_company": current.get("company", ""),
            "uid": uid,
            "full_name": prof.get("fullName", ""),
            "title": current.get("title", ""),
            "role": role,
            "tier": tier,
            "location": prof.get("location", ""),
        })
    # Within a tier, a terse title ("Co-Founder") is the real holder of the role;
    # long ones are usually compound or ceremonial ("Vice President (South East
    # Asia Head & CEO ...)"). Alphabetical order would bury the actual founders.
    picks.sort(key=lambda p: (p["tier"], len(p["title"]), p["full_name"]))
    return picks[:limit]


# Column headers accepted for each field, matched case-insensitively.
COMPANY_COLUMNS = {"company", "company name", "companies", "company_name",
                   "name", "organisation", "organization", "account", "employer"}
LOCATION_COLUMNS = {"location", "city", "region", "place", "country", "hq"}


def _pick_column(columns: list[str], wanted: set[str]) -> str | None:
    for column in columns:
        if str(column).strip().lower() in wanted:
            return column
    return None


def load_companies(path: Path, default_location: str) -> list[tuple[str, str]]:
    """Read company names from .xlsx/.xls, .csv or a plain .txt list.

    Excel and CSV: uses a column named Company (or Name, Organisation, ...) if
    one is present, otherwise the first column. An optional Location column
    overrides the default for that row. Text files take one company per line,
    optionally "Company | Location".

    Every company gets `default_location` unless its row says otherwise. A
    location is worth overriding for short, ambiguous names -- searching "CRED"
    across all of India returns unrelated people with CEO titles, while
    "Bengaluru, India" returns the actual company.
    """
    suffix = path.suffix.lower()
    entries: list[tuple[str, str]] = []

    if suffix in {".xlsx", ".xlsm", ".xls", ".csv"}:
        import pandas as pd

        if suffix == ".csv":
            frame = pd.read_csv(path, dtype=str)
        else:
            frame = pd.read_excel(path, dtype=str)
        if frame.empty:
            return []

        columns = list(frame.columns)
        company_col = _pick_column(columns, COMPANY_COLUMNS) or columns[0]
        location_col = _pick_column(columns, LOCATION_COLUMNS)

        for _, row in frame.iterrows():
            name = str(row.get(company_col) or "").strip()
            if not name or name.lower() == "nan":
                continue
            location = ""
            if location_col:
                location = str(row.get(location_col) or "").strip()
                if location.lower() == "nan":
                    location = ""
            entries.append((name, location or default_location))
    else:
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            name, _, location = line.partition("|")
            name = name.strip()
            if name:
                entries.append((name, location.strip() or default_location))

    # De-duplicate, keeping the first occurrence so a repeated company is not
    # searched (and revealed) twice.
    seen, unique = set(), []
    for name, location in entries:
        key = name.casefold()
        if key not in seen:
            seen.add(key)
            unique.append((name, location))
    return unique


def read_cache() -> dict:
    """Read the cache straight from disk; the server writes it from its process."""
    cache_file = ContactCache().cache_path
    if not cache_file.exists():
        return {}
    try:
        data = json.loads(cache_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data.get("contacts", data) if isinstance(data, dict) else {}


def contacts_for(record: dict) -> tuple[list[str], list[str], str]:
    """Pull emails, phones and a LinkedIn URL out of a cache record."""
    emails, phones = [], []
    for entry in record.get("contacts") or []:
        kind, value = (entry.get("type") or "").lower(), entry.get("value")
        if not value:
            continue
        if kind == "email" and value not in emails:
            emails.append(value)
        elif kind == "phone" and value not in phones:
            phones.append(value)
    linkedin = ""
    for social in (record.get("profile") or {}).get("social") or []:
        link = str(social.get("link", ""))
        if "linkedin" in link.lower():
            linkedin = link
            break
    return emails, phones, linkedin


def write_csv(rows: list[dict], path: Path) -> None:
    columns = ["company", "matched_company", "full_name", "title", "role",
               "location", "uid", "emails", "phones", "linkedin", "status"]
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def search_once(client: MCPClient, company: str, location: str, size: int) -> dict:
    """One search page, shrinking size if the response exceeds the size limit.

    server.py caps responses at 100 KB (ResponseLimitingMiddleware). A page that
    exceeds it comes back as truncated text with a notice appended, which is no
    longer valid JSON, so the fix is a smaller page rather than a parse retry.
    """
    while True:
        args = {"company": company, "title": TITLE_QUERY, "size": size}
        if location:
            args["location"] = [location]
        result = client.call("search_prospects", args)
        if "_text" in result and size > 10:
            size = max(10, size // 2)
            continue
        return result


def collect_profiles(client: MCPClient, company: str, location: str, size: int,
                     pages: int) -> list[dict]:
    """Fetch up to `pages` pages of hits for one company."""
    result = search_once(client, company, location, size)
    if "_error" in result or "_text" in result:
        return []
    profiles = list(result.get("profiles") or [])
    total = result.get("total") or 0
    scroll_id, request_id = result.get("scroll_id"), result.get("request_id")

    page = 1
    while page < pages and scroll_id and request_id and len(profiles) < total:
        # scrollId expires after 15s, so this must follow immediately.
        nxt = client.call("scroll_search_results", {
            "request_id": str(request_id), "scroll_id": scroll_id})
        if "_error" in nxt or "_text" in nxt:
            break
        batch = nxt.get("profiles") or []
        if not batch:
            break
        profiles.extend(batch)
        scroll_id = nxt.get("scroll_id")
        page += 1
    return profiles


def search_all(client: MCPClient, companies: list[tuple[str, str]], limit: int,
               size: int, pause: float, pages: int,
               loose: bool) -> tuple[list[dict], list[str]]:
    """Search each company and select its top picks. Costs no credits."""
    selected, empty = [], []
    for index, (company, location) in enumerate(companies, 1):
        profiles = collect_profiles(client, company, location, size, pages)
        picks = pick_for_company(profiles, company, limit, loose)
        kept = len(picks)
        print(f"  [{index}/{len(companies)}] {company}: {len(profiles)} hits "
              f"-> {kept} kept")
        if not kept:
            empty.append(company)
        selected.extend(picks)
        if index < len(companies):
            time.sleep(pause)  # stay clear of the concurrent-search limit
    return selected, empty


def reveal(client: MCPClient, picks: list[dict], wait: int, chunk: int) -> None:
    """Reveal the selected uids and wait for webhook results to land."""
    cached = read_cache()
    todo = [p for p in picks if p["uid"] not in cached]
    free = len(picks) - len(todo)
    if free:
        print(f"{free} already revealed previously - no credits for those.")
    if not todo:
        print("Nothing left to reveal.")
        return

    uids = [p["uid"] for p in todo]
    for start in range(0, len(uids), chunk):
        batch = uids[start:start + chunk]
        result = client.call("batch_reveal_contacts", {"identifiers": batch})
        if "_error" in result:
            print(f"Batch failed: {json.dumps(result['_error'])[:200]}")
            return
        print(f"Submitted {len(batch)} reveal(s), request {result.get('request_id')}")

    print(f"Waiting up to {wait}s for webhook results...")
    pending = set(uids)
    deadline = time.time() + wait
    while pending and time.time() < deadline:
        time.sleep(5)
        cached = read_cache()
        landed = {uid for uid in pending if uid in cached}
        if landed:
            pending -= landed
            print(f"  {len(uids) - len(pending)}/{len(uids)} received")
    if pending:
        print(f"{len(pending)} still outstanding - they may arrive later; "
              f"re-run with --collect to pick them up.")


def build_rows(picks: list[dict]) -> list[dict]:
    cached = read_cache()
    rows = []
    for pick in picks:
        row = dict(pick)
        row.pop("tier", None)
        record = cached.get(pick["uid"])
        if record:
            emails, phones, linkedin = contacts_for(record)
            row.update(emails="; ".join(emails), phones="; ".join(phones),
                       linkedin=linkedin,
                       status="revealed" if (emails or phones) else "no contacts found")
        else:
            row.update(emails="", phones="", linkedin="", status="not revealed")
        rows.append(row)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("companies", type=Path,
                        help="Excel (.xlsx), CSV or text file of company names")
    parser.add_argument("--dry-run", action="store_true",
                        help="show who would be revealed; spends nothing")
    parser.add_argument("--reveal", action="store_true",
                        help="reveal the selected people (1 credit each)")
    parser.add_argument("--collect", action="store_true",
                        help="re-read the cache and rebuild the CSV, no new reveals")
    parser.add_argument("--per-company", type=int, default=3,
                        help="max contacts per company (default 3)")
    parser.add_argument("--size", type=int, default=25,
                        help="results per search page (default 25; larger pages "
                             "exceed the server's 100KB response cap)")
    parser.add_argument("--location", default="India",
                        help="location filter applied to every company unless its "
                             "row overrides it (default: India; pass \"\" to disable)")
    parser.add_argument("--loose-company", action="store_true",
                        help="also accept employers that merely start with the "
                             "target name (recovers 'Razorpay Singapore', but "
                             "lets in lookalikes such as 'Cred Books')")
    parser.add_argument("--pages", type=int, default=2,
                        help="search pages to pull per company (default 2)")
    parser.add_argument("--wait", type=int, default=600,
                        help="seconds to wait for webhook results (default 600)")
    parser.add_argument("--chunk", type=int, default=100,
                        help="identifiers per batch reveal (max 100)")
    parser.add_argument("--pause", type=float, default=0.5,
                        help="seconds between searches (default 0.5)")
    parser.add_argument("--out", type=Path, default=REPO / "enriched_contacts.csv")
    parser.add_argument("--plan", type=Path, default=REPO / "enrichment_plan.json")
    # Latin-script names can still carry characters the Windows console's
    # cp1252 default cannot encode; never let printing abort a run.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    args = parser.parse_args()

    if not (args.dry_run or args.reveal or args.collect):
        parser.error("pass one of --dry-run, --reveal or --collect")
    if not args.companies.exists():
        parser.error(f"no such file: {args.companies}")

    companies = load_companies(args.companies, args.location.strip())
    if not companies:
        parser.error("company file is empty")
    overridden = sum(1 for _, loc in companies if loc != args.location.strip())
    scope = args.location.strip() or "no location filter"
    print(f"{len(companies)} companies, up to {args.per_company} contacts each "
          f"({scope}"
          + (f", {overridden} overridden" if overridden else "") + ")\n")

    if args.collect:
        if not args.plan.exists():
            parser.error(f"no saved plan at {args.plan}; run --dry-run first")
        picks = json.loads(args.plan.read_text(encoding="utf-8"))
        rows = build_rows(picks)
        write_csv(rows, args.out)
        got = sum(1 for r in rows if r["status"] == "revealed")
        print(f"Wrote {args.out} - {got}/{len(rows)} with contacts")
        return

    client = MCPClient()
    try:
        credits = client.call("check_credits", {})
        print(f"Credits available: {credits.get('credits', '?')}\n")

        print("Searching (free)...")
        picks, empty = search_all(client, companies, args.per_company,
                                  args.size, args.pause, args.pages,
                                  args.loose_company)

        args.plan.write_text(json.dumps(picks, indent=2), encoding="utf-8")
        print(f"\nSelected {len(picks)} people across "
              f"{len({p['company'] for p in picks})} companies.")
        if empty:
            print(f"No senior match found for {len(empty)}: {', '.join(empty[:10])}"
                  + (" ..." if len(empty) > 10 else ""))

        by_company: dict[str, list[dict]] = {}
        for pick in picks:
            by_company.setdefault(pick["company"], []).append(pick)
        print()
        for company, people in by_company.items():
            print(f"  {company}")
            for person in people:
                # Show the matched employer: it is how you spot a lookalike
                # company before spending a credit on it.
                print(f"     {person['full_name'][:26]:<28}"
                      f"{person['title'][:34]:<36}"
                      f"@ {person['matched_company'][:24]:<26}[{person['role']}]")

        if args.dry_run:
            already = read_cache()
            new = sum(1 for p in picks if p["uid"] not in already)
            print(f"\nDry run. Revealing these would cost {new} credit(s) "
                  f"({len(picks) - new} already cached).")
            print(f"Plan saved to {args.plan}. Re-run with --reveal to spend.")
            write_csv(build_rows(picks), args.out)
            print(f"Preview CSV (no contacts yet): {args.out}")
            return

        reveal(client, picks, args.wait, min(args.chunk, 100))
        rows = build_rows(picks)
        write_csv(rows, args.out)
        got = sum(1 for r in rows if r["status"] == "revealed")
        print(f"\nWrote {args.out} - {got}/{len(rows)} with contacts")
    finally:
        client.close()


if __name__ == "__main__":
    main()
