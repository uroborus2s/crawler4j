from contextlib import ExitStack
from unittest.mock import patch

import pytest

from src.core.persistence.database import STATE_DB, get_connection
from src.core.rem.models import Environment, EnvKind, EnvStatus
from src.core.rem.pool import EnvPool


@pytest.fixture
def temp_data_dir(tmp_path):
    with ExitStack() as stack:
        stack.enter_context(patch("src.utils.paths.get_app_data_dir", return_value=tmp_path))

        from src.core.persistence.database import init_database

        init_database()
        yield tmp_path


@pytest.mark.asyncio
async def test_env_pool_reload_from_db_replaces_stale_in_memory_cache(temp_data_dir):
    pool = EnvPool(max_instances=10)

    stale_env = Environment(
        id=99,
        name="stale-only-in-memory",
        kind=EnvKind.BROWSER,
        provider="virtualbrowser",
        status=EnvStatus.CREATING,
    )
    pool._environments[stale_env.id] = stale_env

    with get_connection(STATE_DB) as conn:
        conn.execute(
            """
            INSERT INTO environments (
                id, name, kind, provider, status, external_id, capabilities, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                12,
                "db-env-12",
                EnvKind.BROWSER.value,
                "virtualbrowser",
                EnvStatus.READY.value,
                "vb-12",
                '{"capabilities": ["page"]}',
                1,
                1,
            ),
        )

    await pool.reload_from_db()
    envs = await pool.list_all()

    assert [env.id for env in envs] == [12]
    assert envs[0].name == "db-env-12"
    assert envs[0].external_id == "vb-12"
