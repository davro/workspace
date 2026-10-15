# ide/plugins/Codeintelligence/NavigationManager.py

"""
NavigationManager - Jump-to-definition, symbol resolution and cursor movement

Reads the *live* editor text (not the file on disk), ranks candidate definitions
using the current file's imports, and can fall back to module files for
`import a.b.C` style lines.
"""

import ast
import os
import re
from pathlib import Path
from typing import Optional, List, Dict, Tuple

from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QTextCursor, QColor, QCursor
from PyQt6.QtWidgets import QTextEdit, QMenu

from .SymbolInfo import SymbolInfo

IMPORT_LINE_RE = re.compile(r'^\s*(?:from\s+[\w.]+\s+import\b|import\s+[\w.]+)')
FROM_IMPORT_RE = re.compile(r'^\s*from\s+([\w.]+)\s+import\s+\(?\s*([\w\s,]+)')
DEFINITION_TYPES = ('class', 'function', 'interface', 'struct', 'trait', 'enum')
MODULE_EXTENSIONS = ('.py', '.php', '.go')


def _is_word_char(ch: str) -> bool:
    return ch.isalnum() or ch == '_'


class NavigationManager:
    """Manages code navigation"""

    def __init__(self, database, api):
        self.db = database
        self.api = api

    # ------------------------------------------------------------------
    # Cursor / text helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _same_path(a, b) -> bool:
        if not a or not b:
            return False
        return os.path.normpath(str(a)) == os.path.normpath(str(b))

    def _live_text(self, file_path: str) -> Optional[str]:
        """Text of the file as currently shown in an editor, else from disk."""
        try:
            editors = list(self.api.get_all_editors())
            current = self.api.get_current_editor()
            if current is not None:
                editors.append(current)
            for ed in editors:
                if self._same_path(getattr(ed, 'file_path', None), file_path) \
                        and hasattr(ed, 'toPlainText'):
                    return ed.toPlainText()
        except Exception:
            pass
        return self.api.get_file_content(file_path)

    @staticmethod
    def _word_bounds(text: str, col: int) -> Optional[Tuple[int, int]]:
        col = max(0, min(col, len(text)))
        start = col
        while start > 0 and _is_word_char(text[start - 1]):
            start -= 1
        end = col
        while end < len(text) and _is_word_char(text[end]):
            end += 1
        return (start, end) if end > start else None

    @staticmethod
    def _dotted_prefix(text: str, start: int, end: int) -> str:
        """`ide.core.managers.MenuManager` up to and including the word at start:end"""
        s = start
        while s > 0 and (_is_word_char(text[s - 1]) or text[s - 1] == '.'):
            s -= 1
        return text[s:end].strip('.')

    def get_cursor_context(self) -> Optional[dict]:
        """
        Describe what is under the cursor in the current editor.

        Keys: name, file_path, line (1-based), column (0-based, start of word),
              line_text, is_attribute, is_import, dotted
        """
        try:
            editor = self.api.get_current_editor()
            if not editor or not hasattr(editor, 'textCursor'):
                return None
            file_path = getattr(editor, 'file_path', None)
            if not file_path:
                return None

            cursor = editor.textCursor()
            doc = cursor.document()

            if cursor.hasSelection():
                sel_start = min(cursor.selectionStart(), cursor.selectionEnd())
                block = doc.findBlock(sel_start)
                col = sel_start - block.position()
                selected = cursor.selectedText().strip()
                text = block.text()
                if selected.isidentifier():
                    name, start = selected, text.find(selected, col)
                    start = col if start < 0 else start
                    end = start + len(name)
                else:
                    bounds = self._word_bounds(text, col)
                    if not bounds:
                        return None
                    start, end = bounds
                    name = text[start:end]
                line = block.blockNumber() + 1
            else:
                block = cursor.block()
                text = block.text()
                bounds = self._word_bounds(text, cursor.positionInBlock())
                if not bounds:
                    return None
                start, end = bounds
                name = text[start:end]
                line = block.blockNumber() + 1

            before = text[:start]
            return {
                'name': name,
                'file_path': file_path,
                'line': line,
                'column': start,
                'line_text': text,
                'is_attribute': before.endswith(('.', '->', '::')),
                'is_import': bool(IMPORT_LINE_RE.match(text)),
                'dotted': self._dotted_prefix(text, start, end),
            }
        except Exception as e:
            print(f"[NavigationManager] Error getting cursor context: {e}")
            return None

    # Legacy API ---------------------------------------------------------

    def get_symbol_at_cursor(self) -> Optional[tuple]:
        ctx = self.get_cursor_context()
        if not ctx:
            return None
        return (ctx['name'], ctx['file_path'], ctx['line'], ctx['column'])

    def get_symbol_at_position(self, file_path: str, line: int, column: int) -> Optional[str]:
        try:
            content = self._live_text(file_path)
            if not content:
                return None
            lines = content.split('\n')
            if line < 1 or line > len(lines):
                return None
            current_line = lines[line - 1]
            bounds = self._word_bounds(current_line, column)
            return current_line[bounds[0]:bounds[1]] if bounds else None
        except Exception as e:
            print(f"[NavigationManager] Error getting symbol at position: {e}")
            return None

    # ------------------------------------------------------------------
    # Definition lookup
    # ------------------------------------------------------------------

    def _imported_modules(self, file_path: str) -> Dict[str, str]:
        """Map imported name -> module for `from a.b import Name` in a Python file."""
        if not str(file_path).lower().endswith('.py'):
            return {}
        text = self._live_text(file_path) or ''
        result: Dict[str, str] = {}
        try:
            for node in ast.walk(ast.parse(text)):
                if isinstance(node, ast.ImportFrom) and node.module:
                    for alias in node.names:
                        result[alias.name] = node.module
        except SyntaxError:
            for line in text.splitlines():           # mid-edit: fall back to regex
                m = FROM_IMPORT_RE.match(line)
                if m:
                    for part in m.group(2).split(','):
                        name = part.strip().split(' as ')[0].strip()
                        if name:
                            result[name] = m.group(1)
        return result

    @staticmethod
    def _module_matches(file_path: str, dotted: str) -> bool:
        want = dotted.lstrip('.').replace('.', '/')
        if not want:
            return False
        p = Path(file_path).with_suffix('').as_posix()
        return p.endswith('/' + want) or p == want or p.endswith('/' + want + '/__init__')

    def _score(self, sym: SymbolInfo, context_file: str, imported: Optional[str],
               is_attribute: bool) -> int:
        score = 0
        if self._same_path(sym.file_path, context_file):
            score += 100
        if imported and self._module_matches(sym.file_path, imported):
            score += 200
        if Path(sym.file_path).parent == Path(context_file).parent:
            score += 20
        if is_attribute:
            score += 30 if sym.type == 'method' else 0
        else:
            if sym.type in DEFINITION_TYPES:
                score += 30
            elif sym.type == 'method':
                score -= 10
        return score

    def rank_definitions(self, symbol_name: str, context_file: str,
                         is_attribute: bool = False) -> List[Tuple[int, SymbolInfo]]:
        """All definitions of a name, best first, as (score, SymbolInfo)."""
        seen, unique = set(), []
        for sym in self.db.find_symbol(symbol_name):
            key = (os.path.normpath(sym.file_path), sym.line, sym.qualified_name)
            if key not in seen:
                seen.add(key)
                unique.append(sym)
        if not unique:
            return []
        imported = self._imported_modules(context_file).get(symbol_name)
        scored = [(self._score(s, context_file, imported, is_attribute), s) for s in unique]
        scored.sort(key=lambda t: (-t[0], t[1].file_path, t[1].line))
        return scored

    def find_definitions(self, symbol_name: str, context_file: str,
                         is_attribute: bool = False) -> List[SymbolInfo]:
        return [s for _, s in self.rank_definitions(symbol_name, context_file, is_attribute)]

    def find_definition(self, symbol_name: str, context_file: str) -> Optional[SymbolInfo]:
        defs = self.find_definitions(symbol_name, context_file)
        return defs[0] if defs else None

    def _resolve_ambiguous_symbol(self, matches: List[SymbolInfo], context_file: str) -> SymbolInfo:
        imported = None
        scored = sorted(matches, key=lambda s: -self._score(s, context_file, imported, False))
        return scored[0]

    # ------------------------------------------------------------------
    # Module (file) lookup for import lines
    # ------------------------------------------------------------------

    def find_module_files(self, dotted: str) -> List[str]:
        """Resolve a dotted module path / bare module name to files."""
        found: List[str] = []
        want = dotted.lstrip('.').replace('.', '/')
        if not want:
            return found

        roots: List[Path] = []
        try:
            for p in self.api.get_settings().get('active_projects', []) or []:
                roots.append(Path(p))
            ws = self.api.get_workspace_path()
            if ws:
                roots.append(Path(ws))
        except Exception:
            pass
        for root in roots:
            for ext in MODULE_EXTENSIONS:
                for candidate in (root / (want + ext), root / want / ('__init__' + ext)):
                    if candidate.is_file() and str(candidate) not in found:
                        found.append(str(candidate))

        for path in list(self.db.symbols_by_file.keys()):
            if path not in found and self._module_matches(path, dotted):
                found.append(path)
        return found

    # ------------------------------------------------------------------
    # Moving the cursor
    # ------------------------------------------------------------------

    def display_path(self, file_path: str) -> str:
        try:
            ws = self.api.get_workspace_path()
            if ws:
                return Path(file_path).relative_to(Path(ws)).as_posix()
        except Exception:
            pass
        return Path(file_path).as_posix()

    def jump_to_symbol(self, symbol: SymbolInfo):
        self.jump_to_location(symbol.file_path, symbol.line, symbol.column,
                              name=symbol.name)

    def jump_to_location(self, file_path: str, line: int = 1, column: int = 0,
                         length: int = 0, name: Optional[str] = None):
        """Open file_path (if needed) and place the cursor on line/column."""
        try:
            current = self.api.get_current_editor()
            if not (current and self._same_path(getattr(current, 'file_path', None), file_path)):
                self.api.open_file(file_path)
            self._move_when_ready(file_path, line, column, length, name, attempts=15)
        except Exception as e:
            print(f"[NavigationManager] Error jumping to {file_path}:{line}: {e}")

    def _move_when_ready(self, file_path, line, column, length, name, attempts):
        editor = self.api.get_current_editor()
        if editor is not None and self._same_path(getattr(editor, 'file_path', None), file_path):
            self._move_cursor(editor, line, column, length, name)
        elif attempts > 0:   # editor tab still opening - retry instead of a fixed delay
            QTimer.singleShot(80, lambda: self._move_when_ready(
                file_path, line, column, length, name, attempts - 1))

    def _move_to_symbol(self, editor, symbol: SymbolInfo):
        self._move_cursor(editor, symbol.line, symbol.column, 0, symbol.name)

    _move_cursor_to_symbol = _move_to_symbol  # legacy alias (signature differs, see above)

    def _move_cursor(self, editor, line: int, column: int, length: int, name: Optional[str]):
        """Position by document block (correct with word-wrap) and select the name."""
        try:
            block = editor.document().findBlockByNumber(max(0, line - 1))
            if not block.isValid():
                return
            text = block.text()
            col = max(0, min(column, len(text)))
            if name:
                if text[col:col + len(name)] != name:
                    idx = text.find(name)
                    if idx >= 0:
                        col = idx
                length = len(name)

            cursor = editor.textCursor()
            cursor.setPosition(block.position() + col)
            if length:
                cursor.setPosition(block.position() + col + length,
                                   QTextCursor.MoveMode.KeepAnchor)
            editor.setTextCursor(cursor)
            if hasattr(editor, 'centerCursor'):
                editor.centerCursor()
            else:
                editor.ensureCursorVisible()
            editor.setFocus()
            self._flash(editor, cursor)
        except Exception as e:
            print(f"[NavigationManager] Error moving cursor: {e}")

    def _flash(self, editor, cursor):
        """Briefly highlight without clobbering the editor's own extra selections."""
        try:
            previous = list(editor.extraSelections())
            sel = QTextEdit.ExtraSelection()
            sel.cursor = cursor
            sel.format.setBackground(QColor("#4A9EFF"))
            sel.format.setForeground(QColor("#FFFFFF"))
            editor.setExtraSelections(previous + [sel])

            def restore():
                try:
                    editor.setExtraSelections(previous)
                except RuntimeError:   # editor closed in the meantime
                    pass
            QTimer.singleShot(600, restore)
        except Exception as e:
            print(f"[NavigationManager] Error highlighting: {e}")

    # ------------------------------------------------------------------
    # Disambiguation menu
    # ------------------------------------------------------------------

    def choose_and_jump(self, symbols: List[SymbolInfo]):
        """Pop up a menu when several definitions are equally plausible."""
        menu = QMenu(self.api.ide)
        for sym in symbols[:25]:
            label = f"{sym.get_icon()} {sym.qualified_name}  —  " \
                    f"{self.display_path(sym.file_path)}:{sym.line}"
            action = menu.addAction(label)
            action.triggered.connect(lambda checked=False, s=sym: self.jump_to_symbol(s))
        menu.exec(QCursor.pos())

    def choose_file_and_open(self, files: List[str]):
        menu = QMenu(self.api.ide)
        for path in files[:25]:
            action = menu.addAction(f"📄 {self.display_path(path)}")
            action.triggered.connect(lambda checked=False, p=path: self.jump_to_location(p, 1, 0))
        menu.exec(QCursor.pos())