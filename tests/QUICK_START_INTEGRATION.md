# Quick Start: Integration Tests

A quick reference for running OAuth integration tests with real Meta API calls.

## TL;DR

```bash
# 1. Set up environment
export META_MCP_APP_ID=your_app_id
export META_MCP_APP_SECRET=your_app_secret  
export META_MCP_OAUTH_REDIRECT_URI=http://localhost:8000/oauth/callback
export RUN_INTEGRATION_TESTS=true

# 2. Get authorization URL
pytest tests/test_integration_auth_manual.py::test_generate_authorization_url -v -s

# 3. Visit URL, grant permissions, copy code from redirect

# 4. Run test with code
INTEGRATION_TEST_AUTH_CODE=your_code \
pytest tests/test_integration_auth_manual.py::test_oauth_login_integration -v -s
```

## Step-by-Step

### 1. Configure Credentials

Create `.env.integration`:
```bash
META_MCP_APP_ID=123456789
META_MCP_APP_SECRET=abc123xyz789
META_MCP_OAUTH_REDIRECT_URI=http://localhost:8000/oauth/callback
META_MCP_VERIFY_TOKEN=test_token
```

Load it:
```bash
export $(cat .env.integration | xargs)
export RUN_INTEGRATION_TESTS=true
```

### 2. Generate Auth URL

```bash
pytest tests/test_integration_auth_manual.py::test_generate_authorization_url -v -s
```

Copy the URL from output.

### 3. Get Auth Code

1. Visit URL in browser (logged in as app developer)
2. Grant permissions
3. Copy `code` from redirect URL

Example redirect:
```
http://localhost:8000/oauth/callback?code=ABC123XYZ&state=...
```

Copy: `ABC123XYZ`

### 4. Run Integration Test

```bash
INTEGRATION_TEST_AUTH_CODE=ABC123XYZ \
pytest tests/test_integration_auth_manual.py::test_oauth_login_integration -v -s
```

## What Gets Tested

✅ OAuth code → token exchange  
✅ Token validation via `/debug_token`  
✅ Token persistence to database  
✅ Token usage in API calls  

## Important Notes

- **Authorization codes expire in ~10 minutes**
- **Each code is single-use only**
- **Generate a fresh code for each test run**
- **Do not run in CI/CD** (requires manual steps)

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Invalid authorization code" | Generate fresh code and run immediately |
| Tests skipped | Set `RUN_INTEGRATION_TESTS=true` |
| "Token validation failed" | Verify app is in Development mode |
| No output | Add `-s` flag to pytest command |

## Full Documentation

See `INTEGRATION_TESTS.md` for complete details.
