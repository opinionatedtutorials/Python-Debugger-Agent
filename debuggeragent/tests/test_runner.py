"""Tests for the code runner."""

import pytest
from debuggeragent.core.runner import CodeRunner, create_runner


def test_runner_success():
    """Test successful code execution."""
    runner = create_runner({"timeout": 5, "command": "python"})
    result = runner.run_code("print('hello')")
    assert result.success
    assert "hello" in result.stdout


def test_runner_error():
    """Test code execution with error."""
    runner = create_runner({"timeout": 5, "command": "python"})
    result = runner.run_code("print(1/0)")
    assert not result.success
    assert result.error_type == "ZeroDivisionError"


def test_runner_syntax_error():
    """Test code execution with syntax error."""
    runner = create_runner({"timeout": 5, "command": "python"})
    result = runner.run_code("print('hello'")
    assert not result.success
    assert result.error_type in ("SyntaxError", "Error")


def test_runner_timeout():
    """Test code execution timeout."""
    runner = create_runner({"timeout": 1, "command": "python"})
    result = runner.run_code("import time; time.sleep(5)")
    assert not result.success
    assert result.error_type == "TimeoutError"