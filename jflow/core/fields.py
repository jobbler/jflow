# ==============================================================================
# jflow - Dual-Interface CLI & MCP Server for Jira Cloud
# Co-created through collaborative AI pair programming with Gemini.
# Refined / authored with assistance from Cursor (Grok).
# Created in whole or in part by AI using Cursor (Grok 4.5).
# ==============================================================================
import json
from pathlib import Path
from typing import Any, Dict, Optional

from jflow.core.client import JiraClient

CACHE_FILE_PATH = Path("~/.config/jflow/fields_cache.json").expanduser()


def _is_structured_cache(data: Any) -> bool:
    return isinstance(data, dict) and "by_id" in data and "by_name" in data


class FieldCacheManager:
    def __init__(self, client: JiraClient, cache_path: Path = CACHE_FILE_PATH):
        self.client = client
        self.cache_path = cache_path

    def sync_field_cache(self) -> Dict[str, Any]:
        fields = self.client.get("/rest/api/3/field")
        by_id: Dict[str, Dict[str, Any]] = {}
        by_name: Dict[str, str] = {}

        for field in fields:
            field_id = field["id"]
            name = field["name"]
            entry = {
                "id": field_id,
                "name": name,
                "custom": bool(field.get("custom", False)),
                "schema": field.get("schema") or {},
            }
            by_id[field_id] = entry
            by_name[name] = field_id
            by_name[name.lower()] = field_id

        cache = {"by_id": by_id, "by_name": by_name}
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.cache_path, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2)

        return cache

    def load_cache(self) -> Dict[str, Any]:
        if not self.cache_path.exists():
            return self.sync_field_cache()
        with open(self.cache_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not _is_structured_cache(data):
            return self.sync_field_cache()
        return data

    def resolve_field_id(self, name: str) -> Optional[str]:
        cache = self.load_cache()
        by_name = cache.get("by_name", {})
        field_id = by_name.get(name) or by_name.get(name.lower())

        if not field_id and name in cache.get("by_id", {}):
            field_id = name

        if not field_id:
            cache = self.sync_field_cache()
            by_name = cache.get("by_name", {})
            field_id = by_name.get(name) or by_name.get(name.lower())
            if not field_id and name in cache.get("by_id", {}):
                field_id = name

        return field_id

    def resolve_field(self, name_or_id: str) -> Optional[Dict[str, Any]]:
        """Resolve a field by display name or id; returns cache entry with schema."""
        cache = self.load_cache()
        by_id = cache.get("by_id", {})
        by_name = cache.get("by_name", {})

        field_id = by_name.get(name_or_id) or by_name.get(name_or_id.lower())
        if not field_id and name_or_id in by_id:
            field_id = name_or_id

        if not field_id:
            cache = self.sync_field_cache()
            by_id = cache.get("by_id", {})
            by_name = cache.get("by_name", {})
            field_id = by_name.get(name_or_id) or by_name.get(name_or_id.lower())
            if not field_id and name_or_id in by_id:
                field_id = name_or_id

        if not field_id:
            return None
        return by_id.get(field_id)
