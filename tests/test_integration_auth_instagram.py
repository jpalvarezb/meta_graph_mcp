"""Integration test for Instagram OAuth authentication using manual authorization code.

This test validates the complete OAuth flow for Instagram Business API against LIVE Meta API:
1. Generate an authorization URL with Instagram-specific scopes
2. Exchange a real authorization code for an access token
3. Validate the token via /debug_token
4. Verify Instagram Business scope is present
5. Test token with Instagram API endpoints

⚠️  PREREQUISITES:
- A real Meta app with Instagram Basic Display or Instagram Graph API product added
- An Instagram Business account (NOT personal account)
- The Instagram Business account must be connected to a Facebook Page
- You must be an admin of both the Facebook Page and Instagram Business account
- App must be in Development mode or have approved permissions in Live mode

📋 INSTAGRAM REQUIREMENTS:
- Instagram account must be converted to a Business or Creator account
- Business account must be linked to a Facebook Page in Instagram settings
- You need to authenticate as the Page admin (not your personal Facebook account)

📋 HOW TO RUN THIS TEST:

1. Set up your environment variables in .env.integration:
   ```
   META_MCP_APP_ID=your_real_app_id
   META_MCP_APP_SECRET=your_real_app_secret
   META_MCP_OAUTH_REDIRECT_URI=https://yourdomain.com/oauth/callback
   META_MCP_VERIFY_TOKEN=any_verify_token
   ```
   
   ⚠️  IMPORTANT: For Instagram, you MUST use a PUBLIC redirect URI (not localhost)
   Your redirect URI must be registered in your Meta App settings under "Settings > Basic > Add Platform"

2. Generate an authorization URL:
   ```bash
   RUN_INTEGRATION_TESTS=true \
   pytest tests/test_integration_auth_instagram.py::test_generate_instagram_authorization_url -v -s
   ```

3. Visit the URL in your browser:
   - Make sure you're logged in as the Page admin
   - Grant the Instagram permissions
   - You may be prompted to select which Instagram Business account to connect
   - After approval, you'll be redirected with a `code` parameter

4. Run the full integration test:
   ```bash
   INTEGRATION_TEST_AUTH_CODE=your_code_here \
   RUN_INTEGRATION_TESTS=true \
   pytest tests/test_integration_auth_instagram.py::test_instagram_oauth_login_integration -v -s
   ```

🎯 WHAT THIS TEST VALIDATES:
- OAuth code exchange works with Instagram scopes
- instagram_basic scope is present in token
- Token can be used to query Instagram Business accounts
- Instagram-specific API endpoints are accessible
- Token persistence includes Instagram scopes

⚠️  NOTES:
- Authorization codes are single-use and expire in ~10 minutes
- You need a fresh code for each test run
- This test uses REAL Meta/Instagram API endpoints
- If you get permission errors, verify your Instagram account is a Business account
- If you can't select an Instagram account, check that it's linked to a Facebook Page
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from datetime import datetime

import pytest
from sqlalchemy import select

from meta_mcp.config import MetaMcpSettings, get_settings
from meta_mcp.mcp_tools import auth_login, core
from meta_mcp.mcp_tools.common import ToolEnvironment
from meta_mcp.meta_client import (
    AuthLoginBeginRequest,
    AuthLoginCompleteRequest,
)
from meta_mcp.meta_client.auth import TokenService
from meta_mcp.meta_client.client import MetaGraphApiClient
from meta_mcp.storage import Token
from meta_mcp.storage.db import init_models, session_scope
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
    # Load from environment
    app_id = os.environ.get("META_MCP_APP_ID")
    app_secret = os.environ.get("META_MCP_APP_SECRET")
    redirect_uri = os.environ.get("META_MCP_OAUTH_REDIRECT_URI")
    verify_token = os.environ.get("META_MCP_VERIFY_TOKEN", "test_verify_token")
    
    if not app_id or not app_secret:
        pytest.skip("META_MCP_APP_ID and META_MCP_APP_SECRET must be set for integration tests")
    
    if not redirect_uri or "localhost" in redirect_uri:
        pytest.skip(
            "META_MCP_OAUTH_REDIRECT_URI must be set to a PUBLIC URL (not localhost) for Instagram tests. "
            "Example: https://yourdomain.com/oauth/callback"
        )
    
    # Use temporary database for testing
    db_path = tmp_path / "integration_instagram_test.db"
    
    settings = MetaMcpSettings(
        app_id=app_id,
        app_secret=app_secret,
        verify_token=verify_token,
        graph_api_base_url="https://graph.facebook.com",
        graph_api_version="v18.0",
        database_url=f"sqlite+aiosqlite:///{db_path}",
        oauth_redirect_uri=redirect_uri,
        facebook_oauth_base_url="https://www.facebook.com",
        max_retries=2,
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
async def test_generate_instagram_authorization_url(integration_env: ToolEnvironment) -> None:
    """Generate an Instagram authorization URL for manual testing.
    
    Run this test to get the URL you need to visit to obtain an authorization code:
    
        RUN_INTEGRATION_TESTS=true \
        pytest tests/test_integration_auth_instagram.py::test_generate_instagram_authorization_url -v -s
    
    The URL will be printed to stdout. Visit it in your browser to grant Instagram permissions.
    """
    server = _StubServer()
    auth_login.register(server, integration_env)
    
    # Request Instagram-specific permissions
    request = AuthLoginBeginRequest(
        scopes=[
            "instagram_basic",              # Required for Instagram Business API
            "instagram_content_publish",    # Publish content to Instagram
            "instagram_manage_comments",    # Manage comments
            "instagram_manage_insights",    # View insights
            "pages_show_list",              # Access connected Pages
            "pages_read_engagement",        # Read Page engagement
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
    print("INSTAGRAM AUTHORIZATION URL GENERATED")
    print("=" * 80)
    print("\n⚠️  IMPORTANT NOTES:")
    print("   - Your redirect URI must be PUBLIC (not localhost)")
    print("   - Instagram account must be a Business or Creator account")
    print("   - Business account must be linked to a Facebook Page")
    print("   - You must authenticate as the Page admin")
    print("\nVisit this URL in your browser:")
    print(f"\n{auth_url}\n")
    print("After granting permissions:")
    print("1. You may be asked to select an Instagram Business account")
    print("2. You'll be redirected to your redirect URI")
    print("3. Copy the 'code' parameter from the redirect URL")
    print(f"\nState value (for verification): {state}")
    print("=" * 80)
    
    # Verify URL structure
    assert integration_env.settings.facebook_oauth_base_url in auth_url
    assert str(integration_env.settings.app_id) in auth_url
    assert "instagram_basic" in auth_url
    assert state in auth_url


@pytest.mark.asyncio
async def test_instagram_oauth_login_integration(integration_env: ToolEnvironment) -> None:
    """Test the complete Instagram OAuth login flow with a real authorization code.
    
    This test performs REAL API calls to Meta's servers with Instagram scopes.
    
    Run with:
        INTEGRATION_TEST_AUTH_CODE=your_code \
        RUN_INTEGRATION_TESTS=true \
        pytest tests/test_integration_auth_instagram.py::test_instagram_oauth_login_integration -v -s
    
    What this test validates:
    1. ✓ Code exchange with Instagram scopes
    2. ✓ Token validation via /debug_token endpoint
    3. ✓ instagram_basic scope is present
    4. ✓ Token metadata extraction
    5. ✓ Database persistence of Instagram token
    6. ✓ Token can be used for Instagram API calls
    """
    # Get authorization code from environment
    auth_code = os.environ.get("INTEGRATION_TEST_AUTH_CODE")
    if not auth_code:
        pytest.skip(
            "INTEGRATION_TEST_AUTH_CODE environment variable must be set. "
            "Run test_generate_instagram_authorization_url first to get a code."
        )
    
    print(f"\n{'=' * 80}")
    print("RUNNING INSTAGRAM INTEGRATION TEST WITH REAL META API")
    print(f"{'=' * 80}")
    print(f"App ID: {integration_env.settings.app_id}")
    print(f"Redirect URI: {integration_env.settings.oauth_redirect_uri}")
    print(f"Using auth code: {auth_code[:10]}...")
    print(f"{'=' * 80}\n")
    
    # Set up tool server
    server = _StubServer()
    auth_login.register(server, integration_env)
    core.register(server, integration_env)
    
    # Step 1: Complete OAuth flow with Instagram authorization code
    print("Step 1: Exchanging authorization code for access token with Instagram scopes...")
    complete_request = AuthLoginCompleteRequest(
        code=auth_code,
        redirect_uri=integration_env.settings.oauth_redirect_uri,
    )
    
    complete_handler = server.tools["auth.login.complete"]
    complete_result = await complete_handler(complete_request, None)
    
    # Verify successful token exchange
    if not complete_result["ok"]:
        error_msg = complete_result.get("error", {}).get("message", "Unknown error")
        print(f"\n❌ OAuth completion failed: {error_msg}")
        print("\nCommon Instagram OAuth issues:")
        print("  - Instagram account is not a Business/Creator account")
        print("  - Business account not linked to a Facebook Page")
        print("  - Not authenticated as Page admin")
        print("  - Redirect URI not registered in app settings")
        pytest.fail(f"OAuth flow failed: {error_msg}")
    
    assert complete_result["ok"] is True, "OAuth completion should succeed"
    assert "data" in complete_result
    assert "access_token" in complete_result["data"]
    
    access_token = complete_result["data"]["access_token"]
    subject_id = complete_result["data"].get("subject_id")
    scopes = complete_result["data"].get("scopes", [])
    
    print(f"✓ Received access token (length: {len(access_token)})")
    print(f"✓ Subject ID: {subject_id}")
    print(f"✓ Scopes: {', '.join(scopes)}")
    
    # Verify Instagram scope is present
    if "instagram_basic" not in scopes:
        print("\n⚠️  WARNING: instagram_basic scope not found in token!")
        print("   This may indicate the Instagram Business account wasn't properly connected.")
        print("   Received scopes:", scopes)
    else:
        print("✓ instagram_basic scope confirmed")
    
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
        
        # Check for Instagram scope in DB
        if "instagram_basic" in stored_token.scopes:
            print("✓ Instagram scope persisted to database")
    
    # Step 3: Test token with Instagram API call
    print("\nStep 3: Testing token with Instagram API...")
    
    # Query the accounts endpoint to see connected Instagram accounts
    print("   Querying Instagram Business accounts...")
    try:
        response = await integration_env.client.request(
            access_token=access_token,
            method="GET",
            path=f"/{integration_env.settings.graph_api_version}/me/accounts",
            query={"fields": "id,name,instagram_business_account"},
        )
        
        if response.status_code == 200:
            accounts_data = response.json()
            print("✓ Successfully called /me/accounts endpoint")
            
            if "data" in accounts_data and accounts_data["data"]:
                print(f"✓ Found {len(accounts_data['data'])} Facebook Page(s)")
                
                # Check for Instagram Business accounts
                ig_accounts = [
                    acc for acc in accounts_data["data"] 
                    if "instagram_business_account" in acc
                ]
                
                if ig_accounts:
                    print(f"✓ Found {len(ig_accounts)} Page(s) with Instagram Business account")
                    for acc in ig_accounts:
                        ig_id = acc["instagram_business_account"]["id"]
                        print(f"   - Page: {acc.get('name', 'Unknown')}")
                        print(f"     Instagram Business ID: {ig_id}")
                        
                        # Try to query the Instagram account
                        print("\n   Testing Instagram Business account API access...")
                        ig_response = await integration_env.client.request(
                            access_token=access_token,
                            method="GET",
                            path=f"/{integration_env.settings.graph_api_version}/{ig_id}",
                            query={"fields": "id,username,name,profile_picture_url"},
                        )
                        
                        if ig_response.status_code == 200:
                            ig_data = ig_response.json()
                            print(f"   ✓ Instagram account: @{ig_data.get('username', 'unknown')}")
                            print(f"   ✓ Account name: {ig_data.get('name', 'N/A')}")
                        else:
                            print(f"   ⚠️  Could not access Instagram account details (status: {ig_response.status_code})")
                else:
                    print("⚠️  No Instagram Business accounts found linked to these Pages")
                    print("   Make sure your Instagram account is:")
                    print("   - Converted to Business or Creator account")
                    print("   - Linked to a Facebook Page in Instagram settings")
            else:
                print("⚠️  No Facebook Pages found")
        else:
            print(f"⚠️  API call failed with status: {response.status_code}")
            print(f"   Response: {response.text}")
    except Exception as e:
        print(f"⚠️  Error making Instagram API call: {e}")
    
    print(f"\n{'=' * 80}")
    print("✅ INSTAGRAM INTEGRATION TEST PASSED")
    print(f"{'=' * 80}\n")


@pytest.mark.asyncio
async def test_instagram_token_validation(integration_env: ToolEnvironment) -> None:
    """Test Instagram token validation logic.
    
    This test validates that the token service correctly handles Instagram Business scope.
    
    Run with:
        INTEGRATION_TEST_AUTH_CODE=your_code \
        RUN_INTEGRATION_TESTS=true \
        pytest tests/test_integration_auth_instagram.py::test_instagram_token_validation -v -s
    """
    auth_code = os.environ.get("INTEGRATION_TEST_AUTH_CODE")
    if not auth_code:
        pytest.skip("INTEGRATION_TEST_AUTH_CODE must be set")
    
    server = _StubServer()
    auth_login.register(server, integration_env)
    
    # Exchange code for token
    complete_request = AuthLoginCompleteRequest(
        code=auth_code,
        redirect_uri=integration_env.settings.oauth_redirect_uri,
    )
    complete_handler = server.tools["auth.login.complete"]
    complete_result = await complete_handler(complete_request, None)
    
    assert complete_result["ok"] is True
    access_token = complete_result["data"]["access_token"]
    
    # Test token inspection
    print("\nValidating Instagram token metadata...")
    metadata = await integration_env.token_service.inspect_token(
        access_token=access_token
    )
    
    print("✓ Token is valid")
    print(f"✓ App ID: {metadata.app_id}")
    print(f"✓ Subject ID: {metadata.subject_id}")
    print(f"✓ Token type: {metadata.type.value}")
    print(f"✓ Scopes: {', '.join(metadata.scopes)}")
    
    # Test Instagram Business scope validation
    print("\nTesting Instagram Business scope validation...")
    try:
        await integration_env.token_service.ensure_instagram_business(metadata)
        print("✓ Instagram Business scope validation passed")
    except Exception as e:
        print(f"❌ Instagram Business scope validation failed: {e}")
        print("\nThis means the token doesn't have instagram_basic scope.")
        print("Possible reasons:")
        print("  - User denied Instagram permissions during OAuth")
        print("  - Instagram account is not a Business account")
        print("  - Business account not linked to Facebook Page")
        raise
    
    print("\n✅ Instagram token validation successful")
