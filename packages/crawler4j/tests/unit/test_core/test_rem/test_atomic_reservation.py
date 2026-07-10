import asyncio
from unittest.mock import MagicMock, patch

import pytest

from src.core.rem.manager import EnvironmentManager
from src.core.rem.models import EnvKind, EnvStatus


@pytest.mark.asyncio
async def test_reserve_env_placeholder_max_plus_one():
    """Verify that _reserve_env_placeholder calculates name based on max existing sequence + 1."""
    # Setup
    manager = EnvironmentManager()
    manager.pool = MagicMock()
    manager.pool._lock = asyncio.Lock()
    manager.pool._environments = {}
    
    # Mock datetime to fixed date
    fixed_date_str = "07102014"
    
    with patch("src.core.rem.manager.datetime") as mock_datetime, \
         patch("src.core.rem.manager.get_connection") as mock_get_conn:
        
        # Mock datetime.now()
        mock_now = MagicMock()
        mock_now.strftime.return_value = fixed_date_str
        # Note: We need to mock 'now' method of datetime class, but datetime is immutable C class.
        # Usually it's better to wrap datetime or use freezegun. 
        # But here we patched functionality in the manager module so manager.datetime is the mock.
        mock_datetime.now.return_value = mock_now
        
        # Mock DB connection and cursor
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        mock_conn.execute.return_value = mock_cursor
        
        # Simulate existing names: -1, -2, -5 (gap exists, should take max=5 + 1 = 6)
        existing_names = [
            f"t_{fixed_date_str}_0001",
            f"t_{fixed_date_str}_0002",
            f"t_{fixed_date_str}_0005",
        ]
        # In the code: cursor.fetchall() returns list of tuples [(name,), ...]
        mock_cursor.fetchall.return_value = [(n,) for n in existing_names]
        mock_cursor.lastrowid = 106
        
        # Action
        env = await manager._reserve_env_placeholder(EnvKind.BROWSER, "test_provider")
        
        # Assertion
        # Max existing seq is 5. Next should be 6.
        expected_name = f"t_{fixed_date_str}_0006"
        assert env.name == expected_name
        assert env.status == EnvStatus.CREATING
        assert env.id == 106
        assert manager.pool._environments[106].name == expected_name

@pytest.mark.asyncio
async def test_reserve_env_placeholder_no_existing():
    """Verify that _reserve_env_placeholder starts at 1 if no existing names."""
    # Setup
    manager = EnvironmentManager()
    manager.pool = MagicMock()
    manager.pool._lock = asyncio.Lock()
    manager.pool._environments = {}
    
    fixed_date_str = "07102014"
    
    with patch("src.core.rem.manager.datetime") as mock_datetime, \
         patch("src.core.rem.manager.get_connection") as mock_get_conn:
        
        mock_now = MagicMock()
        mock_now.strftime.return_value = fixed_date_str
        mock_datetime.now.return_value = mock_now
        
        # Mock empty DB result
        mock_conn = mock_get_conn.return_value.__enter__.return_value
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_cursor.lastrowid = 1
        mock_conn.execute.return_value = mock_cursor
        
        # Action
        env = await manager._reserve_env_placeholder(EnvKind.BROWSER, "test_provider")
        
        # Assertion
        # No existing -> starts at 1
        expected_name = f"t_{fixed_date_str}_0001"
        assert env.name == expected_name
        assert env.status == EnvStatus.CREATING
        assert env.id == 1
