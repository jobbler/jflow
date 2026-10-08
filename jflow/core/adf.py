# ==============================================================================
# jflow - Dual-Interface CLI & MCP Server for Jira Cloud
# Co-created through collaborative AI pair programming with Gemini.
# Refined / authored with assistance from Cursor (Grok).
# ==============================================================================
from typing import Any, Dict, List


def text_to_adf_doc(text: str) -> Dict[str, Any]:
    """Convert plain text to an Atlassian Document Format doc.

    Newlines become separate paragraphs. Empty lines become empty paragraphs
    (visual blank lines in Jira). ``\\r\\n`` is normalized to ``\\n``.
    """
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized.split("\n")
    content: List[Dict[str, Any]] = []
    for line in lines:
        if line:
            content.append(
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": line}],
                }
            )
        else:
            content.append({"type": "paragraph"})
    if not content:
        content.append({"type": "paragraph"})
    return {"version": 1, "type": "doc", "content": content}


def collapse_to_single_line(text: str) -> str:
    """Normalize summary-like fields to a single line for Jira."""
    return " ".join(text.replace("\r\n", "\n").replace("\r", "\n").split())


def adf_to_text(node: Any) -> str:
    """Extract plain text from an ADF document or nested node."""
    if node is None:
        return ""
    if isinstance(node, str):
        return node
    if isinstance(node, list):
        parts = [adf_to_text(item) for item in node]
        return "\n".join(p for p in parts if p)
    if not isinstance(node, dict):
        return str(node)

    node_type = node.get("type")
    if node_type == "text":
        return node.get("text") or ""
    if node_type == "hardBreak":
        return "\n"

    content = node.get("content") or []
    if node_type in ("paragraph", "heading", "blockquote", "listItem"):
        inner = "".join(adf_to_text(child) for child in content)
        return inner
    if node_type in ("doc", "bulletList", "orderedList", "panel", "expand", "table", "tableRow", "tableCell", "tableHeader"):
        blocks = [adf_to_text(child) for child in content]
        return "\n".join(b for b in blocks if b is not None)
    if content:
        return "\n".join(adf_to_text(child) for child in content)
    return ""
