# ide/plugins/Codeintelligence/SymbolIndexer.py

"""
SymbolIndexer - Parse files and extract symbols
Uses AST for Python, OutlineParser for other languages
"""

import ast
import re
from pathlib import Path
from typing import List, Optional
from ide.core.OutlineParser import OutlineParser

from .SymbolInfo import SymbolInfo

CONSTANT_RE = re.compile(r'^[A-Z][A-Z0-9_]*$')


class SymbolIndexer:
    """
    Indexes code symbols from files
    Uses AST for detailed Python parsing, OutlineParser for other languages
    """

    def __init__(self):
        self.parsers = {
            '.py':  self.parse_python_ast,
            '.php': self.parse_with_outline_parser,
            '.go':  self.parse_with_outline_parser,
        }

    def index_file(self, file_path: str) -> Optional[List[SymbolInfo]]:
        """
        Parse a file and return all symbols

        Returns:
            List of SymbolInfo, [] for unsupported/empty files, or None when the
            file could not be parsed (e.g. a syntax error while mid-edit). Callers
            should keep the previously indexed symbols when None is returned.
        """
        parser = self.parsers.get(Path(file_path).suffix.lower())
        if parser is None:
            return []
        try:
            return parser(file_path)
        except Exception as e:
            print(f"[SymbolIndexer] Error indexing {file_path}: {e}")
            return None

    # ------------------------------------------------------------------
    # Python
    # ------------------------------------------------------------------

    def parse_python_ast(self, file_path: str) -> Optional[List[SymbolInfo]]:
        """
        Parse Python using AST.

        Extracts classes (incl. nested), functions, methods (sync + async) and
        module-level UPPER_CASE constants. Each symbol is reported exactly once.
        The column points at the symbol *name*, not at the `def`/`class` keyword.
        Returns None on a syntax error.
        """
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            tree = ast.parse(content)
        except SyntaxError as e:
            print(f"[SymbolIndexer] Syntax error in {file_path}: {e}")
            return None

        symbols: List[SymbolInfo] = []
        self._collect_python(tree.body, symbols, file_path, content.splitlines(),
                             parent=None, in_class=False)
        return sorted(symbols, key=lambda s: (s.line, s.column))

    def _collect_python(self, body, symbols, file_path, lines, parent, in_class):
        for node in body:
            if isinstance(node, ast.ClassDef):
                symbols.append(SymbolInfo(
                    name=node.name,
                    symbol_type='class',
                    file_path=file_path,
                    line=node.lineno,
                    column=self._name_column(lines, node, node.name),
                    parent=parent,
                    bases=[self._get_name(b) for b in node.bases],
                    decorators=[self._get_name(d) for d in node.decorator_list],
                    docstring=ast.get_docstring(node),
                ))
                self._collect_python(node.body, symbols, file_path, lines,
                                     parent=node.name, in_class=True)

            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                symbols.append(SymbolInfo(
                    name=node.name,
                    symbol_type='method' if in_class else 'function',
                    file_path=file_path,
                    line=node.lineno,
                    column=self._name_column(lines, node, node.name),
                    parent=parent if in_class else None,
                    parameters=self._get_parameters(node.args),
                    decorators=[self._get_name(d) for d in node.decorator_list],
                    docstring=ast.get_docstring(node),
                ))
                # Nested functions are deliberately not indexed

            elif isinstance(node, (ast.Assign, ast.AnnAssign)) and not in_class:
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for target in targets:
                    if isinstance(target, ast.Name) and CONSTANT_RE.match(target.id):
                        symbols.append(SymbolInfo(
                            name=target.id,
                            symbol_type='constant',
                            file_path=file_path,
                            line=target.lineno,
                            column=target.col_offset,
                        ))

            elif isinstance(node, (ast.If, ast.Try, ast.With, ast.For, ast.While)):
                # Definitions guarded by `if TYPE_CHECKING:`, `try/except ImportError:` etc.
                for attr in ('body', 'orelse', 'finalbody'):
                    self._collect_python(getattr(node, attr, []) or [], symbols,
                                         file_path, lines, parent, in_class)
                for handler in getattr(node, 'handlers', []) or []:
                    self._collect_python(handler.body, symbols, file_path, lines,
                                         parent, in_class)

    @staticmethod
    def _name_column(lines, node, name) -> int:
        """Column of the symbol name (node.col_offset points at 'def'/'class')."""
        idx = node.lineno - 1
        if 0 <= idx < len(lines):
            col = lines[idx].find(name, node.col_offset)
            if col >= 0:
                return col
        return node.col_offset

    # ------------------------------------------------------------------
    # Other languages
    # ------------------------------------------------------------------

    def parse_with_outline_parser(self, file_path: str) -> List[SymbolInfo]:
        """Use the existing OutlineParser for non-Python files"""
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()

        outline_symbols = OutlineParser.parse(file_path, content)

        symbols = []
        for sym in outline_symbols:
            symbols.append(SymbolInfo(
                name=sym.name,
                symbol_type=sym.type,
                file_path=file_path,
                line=sym.line,
                column=0,  # OutlineParser doesn't provide column; navigation finds the name
                parent=sym.parent.name if sym.parent else None,
                children=[c.name for c in sym.children]
            ))
            for child in sym.children:
                symbols.append(SymbolInfo(
                    name=child.name,
                    symbol_type=child.type,
                    file_path=file_path,
                    line=child.line,
                    column=0,
                    parent=sym.name
                ))
        return symbols

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_name(self, node) -> str:
        """Extract name from AST node"""
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return f"{self._get_name(node.value)}.{node.attr}"
        if isinstance(node, ast.Call):
            return self._get_name(node.func)
        if hasattr(node, 'id'):
            return node.id
        return str(node)

    def _get_parameters(self, args: ast.arguments) -> List[str]:
        """Extract parameter names (positional-only, regular, *args, kw-only, **kwargs)"""
        params = [a.arg for a in getattr(args, 'posonlyargs', [])]
        params += [a.arg for a in args.args]
        if args.vararg:
            params.append(f"*{args.vararg.arg}")
        params += [a.arg for a in args.kwonlyargs]
        if args.kwarg:
            params.append(f"**{args.kwarg.arg}")
        return params