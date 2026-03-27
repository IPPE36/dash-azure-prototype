import json
import logging
import sys

from shared import log as log_mod
from shared.log import JsonFormatter, log_timed, log_timed_block


def test_json_formatter_includes_context_fields():
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello %s",
        args=("world",),
        exc_info=None,
    )
    record.trace_id = "t-123"
    record.request_id = "r-456"
    record.task_id = "task-1"
    record.task_name = "long_task"

    formatted = JsonFormatter().format(record)
    payload = json.loads(formatted)

    assert payload["message"] == "hello world"
    assert payload["trace_id"] == "t-123"
    assert payload["request_id"] == "r-456"
    assert payload["task_id"] == "task-1"
    assert payload["task_name"] == "long_task"


def test_json_formatter_includes_exc_info():
    try:
        raise ValueError("boom")
    except ValueError:
        exc_info = sys.exc_info()

    record = logging.LogRecord(
        name="test_logger",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="failed",
        args=(),
        exc_info=exc_info,
    )

    formatted = JsonFormatter().format(record)
    payload = json.loads(formatted)

    assert payload["message"] == "failed"
    assert "exc_info" in payload
    assert "ValueError" in payload["exc_info"]


def test_log_timed_success_logs_completed(caplog):
    logger = logging.getLogger("test_log_timed_success")
    caplog.set_level(logging.INFO)

    @log_timed(logger=logger, label="work")
    def do_work():
        return 123

    assert do_work() == 123
    assert any("completed work" in record.message for record in caplog.records)


def test_log_timed_failure_logs_failed(caplog):
    logger = logging.getLogger("test_log_timed_failure")
    caplog.set_level(logging.ERROR)

    @log_timed(logger=logger, label="work")
    def do_work():
        raise RuntimeError("nope")

    try:
        do_work()
    except RuntimeError:
        pass

    assert any("failed work" in record.message for record in caplog.records)


def test_log_timed_block_success_logs_completed(caplog):
    logger = logging.getLogger("test_log_timed_block_success")
    caplog.set_level(logging.INFO)

    with log_timed_block("block", logger=logger):
        pass

    assert any("completed block" in record.message for record in caplog.records)


def test_log_timed_block_failure_logs_failed(caplog):
    logger = logging.getLogger("test_log_timed_block_failure")
    caplog.set_level(logging.ERROR)

    try:
        with log_timed_block("block", logger=logger):
            raise ValueError("boom")
    except ValueError:
        pass

    assert any("failed block" in record.message for record in caplog.records)


def test_configure_logs_json_sets_json_formatter():
    root = logging.getLogger()
    old_handlers = list(root.handlers)
    old_level = root.level
    old_configured = log_mod._CONFIGURED
    old_format = log_mod.LOG_FORMAT
    old_level_setting = log_mod.LOG_LEVEL
    try:
        root.handlers.clear()
        log_mod._CONFIGURED = False
        log_mod.LOG_FORMAT = "json"
        log_mod.LOG_LEVEL = "INFO"

        log_mod.configure_logs()

        assert len(root.handlers) == 1
        assert isinstance(root.handlers[0].formatter, JsonFormatter)
    finally:
        root.handlers.clear()
        root.handlers.extend(old_handlers)
        root.setLevel(old_level)
        log_mod._CONFIGURED = old_configured
        log_mod.LOG_FORMAT = old_format
        log_mod.LOG_LEVEL = old_level_setting


def test_configure_logs_console_sets_standard_formatter():
    root = logging.getLogger()
    old_handlers = list(root.handlers)
    old_level = root.level
    old_configured = log_mod._CONFIGURED
    old_format = log_mod.LOG_FORMAT
    old_level_setting = log_mod.LOG_LEVEL
    try:
        root.handlers.clear()
        log_mod._CONFIGURED = False
        log_mod.LOG_FORMAT = "console"
        log_mod.LOG_LEVEL = "INFO"

        log_mod.configure_logs()

        assert len(root.handlers) == 1
        assert isinstance(root.handlers[0].formatter, logging.Formatter)
        assert not isinstance(root.handlers[0].formatter, JsonFormatter)
    finally:
        root.handlers.clear()
        root.handlers.extend(old_handlers)
        root.setLevel(old_level)
        log_mod._CONFIGURED = old_configured
        log_mod.LOG_FORMAT = old_format
        log_mod.LOG_LEVEL = old_level_setting


def test_configure_logs_idempotent():
    root = logging.getLogger()
    old_handlers = list(root.handlers)
    old_level = root.level
    old_configured = log_mod._CONFIGURED
    old_format = log_mod.LOG_FORMAT
    old_level_setting = log_mod.LOG_LEVEL
    try:
        root.handlers.clear()
        log_mod._CONFIGURED = False
        log_mod.LOG_FORMAT = "console"
        log_mod.LOG_LEVEL = "INFO"

        log_mod.configure_logs()
        log_mod.configure_logs()

        assert len(root.handlers) == 1
    finally:
        root.handlers.clear()
        root.handlers.extend(old_handlers)
        root.setLevel(old_level)
        log_mod._CONFIGURED = old_configured
        log_mod.LOG_FORMAT = old_format
        log_mod.LOG_LEVEL = old_level_setting
