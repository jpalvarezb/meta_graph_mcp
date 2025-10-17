"""Integration test for OAuth authentication using a manual authorization code.

This test validates the complete OAuth flow against the LIVE Meta API:
1. Generate an authorization URL
2. Exchange a real authorization code for an access token
3. Validate the token via /debug_token
4. Persist token metadata to the database
5. Verify the token can be used for API calls

⚠️  PREREQUISITES:
- A real Meta app (not a test app) with valid App ID and App Secret
- The app must be in Development mode (or have approved permissions in Live mode)
- You need to manually obtain an authorization code before running this test

📋 HOW TO RUN THIS TEST:

1. Set up your environment variables in .env.integration:
   ```
   META_MCP_APP_ID=your_real_app_id
   META_MCP_APP_SECRET=your_real_app_secret
   META_MCP_OAUTH_REDIRECT_URI=http://localhost:8000/oauth/callback
   META_MCP_VERIFY_TOKEN=any_verify_token
   ```

2. Manually generate an authorization code:
   
   a) Run the test in "URL generation mode" to get your authorization URL:
      ```bash
      pytest tests/test_integration_auth_manual.py::test_generate_authorization_url -v
      ```
   
   b) Copy the authorization URL from the test output
   
   c) Visit the URL in your browser while logged into Facebook/Meta as a developer on your app
   
   d) Grant the requested permissions
   
   e) Meta will redirect to your redirect_uri with a `code` parameter in the URL
   
   f) Copy the `code` value from the URL

3. Run the full integration test with your authorization code:
   ```bash
   INTEGRATION_TEST_AUTH_CODE=your_code_here pytest tests/test_integration_auth_manual.py::test_oauth_login_integration -v
   ```

4. The test will:
   - Exchange your code for a real access token from Meta
   - Call /debug_token to validate the token
   - Store the token in the test database
   - Verify the token works by calling the /me endpoint

⚠️  NOTES:
- Authorization codes are single-use and expire quickly (~10 minutes)
- You'll need to generate a fresh code each time you run the test
- This test uses REAL Meta API endpoints (not mocked)
- The test creates a temporary database that is cleaned up after the test
- DO NOT run this in CI/CD pipelines (it requires manual intervention)

🎯 WHAT THIS TEST VALIDATES:
- OAuth code exchange works with live Meta servers
- Token validation via /debug_token works correctly
- Token persistence to database works correctly
- Scope validation logic works correctly
- The complete authentication flow end-to-end
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import AsyncIterator

import pytest
from sqlalchemy import select

from meta_mcp.config import MetaMcpSettings, get_settings
from meta_mcp.meta_client import (
    AuthLoginBeginRequest,
    AuthLoginCompleteRequest,
    GraphRequestInput,
)
from meta_mcp.meta_client.auth import TokenService
from meta_mcp.meta_client.client import MetaGraphApiClient
from meta_mcp.mcp_tools import auth_login, core
from meta_mcp.mcp_tools.common import ToolEnvironment
from meta_mcp.storage import Token
from meta_mcp.storage.db import get_session_factory, init_models, session_scope
from meta_mcp.storage.queue import WebhookEventQueue


# Skip these tests by default unless explicitly enabled
pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_INTEGRATION_TESTS") != "true",
    reason="Integration tests require RUN_INTEGRATION_TESTS=true environment variable",
)


class _StubServer:
    """Stub server for registering tool handlers in tests."""

    def __init__(self) -> None:
        self.tools: dict[str, object] = {}

    def tool(self, name: str, structured_output: bool = True):
        def decorator(fn):
            self.tools[name] = fn
            return fn

        return decorator


@pytest.fixture
async def integration_settings(tmp_path) -> AsyncIterator[MetaMcpSettings]:
    """Create settings using real Meta app credentials from environment.
    
    This fixture loads actual credentials but uses a temporary test database.
    """
    # Load from environment or .env.integration file
    app_id = os.environ.get("META_MCP_APP_ID")
    app_secret = os.environ.get("META_MCP_APP_SECRET")
    redirect_uri = os.environ.get("META_MCP_OAUTH_REDIRECT_URI", "http://localhost:8000/oauth/callback")
    verify_token = os.environ.get("META_MCP_VERIFY_TOKEN", "test_verify_token")
    
    if not app_id or not app_secret:
        pytest.skip("META_MCP_APP_ID and META_MCP_APP_SECRET must be set for integration tests")
    
    # Use temporary database for testing
    db_path = tmp_path / "integration_test.db"
    
    settings = MetaMcpSettings(
        app_id=app_id,
        app_secret=app_secret,
        verify_token=verify_token,
        graph_api_base_url="https://graph.facebook.com",
        graph_api_version="v18.0",
        database_url=f"sqlite+aiosqlite:///{db_path}",
        oauth_redirect_uri=redirect_uri,
        facebook_oauth_base_url="https://www.facebook.com",
        max_retries=2,  # Allow some retries for real network calls
        default_timeout_seconds=30.0,
    )
    
    # Override global settings for this test
    os.environ["META_MCP_DATABASE_URL"] = str(settings.database_url)
    get_settings.cache_clear()
    
    # Initialize database
    await init_models()
    
    yield settings
    
    # Cleanup
    get_settings.cache_clear()
    os.environ.pop("META_MCP_DATABASE_URL", None)


@pytest.fixture
async def integration_env(integration_settings: MetaMcpSettings) -> AsyncIterator[ToolEnvironment]:
    """Create a complete tool environment for integration testing."""
    client = MetaGraphApiClient()
    token_service = TokenService(client)
    event_queue = WebhookEventQueue()
    
    env = ToolEnvironment(
        settings=integration_settings,
        client=client,
        token_service=token_service,
        event_queue=event_queue,
    )
    
    yield env
    
    # Cleanup
    await client.aclose()


@pytest.mark.asyncio
async def test_generate_authorization_url(integration_env: ToolEnvironment) -> None:
    """Generate an authorization URL for manual testing.
    
    Run this test to get the URL you need to visit to obtain an authorization code:
    
        pytest tests/test_integration_auth_manual.py::test_generate_authorization_url -v -s
    
    The URL will be printed to stdout. Visit it in your browser to grant permissions.
    """
    server = _StubServer()
    auth_login.register(server, integration_env)
    
    # Request common permissions for testing
    request = AuthLoginBeginRequest(
        scopes=[
            "pages_manage_posts",
            "pages_read_engagement",
            "pages_read_user_content",
        ]
    )
    
    handler = server.tools["auth.login.begin"]
    result = await handler(request, None)
    
    assert result["ok"] is True
    assert "authorization_url" in result["data"]
    assert "state" in result["data"]
    
    auth_url = result["data"]["authorization_url"]
    state = result["data"]["state"]
    
    # Print the URL for the user to visit
    print("\n" + "=" * 80)
    print("AUTHORIZATION URL GENERATED")
    print("=" * 80)
    print("\nVisit this URL in your browser (logged in as a developer on your app):")
    print(f"\n{auth_url}\n")
    print("After granting permissions, copy the 'code' parameter from the redirect URL.")
    print(f"\nState value (for verification): {state}")
    print("=" * 80)
    
    # Verify URL structure
    assert integration_env.settings.facebook_oauth_base_url in auth_url
    assert str(integration_env.settings.app_id) in auth_url
    assert "pages_manage_posts" in auth_url
    assert state in auth_url


@pytest.mark.asyncio
async def test_oauth_login_integration(integration_env: ToolEnvironment) -> None:
    """Test the complete OAuth login flow with a real authorization code.
    
    This test performs REAL API calls to Meta's servers.
    
    Run with:
        INTEGRATION_TEST_AUTH_CODE=your_code RUN_INTEGRATION_TESTS=true \\
        pytest tests/test_integration_auth_manual.py::test_oauth_login_integration -v -s
    
    What this test validates:
    1. ✓ Code exchange with Meta's /oauth/access_token endpoint
    2. ✓ Token validation via /debug_token endpoint  
    3. ✓ Token metadata extraction (scopes, expiry, user ID)
    4. ✓ Database persistence of token data
    5. ✓ Token can be used for subsequent API calls
    """
    # Get authorization code from environment
    auth_code = os.environ.get("INTEGRATION_TEST_AUTH_CODE")
    if not auth_code:
        pytest.skip(
            "INTEGRATION_TEST_AUTH_CODE environment variable must be set. "
            "Run test_generate_authorization_url first to get a code."
        )
    
    print(f"\n{'=' * 80}")
    print("RUNNING INTEGRATION TEST WITH REAL META API")
    print(f"{'=' * 80}")
    print(f"App ID: {integration_env.settings.app_id}")
    print(f"Using auth code: {auth_code[:10]}...")
    print(f"{'=' * 80}\n")
    
    # Set up tool server
    server = _StubServer()
    auth_login.register(server, integration_env)
    core.register(server, integration_env)
    
    # Step 1: Complete OAuth flow with real authorization code
    print("Step 1: Exchanging authorization code for access token...")
    complete_request = AuthLoginCompleteRequest(
        code=auth_code,
        redirect_uri=integration_env.settings.oauth_redirect_uri,
    )
    
    complete_handler = server.tools["auth.login.complete"]
    complete_result = await complete_handler(complete_request, None)
    
    # Verify successful token exchange
    if not complete_result["ok"]:
        print(f"\n❌ OAuth completion failed: {complete_result}")
        pytest.fail(f"OAuth flow failed: {complete_result.get('error', {}).get('message', 'Unknown error')}")
    
    assert complete_result["ok"] is True, "OAuth completion should succeed"
    assert "data" in complete_result
    assert "access_token" in complete_result["data"]
    
    access_token = complete_result["data"]["access_token"]
    subject_id = complete_result["data"].get("subject_id")
    scopes = complete_result["data"].get("scopes", [])
    
    print(f"✓ Received access token (length: {len(access_token)})")
    print(f"✓ Subject ID: {subject_id}")
    print(f"✓ Scopes: {', '.join(scopes)}")
    
    # Step 2: Verify token was persisted to database
    print("\nStep 2: Verifying token persistence in database...")
    
    async with session_scope() as session:
        stmt = select(Token)
        result = await session.execute(stmt)
        tokens = list(result.scalars().all())
        
        assert len(tokens) == 1, "Exactly one token should be in database"
        
        stored_token = tokens[0]
        assert stored_token.subject_id == subject_id
        assert stored_token.app_id == integration_env.settings.app_id
        assert len(stored_token.scopes) > 0
        assert stored_token.expires_at is None or stored_token.expires_at > datetime.now(stored_token.expires_at.tzinfo)
        
        print(f"✓ Token persisted with hash: {stored_token.id[:16]}...")
        print(f"✓ Token type: {stored_token.type.value}")
        print(f"✓ Scopes in DB: {', '.join(stored_token.scopes)}")
        if stored_token.expires_at:
            print(f"✓ Expires at: {stored_token.expires_at.isoformat()}")
    
    # Step 3: Use the token to make a real API call
    print("\nStep 3: Testing token with real API call to /me...")
    
    # Use the graph.request tool to call /me
    graph_request = GraphRequestInput(
        method="GET",
        path=f"/{integration_env.settings.graph_api_version}/me",
        query={"fields": "id,name"},
    )
    
    # Create a mock context with the access token
    class _MockContext:
        class _RequestContext:
            class _Request:
                class _Params:
                    arguments = {}
                params = _Params()
            request = _Request()
            meta = None
        request_context = _RequestContext()
    
    # We need to pass the token through the context - let's do it via arguments instead
    graph_request_dict = graph_request.model_dump()
    
    # For this test, we'll use the client directly since we have the token
    print("   Making API call to /me endpoint...")
    response = await integration_env.client.request(
        access_token=access_token,
        method="GET",
        path=f"/{integration_env.settings.graph_api_version}/me",
        query={"fields": "id,name"},
    )
    
    assert response.status_code == 200, f"API call should succeed, got {response.status_code}"
    
    me_data = response.json()
    assert "id" in me_data
    assert me_data["id"] == subject_id
    
    print(f"✓ Successfully called /me endpoint")
    print(f"✓ User ID: {me_data['id']}")
    if "name" in me_data:
        print(f"✓ User name: {me_data['name']}")
    
    print(f"\n{'=' * 80}")
    print("✅ INTEGRATION TEST PASSED - ALL VALIDATIONS SUCCESSFUL")
    print(f"{'=' * 80}\n")


@pytest.mark.asyncio
async def test_token_validation_with_real_api(integration_env: ToolEnvironment) -> None:
    """Test token validation against real Meta API.
    
    This test can use either:
    1. A fresh authorization code (from INTEGRATION_TEST_AUTH_CODE)
    2. Or an existing access token (from INTEGRATION_TEST_ACCESS_TOKEN)
    
    This is useful for testing token validation logic without going through the full OAuth flow.
    """
    # Try to get either an auth code or existing access token
    auth_code = os.environ.get("INTEGRATION_TEST_AUTH_CODE")
    access_token = os.environ.get("INTEGRATION_TEST_ACCESS_TOKEN")
    
    if not auth_code and not access_token:
        pytest.skip(
            "Either INTEGRATION_TEST_AUTH_CODE or INTEGRATION_TEST_ACCESS_TOKEN must be set"
        )
    
    server = _StubServer()
    auth_login.register(server, integration_env)
    
    # If we have a code, exchange it for a token first
    if auth_code and not access_token:
        print("Exchanging auth code for access token...")
        complete_request = AuthLoginCompleteRequest(
            code=auth_code,
            redirect_uri=integration_env.settings.oauth_redirect_uri,
        )
        complete_handler = server.tools["auth.login.complete"]
        complete_result = await complete_handler(complete_request, None)
        
        assert complete_result["ok"] is True
        access_token = complete_result["data"]["access_token"]
    
    # Now test token validation
    print(f"\nValidating token against Meta API...")
    metadata = await integration_env.token_service.inspect_token(
        access_token=access_token
    )
    
    print(f"✓ Token is valid")
    print(f"✓ App ID: {metadata.app_id}")
    print(f"✓ Subject ID: {metadata.subject_id}")
    print(f"✓ Token type: {metadata.type.value}")
    print(f"✓ Scopes: {', '.join(metadata.scopes)}")
    print(f"✓ Issued at: {metadata.issued_at.isoformat()}")
    if metadata.expires_at:
        print(f"✓ Expires at: {metadata.expires_at.isoformat()}")
    else:
        print(f"✓ Token does not expire (long-lived)")
    
    # Verify token metadata
    assert metadata.app_id == integration_env.settings.app_id
    assert len(metadata.scopes) > 0
    assert not metadata.is_expired
    
    print("\n✅ Token validation successful")
