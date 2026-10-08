# ==============================================================================
# jflow - Dual-Interface CLI & MCP Server for Jira Cloud
# Co-created through collaborative AI pair programming with Gemini.
# Refined / authored with assistance from Cursor (Grok).
# ==============================================================================
from typing import Any, Dict, List
from jflow.core.client import JiraClient


def add_labels(client: JiraClient, issue_key: str, labels: List[str]) -> Dict[str, Any]:
    """Adds one or more labels to an issue without overwriting existing labels."""
    update_operations = [{"add": label} for label in labels]
    payload = {"update": {"labels": update_operations}}
    client.put(f"/rest/api/3/issue/{issue_key}", payload=payload)
    return {"key": issue_key, "added": labels, "status": "Labels Added"}


def remove_labels(client: JiraClient, issue_key: str, labels: List[str]) -> Dict[str, Any]:
    """Removes specified labels from an issue."""
    update_operations = [{"remove": label} for label in labels]
    payload = {"update": {"labels": update_operations}}
    client.put(f"/rest/api/3/issue/{issue_key}", payload=payload)
    return {"key": issue_key, "removed": labels, "status": "Labels Removed"}


def set_labels(client: JiraClient, issue_key: str, labels: List[str]) -> Dict[str, Any]:
    """Replaces all existing labels on an issue with the provided list."""
    payload = {"fields": {"labels": labels}}
    client.put(f"/rest/api/3/issue/{issue_key}", payload=payload)
    return {"key": issue_key, "labels": labels, "status": "Labels Updated"}
