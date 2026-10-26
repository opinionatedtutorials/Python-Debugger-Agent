"""Diff generation and display utilities."""

import difflib
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.text import Text


def generate_diff(original: str, modified: str, file_path: Path | None = None) -> str:
    """Generate a unified diff between original and modified content."""
    orig_lines = original.splitlines(keepends=True)
    mod_lines = modified.splitlines(keepends=True)

    diff = difflib.unified_diff(
        orig_lines,
        mod_lines,
        fromfile=str(file_path) if file_path else "original",
        tofile=str(file_path) if file_path else "modified",
        lineterm="",
    )
    return "".join(diff)


def parse_llm_diff_response(response: str) -> tuple[str, str]:
    """Parse LLM response to extract original and modified code blocks.

    Expected format:
    ```python
    # original code
    ```

    ```python
    # modified code
    ```

    Or unified diff format.
    """
    import re

    # Try to find code blocks
    code_blocks = re.findall(r'```(?:python)?\n(.*?)\n```', response, re.DOTALL)

    if len(code_blocks) >= 2:
        return code_blocks[0].rstrip(), code_blocks[1].rstrip()

    # Try unified diff format
    if response.strip().startswith('---') or response.strip().startswith('@@'):
        # This is already a diff, we'd need the original to apply it
        # For now, return empty - caller should handle this case
        return "", response

    # Fallback: assume the response IS the modified code
    return "", response.strip()


def apply_diff(original: str, diff: str) -> tuple[str, bool]:
    """Apply a unified diff to original content. Returns (new_content, success)."""
    try:
        orig_lines = original.splitlines(keepends=True)
        # Parse unified diff
        diff_lines = diff.splitlines(keepends=True)

        # Simple apply - in production use `patch` library or similar
        # For now, we'll use a basic approach
        result = list(orig_lines)

        # This is a simplified implementation
        # A full implementation would properly parse the unified diff format
        return original, False

    except Exception:
        return original, False


def display_diff(original: str, modified: str, file_path: Path | None = None,
                 console: Console | None = None) -> None:
    """Display a colored diff using Rich."""
    if console is None:
        console = Console()

    diff = generate_diff(original, modified, file_path)

    if not diff.strip():
        console.print("[yellow]No changes[/yellow]")
        return

    # Colorize the diff
    lines = diff.splitlines(keepends=True)
    output = Text()

    for line in lines:
        if line.startswith('+++') or line.startswith('---'):
            output.append(line, style="bold cyan")
        elif line.startswith('@@'):
            output.append(line, style="bold magenta")
        elif line.startswith('+'):
            output.append(line, style="green")
        elif line.startswith('-'):
            output.append(line, style="red")
        else:
            output.append(line)

    console.print(Panel(output, title=f"Changes to {file_path or 'file'}", border_style="blue"))


def prompt_apply_diff(original: str, modified: str, file_path: Path,
                      console: Console | None = None) -> tuple[bool, str | None]:
    """Prompt user to apply, edit, or reject a diff.

    Returns:
        (should_apply, edited_content_or_None)
        - If user accepts: (True, None)
        - If user edits: (True, edited_content)
        - If user rejects: (False, None)
    """
    if console is None:
        console = Console()

    display_diff(original, modified, file_path, console)

    while True:
        console.print("\n[bold]Apply this fix?[/bold]")
        console.print("  [green]y[/green] - Yes, apply")
        console.print("  [red]n[/red] - No, reject")
        console.print("  [yellow]e[/yellow] - Edit in $EDITOR")
        console.print("  [red]a[/red] - Abort debugging")

        choice = console.input("Choice [y/n/e/a]: ").strip().lower()

        if choice == 'y':
            return True, None
        elif choice == 'n':
            return False, None
        elif choice == 'e':
            edited = edit_in_editor(modified, console)
            if edited is not None:
                return True, edited
        elif choice == 'a':
            raise KeyboardInterrupt("User aborted debugging")
        else:
            console.print("[red]Invalid choice. Please enter y, n, e, or a.[/red]")


def edit_in_editor(content: str, console: Console) -> str | None:
    """Open content in $EDITOR for editing."""
    import os
    import subprocess
    import tempfile

    editor = os.environ.get('EDITOR', 'vim')

    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(content)
        temp_path = f.name

    try:
        console.print(f"[dim]Opening {editor}...[/dim]")
        subprocess.run([editor, temp_path], check=True)

        with open(temp_path) as f:
            edited = f.read()

        return edited
    except subprocess.CalledProcessError:
        console.print("[red]Editor exited with error[/red]")
        return None
    except FileNotFoundError:
        console.print(f"[red]Editor '{editor}' not found[/red]")
        return None
    finally:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
