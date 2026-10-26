"""Debug session state management."""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from debuggeragent.core.runner import RunResult


@dataclass
class FixAttempt:
    """Record of a fix attempt."""
    iteration: int
    error_type: str
    error_message: str
    proposed_diff: str
    applied: bool
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class DocQuery:
    """Record of a documentation query."""
    query: str
    result: str
    source: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class DebugSession:
    """Manages state for a debugging session."""
    file_path: Path
    start_time: datetime = field(default_factory=datetime.now)
    runs: list[RunResult] = field(default_factory=list)
    fix_attempts: list[FixAttempt] = field(default_factory=list)
    doc_queries: list[DocQuery] = field(default_factory=list)
    current_iteration: int = 0
    max_iterations: int = 5

    def add_run(self, result: RunResult) -> None:
        """Add a run result to history."""
        self.runs.append(result)

    def add_fix_attempt(self, error_type: str, error_message: str,
                        proposed_diff: str, applied: bool) -> None:
        """Record a fix attempt."""
        self.current_iteration += 1
        attempt = FixAttempt(
            iteration=self.current_iteration,
            error_type=error_type,
            error_message=error_message,
            proposed_diff=proposed_diff,
            applied=applied,
        )
        self.fix_attempts.append(attempt)

    def add_doc_query(self, query: str, result: str, source: str) -> None:
        """Record a documentation query."""
        self.doc_queries.append(DocQuery(query=query, result=result, source=source))

    def get_latest_error(self) -> RunResult | None:
        """Get the most recent error run."""
        for run in reversed(self.runs):
            if not run.success:
                return run
        return None

    def get_context_summary(self) -> str:
        """Generate a summary of the session for LLM context."""
        parts = [
            f"Debugging session for: {self.file_path}",
            f"Started: {self.start_time.isoformat()}",
            f"Iterations: {self.current_iteration}/{self.max_iterations}",
            "",
        ]

        if self.runs:
            parts.append("Recent runs:")
            for i, run in enumerate(self.runs[-3:], 1):
                status = "✓" if run.success else "✗"
                parts.append(f"  {i}. {status} Exit code: {run.returncode}")
                if not run.success and run.error_type:
                    parts.append(f"     Error: {run.error_type}: {run.error_message}")

        if self.fix_attempts:
            parts.append("\nFix attempts:")
            for attempt in self.fix_attempts[-3:]:
                status = "Applied" if attempt.applied else "Rejected"
                parts.append(f"  Iter {attempt.iteration}: {attempt.error_type} - {status}")

        if self.doc_queries:
            parts.append("\nDocumentation consulted:")
            for query in self.doc_queries[-5:]:
                parts.append(f"  - {query.query} (via {query.source})")

        return "\n".join(parts)

    def should_continue(self) -> bool:
        """Check if debugging should continue."""
        if self.current_iteration >= self.max_iterations:
            return False
        latest = self.get_latest_error()
        return latest is not None and not latest.success
