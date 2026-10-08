<!--
  Created in whole or in part by AI using Cursor (Grok).
-->

# Authentication

`jflow` supports two ways to talk to Jira Cloud:

1. **API token** (default) — Basic Auth with email + Atlassian API token against `https://{domain}`
2. **OAuth 2.0 (3LO)** — authorization code grant with client id/secret; Bearer tokens against `https://api.atlassian.com/ex/jira/{cloudId}`

## API token (default)

```yaml
jira:
  auth: "api_token"   # optional; this is the default
  domain: "your-domain.atlassian.net"
  email: "you@example.com"
  api_token: "YOUR_JIRA_API_TOKEN"
```

Create a token at [Atlassian API tokens](https://id.atlassian.com/manage-profile/security/api-tokens).

## OAuth 2.0 (3LO)

Atlassian Cloud 3LO requires a **client id and client secret** from an OAuth 2.0 integration you create (PKCE-only public clients are not supported by Atlassian Cloud 3LO today).

### 1. Create an Atlassian OAuth app

1. Open the [Atlassian developer console](https://developer.atlassian.com/console/myapps/)
2. Create an **OAuth 2.0 integration**
3. Under **Authorization**, configure callback URL exactly:

   `http://127.0.0.1:8391/callback`

   (or set `oauth_redirect_uri` in `user.yaml` to match whatever you register)
4. Under **Permissions**, add **Jira API** scopes used by this tool, at least:

   - `read:jira-work`
   - `write:jira-work`
   - `read:jira-user`

   And include `offline_access` in the authorize request (jflow adds it) so refresh tokens are issued.
5. Copy **Client ID** and **Secret** from Settings.

### 2. Configure `user.yaml`

```yaml
jira:
  auth: "oauth"
  domain: "your-domain.atlassian.net"   # used to pick the site after login
  oauth_client_id: "YOUR_CLIENT_ID"
  oauth_client_secret: "YOUR_CLIENT_SECRET"
  oauth_redirect_uri: "http://127.0.0.1:8391/callback"  # optional; this is the default
  # oauth_cloud_id: "uuid-from-accessible-resources"    # optional override
```

Env overrides (optional):

- `JFLOW_OAUTH_CLIENT_ID`
- `JFLOW_OAUTH_CLIENT_SECRET`

### 3. Login

```bash
jflow auth login
# or: jflow auth login --no-browser   # prints URL; still waits for callback
jflow auth status
jflow status          # same health check as with API tokens
```

Tokens are stored at `~/.config/jflow/oauth_tokens.json` (mode `0600`), not in `user.yaml`.

```bash
jflow auth logout     # deletes the token file
```

### Headless / CI

For non-interactive environments:

- complete `jflow auth login` once so a refresh token exists on disk, then use `auth: oauth`, or
- use **API token** auth for scripts and staging.

## Choosing a mode

| Situation | Prefer |
|-----------|--------|
| Personal scripts, staging tests | API token |
| Avoid long-lived API tokens / org policy wants OAuth | OAuth 3LO |
| CI without a browser | API token (or pre-provisioned OAuth refresh token file) |
