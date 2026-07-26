import json
import logging

from app.logging_config import JSONFormatter


def test_json_formatter_includes_standard_and_extra_fields():
    formatter = JSONFormatter()
    record = logging.LogRecord(
        name="app.llm",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="llm_call",
        args=(),
        exc_info=None,
    )
    record.model = "gpt-4o-mini"
    record.prompt_tokens = 42

    output = json.loads(formatter.format(record))

    assert output["message"] == "llm_call"
    assert output["level"] == "INFO"
    assert output["logger"] == "app.llm"
    assert output["model"] == "gpt-4o-mini"
    assert output["prompt_tokens"] == 42
    assert "timestamp" in output


def test_json_formatter_serializes_exceptions():
    formatter = JSONFormatter()
    try:
        raise ValueError("boom")
    except ValueError:
        record = logging.LogRecord(
            name="app.test",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="failed",
            args=(),
            exc_info=True,
        )
        import sys

        record.exc_info = sys.exc_info()

    output = json.loads(formatter.format(record))

    assert "ValueError: boom" in output["exc_info"]
