from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_meta_sdk import MetaMcpSdk


@pytest.mark.asyncio
async def test_connect_mock_session():
    with patch("mcp_meta_sdk.client.streamablehttp_client") as mock_client,          patch("mcp_meta_sdk.client.ClientSession") as mock_session_cls:
        
        mock_ctx = AsyncMock()
        mock_client.return_value = mock_ctx
        mock_ctx.__aenter__.return_value = (MagicMock(), MagicMock(), MagicMock(return_value="sess_1"))
        
        mock_session = AsyncMock()
        mock_session_cls.return_value = mock_session
        
        # Configure call_tool return value
        mock_result = MagicMock()
        mock_result.structuredContent = {
            "ok": True, 
            "data": {"app_id": "1", "type": "p", "scopes": [], "valid": True, "expires_at": None}, 
            "meta": {}
        }
        mock_session.call_tool.return_value = mock_result
        
        async with MetaMcpSdk(base_url="http://localhost") as sdk:
            assert sdk.session_id == "sess_1"
            await sdk.auth_permissions_check("tok")
            
        mock_session.initialize.assert_awaited_once()
        mock_session.call_tool.assert_awaited()
        mock_ctx.__aexit__.assert_awaited()

@pytest.mark.asyncio
async def test_connect_mock_session_twice():
    with patch("mcp_meta_sdk.client.streamablehttp_client") as mock_client,          patch("mcp_meta_sdk.client.ClientSession") as mock_session_cls:
        
        mock_ctx = AsyncMock()
        mock_client.return_value = mock_ctx
        mock_ctx.__aenter__.return_value = (MagicMock(), MagicMock(), MagicMock())
        
        mock_session = AsyncMock()
        mock_session_cls.return_value = mock_session
        
        sdk = MetaMcpSdk(base_url="http://localhost")
        await sdk.connect()
        await sdk.connect()
        
        assert mock_session.initialize.call_count == 1
        await sdk.close()
