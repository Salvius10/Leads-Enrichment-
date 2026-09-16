"""Utility helpers for caching revealed contact information locally.

The cache allows CLI workflows to avoid re-revealing contacts that were already
fetched previously while still making the data available for exports and other
post-processing steps.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

CACHE_DIR_NAME = ".signalhire-agent"
CACHE_FILE_NAME = "revealed_contacts.json"
CACHE_SUBDIR_NAME = "cache"


def _default_cache_path() -> Path:
    """Return the default path for the revealed contact cache file."""
    home = Path.home()
    return home / CACHE_DIR_NAME / CACHE_SUBDIR_NAME / CACHE_FILE_NAME


def _utc_now_iso() -> str:
    """Return the current UTC timestamp in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()


def normalize_contacts(payload: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Normalize raw contact payloads into a consistent list structure."""
    if not payload:
        return []

    contacts: List[Dict[str, Any]] = []
    raw_contacts = payload.get("contacts")

    if isinstance(raw_contacts, list):
        for entry in raw_contacts:
            if not isinstance(entry, dict):
                continue
            value = entry.get("value") or entry.get("contact") or entry.get("email")
            if not value:
                continue
            contact_type = (
                entry.get("type")
                or entry.get("contact_type")
                or entry.get("kind")
                or entry.get("category")
                or "unknown"
            )
            label = entry.get("label") or entry.get("source") or entry.get("location")
            contacts.append(
                {
                    "type": str(contact_type),
                    "value": str(value),
                    "label": str(label) if label else None,
                }
            )

    # Some API responses flatten email/phone/linkedin fields
    flattened_keys = {
        "email": "email",
        "primary_email": "email",
        "email_address": "email",
        "phone": "phone",
        "primary_phone": "phone",
        "mobile_phone": "mobile",
        "linkedin_url": "linkedin",
        "linkedin": "linkedin",
    }

    for key, contact_type in flattened_keys.items():
        value = payload.get(key)
        if not value:
            continue
        if isinstance(value, (list, tuple, set)):
            for item in value:
                if item:
                    contacts.append(
                        {
                            "type": contact_type,
                            "value": str(item),
                            "label": key,
                        }
                    )
        else:
            contacts.append(
                {
                    "type": contact_type,
                    "value": str(value),
                    "label": key,
                }
            )

    # Deduplicate contacts by type + value
    seen = set()
    deduped: List[Dict[str, Any]] = []
    for contact in contacts:
        if not contact.get("value"):
            continue
        key = (contact.get("type"), contact.get("value"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(contact)

    return deduped


@dataclass
class CachedContact:
    """Cached contact data for a single prospect UID."""

    uid: str
    contacts: List[Dict[str, Any]] = field(default_factory=list)
    profile: Optional[Dict[str, Any]] = None
    first_revealed_at: str = field(default_factory=_utc_now_iso)
    last_updated_at: str = field(default_factory=_utc_now_iso)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, uid: str, data: Dict[str, Any]) -> "CachedContact":
        contacts = data.get("contacts") or []
        profile = data.get("profile")
        metadata = data.get("metadata") or {}
        first_revealed = data.get("first_revealed_at") or _utc_now_iso()
        last_updated = data.get("last_updated_at") or first_revealed
        return cls(
            uid=uid,
            contacts=list(contacts),
            profile=profile,
            first_revealed_at=first_revealed,
            last_updated_at=last_updated,
            metadata=dict(metadata),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "uid": self.uid,
            "contacts": list(self.contacts),
            "profile": self.profile,
            "first_revealed_at": self.first_revealed_at,
            "last_updated_at": self.last_updated_at,
            "metadata": dict(self.metadata),
        }

    def merge_contacts(self, new_contacts: Iterable[Dict[str, Any]]) -> None:
        """Merge new contact entries into the cache, deduplicating by type + value."""
        combined = list(self.contacts)
        existing = {(c.get("type"), c.get("value")) for c in combined if c.get("value")}

        for entry in new_contacts:
            if not isinstance(entry, dict) or not entry.get("value"):
                continue
            key = (entry.get("type"), entry.get("value"))
            if key in existing:
                continue
            existing.add(key)
            combined.append({
                "type": entry.get("type") or "unknown",
                "value": entry.get("value"),
                "label": entry.get("label"),
            })

        self.contacts = combined
        self.last_updated_at = _utc_now_iso()

    def merge_profile(self, profile: Optional[Dict[str, Any]]) -> None:
        if not profile:
            return
        if not isinstance(profile, dict):
            return

        if not self.profile:
            self.profile = dict(profile)
        else:
            merged = dict(self.profile)
            for key, value in profile.items():
                if value is None:
                    continue
                merged[key] = value
            self.profile = merged
        self.last_updated_at = _utc_now_iso()


class ContactCache:
    """Simple JSON-backed cache for revealed contacts."""

    def __init__(self, cache_path: Optional[Path] = None):
        self._cache_path = cache_path or _default_cache_path()
        self._data: Dict[str, CachedContact] = {}
        self._loaded = False
        self._dirty = False

    @property
    def cache_path(self) -> Path:
        return self._cache_path

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return

        if self._cache_path.exists():
            try:
                raw = json.loads(self._cache_path.read_text())
                if isinstance(raw, dict):
                    for uid, payload in raw.items():
                        if not isinstance(payload, dict):
                            continue
                        contact = CachedContact.from_dict(uid, payload)
                        self._data[uid] = contact
            except (OSError, json.JSONDecodeError):
                # Start fresh on load errors
                self._data = {}
        self._loaded = True

    def get(self, uid: str) -> Optional[CachedContact]:
        self._ensure_loaded()
        return self._data.get(uid)

    def upsert(
        self,
        uid: str,
        *,
        contacts: Optional[Iterable[Dict[str, Any]]] = None,
        profile: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> CachedContact:
        self._ensure_loaded()
        record = self._data.get(uid)
        if not record:
            record = CachedContact(uid=uid)
            self._data[uid] = record

        if contacts:
            record.merge_contacts(contacts)
        if profile:
            record.merge_profile(profile)
        if metadata:
            merged_metadata = dict(record.metadata)
            merged_metadata.update(metadata)
            record.metadata = merged_metadata
            record.last_updated_at = _utc_now_iso()

        self._dirty = True
        return record

    def update_from_reveal_payload(
        self,
        uid: str,
        payload: Dict[str, Any],
        profile: Optional[Dict[str, Any]] = None,
    ) -> CachedContact:
        normalized = normalize_contacts(payload)
        metadata = {
            "source": payload.get("source") or "api",
            "raw_keys": sorted(payload.keys()),
        }
        return self.upsert(uid, contacts=normalized, profile=profile, metadata=metadata)

    def merge_profiles(self, profiles: Dict[str, Dict[str, Any]]) -> None:
        self._ensure_loaded()
        for uid, profile in profiles.items():
            self.upsert(uid, profile=profile)

    def list_cached_uids(self) -> List[str]:
        self._ensure_loaded()
        return list(self._data.keys())

    def save(self) -> None:
        if not self._dirty:
            return

        self._ensure_loaded()
        target = self._cache_path
        target.parent.mkdir(parents=True, exist_ok=True)

        serializable = {uid: contact.to_dict() for uid, contact in self._data.items()}
        temp_path = target.with_suffix(".tmp")
        temp_path.write_text(json.dumps(serializable, indent=2, sort_keys=True))
        temp_path.replace(target)
        self._dirty = False

    def clear(self) -> None:
        self._ensure_loaded()
        self._data.clear()
        self._dirty = True
        if self._cache_path.exists():
            try:
                self._cache_path.unlink()
            except OSError:
                pass


__all__ = ["ContactCache", "CachedContact", "normalize_contacts"]
