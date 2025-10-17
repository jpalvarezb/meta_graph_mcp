# Integration Tests Guide

This guide explains how to run integration tests for the Meta Graph MCP server. Integration tests validate the system against **real Meta API endpoints**, ensuring that the authentication flow and API interactions work correctly in production.

## Overview

The integration test suite includes three layers of testing:

1. **Unit Tests** (existing) - Fast, mocked tests for logic validation
2. **Integration Tests** (this guide) - Real API calls to validate actual behavior
3. **End-to-End Tests** (future) - Complete user workflows from server startup through MCP interactions

## Current Status: Test User API Unavailable

⚠️ **Important**: Meta's Test User API is currently unavailable for creating new test users. As stated in their documentation:

> "We will share an update once access to creating new test users has been reinstated."

Due to this limitation, our integration tests use a **manual OAuth flow** approach instead.

## Integration Test: OAuth Authentication Flow

The file `test_integration_auth_manual.py` contains integration tests that validate the complete OAuth authentication workflow using real Meta API endpoints.

### What Gets Tested

✅ OAuth authorization URL generation  
✅ Authorization code exchange for access tokens  
✅ Token validation via `/debug_token` endpoint  
✅ Token metadata extraction (scopes, expiry, user ID)  
✅ Database persistence of token data  
✅ Token usage in subsequent API calls  

## Prerequisites

Before running integration tests, you need:

1. **A Real Meta App**
   - Not a test app (test users are currently unavailable)
   - App must be in **Development mode** or have permissions approved in Live mode
   - You need to be an Administrator or Developer on the app

2. **App Credentials**
   - App ID
   - App Secret
   - These should **never** be committed to version control

3. **Environment Setup**
   - Python 3.11+
   - All project dependencies installed (`pip install -e .[dev]`)

## Setup Instructions

### Step 1: Configure Environment Variables

Create a `.env.integration` file in the project root (this file is gitignored):

```bash
# .env.integration
META_MCP_APP_ID=your_real_app_id
META_MCP_APP_SECRET=your_real_app_secret
META_MCP_OAUTH_REDIRECT_URI=http://localhost:8000/oauth/callback
META_MCP_VERIFY_TOKEN=any_string_for_testing
```

**Important**: Never commit this file to version control!

### Step 2: Load Environment Variables

Before running tests, load your environment:

```bash
export $(cat .env.integration | xargs)
export RUN_INTEGRATION_TESTS=true
```

Or use a tool like `direnv` or `dotenv` to automatically load environment variables.

## Running the Tests

### Test 1: Generate Authorization URL

First, you need to generate an authorization URL to obtain an authorization code.

```bash
# Run with pytest verbose and capture output
RUN_INTEGRATION_TESTS=true pytest tests/test_integration_auth_manual.py::test_generate_authorization_url -v -s
```

**Expected Output:**
```
================================================================================
AUTHORIZATION URL GENERATED
================================================================================

Visit this URL in your browser (logged in as a developer on your app):

https://www.facebook.com/v18.0/dialog/oauth?client_id=...

After granting permissions, copy the 'code' parameter from the redirect URL.

State value (for verification): abc123...
================================================================================
```

**What to do:**
1. Copy the authorization URL from the output
2. Visit the URL in your browser
3. Log in as a developer/admin on your Meta app
4. Grant the requested permissions
5. Meta will redirect to your `redirect_uri` with a `code` parameter
6. **Copy the authorization code** from the redirected URL

Example redirect:
```
http://localhost:8000/oauth/callback?code=YOUR_AUTH_CODE_HERE&state=abc123
```

Copy the value after `code=` (before `&state`).

### Test 2: Run Full OAuth Integration Test

Now run the complete integration test using your authorization code:

```bash
# Replace YOUR_AUTH_CODE with the code you copied
INTEGRATION_TEST_AUTH_CODE=YOUR_AUTH_CODE \
RUN_INTEGRATION_TESTS=true \
pytest tests/test_integration_auth_manual.py::test_oauth_login_integration -v -s
```

