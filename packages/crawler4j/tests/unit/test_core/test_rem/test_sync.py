from unittest.mock import AsyncMock

import pytest

from src.core.rem.sync import ExternalSyncManager


@pytest.mark.asyncio
async def test_external_sync_manager_full_sync_delegates_to_gc_runner():
    gc_runner = AsyncMock(return_value=3)
    manager = ExternalSyncManager(pool=object(), gc_runner=gc_runner)

    result = await manager.full_sync()

    assert result == {"gc": 3}
    gc_runner.assert_awaited_once_with()
