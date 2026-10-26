"""CLI entry point for debuggeragent."""

import asyncio
from pathlib import Path

import click
from rich.console import Console

from debuggeragent import debug_file_cli
from debuggeragent.utils.config import Config, load_config, save_config

console = Console()


@click.group(invoke_without_command=True)
@click.version_option(version="0.1.0")
@click.option('--file', '-f', type=click.Path(exists=True, path_type=Path), help='Python file to debug')
@click.option('--provider', '-p', type=click.Choice(['ollama', 'openai', 'anthropic']), help='LLM provider')
@click.option('--model', '-m', help='Model name')
@click.option('--interactive/--no-interactive', default=True, help='Ask before applying fixes')
@click.option('--max-iterations', '-i', type=int, default=5, help='Maximum fix iterations')
@click.option('--config', '-c', type=click.Path(path_type=Path), help='Config file path')
@click.pass_context
def main(
    ctx: click.Context,
    file: Path | None,
    provider: str | None,
    model: str | None,
    interactive: bool,
    max_iterations: int,
    config: Path | None,
):
    """DebuggerAgent - Python debugger with LLM-powered fixes.

    Examples:
        debug file.py                    # Debug with default settings (Ollama)
        debug file.py -p openai -m gpt-4o  # Use OpenAI GPT-4o
        debug file.py --no-interactive   # Auto-apply fixes
    """
    if ctx.invoked_subcommand is None:
        if file is None:
            console.print("[red]Error:[/red] No file specified. Use [bold]debug file.py[/bold] or [bold]debug --file file.py[/bold]")
            ctx.exit(1)

        # Load config
        cfg = load_config(config)

        # Run debug
        asyncio.run(run_debug(file, cfg, provider, model, interactive, max_iterations))


async def run_debug(
    file: Path,
    config: Config,
    provider: str | None,
    model: str | None,
    interactive: bool,
    max_iterations: int,
):
    """Run the debug process."""
    try:
        session = await debug_file_cli(
            file_path=file,
            config=config,
            provider=provider,
            model=model,
            interactive=interactive,
            max_iterations=max_iterations,
        )

        if session.get_latest_error() is None:
            console.print("\n[green]✅ Debugging successful![/green]")
        else:
            console.print("\n[yellow]⚠️  Debugging incomplete - max iterations reached or fix rejected[/yellow]")

    except KeyboardInterrupt:
        console.print("\n[red]Interrupted by user[/red]")
    except Exception as e:
        console.print(f"\n[red]Error:[/red] {e}")
        import traceback
        console.print(traceback.format_exc())


@main.command()
@click.option('--global/--local', 'global_flag', default=False, help='Save to global config (~/.config/debuggeragent/config.toml)')
@click.pass_context
def config(ctx: click.Context, global_flag: bool):
    """Generate a default configuration file."""
    config = Config()

    if global_flag:
        path = Path.home() / ".config" / "debuggeragent" / "config.toml"
    else:
        path = Path.cwd() / ".debuggeragent.toml"

    save_config(config, path)
    console.print(f"[green]Created config at {path}[/green]")
    console.print("\nEdit this file to customize:")
    console.print("  - LLM provider and model")
    console.print("  - Runner timeout and command")
    console.print("  - Documentation sources")
    console.print("  - Fix behavior")


@main.command()
@click.pass_context
def providers(ctx: click.Context):
    """List available LLM providers."""
    config = load_config()
    from debuggeragent.llm import get_available_providers

    available = get_available_providers(config)

    console.print("[bold]Available providers:[/bold]")
    for p in ['ollama', 'openai', 'anthropic']:
        status = "[green]✓[/green]" if p in available else "[red]✗[/red]"
        console.print(f"  {status} {p}")

    if not available:
        console.print("\n[yellow]No providers configured. Set up:[/yellow]")
        console.print("  - Ollama: Run 'ollama serve' and pull a model")
        console.print("  - OpenAI: Set OPENAI_API_KEY")
        console.print("  - Anthropic: Set ANTHROPIC_API_KEY")


if __name__ == "__main__":
    main()