**What the test does:**

1. **Step 1**: Exchanges your authorization code for a real access token
   - Makes a real API call to `/oauth/access_token`
   - Receives a valid access token from Meta

2. **Step 2**: Validates the token
   - Calls `/debug_token` to verify the token
   - Extracts metadata (scopes, expiry, user ID)
   - Persists token to the test database

3. **Step 3**: Uses the token
   - Makes a test API call to `/me` endpoint
   - Verifies the token works for real API requests

**Expected Output:**
```
================================================================================
RUNNING INTEGRATION TEST WITH REAL META API
================================================================================
App ID: 123456789
Using auth code: AQBNvZD...
================================================================================

Step 1: Exchanging authorization code for access token...
✓ Received access token (length: 195)
✓ Subject ID: 987654321
✓ Scopes: pages_manage_posts, pages_read_engagement, pages_read_user_content

Step 2: Verifying token persistence in database...
✓ Token persisted with hash: 8a4b2c1d3e5f...
✓ Token type: page
✓ Scopes in DB: pages_manage_posts, pages_read_engagement, pages_read_user_content
✓ Expires at: 2025-12-31T23:59:59+00:00

Step 3: Testing token with real API call to /me...
   Making API call to /me endpoint...
✓ Successfully called /me endpoint
✓ User ID: 987654321
✓ User name: Test Page

================================================================================
✅ INTEGRATION TEST PASSED - ALL VALIDATIONS SUCCESSFUL
================================================================================
```

### Test 3: Token Validation Only (Optional)

If you already have an access token and want to test only the validation logic:

```bash
INTEGRATION_TEST_ACCESS_TOKEN=your_existing_token \
RUN_INTEGRATION_TESTS=true \
pytest tests/test_integration_auth_manual.py::test_token_validation_with_real_api -v -s
```

This test validates:
- Token is accepted by Meta's `/debug_token` endpoint
- Metadata extraction works correctly
- Token is not expired
- Scopes are properly parsed

## Important Notes

### Authorization Code Limitations

⚠️ **Authorization codes are single-use and short-lived**
- Each code can only be exchanged once
- Codes expire in ~10 minutes
- You need a fresh code for each test run

### Test Database

- Each test run creates a temporary SQLite database
- The database is automatically cleaned up after the test
- No data persists between test runs

### Not for CI/CD

❌ **Do not run these tests in automated CI/CD pipelines**

These tests require manual intervention to obtain authorization codes. They are intended for:
- Local development validation
- Pre-deployment verification
- Debugging authentication issues

For CI/CD, continue using the existing unit tests with mocked responses.

### Security Considerations

🔒 **Keep your credentials secure**
- Never commit `.env.integration` to version control
- Never share your App Secret or access tokens
- Use environment variables for sensitive data
- Consider using a dedicated development app (not your production app)

## Troubleshooting

### "Authorization code is invalid or expired"

**Solution**: Generate a fresh authorization code and run the test again immediately.

### "Token validation failed"

**Possible causes**:
- App is not in Development mode
- Required permissions not approved
- App Secret is incorrect
- Network connectivity issues

### "pytest: command not found"

**Solution**: Ensure you're in the virtual environment:
```bash
source .venv/bin/activate
pip install -e .[dev]
```

### Tests are skipped

**Solution**: Make sure you set `RUN_INTEGRATION_TESTS=true`:
```bash
export RUN_INTEGRATION_TESTS=true
```

## Next Steps

After successfully running integration tests, you can:

1. **Test other API endpoints** - Extend the integration test to validate other tools
2. **Create E2E tests** - Build full workflow tests that start the server and use the SDK
3. **Document edge cases** - Add tests for error scenarios and edge cases
4. **Monitor test coverage** - Track which API interactions have integration test coverage

## Questions or Issues?

If you encounter problems with the integration tests:
1. Check that your Meta app is properly configured
2. Verify environment variables are set correctly
3. Ensure you're using a fresh authorization code
4. Review the test output for specific error messages
5. Check Meta's developer documentation for API changes
