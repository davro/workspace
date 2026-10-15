# ide/plugins/Codeintelligence/ReferenceTracker.py

"""
ReferenceTracker - Find all references to a symbol

Searches every indexed file plus every open editor. Open editors are searched
using their *live* text, so unsaved edits are included.
"""

import os
import re
from typing import Dict, List, Optional, Tuple

from .SymbolInfo import Reference

MAX_REFERENCES = 5000


class ReferenceTracker:
    """Tracks symbol references across the codebase (whole-word text matching)"""

    def __init__(self, database, api=None):
        self.db = database
        self.api = api

    # ------------------------------------------------------------------

    def _open_editor_texts(self) -> Dict[str, Tuple[str, str]]:
        """normalised path -> (path, live text) for every open editor."""
        live: Dict[str, Tuple[str, str]] = {}
        if not self.api:
            return live
        try:
            editors = list(self.api.get_all_editors())
            current = self.api.get_current_editor()
            if current is not None:
                editors.append(current)
            for ed in editors:
                fp = getattr(ed, 'file_path', None)
                if fp and hasattr(ed, 'toPlainText'):
                    live[os.path.normpath(str(fp))] = (str(fp), ed.toPlainText())
        except Exception as e:
            print(f"[ReferenceTracker] Could not read open editors: {e}")
        return live

    @staticmethod
    def _read(file_path: str) -> Optional[str]:
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                return f.read()
        except Exception:
            return None

    def find_all_references(self, symbol_name: str,
                           file_filter: List[str] = None) -> List[Reference]:
        """
        Find all references to a symbol.

        Args:
            symbol_name: Name to search for (whole word)
            file_filter: Optional list of files to restrict the search to

        Returns:
            Reference objects ordered by file then line. Each has a `kind`:
            'definition', 'reference', 'comment' or 'string'.
        """
        pattern = re.compile(r'(?<!\w)' + re.escape(symbol_name) + r'(?!\w)')
        live = self._open_editor_texts()

        candidates = list(file_filter) if file_filter else list(self.db.symbols_by_file.keys())
        if not file_filter:
            candidates += [path for path, _ in live.values()]

        seen, targets = set(), []
        for fp in candidates:
            key = os.path.normpath(fp)
            if key not in seen:
                seen.add(key)
                targets.append((fp, key))

        definition_lines = {(os.path.normpath(s.file_path), s.line)
                            for s in self.db.find_symbol(symbol_name)}

        references: List[Reference] = []
        for fp, key in sorted(targets, key=lambda t: t[1]):
            text = live[key][1] if key in live else self._read(fp)
            if not text or symbol_name not in text:
                continue
            references.extend(self._search_text(fp, key, text, pattern, definition_lines))
            if len(references) >= MAX_REFERENCES:
                print(f"[ReferenceTracker] Stopped at {MAX_REFERENCES} references")
                break
        return references

    def _search_text(self, file_path, key, text, pattern, definition_lines) -> List[Reference]:
        ext = os.path.splitext(file_path)[1].lower()
        refs = []
        for line_num, line in enumerate(text.splitlines(), 1):
            for match in pattern.finditer(line):
                if (key, line_num) in definition_lines:
                    kind = 'definition'
                else:
                    kind = self._classify(line, match.start(), ext)
                refs.append(Reference(file_path=file_path, line=line_num,
                                      column=match.start(), context=line.strip(),
                                      kind=kind))
        return refs

    @staticmethod
    def _classify(line: str, col: int, ext: str) -> str:
        """
        Single-line heuristic: is the match inside a comment or string literal?
        (Multi-line strings/docstrings and block comments are not tracked.)
        """
        quotes = '"\'`' if ext == '.go' else '"\''
        quote, i = None, 0
        while i < col:
            ch = line[i]
            if quote:
                if ch == '\\':
                    i += 2
                    continue
                if ch == quote:
                    quote = None
            elif ch in quotes:
                quote = ch
            elif ch == '#' and ext in ('.py', '.php'):
                return 'comment'
            elif ch == '/' and line.startswith('//', i) and ext != '.py':
                return 'comment'
            i += 1
        if quote:
            return 'string'
        if ext in ('.php', '.go') and line.lstrip().startswith(('*', '/*')):
            return 'comment'
        return 'reference'

    def count_references(self, symbol_name: str) -> int:
        return len(self.find_all_references(symbol_name))