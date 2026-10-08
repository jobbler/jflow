# ==============================================================================
# jflow - CLI for Jira Cloud
# Co-created through collaborative AI pair programming with Gemini.
# Refined / authored with assistance from Cursor (Grok).
# ==============================================================================
from typer.testing import CliRunner
from jflow.interfaces.cli import app as cli_app
from jflow.core.formatter import format_output

runner = CliRunner()

# 1. Test Formatter Outputs
sample_data = {"key": "PROJ_X-101", "status": "Created"}
json_out = format_output(sample_data, "json")
assert "PROJ_X-101" in json_out

yaml_out = format_output(sample_data, "yaml")
assert "PROJ_X-101" in yaml_out

table_out = format_output(sample_data, "table")
assert "PROJ_X-101" in table_out

# 2. Test CLI Invocation via Typer CliRunner
cli_result = runner.invoke(cli_app, ["issue", "--help"])
assert cli_result.exit_code == 0
assert "Create, view, list, and update Jira issues" in cli_result.output

print("✅ Phase 4 tests passed successfully!")
