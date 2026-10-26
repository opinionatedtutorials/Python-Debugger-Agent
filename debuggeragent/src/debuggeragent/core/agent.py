"""Main debugger agent orchestrating the debug loop."""

from pathlib import Path

from debuggeragent.core.fixer import apply_fix_interactively
from debuggeragent.core.runner import CodeRunner, RunResult, create_runner
from debuggeragent.core.session import DebugSession
from debuggeragent.docs import DocsRegistry, create_docs_registry
from debuggeragent.llm import BaseLLMProvider, create_provider
from debuggeragent.utils.config import Config, load_config
from debuggeragent.utils.diff import generate_diff

# System prompt for error analysis
ERROR_ANALYSIS_PROMPT = """You are an expert Python debugger. Analyze the error and provide a fix.

Given:
1. The code that failed
2. The error traceback
3. Relevant documentation (if available)

Your task:
1. Explain the root cause of the error
2. Provide a corrected version of the code

Format your response as:
```
# Analysis
<explanation of the error>

# Fixed Code
```python
<corrected code>
```
```"""


FIX_GENERATION_PROMPT = """You are an expert Python developer. Fix the code based on the error.

The error has been analyzed. Now generate a clean, minimal fix.

Guidelines:
- Make the minimal change necessary to fix the error
- Don't add unrelated code or refactor unnecessarily
- Preserve the original code style and structure
- If the fix requires imports, add them

Format your response as a unified diff or as the complete corrected file.
"""


class DebuggerAgent:
    """Main debugger agent that orchestrates the debug-fix loop."""

    def __init__(
        self,
        config: Config | None = None,
        llm_provider: BaseLLMProvider | None = None,
        docs_registry: DocsRegistry | None = None,
        runner: CodeRunner | None = None,
    ):
        self.config = config or load_config()
        self.llm = llm_provider or create_provider(self.config)
        self.docs = docs_registry
        self.runner = runner or create_runner(self.config.runner.model_dump())

    async def debug_file(
        self,
        file_path: Path,
        max_iterations: int | None = None,
        interactive: bool = True,
    ) -> DebugSession:
        """Debug a single file until it runs successfully or max iterations reached."""
        session = DebugSession(
            file_path=file_path,
            max_iterations=max_iterations or self.config.fixer.max_iterations,
        )

        # Read original file
        original_content = file_path.read_text(encoding='utf-8')
        current_content = original_content

        print(f"🔍 Debugging: {file_path}")

        # Run at least once
        first_run = True
        while first_run or session.should_continue():
            first_run = False
            # Run the current code
            print(f"\n📝 Iteration {session.current_iteration + 1}/{session.max_iterations}")
            result = self.runner.run_code(current_content, cwd=file_path.parent)
            session.add_run(result)

            if result.success:
                print("✅ Code runs successfully!")
                break

            # Display error
            print(f"❌ Error: {result.error_type}: {result.error_message}")
            if result.traceback:
                print(f"   Traceback:\n{result.traceback}")

            # Get relevant documentation
            doc_context = await self._gather_docs(result, current_content)
            if doc_context:
                print("📚 Found relevant documentation")

            # Generate fix using LLM
            print("🤖 Analyzing error and generating fix...")
            fixed_content = await self._generate_fix(
                current_content, result, doc_context, session
            )

            if fixed_content is None or fixed_content == current_content:
                print("⚠️  No fix generated or fix is identical")
                break

            # Show diff and apply if interactive
            if interactive:
                applied, edited = await apply_fix_interactively(
                    current_content, fixed_content, file_path
                )
                if edited:
                    fixed_content = edited
            else:
                applied = True

            if applied:
                # Write the fix
                file_path.write_text(fixed_content, encoding='utf-8')
                current_content = fixed_content
                session.add_fix_attempt(
                    result.error_type or "Unknown",
                    result.error_message or "Unknown error",
                    generate_diff(original_content, fixed_content, file_path),
                    applied=True,
                )
                print("✅ Fix applied")
            else:
                session.add_fix_attempt(
                    result.error_type or "Unknown",
                    result.error_message or "Unknown error",
                    generate_diff(original_content, fixed_content, file_path),
                    applied=False,
                )
                print("⏭️  Fix rejected")
                break

        print(f"\n🏁 Debugging complete. Iterations: {session.current_iteration}")
        return session

    async def _gather_docs(self, result: RunResult, code: str) -> str:
        """Gather relevant documentation for the error."""
        if not self.docs:
            return ""

        doc_parts = []
        error_type = result.error_type or ""

        # Search for error-related docs
        for query in [error_type, result.error_message or ""]:
            if not query:
                continue
            results = self.docs.search(query, limit=3)
            for symbol, snippet, provider in results:
                doc_parts.append(f"[{provider}] {symbol}: {snippet}")

        return "\n".join(doc_parts) if doc_parts else ""

    async def _generate_fix(
        self,
        code: str,
        result: RunResult,
        doc_context: str,
        session: DebugSession,
    ) -> str | None:
        """Generate a fix using the LLM."""
        # Build context
        context = session.get_context_summary()

        prompt = f"""{ERROR_ANALYSIS_PROMPT}

# Context
{context}

# Current Code
```python
{code}
```

# Error
Type: {result.error_type}
Message: {result.error_message}
Traceback:
{result.traceback}

# Documentation Context
{doc_context or 'None available'}
"""

        try:
            response = await self.llm.complete(
                prompt=prompt,
                system_prompt="You are an expert Python debugger. Provide minimal, correct fixes.",
                model=self.config.llm.model,
                temperature=0.1,
            )

            # Extract fixed code from response
            fixed_code = self._extract_fixed_code(response.content, code)
            return fixed_code

        except Exception as e:
            print(f"⚠️  LLM error: {e}")
            return None

    def _extract_fixed_code(self, response: str, original: str) -> str | None:
        """Extract fixed code from LLM response."""
        import re

        # Try to find code block with fixed code
        code_blocks = re.findall(r'```(?:python)?\n(.*?)\n```', response, re.DOTALL)

        if code_blocks:
            # Usually the last code block is the fixed version
            return code_blocks[-1].strip()

        # If no code blocks, maybe the whole response is the fixed code
        if 'def ' in response or 'import ' in response or 'class ' in response:
            return response.strip()

        return None


async def debug_file_cli(
    file_path: Path,
    config: Config | None = None,
    provider: str | None = None,
    model: str | None = None,
    interactive: bool = True,
    max_iterations: int | None = None,
) -> DebugSession:
    """CLI entry point for debugging a file."""
    config = config or load_config()

    # Override provider/model if specified
    if provider:
        config.llm.provider = provider
    if model:
        config.llm.model = model

    llm = create_provider(config, provider, model)
    docs = create_docs_registry(config.docs.model_dump()) if config.docs.sources else None
    runner = create_runner(config.runner.model_dump())

    agent = DebuggerAgent(
        config=config,
        llm_provider=llm,
        docs_registry=docs,
        runner=runner,
    )

    return await agent.debug_file(file_path, max_iterations, interactive)
