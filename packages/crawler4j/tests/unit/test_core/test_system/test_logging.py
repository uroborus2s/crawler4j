from __future__ import annotations

import logging

import pytest

from crawler4j_sdk import TaskContext
from src.core.foundation.logging import logger
from src.core.system.preferences_service import PreferenceKey, PreferencesService
from src.ui.app import install_logging_preferences_sync


@pytest.fixture(autouse=True)
def patch_app_data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr("src.utils.paths.get_app_data_dir", lambda: tmp_path)
    monkeypatch.setattr("src.core.mms.registry.get_app_data_dir", lambda: tmp_path)
    from src.core.persistence.database import init_database

    init_database()
    yield tmp_path


@pytest.fixture(autouse=True)
def preserve_logger_state():
    old_entries = list(logger._entries)
    old_level = logger.level
    old_log_dir = logger._log_dir
    old_retention = logger._retention_days
    yield
    logger._entries = old_entries
    logger.configure(
        log_dir=old_log_dir,
        level=old_level,
        retention_days=old_retention,
    )


def test_task_context_defaults_to_app_logger():
    ctx = TaskContext(env_id=1, task_name="demo")

    assert ctx.logger is logger


def test_app_logger_captures_standard_logging_and_reconfigures_hot(tmp_path):
    log_dir = tmp_path / "logs"
    logger._entries = []
    logger.configure(log_dir=log_dir, level="ERROR", retention_days=3)

    sdk_logger = logging.getLogger("crawler4j_sdk.assembler")
    sdk_logger.info("hidden-before-hot-update")
    assert all(
        entry.message != "hidden-before-hot-update"
        for entry in logger.get_entries(limit=20)
    )

    logger.configure(log_dir=log_dir, level="INFO", retention_days=7)
    sdk_logger.info("visible-after-hot-update")

    messages = [entry.message for entry in logger.get_entries(limit=20)]
    assert "visible-after-hot-update" in messages
    assert logger._file_handler is not None
    assert logger._file_handler.backupCount == 7

    logger._file_handler.flush()
    log_text = (log_dir / "crawler4j.log").read_text(encoding="utf-8")
    assert "visible-after-hot-update" in log_text
    assert "hidden-before-hot-update" not in log_text


def test_install_logging_preferences_sync_hot_updates_unique_logger(tmp_path):
    prefs = PreferencesService()
    prefs.set(PreferenceKey.LOG_LEVEL, "WARNING")
    prefs.set(PreferenceKey.LOG_RETENTION, 5)

    install_logging_preferences_sync(prefs, log_dir=tmp_path / "logs")
    assert logger.level == logging.WARNING
    assert logger._file_handler is not None
    assert logger._file_handler.backupCount == 5

    prefs.set(PreferenceKey.LOG_LEVEL, "DEBUG")
    prefs.set(PreferenceKey.LOG_RETENTION, 9)

    assert logger.level == logging.DEBUG
    assert logger._file_handler is not None
    assert logger._file_handler.backupCount == 9
