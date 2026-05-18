# User Login Flow

The MCP server supports a two-step OAuth login so agents (or human users) can obtain access tokens interactively. You must have your own Meta App configured with `META_MCP_APP_ID`, `META_MCP_APP_SECRET`, and `META_MCP_OAUTH_REDIRECT_URI` in `.env` before using this flow.

## Steps

1. **Begin** — Call `auth.login.begin` (or `MetaMcpSdk.auth_login_begin`) with the scopes you need. The server returns an authorization URL and a `state` token. Redirect the user to the URL.
2. **Callback** — Your redirect handler receives the authorization `code` and `state` from Meta.
3. **Complete** — Call `auth.login.complete` (or `MetaMcpSdk.auth_login_complete`) with the `code` and optional `expected_state`. The server exchanges the code for an access token, validates required scopes via `/debug_token`, and persists the token metadata in SQLite.
4. **Use** — The tool response returns the access token, subject info, and granted scopes. Store the values or rely on the MCP `tokens` table for subsequent calls.

All login helpers honour `META_MCP_FACEBOOK_OAUTH_BASE_URL` and `META_MCP_OAUTH_REDIRECT_URI`, making it easy to switch between staging and production apps.

## SDK Example

```python
from meta_mcp.meta_client import AuthLoginBeginRequest, AuthLoginCompleteRequest

begin = await sdk.auth_login_begin(AuthLoginBeginRequest(scopes=["pages_manage_posts"]))
print(begin.authorization_url)

complete = await sdk.auth_login_complete(
    AuthLoginCompleteRequest(code=code, expected_state=begin.state)
)
print(complete.access_token)
```
