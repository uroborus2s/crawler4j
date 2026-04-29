from __future__ import annotations

import logging

import pytest

from crawler4j_contracts import TaskContext
from src.core.foundation.logging import logger
from src.core.system.config_center import get_config_center
from src.ui.app import install_logging_config_sync


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


def test_app_logger_captures_structured_json_logs(tmp_path):
    log_dir = tmp_path / "logs"
    logger._entries = []
    logger.configure(log_dir=log_dir, level="INFO", retention_days=3)

    logger.json(
        "[web-quiz] task snapshot",
        {
            "account_id": 1,
            "failed_task_count": 0,
            "phone_masked": "185****2132",
        },
        environment_id=313,
    )

    entry = logger.get_entries(limit=1)[0]
    assert entry.message.startswith("[web-quiz] task snapshot:\n{")
    assert entry.environment_id == 313
    assert entry.structured_type == "json"
    assert entry.structured_label == "[web-quiz] task snapshot"
    assert entry.structured_payload == {
        "account_id": 1,
        "failed_task_count": 0,
        "phone_masked": "185****2132",
    }

    assert logger._file_handler is not None
    logger._file_handler.flush()
    log_text = (log_dir / "crawler4j.log").read_text(encoding="utf-8")
    assert "[web-quiz] task snapshot:" in log_text
    assert '"failed_task_count": 0' in log_text


def test_install_logging_config_sync_hot_updates_unique_logger(tmp_path):
    config = get_config_center()
    config.set("logging.level", "WARNING")
    config.set("logging.retention_days", 5)

    install_logging_config_sync(config, log_dir=tmp_path / "logs")
    assert logger.level == logging.WARNING
    assert logger._file_handler is not None
    assert logger._file_handler.backupCount == 5

    config.set("logging.level", "DEBUG")
    config.set("logging.retention_days", 9)

    assert logger.level == logging.DEBUG
    assert logger._file_handler is not None
    assert logger._file_handler.backupCount == 9


def test_apscheduler_periodic_info_is_suppressed_below_warning(tmp_path):
    log_dir = tmp_path / "logs"
    logger._entries = []
    logger.configure(log_dir=log_dir, level="INFO", retention_days=3)

    scheduler_logger = logging.getLogger("apscheduler.executors.default")
    scheduler_logger.info("apscheduler-hidden-periodic-info")
    scheduler_logger.warning("apscheduler-visible-warning")

    messages = [entry.message for entry in logger.get_entries(limit=20)]
    assert "apscheduler-hidden-periodic-info" not in messages
    assert "apscheduler-visible-warning" in messages
    assert logging.getLogger("apscheduler").level == logging.WARNING


def test_debug_level_keeps_crawler4j_debug_but_suppresses_qasync_noise(tmp_path):
    log_dir = tmp_path / "logs"
    logger._entries = []
    logger.configure(log_dir=log_dir, level="DEBUG", retention_days=3)

    logging.getLogger("crawler4j").debug("crawler4j-debug-visible")
    qasync_logger = logging.getLogger("qasync._QThreadWorker")
    qasync_logger.debug("qasync-hidden-debug")
    qasync_logger.warning("qasync-visible-warning")

    messages = [entry.message for entry in logger.get_entries(limit=20)]
    assert "crawler4j-debug-visible" in messages
    assert "qasync-hidden-debug" not in messages
    assert "qasync-visible-warning" in messages
    assert logging.getLogger("qasync").level == logging.WARNING
