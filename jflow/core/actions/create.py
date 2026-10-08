# ==============================================================================
# jflow - Dual-Interface CLI & MCP Server for Jira Cloud
# Co-created through collaborative AI pair programming with Gemini.
# Refined / authored with assistance from Cursor (Grok).
# Created in whole or in part by AI using Cursor (Grok 4.5).
# Created in whole or in part by AI using Cursor (Composer).
# ==============================================================================
from typing import Any, Dict, List, Optional, Tuple

from jflow.config.models import AppConfig
from jflow.core.adf import text_to_adf_doc
from jflow.core.client import JiraClient
from jflow.core.actions.fields import encode_field_value
from jflow.core.actions.sprint import add_issue_to_sprint, resolve_board
from jflow.core.actions.system import get_server_info
from jflow.core.fields import FieldCacheManager
from jflow.core.templates import process_template

CURRENT_SPRINT_TOKEN = "@current_sprint"


def validate_create_params(project: Optional[str], issue_type: Optional[str], summary: Optional[str]) -> List[str]:
    missing = []
    if not project:
        missing.append("project")
    if not issue_type:
        missing.append("issue_type")
    if not summary:
        missing.append("summary")
    return missing


def _apply_named_fields(
    fields_mgr: FieldCacheManager,
    fields_payload: Dict[str, Any],
    named_fields: Dict[str, Any],
) -> None:
    for key, value in named_fields.items():
        meta = fields_mgr.resolve_field(key)
        if meta:
            field_id = meta["id"]
            encoded = encode_field_value(meta.get("schema"), value)
        else:
            field_id = fields_mgr.resolve_field_id(key) or key
            encoded = value
        fields_payload[field_id] = encoded


def _strip_current_sprint_token(
    named_fields: Dict[str, Any],
) -> Tuple[Dict[str, Any], bool]:
    """Remove @current_sprint entries from a fields map. Returns (cleaned, wanted)."""
    cleaned: Dict[str, Any] = {}
    wanted = False
    for key, value in named_fields.items():
        if value == CURRENT_SPRINT_TOKEN:
            wanted = True
            continue
        cleaned[key] = value
    return cleaned, wanted


def create_issue(
    client: JiraClient,
    config: AppConfig,
    fields_mgr: FieldCacheManager,
    project: Optional[str] = None,
    issue_type: Optional[str] = None,
    summary: Optional[str] = None,
    description: Optional[str] = None,
    template_name: Optional[str] = None,
    template_vars: Optional[Dict[str, str]] = None,
    labels: Optional[List[str]] = None,
    extra_fields: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    tpl_project = None
    tpl_type = None
    tpl_summary = None
    tpl_description = None
    tpl_labels: List[str] = []
    tpl_components: List[str] = []
    tpl_fields: Dict[str, Any] = {}
    want_current_sprint = False

    if template_name:
        tpl = process_template(config, template_name, template_vars)
        tpl_project = tpl.project
        tpl_type = tpl.issue_type
        tpl_summary = tpl.summary
        tpl_description = tpl.description
        tpl_labels = tpl.labels
        tpl_components = tpl.components
        tpl_fields, want_current_sprint = _strip_current_sprint_token(dict(tpl.fields))

    final_project = project or tpl_project or config.get_default_project()
    proj_cfg = config.get_project_config(final_project) if final_project else None
    default_type = proj_cfg.default_issue_type if proj_cfg else "Task"

    final_type = issue_type or tpl_type or default_type
    final_summary = summary or tpl_summary
    final_description = description or tpl_description
    final_labels = list(set((labels or []) + tpl_labels))

    missing = validate_create_params(final_project, final_type, final_summary)
    if missing:
        raise ValueError(f"Missing required parameters for issue creation: {', '.join(missing)}")

    fields_payload: Dict[str, Any] = {
        "project": {"key": final_project},
        "issuetype": {"name": final_type},
        "summary": final_summary,
    }

    if final_description:
        fields_payload["description"] = text_to_adf_doc(final_description)

    if final_labels:
        fields_payload["labels"] = final_labels

    if tpl_components:
        fields_payload["components"] = [{"name": c} for c in tpl_components]

    if tpl_fields:
        _apply_named_fields(fields_mgr, fields_payload, tpl_fields)

    if extra_fields:
        cleaned_extra, extra_wants = _strip_current_sprint_token(dict(extra_fields))
        want_current_sprint = want_current_sprint or extra_wants
        if cleaned_extra:
            _apply_named_fields(fields_mgr, fields_payload, cleaned_extra)

    response = client.post("/rest/api/3/issue", {"fields": fields_payload})
    key = response.get("key")
    server_url = (get_server_info(client).get("url") or "").rstrip("/")
    url = f"{server_url}/browse/{key}" if server_url and key else None

    if want_current_sprint:
        if not key:
            raise ValueError("Issue created without a key; cannot add to current sprint.")
        board = config.get_default_board()
        if not board:
            raise ValueError(
                f"Template used {CURRENT_SPRINT_TOKEN} but defaults.board is not set in user.yaml."
            )
        board_id = resolve_board(client, board)
        add_issue_to_sprint(client, issue_key=key, board_id=board_id)

    return {
        "key": key,
        "url": url,
    }
