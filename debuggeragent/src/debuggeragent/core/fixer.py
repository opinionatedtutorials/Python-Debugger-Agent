"""Interactive fix application utilities."""

from pathlib import Path

from rich.console import Console

from debuggeragent.utils.diff import (
    display_diff,
    prompt_apply_diff,
)


async def apply_fix_interactively(
    original: str,
    modified: str,
    file_path: Path,
    console: Console | None = None,
) -> tuple[bool, str | None]:
    """Apply a fix interactively with user confirmation.

    Returns:
        (applied, edited_content)
        - applied=True, edited_content=None: user accepted as-is
        - applied=True, edited_content=str: user edited and accepted
        - applied=False, edited_content=None: user rejected
    """
    if console is None:
        console = Console()

    # Show the diff
    display_diff(original, modified, file_path, console)

    # Prompt for action
    return prompt_apply_diff(original, modified, file_path, console)


def create_fixed_file(original: str, modified: str, backup: bool = True) -> Path:
    """Create a fixed version of a file, optionally backing up the original."""
    import tempfile

    # Create temp file with fixed content
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(modified)
        temp_path = Path(f.name)

    return temp_path


def apply_diff_to_file(file_path: Path, diff: str, backup: bool = True) -> bool:
    """Apply a unified diff to a file."""
    try:
        import subprocess
        result = subprocess.run(
            ['patch', '-p0', str(file_path)],
            input=diff.encode(),
            capture_output=True,
        )
        return result.returncode == 0
    except Exception:
        return False
