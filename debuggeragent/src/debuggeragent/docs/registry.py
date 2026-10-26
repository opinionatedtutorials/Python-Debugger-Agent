"""Unified documentation registry with multiple providers."""

import ast
import importlib.util
import inspect
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class DocProvider(ABC):
    """Abstract base for documentation providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name."""
        pass

    @abstractmethod
    def get_doc(self, symbol: str) -> str | None:
        """Get documentation for a symbol."""
        pass

    @abstractmethod
    def get_signature(self, symbol: str) -> str | None:
        """Get signature for a callable."""
        pass

    @abstractmethod
    def search(self, query: str, limit: int = 5) -> list[tuple[str, str]]:
        """Search for symbols matching query. Returns [(symbol, snippet)]."""
        pass


class PydocProvider(DocProvider):
    """Documentation via Python's built-in pydoc and inspect."""

    @property
    def name(self) -> str:
        return "pydoc"

    def get_doc(self, symbol: str) -> str | None:
        """Get docstring using pydoc."""
        try:
            obj = self._resolve_symbol(symbol)
            if obj is None:
                return None
            doc = inspect.getdoc(obj)
            return doc
        except Exception:
            return None

    def get_signature(self, symbol: str) -> str | None:
        """Get signature using inspect."""
        try:
            obj = self._resolve_symbol(symbol)
            if obj is None or not callable(obj):
                return None
            sig = inspect.signature(obj)
            return f"{symbol}{sig}"
        except Exception:
            return None

    def search(self, query: str, limit: int = 5) -> list[tuple[str, str]]:
        """Search is limited with pydoc - return empty."""
        return []

    def _resolve_symbol(self, symbol: str) -> Any:
        """Resolve a symbol string to an object."""
        # Handle module.symbol format
        parts = symbol.split('.')
        if len(parts) == 1:
            # Try builtins first
            if hasattr(__builtins__, symbol):
                return getattr(__builtins__, symbol)
            # Try imported modules
            for module in sys.modules.values():
                if hasattr(module, symbol):
                    return getattr(module, symbol)
            return None

        # Module path
        module_name = '.'.join(parts[:-1])
        attr_name = parts[-1]

        try:
            module = importlib.import_module(module_name)
            return getattr(module, attr_name, None)
        except ImportError:
            return None


class SourceProvider(DocProvider):
    """Documentation by parsing source files."""

    def __init__(self, cache_ttl: int = 3600):
        self.cache_ttl = cache_ttl
        self._cache: dict[str, tuple[float, Any]] = {}

    @property
    def name(self) -> str:
        return "source"

    def get_doc(self, symbol: str) -> str | None:
        """Extract docstring from source file."""
        try:
            file_path, node = self._find_symbol_node(symbol)
            if node and isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)):
                return ast.get_docstring(node)
        except Exception:
            pass
        return None

    def get_signature(self, symbol: str) -> str | None:
        """Extract signature from source."""
        try:
            file_path, node = self._find_symbol_node(symbol)
            if node and isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                args = []
                for arg in node.args.args:
                    arg_str = arg.arg
                    if arg.annotation:
                        arg_str += f": {ast.unparse(arg.annotation)}"
                    args.append(arg_str)
                if node.args.vararg:
                    args.append(f"*{node.args.vararg.arg}")
                if node.args.kwarg:
                    args.append(f"**{node.args.kwarg.arg}")
                return f"{symbol}({', '.join(args)})"
        except Exception:
            pass
        return None

    def search(self, query: str, limit: int = 5) -> list[tuple[str, str]]:
        """Search source files for matching symbols."""
        results = []
        query_lower = query.lower()

        # Search in site-packages and current directory
        search_paths = self._get_search_paths()

        for path in search_paths:
            if len(results) >= limit:
                break
            for py_file in path.rglob("*.py"):
                try:
                    content = py_file.read_text(encoding='utf-8')
                    if query_lower in content.lower():
                        # Parse and find relevant symbols
                        tree = ast.parse(content)
                        for node in ast.walk(tree):
                            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                                if query_lower in node.name.lower():
                                    doc = ast.get_docstring(node) or ""
                                    results.append((node.name, doc[:200]))
                                    if len(results) >= limit:
                                        break
                except Exception:
                    continue

        return results[:limit]

    def _get_search_paths(self) -> list[Path]:
        """Get paths to search for source files."""
        paths = [Path.cwd()]

        # Add site-packages
        for p in sys.path:
            path = Path(p)
            if path.exists() and (path / "site-packages").exists():
                paths.append(path / "site-packages")
            elif path.exists() and path.name in ("dist-packages", "site-packages"):
                paths.append(path)

        return paths

    def _find_symbol_node(self, symbol: str) -> tuple[Path | None, ast.AST | None]:
        """Find the AST node for a symbol."""
        parts = symbol.split('.')
        if len(parts) < 2:
            return None, None

        module_name = '.'.join(parts[:-1])
        attr_name = parts[-1]

        # Find module file
        try:
            spec = importlib.util.find_spec(module_name)
            if spec and spec.origin:
                file_path = Path(spec.origin)
                content = file_path.read_text(encoding='utf-8')
                tree = ast.parse(content)

                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                        if node.name == attr_name:
                            return file_path, node
        except Exception:
            pass

        return None, None


