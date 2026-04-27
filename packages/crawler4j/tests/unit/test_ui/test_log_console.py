from src.core.foundation.context import current_task_id
from src.core.foundation.logging import logger
from src.ui.components.log_console import LogConsoleWidget


def test_log_console_widget_renders_global_logs_from_unique_service(qtbot):
    old_entries = list(logger._entries)
    logger._entries = []
    try:
        widget = LogConsoleWidget()
        qtbot.addWidget(widget)

        logger.info("system-log-visible")

        qtbot.waitUntil(lambda: "system-log-visible" in widget.text_edit.toPlainText())
    finally:
        logger._entries = old_entries


def test_log_console_widget_filters_task_logs_from_same_service(qtbot):
    old_entries = list(logger._entries)
    logger._entries = []
    try:
        widget = LogConsoleWidget()
        qtbot.addWidget(widget)
        widget.set_filter("task-1")

        token = current_task_id.set("task-1")
        try:
            logger.info("task-1-log")
        finally:
            current_task_id.reset(token)

        token = current_task_id.set("task-2")
        try:
            logger.info("task-2-log")
        finally:
            current_task_id.reset(token)

        qtbot.waitUntil(lambda: "task-1-log" in widget.text_edit.toPlainText())
        assert "task-2-log" not in widget.text_edit.toPlainText()
    finally:
        logger._entries = old_entries


def test_log_console_widget_batches_duplicate_logs_into_single_line(qtbot):
    old_entries = list(logger._entries)
    logger._entries = []
    try:
        widget = LogConsoleWidget()
        qtbot.addWidget(widget)

        for _ in range(5):
            logger.warning("duplicate-storm-log")

        qtbot.waitUntil(lambda: "duplicate-storm-log" in widget.text_edit.toPlainText())
        rendered = widget.text_edit.toPlainText()
        assert rendered.count("duplicate-storm-log") == 1
        assert "(x5)" in rendered
    finally:
        logger._entries = old_entries


def test_log_console_widget_renders_structured_json_logs(qtbot):
    old_entries = list(logger._entries)
    logger._entries = []
    try:
        widget = LogConsoleWidget()
        qtbot.addWidget(widget)

        logger.json(
            "[web-quiz] task snapshot",
            {
                "account_id": 1,
                "failed_task_count": 0,
                "phone_masked": "185****2132",
            },
        )

        qtbot.waitUntil(lambda: '"failed_task_count": 0' in widget.text_edit.toPlainText())
        rendered = widget.text_edit.toPlainText()
        assert "[web-quiz] task snapshot" in rendered
        assert '"account_id": 1' in rendered
        assert '"phone_masked": "185****2132"' in rendered
    finally:
        logger._entries = old_entries
