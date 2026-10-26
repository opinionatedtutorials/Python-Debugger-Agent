# DebuggerAgent

A Python debugger agent that uses local LLMs (Ollama) or cloud APIs (OpenAI, Anthropic) to automatically find and fix bugs in your code.

## Features

- **CLI & Library**: Use as `debug file.py` or import in your own tools
- **Multiple LLM Providers**: Ollama (local), OpenAI, Anthropic
- **Local Documentation Access**: pydoc, source parsing, typeshed stubs
- **Interactive Fixes**: See diffs, approve/reject/edit before applying
- **Project & File Mode**: Debug single files or entire projects

## Installation

```bash
# From source (development)
cd debuggeragent
pip install -e .

# Or with optional dependencies
pip install -e ".[openai,anthropic]"
```

## Quick Start

```bash
# 1. Start Ollama (if using local models)
ollama serve
ollama pull llama3.1

# 2. Debug a file
debug my_buggy_script.py

# 3. Or with specific provider
debug my_buggy_script.py --provider openai --model gpt-4o
```

## Configuration

Create a config file at `~/.config/debuggeragent/config.toml` or `.debuggeragent.toml` in your project:

```toml
[runner]
timeout = 30
command = "python"

[llm]
provider = "ollama"
model = "llama3.1"
ollama_host = "http://localhost:11434"

[llm.openai]
api_key = "${OPENAI_API_KEY}"

[llm.anthropic]
api_key = "${ANTHROPIC_API_KEY}"

[docs]
sources = ["pydoc", "source", "stubs"]
cache_ttl = 3600

[fixer]
interactive = true
max_iterations = 5
```

Environment variables supported:
- `OPENAI_API_KEY` - OpenAI API key
- `ANTHROPIC_API_KEY` - Anthropic API key
- `DEBUGGERAGENT_PROVIDER` - Override provider
- `DEBUGGERAGENT_MODEL` - Override model
- `DEBUGGERAGENT_OLLAMA_HOST` - Override Ollama host

## Usage

### CLI

```bash
# Basic usage
debug file.py

# With options
debug file.py --provider anthropic --model claude-3-5-sonnet-20241022
debug file.py --no-interactive --max-iterations 10
debug --config myconfig.toml file.py

# Project mode (run tests)
debug --project . --command "pytest"

# Config management
debug config --global    # Create global config
debug config             # Create local config
debug providers          # List available providers
```

### Library

```python
from debuggeragent import DebuggerAgent, debug_file_cli
import asyncio

# Simple usage
async def main():
    session = await debug_file_cli(Path("buggy.py"))
    print(f"Success: {session.get_latest_error() is None}")

asyncio.run(main())

# Advanced usage
agent = DebuggerAgent()
session = await agent.debug_file(Path("buggy.py"), max_iterations=10)
```

## How It Works

1. **Run** - Executes your code and captures errors (stdout, stderr, traceback)
2. **Analyze** - LLM analyzes the error with context (code, traceback, docs)
3. **Document** - Queries local Python docs (pydoc, source, stubs) for relevant info
4. **Fix** - Generates a minimal fix for the specific error
5. **Apply** - Shows diff, asks for approval (interactive mode)
6. **Repeat** - Re-runs until success or max iterations

## Requirements

- Python 3.10+
- Ollama (for local models): `curl -fsSL https://ollama.com/install.sh | sh`
- Optional: OpenAI/Anthropic API keys for cloud providers

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Lint
ruff check .
mypy src/
```

## Architecture

```
debuggeragent/
├── src/debuggeragent/
│   ├── cli.py              # CLI entry point
│   ├── core/
│   │   ├── agent.py        # Main orchestration
│   │   ├── runner.py       # Code execution
│   │   ├── session.py      # Session state
│   │   └── fixer.py        # Fix application
│   ├── docs/
│   │   └── registry.py     # Multi-source docs
│   ├── llm/
│   │   ├── base.py         # Provider interface
│   │   ├── ollama.py       # Ollama provider
│   │   ├── openai.py       # OpenAI provider
│   │   ├── anthropic.py    # Anthropic provider
│   │   └── factory.py      # Provider factory
│   └── utils/
│       ├── config.py       # Configuration
│       └── diff.py         # Diff utilities
├── tests/
└── pyproject.toml
```

## License

GNU
