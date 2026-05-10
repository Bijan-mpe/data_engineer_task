"""Unit tests for src.core.logging — structlog setup and logger behaviour."""

from structlog.testing import capture_logs

from src.core.logging import get_logger, setup_logging


def test_get_logger_has_expected_interface():
    """Logger must expose all standard log-level methods."""
    logger = get_logger("test.interface")
    for method in ("debug", "info", "warning", "error", "critical"):
        assert callable(getattr(logger, method))


def test_get_logger_emits_structured_event():
    """Emitted events must include the event key and any extra keyword fields."""
    logger = get_logger("test.emit")
    with capture_logs() as events:
        logger.info("file.processed", filename="corporates_A_1.xlsm", rows=40)
    assert events[0]["event"] == "file.processed"
    assert events[0]["filename"] == "corporates_A_1.xlsm"
    assert events[0]["rows"] == 40


def test_bound_logger_preserves_context():
    """Bound context must be included in each emitted log event."""
    logger = get_logger("test.bind").bind(process="pipeline", filename="a.xlsm")
    with capture_logs() as events:
        logger.info("pipeline.file_started")
    assert events[0]["process"] == "pipeline"
    assert events[0]["filename"] == "a.xlsm"


def test_get_logger_records_correct_log_level():
    """The log_level field must match the method used to emit each event."""
    logger = get_logger("test.levels")
    with capture_logs() as events:
        logger.warning("a_warning")
        logger.error("an_error")
    assert events[0]["log_level"] == "warning"
    assert events[1]["log_level"] == "error"


def test_setup_logging_configures_for_all_standard_levels():
    """setup_logging must not raise for any standard level, including the no-arg default."""
    setup_logging()
    for level in ("DEBUG", "INFO", "WARNING", "ERROR"):
        setup_logging(level)
