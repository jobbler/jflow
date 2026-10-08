# ==============================================================================
# jflow - Dual-Interface CLI & MCP Server for Jira Cloud
# Co-created through collaborative AI pair programming with Gemini.
# Refined / authored with assistance from Cursor (Grok).
# ==============================================================================
from jflow.config import load_config

config = load_config()

# Verify that configuration loads required user settings
assert config.user.jira.domain, "Jira domain must be set"
assert config.user.jira.email, "Jira email must be set"
assert config.user.jira.api_token, "Jira API token must be set"

print("✅ Phase 1 tests passed successfully!")
