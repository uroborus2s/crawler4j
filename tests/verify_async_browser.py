
import asyncio
import logging
import sys
from unittest.mock import AsyncMock, MagicMock

# Add project root to path
sys.path.append("/Users/uroborus/PythonProject/crawler4j")

# Mock dependencies
sys.modules["PyQt6"] = MagicMock()
sys.modules["PyQt6.QtCore"] = MagicMock()
sys.modules["requests"] = MagicMock()
sys.modules["playwright"] = MagicMock()
sys.modules["playwright.async_api"] = MagicMock()
sys.modules["cv2"] = MagicMock()
sys.modules["numpy"] = MagicMock()
sys.modules["ddddocr"] = MagicMock()
sys.modules["aiohttp"] = MagicMock()

# Mock logger
mock_logger_module = MagicMock()
mock_logger_module.logger = logging.getLogger("mock_logger")
sys.modules["src.utils.logger"] = mock_logger_module

from src.config import config
from src.core.browser_api import BrowserAPI
from src.utils.http_client import AsyncHttpClient

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("verifier")

async def test_async_browser_api():
    logger.info("Starting Async BrowserAPI Verification...")

    # Mock config
    config.browser_type = "bitbrowser"
    config.browser_api_url = "http://localhost:54345"

    # Mock AsyncHttpClient.post
    mock_post = AsyncMock()
    mock_response = {
        "success": True, 
        "data": {
            "ws": "ws://127.0.0.1:9222/devtools/browser/123",
            "http": "127.0.0.1:9222", 
            "driver": "/path/to/driver",
            "id": "profile_123"
        }
    }
    
    # We mock the static method directly to avoid real network call
    original_post = AsyncHttpClient.post
    AsyncHttpClient.post = mock_post
    mock_post.return_value = mock_response

    try:
        # Test open_browser_async
        logger.info("Testing open_browser_async...")
        res = await BrowserAPI.open_browser_async("profile_123")
        logger.info(f"Open Result: {res}")
        assert res["ws_endpoint"] == "ws://127.0.0.1:9222/devtools/browser/123"
        mock_post.assert_awaited_once()
        args, kwargs = mock_post.await_args
        assert args[0] == "http://localhost:54345/browser/open"
        assert kwargs["json"] == {"id": "profile_123"}
        
        # Test create_profile_async
        logger.info("Testing create_profile_async...")
        mock_post.reset_mock()
        mock_post.return_value = {"success": True, "data": {"id": "new_profile_id"}}
        
        pid = await BrowserAPI.create_profile_async(name="test_profile")
        logger.info(f"Create Result: {pid}")
        assert pid == "new_profile_id"
        mock_post.assert_awaited()
        
        # Test close_browser_async
        logger.info("Testing close_browser_async...")
        mock_post.reset_mock()
        mock_post.return_value = {"success": True}
        
        success = await BrowserAPI.close_browser_async("profile_123")
        logger.info(f"Close Result: {success}")
        assert success is True
        
        logger.info("✅ Async BrowserAPI Verification PASSED")
        
    except Exception as e:
        logger.error(f"❌ Verification FAILED: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        # Restore original method
        AsyncHttpClient.post = original_post

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(test_async_browser_api())
