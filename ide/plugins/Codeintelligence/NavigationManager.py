# ide/plugins/Codeintelligence/NavigationManager.py

"""
NavigationManager - Handle jump-to-definition and symbol resolution
"""

from pathlib import Path
from typing import Optional, List
from PyQt6.QtGui import QTextCursor
from .SymbolInfo import SymbolInfo


class NavigationManager:
    """
    Manages code navigation
    Resolves symbols at cursor position and jumps to definitions
    """
    
    def __init__(self, database, api):
        self.db = database
        self.api = api
    
    def get_symbol_at_position(self, file_path: str, line: int, column: int) -> Optional[str]:
        """
        Get symbol name at cursor position
        
        Args:
            file_path: Current file
            line: Line number (1-based)
            column: Column number (0-based)
            
        Returns:
            Symbol name at cursor, or None
        """
        try:
            # Get the editor content
            content = self.api.get_file_content(file_path)
            if not content:
                return None
            
            lines = content.split('\n')
            if line < 1 or line > len(lines):
                return None
            
            current_line = lines[line - 1]
            
            # Extract word at column position
            # Find word boundaries (alphanumeric + underscore)
            start = column
            while start > 0 and (current_line[start-1].isalnum() or current_line[start-1] == '_'):
                start -= 1
            
            end = column
            while end < len(current_line) and (current_line[end].isalnum() or current_line[end] == '_'):
                end += 1
            
            if start == end:
                return None
            
            symbol_name = current_line[start:end]
            return symbol_name if symbol_name else None
        
        except Exception as e:
            print(f"[NavigationManager] Error getting symbol at position: {e}")
            return None
    
    def find_definition(self, symbol_name: str, context_file: str) -> Optional[SymbolInfo]:
        """
        Find definition of a symbol
        
        Args:
            symbol_name: Name of symbol to find
            context_file: File where symbol is referenced (for context)
            
        Returns:
            SymbolInfo of definition, or None if not found
        """
        # Try exact match first
        matches = self.db.find_symbol(symbol_name)
        
        if not matches:
            return None
        
        # If only one match, return it
        if len(matches) == 1:
            return matches[0]
        
        # Multiple matches - use heuristics to pick best one
        return self._resolve_ambiguous_symbol(matches, context_file)
    
    def _resolve_ambiguous_symbol(self, matches: List[SymbolInfo], context_file: str) -> SymbolInfo:
        """
        Resolve which symbol definition to use when there are multiple matches
        
        Strategy:
        1. Prefer same file
        2. Prefer same directory
        3. Prefer class definitions over functions
        4. Return first match as fallback
        """
        # 1. Prefer same file
        same_file = [m for m in matches if m.file_path == context_file]
        if same_file:
            # If multiple in same file, prefer classes
            classes = [m for m in same_file if m.type == 'class']
            return classes[0] if classes else same_file[0]
        
        # 2. Prefer same directory
        context_dir = Path(context_file).parent
        same_dir = [m for m in matches if Path(m.file_path).parent == context_dir]
        if same_dir:
            return same_dir[0]
        
        # 3. Prefer classes over functions
        classes = [m for m in matches if m.type == 'class']
        if classes:
            return classes[0]
        
        # 4. Fallback to first match
        return matches[0]
    
    def jump_to_symbol(self, symbol: SymbolInfo):
        """
        Navigate to symbol definition
        
        Args:
            symbol: SymbolInfo to jump to
        """
        try:
            # Open the file
            self.api.open_file(symbol.file_path)
            
            # Small delay to ensure editor is ready
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(100, lambda: self._move_cursor_to_symbol(symbol))
        
        except Exception as e:
            print(f"[NavigationManager] Error jumping to symbol: {e}")
    
    def _move_cursor_to_symbol(self, symbol: SymbolInfo):
        """Move cursor to symbol position"""
        try:
            # Get the editor
            editor = self.api.get_current_editor()
            if not editor or not hasattr(editor, 'textCursor'):
                return
            
            cursor = editor.textCursor()
            
            # Move to beginning of document
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            
            # Move down to target line
            if symbol.line > 1:
                cursor.movePosition(
                    QTextCursor.MoveOperation.Down,
                    QTextCursor.MoveMode.MoveAnchor,
                    symbol.line - 1
                )
            
            # Move right to column
            if symbol.column > 0:
                cursor.movePosition(
                    QTextCursor.MoveOperation.Right,
                    QTextCursor.MoveMode.MoveAnchor,
                    symbol.column
                )
            
            # Set cursor and ensure visible
            editor.setTextCursor(cursor)
            editor.ensureCursorVisible()
            
            # Optionally highlight the symbol briefly
            self._highlight_symbol(editor, symbol.name)
        
        except Exception as e:
            print(f"[NavigationManager] Error moving cursor: {e}")
    
    def _highlight_symbol(self, editor, symbol_name: str):
        """Briefly highlight a symbol (visual feedback)"""
        try:
            from PyQt6.QtWidgets import QTextEdit
            from PyQt6.QtGui import QTextCharFormat, QColor, QTextCursor
            from PyQt6.QtCore import QTimer
            
            cursor = editor.textCursor()
            
            # Select the symbol name
            cursor.movePosition(QTextCursor.MoveOperation.StartOfWord)
            cursor.movePosition(
                QTextCursor.MoveOperation.EndOfWord,
                QTextCursor.MoveMode.KeepAnchor
            )
            
            # Create highlight format
            selection = QTextEdit.ExtraSelection()
            selection.cursor = cursor
            selection.format.setBackground(QColor("#4A9EFF"))
            selection.format.setForeground(QColor("#FFFFFF"))
            
            # Apply highlight
            editor.setExtraSelections([selection])
            
            # Remove highlight after 500ms
            QTimer.singleShot(500, lambda: editor.setExtraSelections([]))
        
        except Exception as e:
            print(f"[NavigationManager] Error highlighting: {e}")
    
    def get_symbol_at_cursor(self) -> Optional[tuple]:
        """
        Get symbol at current cursor position
        
        Returns:
            Tuple of (symbol_name, file_path, line, column) or None
        """
        try:
            editor = self.api.get_current_editor()
            if not editor or not hasattr(editor, 'file_path') or not editor.file_path:
                return None
            
            cursor = editor.textCursor()
            line = cursor.blockNumber() + 1
            column = cursor.columnNumber()
            
            symbol_name = self.get_symbol_at_position(editor.file_path, line, column)
            
            if symbol_name:
                return (symbol_name, editor.file_path, line, column)
            
            return None
        
        except Exception as e:
            print(f"[NavigationManager] Error getting symbol at cursor: {e}")
            return None

