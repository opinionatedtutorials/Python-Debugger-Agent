"""Code execution and error capture for debuggeragent."""

import shlex
import subprocess
import traceback
from dataclasses import dataclass
from pathlib import Path


@dataclass
class RunResult:
    """Result of code execution."""
    success: bool
    stdout: str
    stderr: str
    returncode: int
    traceback: str | None = None
    error_type: str | None = None
    error_message: str | None = None


class CodeRunner:
    """Executes Python code and captures errors."""

    def __init__(self, timeout: int = 30, command: str = "python"):
        self.timeout = timeout
        self.command = command

    def run_file(self, file_path: Path, args: list[str] | None = None) -> RunResult:
        """Run a Python file and capture output."""
        cmd = [self.command, str(file_path)]
        if args:
            cmd.extend(args)

        return self._run_command(cmd, cwd=file_path.parent)

    def run_code(self, code: str, cwd: Path | None = None) -> RunResult:
        """Run a code string and capture output."""
        cmd = [self.command, "-c", code]
        return self._run_command(cmd, cwd=cwd or Path.cwd())

    def run_module(self, module: str, cwd: Path | None = None, args: list[str] | None = None) -> RunResult:
        """Run a Python module (e.g., pytest)."""
        cmd = [self.command, "-m", module]
        if args:
            cmd.extend(args)
        return self._run_command(cmd, cwd=cwd or Path.cwd())

    def run_command(self, command: str, cwd: Path | None = None) -> RunResult:
        """Run a shell command."""
        cmd = shlex.split(command)
        return self._run_command(cmd, cwd=cwd or Path.cwd())

    def _run_command(self, cmd: list[str], cwd: Path) -> RunResult:
        """Execute command and capture all output."""
        try:
            result = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )

            stdout = result.stdout
            stderr = result.stderr
            returncode = result.returncode

            # Extract traceback and error info from stderr
            traceback_str = None
            error_type = None
            error_message = None

            if returncode != 0:
                traceback_str = stderr
                # Try to parse the error type and message
                error_type, error_message = self._parse_error(stderr)

            return RunResult(
                success=returncode == 0,
                stdout=stdout,
                stderr=stderr,
                returncode=returncode,
                traceback=traceback_str,
                error_type=error_type,
                error_message=error_message,
            )

        except subprocess.TimeoutExpired:
            return RunResult(
                success=False,
                stdout="",
                stderr=f"Execution timed out after {self.timeout} seconds",
                returncode=-1,
                traceback=f"TimeoutError: Execution timed out after {self.timeout} seconds",
                error_type="TimeoutError",
                error_message=f"Execution timed out after {self.timeout} seconds",
            )
        except Exception as e:
            return RunResult(
                success=False,
                stdout="",
                stderr=str(e),
                returncode=-1,
                traceback=traceback.format_exc(),
                error_type=type(e).__name__,
                error_message=str(e),
            )

    def _parse_error(self, stderr: str) -> tuple[str | None, str | None]:
        """Parse error type and message from stderr."""
        lines = stderr.strip().split('\n')
        if not lines:
            return None, None

        # Look for the last line that looks like an exception
        for line in reversed(lines):
            line = line.strip()
            if ':' in line and not line.startswith(' '):
                # Might be "ErrorType: message"
                parts = line.split(':', 1)
                if len(parts) == 2:
                    error_type = parts[0].strip()
                    error_message = parts[1].strip()
                    # Validate it looks like an exception type
                    if error_type[0].isupper() and ' ' not in error_type:
                        return error_type, error_message

        # Fallback: return last non-empty line
        for line in reversed(lines):
            if line.strip():
                return "Error", line.strip()

        return None, None


def create_runner(config: dict | None = None) -> CodeRunner:
    """Factory function to create a CodeRunner from config."""
    if config is None:
        config = {}
    return CodeRunner(
        timeout=config.get("timeout", 30),
        command=config.get("command", "python"),
    )
