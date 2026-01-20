
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.rem.manager import EnvironmentManager
from src.core.rem.models import Environment, EnvKind, EnvStatus


@pytest.mark.asyncio
async def test_reserve_env_placeholder_max_plus_one():
    """Verify that _reserve_env_placeholder calculates name based on max existing sequence + 1."""
    # Setup
    manager = EnvironmentManager()
    manager.pool = MagicMock()
    manager.pool.add = AsyncMock()
    
    # Mock datetime to fixed date
    fixed_date_str = "20260118"
    
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
            f"env-{fixed_date_str}-1",
            f"env-{fixed_date_str}-2",
            f"env-{fixed_date_str}-5",
        ]
        # In the code: cursor.fetchall() returns list of tuples [(name,), ...]
        mock_cursor.fetchall.return_value = [(n,) for n in existing_names]
        
        # Action
        env = await manager._reserve_env_placeholder(EnvKind.BROWSER, "test_provider")
        
        # Assertion
        # Max existing seq is 5. Next should be 6.
        expected_name = f"env-{fixed_date_str}-6"
        assert env.name == expected_name
        assert env.status == EnvStatus.CREATING
        
        # Verify pool.add was called (Persistence)
        manager.pool.add.assert_called_once()
        saved_env = manager.pool.add.call_args[0][0]
        assert saved_env.name == expected_name

@pytest.mark.asyncio
async def test_reserve_env_placeholder_no_existing():
    """Verify that _reserve_env_placeholder starts at 1 if no existing names."""
    # Setup
    manager = EnvironmentManager()
    manager.pool = MagicMock()
    manager.pool.add = AsyncMock()
    
    fixed_date_str = "20260118"
    
    with patch("src.core.rem.manager.datetime") as mock_datetime, \
         patch("src.core.rem.manager.get_connection") as mock_get_conn:
        
        mock_now = MagicMock()
        mock_now.strftime.return_value = fixed_date_str
        mock_datetime.now.return_value = mock_now
        
        # Mock empty DB result
        mock_get_conn.return_value.__enter__.return_value.execute.return_value.fetchall.return_value = []
        
        # Action
        env = await manager._reserve_env_placeholder(EnvKind.BROWSER, "test_provider")
        
        # Assertion
        # No existing -> starts at 1
        expected_name = f"env-{fixed_date_str}-1"
        assert env.name == expected_name
        assert env.status == EnvStatus.CREATING
