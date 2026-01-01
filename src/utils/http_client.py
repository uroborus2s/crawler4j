"""Async HTTP Client module.

Provides a shared aiohttp.ClientSession for the application.
"""

from typing import Any, Optional

import aiohttp

from src.utils.logger import logger


class AsyncHttpClient:
    _session: Optional[aiohttp.ClientSession] = None
    
    @classmethod
    async def get_session(cls) -> aiohttp.ClientSession:
        """Get or create the shared ClientSession."""
        if cls._session is None or cls._session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            connector = aiohttp.TCPConnector(limit=100, ttl_dns_cache=300)
            cls._session = aiohttp.ClientSession(
                timeout=timeout, 
                connector=connector,
                # Trust env proxy settings or bypass them explicitly in requests
                trust_env=False 
            )
        return cls._session

    @classmethod
    async def close(cls):
        """Close the shared session."""
        if cls._session and not cls._session.closed:
            await cls._session.close()
            cls._session = None
            logger.info("AsyncHttpClient session closed")

    @classmethod
    async def get(cls, url: str, **kwargs) -> Any:
        """Helper for GET request."""
        session = await cls.get_session()
        async with session.get(url, **kwargs) as response:
            return await cls._handle_response(response)

    @classmethod
    async def post(cls, url: str, json: dict = None, **kwargs) -> Any:
        """Helper for POST request."""
        session = await cls.get_session()
        async with session.post(url, json=json, **kwargs) as response:
            return await cls._handle_response(response)

    @staticmethod
    async def _handle_response(response: aiohttp.ClientResponse) -> Any:
        """Handle response and parse JSON."""
        try:
            if response.content_type == 'application/json':
                return await response.json()
            return await response.text()
        except Exception as e:
            logger.error(f"Failed to parse response from {response.url}: {e}")
            raise
