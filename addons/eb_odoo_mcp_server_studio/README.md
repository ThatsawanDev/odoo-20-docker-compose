# Odoo MCP Studio

OAuth 2.1 + Bearer token MCP server for Odoo 19.

## OAuth Flow

1. Client fetches `/.well-known/oauth-protected-resource` → gets `authorization_servers`
2. Client fetches `/.well-known/oauth-authorization-server` → gets `authorization_endpoint`, `token_endpoint`, `registration_endpoint`
3. Client may register via `POST /oauth/register` (Dynamic Client Registration) to get `client_id`
4. Client redirects user to `/oauth/authorize` → user logs in, clicks Allow
5. Redirect back with `?code=xxx` → client exchanges at `POST /oauth/token`
6. Server creates `mcp.api.token` and returns `access_token`
7. Client sends `Authorization: Bearer <token>` on MCP requests

## Token Module (mcp.api.token)

- **Manual:** Create in MCP Studio → API Tokens. Use as Bearer token.
- **OAuth:** Created automatically when user completes OAuth flow.

Both use the same model. Token authenticates MCP requests and maps to an Odoo user.

## ChatGPT: Client ID

When prompted "Enter a client ID", use: **`odoo-mcp-public`**

Or register first: `POST https://your-odoo.com/oauth/register` with JSON:
```json
{"client_name": "ChatGPT", "redirect_uris": ["https://chat.openai.com/..."]}
```
Use the returned `client_id`.

## ngrok

Set `web.base.url` and `web.base.url.freeze=True` in System Parameters.
