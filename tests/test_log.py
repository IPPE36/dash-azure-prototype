import json
import logging
import sys

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
