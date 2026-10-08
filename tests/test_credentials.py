# ==============================================================================
# jflow - Dual-Interface CLI & MCP Server for Jira Cloud
# Co-created through collaborative AI pair programming with Gemini.
# Refined / authored with assistance from Cursor (Grok).
# ==============================================================================
from jflow.config import load_config
from jflow.core import JiraClient


def main():
    try:
        config = load_config()
        client = JiraClient.from_settings(config.user)

        # GET /rest/api/3/myself returns authenticated user details
        user_data = client.get("/rest/api/3/myself")

        print("✅ Credentials verified successfully!\n")
        print(f"Display Name: {user_data.get('displayName')}")
        print(f"Email:        {user_data.get('emailAddress')}")
        print(f"Account ID:   {user_data.get('accountId')}")
        print(f"Active:       {user_data.get('active')}")

    except Exception as exc:
        print(f"❌ Connection/Authentication Failed:\n{exc}")


if __name__ == "__main__":
    main()
