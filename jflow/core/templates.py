# ==============================================================================
# jflow - Dual-Interface CLI & MCP Server for Jira Cloud
# Co-created through collaborative AI pair programming with Gemini.
# Refined / authored with assistance from Cursor (Grok).
# Created in whole or in part by AI using Cursor (Grok 4.5).
# Created in whole or in part by AI using Cursor (Composer).
# ==============================================================================
import re
from typing import Any, Dict, List, Optional

from jflow.config.models import AppConfig, IssueTemplate


def render_string(template_str: Optional[str], variables: Dict[str, str]) -> Optional[str]:
    """Replaces placeholders like {var_name} with values from variables dictionary."""
    if not template_str:
        return template_str

    def replace_match(match):
        var_name = match.group(1)
        return variables.get(var_name, match.group(0))

    return re.sub(r"\{([a-zA-Z0-9_]+)\}", replace_match, template_str)


def _render_value(value: Any, variables: Dict[str, str]) -> Any:
    if isinstance(value, str):
        return render_string(value, variables)
    if isinstance(value, list):
        return [_render_value(item, variables) for item in value]
    if isinstance(value, dict):
        return {k: _render_value(v, variables) for k, v in value.items()}
    return value


def apply_workflow_vars(
    steps: List[Dict[str, Any]],
    variables: Optional[Dict[str, str]] = None,
) -> List[Dict[str, Any]]:
    """Deep-render ``{placeholders}`` in workflow steps and merge vars into create template_vars.

    CLI ``--var`` values win over keys already present in a create step's ``template_vars``.
    """
    vars_dict = variables or {}
    if not vars_dict:
        return steps

    rendered = _render_value(steps, vars_dict)
    if not isinstance(rendered, list):
        return steps

    for step in rendered:
        if not isinstance(step, dict) or step.get("action") != "create":
            continue
        existing = step.get("template_vars") or {}
        if not isinstance(existing, dict):
            existing = {}
        merged: Dict[str, str] = {
            str(k): "" if v is None else str(v) for k, v in existing.items()
        }
        merged.update(vars_dict)
        step["template_vars"] = merged
    return rendered


def process_template(
    config: AppConfig,
    template_name: str,
    variables: Optional[Dict[str, str]] = None,
) -> IssueTemplate:
    """Retrieves template by name and renders placeholders in text and field values."""
    if template_name not in config.user.templates:
        available = ", ".join(f"'{t}'" for t in config.user.templates.keys()) or "none"
        raise ValueError(
            f"Template '{template_name}' not found. Available templates: {available}"
        )

    template = config.user.templates[template_name]
    vars_dict = variables or {}

    rendered_summary = render_string(template.summary, vars_dict)
    rendered_description = render_string(template.description, vars_dict)
    rendered_components: List[str] = [
        render_string(c, vars_dict) or c for c in template.components
    ]
    rendered_fields = _render_value(dict(template.fields), vars_dict)

    return IssueTemplate(
        summary=rendered_summary,
        description=rendered_description,
        issue_type=template.issue_type,
        project=template.project,
        labels=template.labels,
        components=rendered_components,
        fields=rendered_fields if isinstance(rendered_fields, dict) else {},
    )