class StubsProvider(DocProvider):
    """Documentation from typeshed/stub files."""

    def __init__(self, cache_ttl: int = 3600):
        self.cache_ttl = cache_ttl
        self._stub_paths: list[Path] = []
        self._init_stub_paths()

    @property
    def name(self) -> str:
        return "stubs"

    def _init_stub_paths(self):
        """Find typeshed or stub directories."""
        # Check for typeshed (optional)
        try:
            import typeshed_client
            self._stub_paths = [Path(typeshed_client.get_typeshed_dir())]
        except Exception:
            pass

        # Check for .pyi files in site-packages
        for p in sys.path:
            path = Path(p)
            if path.exists():
                for pyi in path.rglob("*.pyi"):
                    self._stub_paths.append(pyi.parent)
                    break  # Just need one per package

    def get_doc(self, symbol: str) -> str | None:
        """Get docstring from stub file."""
        try:
            file_path, node = self._find_symbol_in_stubs(symbol)
            if node:
                return ast.get_docstring(node)
        except Exception:
            pass
        return None

    def get_signature(self, symbol: str) -> str | None:
        """Get signature from stub file."""
        try:
            file_path, node = self._find_symbol_in_stubs(symbol)
            if node and isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                return ast.unparse(node).split(':')[0] + ')'  # Simplified
        except Exception:
            pass
        return None

    def search(self, query: str, limit: int = 5) -> list[tuple[str, str]]:
        """Search stub files."""
        results = []
        query_lower = query.lower()

        for stub_dir in self._stub_paths:
            if len(results) >= limit:
                break
            for pyi_file in stub_dir.rglob("*.pyi"):
                try:
                    content = pyi_file.read_text(encoding='utf-8')
                    if query_lower in content.lower():
                        tree = ast.parse(content)
                        for node in ast.walk(tree):
                            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                                if query_lower in node.name.lower():
                                    doc = ast.get_docstring(node) or ""
                                    results.append((node.name, doc[:200]))
                                    if len(results) >= limit:
                                        break
                except Exception:
                    continue

        return results[:limit]

    def _find_symbol_in_stubs(self, symbol: str) -> tuple[Path | None, ast.AST | None]:
        """Find symbol in stub files."""
        parts = symbol.split('.')
        if len(parts) < 2:
            return None, None

        module_name = '.'.join(parts[:-1])
        attr_name = parts[-1]

        for stub_dir in self._stub_paths:
            # Convert module name to path
            module_path = stub_dir / module_name.replace('.', '/')
            pyi_file = module_path.with_suffix('.pyi')
            if not pyi_file.exists():
                pyi_file = module_path / '__init__.pyi'

            if pyi_file.exists():
                try:
                    content = pyi_file.read_text(encoding='utf-8')
                    tree = ast.parse(content)
                    for node in ast.walk(tree):
                        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                            if node.name == attr_name:
                                return pyi_file, node
                except Exception:
                    continue

        return None, None


class DocsRegistry:
    """Unified registry combining multiple documentation providers."""

    def __init__(self, providers: list[DocProvider], cache_ttl: int = 3600):
        self.providers = providers
        self.cache_ttl = cache_ttl
        self._doc_cache: dict[str, tuple[str, str]] = {}  # symbol -> (provider, doc)
        self._sig_cache: dict[str, tuple[str, str]] = {}

    def get_doc(self, symbol: str) -> str | None:
        """Get documentation, trying providers in order."""
        # Check cache
        if symbol in self._doc_cache:
            return self._doc_cache[symbol][1]

        for provider in self.providers:
            doc = provider.get_doc(symbol)
            if doc:
                self._doc_cache[symbol] = (provider.name, doc)
                return doc
        return None

    def get_signature(self, symbol: str) -> str | None:
        """Get signature, trying providers in order."""
        if symbol in self._sig_cache:
            return self._sig_cache[symbol][1]

        for provider in self.providers:
            sig = provider.get_signature(symbol)
            if sig:
                self._sig_cache[symbol] = (provider.name, sig)
                return sig
        return None

    def search(self, query: str, limit: int = 5) -> list[tuple[str, str, str]]:
        """Search all providers. Returns [(symbol, snippet, provider)]."""
        results = []
        for provider in self.providers:
            provider_results = provider.search(query, limit)
            for symbol, snippet in provider_results:
                results.append((symbol, snippet, provider.name))
                if len(results) >= limit:
                    break
            if len(results) >= limit:
                break
        return results

    def clear_cache(self):
        """Clear internal caches."""
        self._doc_cache.clear()
        self._sig_cache.clear()


def create_docs_registry(config: dict) -> DocsRegistry:
    """Create a docs registry from configuration."""
    sources = config.get("sources", ["pydoc", "source", "stubs"])
    cache_ttl = config.get("cache_ttl", 3600)

    providers = []
    if "pydoc" in sources:
        providers.append(PydocProvider())
    if "source" in sources:
        providers.append(SourceProvider(cache_ttl))
    if "stubs" in sources:
        providers.append(StubsProvider(cache_ttl))

    return DocsRegistry(providers, cache_ttl)
