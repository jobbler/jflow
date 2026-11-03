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


def merge_config_vars(
    config: Optional[AppConfig],
    overrides: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    """Names for ``{placeholders}`` in searches, templates, and chains.

    ``defaults.project`` fills ``{project}``. ``defaults.vars`` fills the rest
    and overrides ``{project}`` when it sets that name. ``overrides`` (CLI
    ``--var`` / ``-V``) win over both.
    """
    merged: Dict[str, str] = {}
    if config is not None:
        project = config.user.defaults.project
        if project:
            merged["project"] = project
        for key, value in config.user.defaults.vars.items():
            merged[key] = value
    if overrides:
        merged.update(overrides)
    return merged


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
    config: Optional[AppConfig] = None,
) -> List[Dict[str, Any]]:
    """Deep-render ``{placeholders}`` in workflow steps and merge vars into create template_vars.

    Settings nicknames fill first. A create step's own ``template_vars`` replace
    those nicknames. CLI ``--var`` values win over both.
    """
    cli_vars = variables or {}
    settings = merge_config_vars(config)
    render_vars = dict(settings)
    render_vars.update(cli_vars)
    if not render_vars:
        return steps

    rendered = _render_value(steps, render_vars)
    if not isinstance(rendered, list):
        return steps

    for step in rendered:
        if not isinstance(step, dict) or step.get("action") != "create":
            continue
        existing = step.get("template_vars") or {}
        if not isinstance(existing, dict):
            existing = {}
        merged = dict(settings)
        merged.update(
            {str(k): "" if v is None else str(v) for k, v in existing.items()}
        )
        merged.update(cli_vars)
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
    vars_dict = merge_config_vars(config, variables)

    rendered_summary = render_string(template.summary, vars_dict)
    rendered_description = render_string(template.description, vars_dict)
    rendered_components: List[str] = [
        render_string(c, vars_dict) or c for c in template.components
    ]
    rendered_fields = _render_value(dict(template.fields), vars_dict)

    rendered_parent = render_string(template.parent, vars_dict)
    rendered_project = render_string(template.project, vars_dict)

    return IssueTemplate(
        summary=rendered_summary,
        description=rendered_description,
        issue_type=template.issue_type,
        project=rendered_project,
        parent=rendered_parent,
        labels=template.labels,
        components=rendered_components,
        fields=rendered_fields if isinstance(rendered_fields, dict) else {},
    )
