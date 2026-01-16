from pathlib import Path

from PyQt6.QtWidgets import QPlainTextEdit, QWidget, QTextEdit, QMessageBox
from PyQt6.QtGui import (
    QKeyEvent,
    QColor,
    QPainter,
    QTextFormat,
    QFont,
    QSyntaxHighlighter,
    QTextCharFormat,
    QFontMetricsF,
    QTextCursor
)
from PyQt6.QtCore import Qt, QRect, QSize

from ide.core.SyntaxHighlighter import PythonHighlighter, PhpHighlighter
from ide.core.SettingDescriptor import SettingsProvider, SettingDescriptor, SettingType
from ide.core.CodeFolding import CodeFoldingManager
from ide.core.FileMonitor import FileMonitor

"""
Main Code Editor Class
A custom QTextEdit widget with enhanced features for code editing.
"""
class CodeEditor(QPlainTextEdit, SettingsProvider):
    """
    Main Code Editor Class
    A custom QTextEdit widget with enhanced features for code editing.
    """
    
    # =============================================================================
    # Settings Descriptors - Define what settings CodeEditor uses
    # =============================================================================
    SETTINGS_DESCRIPTORS = [
        SettingDescriptor(
            key='editor_font_size',
            label='Editor Font Size',
            setting_type=SettingType.INTEGER,
            default=10,
            min_value=8,
            max_value=32,
            description='Font size for the code editor',
            section='Editor'
        ),
        SettingDescriptor(
            key='tab_width',
            label='Tab Width',
            setting_type=SettingType.INTEGER,
            default=4,
            min_value=2,
            max_value=8,
            suffix=' spaces',
            description='Number of spaces per tab character',
            section='Editor'
        ),
        SettingDescriptor(
            key='show_line_numbers',
            label='Show Line Numbers',
            setting_type=SettingType.BOOLEAN,
            default=True,
            description='Display line numbers in the editor gutter',
            section='Editor'
        ),
        SettingDescriptor(
            key='gutter_width',
            label='Gutter Width (padding)',
            setting_type=SettingType.INTEGER,
            default=10,
            min_value=0,
            max_value=50,
            suffix=' px',
            description='Padding between line numbers and text',
            section='Editor'
        ),

        # Column marker
        SettingDescriptor(
            key='show_column_marker',
            label='Show Column Marker',
            setting_type=SettingType.BOOLEAN,
            default=True,
            section='Editor'
        ),
        SettingDescriptor(
            key='column_marker_position',
            label='Column Marker Position',
            setting_type=SettingType.INTEGER,
            default=80,
            min_value=40,
            max_value=120,
            section='Editor'
        ),

        # Code Folding
        SettingDescriptor(
            key='enable_code_folding',
            label='Enable Code Folding',
            setting_type=SettingType.BOOLEAN,
            default=True,
            description='Enable code folding for functions, classes, and blocks',
            section='Editor'
        ),
    ]


    def __init__(self, file_path=None, font_size=10, tab_width=4,
                 show_line_numbers=True, gutter_width=10):
        """
        Initialize code editor
    
        Args:
            file_path: Path to file to load
            font_size: Font size in points
            tab_width: Tab width in spaces
            show_line_numbers: Show line numbers
            gutter_width: Gutter width (padding) in pixels between line numbers and text
        """
        super().__init__()
    
        # File monitoring (NEW!)
        self.file_monitor = None  # Will be set by workspace
        self.external_change_pending = False

        # Font and styling
        font = QFont("Monospace", font_size)
        font.setStyleHint(QFont.StyleHint.TypeWriter)
        self.setFont(font)
        self.setStyleSheet(
            "QPlainTextEdit { background-color: #2B2B2B; color: #A9B7C6; border: none; }"
        )
    
        # Tab settings
        self.setTabStopDistance(
            QFontMetricsF(self.font()).horizontalAdvance(' ') * tab_width
        )
    
        # State
        self.file_path         = None
        self.highlighter       = None
        self.show_line_numbers = show_line_numbers
        self.gutter_width      = gutter_width
        self.tab_width         = tab_width
    
        # Track extra selections separately to avoid conflicts
        self.current_line_selection = None
        self.find_replace_selections = []
    
        # Line number area
        self.line_number_area = LineNumberArea(self) if show_line_numbers else None
    
        # Column marker (NEW!)
        self.column_marker = ColumnMarker(self)
        self.column_marker.setGeometry(self.viewport().geometry())
        self.column_marker.show()
    
        # Connect signals
        if self.line_number_area:
            self.blockCountChanged.connect(self.update_line_number_area_width)
            self.updateRequest.connect(self.update_line_number_area)
    
        # Connections for line numbers and highlighting
        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.cursorPositionChanged.connect(self.highlight_current_line)
        self.update_line_number_area_width(0)
    
        # Notify parent IDE whenever the document modified state changes
        self.textChanged.connect(self.on_text_changed)

        # Code folding manager (NEW!)
        self.folding_manager = CodeFoldingManager(self)
        
        # Timer for debounced fold region updates
        from PyQt6.QtCore import QTimer
        self.fold_update_timer = QTimer()
        self.fold_update_timer.setSingleShot(True)
        self.fold_update_timer.timeout.connect(self._update_fold_regions)
        
        # Connect text changed to update folds (debounced)
        self.textChanged.connect(self._schedule_fold_update)


        # Load file if provided
        if file_path:
            self.load_file(file_path)
    
        # Connect text changed signal for plugins
        self.textChanged.connect(self._on_text_changed)


    def _on_text_changed(self):
        """Notify plugins about text change"""
        # This allows plugins to hook into typing
        pass

    # =============================================================================
    # Line Number Area
    # =============================================================================

    def update_line_number_area_width(self, _):
        """
        Update the viewport margins when line count changes.
        This is called automatically by Qt when blockCountChanged signal fires.
        """
        left_margin = self.line_number_area_width()
        self.setViewportMargins(left_margin, 0, 0, 0)
        
        # Also update the line number area geometry to match the new width
        if self.line_number_area:
            self.line_number_area.setGeometry(
                QRect(
                    self.contentsRect().left(),
                    self.contentsRect().top(),
                    left_margin,
                    self.contentsRect().height()
                )
            )

    def line_number_area_width(self):
        """
        Calculate the width needed for line numbers + gutter.
        This dynamically adjusts based on the number of lines.
        """
        if not self.show_line_numbers or not self.line_number_area:
            return self.gutter_width
    
        # Get the total number of lines
        max_line = max(1, self.blockCount())
        
        # Calculate how many digits we need (e.g., 5 digits for line 20180)
        digits = len(str(max_line))
        
        # Always reserve space for at least 2 digits to prevent shifting
        digits = max(2, digits)
        
        # Calculate total width needed:
        # 16px for fold markers + (digit width * number of digits) + 3px padding + gutter
        fold_marker_space = 16
        digit_space = self.fontMetrics().horizontalAdvance('9') * digits
        padding = 3
        
        total_width = fold_marker_space + digit_space + padding + self.gutter_width
        
        return total_width

    # def line_number_area_width(self):
        # """
        # Calculate the width needed for line numbers + gutter.
        # This dynamically adjusts based on the number of lines.
        # """
        # if not self.show_line_numbers or not self.line_number_area:
            # return self.gutter_width
    
        # # Get the total number of lines
        # max_line = max(1, self.blockCount())
        
        # # Calculate how many digits we need (e.g., 5 digits for line 20180)
        # digits = len(str(max_line))
        
        # # Calculate total width needed:
        # # 16px for fold markers + (digit width * number of digits) + 3px padding + gutter
        # fold_marker_space = 16
        # digit_space = self.fontMetrics().horizontalAdvance('9') * digits
        # padding = 3
        
        # total_width = fold_marker_space + digit_space + padding + self.gutter_width
        
        # return total_width

    # =============================================================================
    # Update line number area
    # =============================================================================
    
    def update_line_number_area(self, rect, dy):
        """Update the line number area when the editor scrolls or updates"""
        if not self.line_number_area:
            return
        
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(
                0, rect.y(), self.line_number_area.width(), rect.height()
            )
        
        if rect.contains(self.viewport().rect()):
            self.update_line_number_area_width(0)
        
        # Update column marker when scrolling
        if hasattr(self, 'column_marker'):
            self.column_marker.update()

    def set_gutter_width(self, width):
        """Set the gutter width and update display"""
        self.gutter_width = width
        self.update_line_number_area_width(0)
        if self.line_number_area:
            self.line_number_area.update()

    def set_show_line_numbers(self, show):
        """Toggle line numbers display"""
        self.show_line_numbers = show

        if show and not self.line_number_area:
            self.line_number_area = LineNumberArea(self)
            self.blockCountChanged.connect(self.update_line_number_area_width)
            self.updateRequest.connect(self.update_line_number_area)
            self.line_number_area.show()
        elif not show and self.line_number_area:
            self.line_number_area.hide()

        self.update_line_number_area_width(0)

    def set_font_size(self, size):
        """Set font size and update display"""
        font = self.font()
        font.setPointSize(size)
        self.setFont(font)

        tab_width = int(self.tabStopDistance() /
                       QFontMetricsF(font).horizontalAdvance(' '))
        self.setTabStopDistance(
            QFontMetricsF(font).horizontalAdvance(' ') * tab_width
        )

        self.update_line_number_area_width(0)
        if self.line_number_area:
            self.line_number_area.update()

    def set_tab_width(self, width):
        """Set tab width and update display"""
        self.setTabStopDistance(
            QFontMetricsF(self.font()).horizontalAdvance(' ') * width
        )

    def resizeEvent(self, event):
        """
        Handle resize events to update line number area and column marker.
        This ensures the line number area always has the correct width.
        """
        super().resizeEvent(event)
        
        # Update line number area
        if self.line_number_area:
            cr = self.contentsRect()
            # Use our calculated width method
            line_number_width = self.line_number_area_width()
            
            self.line_number_area.setGeometry(
                QRect(cr.left(), cr.top(), line_number_width, cr.height())
            )
        
        # Update column marker
        if hasattr(self, 'column_marker'):
            self.column_marker.setGeometry(self.viewport().geometry())
            self.column_marker.raise_()

    # =============================================================================
    # Methods to toggle column marker visibility
    # =============================================================================
    
    def set_show_column_marker(self, show):
        """
        Toggle column marker visibility.
        
        Args:
            show: Boolean to show/hide the marker
        """
        if hasattr(self, 'column_marker'):
            if show:
                self.column_marker.show()
            else:
                self.column_marker.hide()
    
    
    def set_column_marker_position(self, position):
        """
        Set the column marker position.
        
        Args:
            position: Column number (e.g., 80, 100, 120)
        """
        if hasattr(self, 'column_marker'):
            self.column_marker.update()  # Trigger repaint


    # =============================================================================
    # Line number area methods
    # =============================================================================

    def line_number_area_paint_event(self, event):
        """
        Paint line numbers and fold markers.
        Now with proper width calculation for any number of digits.
        """
        painter = QPainter(self.line_number_area)
        painter.fillRect(event.rect(), QColor("#313335"))
        
        block = self.firstVisibleBlock()
        
        while block.isValid():
            where_to_draw = self.blockBoundingGeometry(block).translated(self.contentOffset())
            
            if where_to_draw.top() > event.rect().bottom():
                break
            
            if block.isVisible():
                line_number = block.blockNumber() + 1
                
                # Draw line number
                painter.setPen(QColor("#606366"))
                
                # Calculate available width for text (total width - fold marker space - padding)
                available_width = self.line_number_area.width() - 16 - 3
                
                painter.drawText(
                    16,  # Start after fold markers (16px)
                    int(where_to_draw.top()),
                    available_width,  # Use all available space
                    self.fontMetrics().height(),
                    Qt.AlignmentFlag.AlignRight,
                    str(line_number)
                )
                
                # Draw fold marker
                if self._is_folding_enabled():
                    self.folding_manager.draw_fold_marker(
                        painter,
                        block.blockNumber(),
                        int(where_to_draw.top()),
                        self.fontMetrics().height()
                    )
            
            block = block.next()

    def highlight_current_line(self):
        """Highlight the current line - works with extra selections"""
        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()
            selection.format.setBackground(QColor("#2F3437"))
            selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            self.current_line_selection = selection
        else:
            self.current_line_selection = None

        self._update_extra_selections()

    def set_find_replace_selections(self, selections):
        """Set find/replace selections (called by FindReplaceWidget)"""
        self.find_replace_selections = selections
        self._update_extra_selections()

    def _update_extra_selections(self):
        """Update all extra selections (current line + find/replace)"""
        all_selections = []

        # Add find/replace selections first (so they're under current line)
        all_selections.extend(self.find_replace_selections)

        # Add current line selection on top
        if self.current_line_selection:
            all_selections.append(self.current_line_selection)

        self.setExtraSelections(all_selections)

    # =============================================================================
    # Modification tracking
    # =============================================================================
    def on_text_changed(self):
        """Notify the main window when the document's modified state changes"""
        # Find the WorkspaceIDE instance
        parent = self.parent()
        while parent is not None:
            if hasattr(parent, "on_editor_modified"):
                parent.on_editor_modified(self)
                break
            parent = parent.parent()

    # =============================================================================
    # File operations
    # =============================================================================
    def load_file(self, path: str) -> bool:
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
    
            # Prevent textChanged signals during load
            self.blockSignals(True)
            self.setPlainText(content)
            self.blockSignals(False)
    
            self.file_path = path
    
            # Python Apply syntax highlighting
            if str(path).lower().endswith(".py"):
                self.highlighter = PythonHighlighter(self.document())
    
            # PHP Apply syntax highlighting
            if str(path).lower().endswith(".php"):
                self.highlighter = PhpHighlighter(self.document())
    
            self.document().setModified(False)
    
            # **FIX: Force update line number area width after loading**
            self.update_line_number_area_width(0)
            if self.line_number_area:
                self.line_number_area.update()
    
            # Update fold regions for new file
            if self._is_folding_enabled():
                self.folding_manager.update_regions()
            
            # Start monitoring file for external changes
            if self.file_monitor:
                self.file_monitor.watch_file(path)
    
            return True
        except Exception as e:
            QMessageBox.critical(self, "Error loading file", str(e))
            return False

    # def load_file(self, path: str) -> bool:
        # try:
            # with open(path, "r", encoding="utf-8") as f:
                # content = f.read()

            # # Prevent textChanged signals during load
            # self.blockSignals(True)
            # self.setPlainText(content)
            # self.blockSignals(False)

            # self.file_path = path

            # # Python Apply syntax highlighting
            # if str(path).lower().endswith(".py"):
                # self.highlighter = PythonHighlighter(self.document())

            # # PHP Apply syntax highlighting
            # if str(path).lower().endswith(".php"):
                # self.highlighter = PhpHighlighter(self.document())

            # self.document().setModified(False)

            # # Update fold regions for new file (NEW!)
            # if self._is_folding_enabled():
                # self.folding_manager.update_regions()
            
            # # Start monitoring file for external changes (NEW!)
            # if self.file_monitor:
                # self.file_monitor.watch_file(path)

            # return True
        # except Exception as e:
            # QMessageBox.critical(self, "Error loading file", str(e))
            # return False

    def save_file(self) -> bool:
        if not self.file_path:
            return False

        try:
            # Notify monitor we're saving (NEW!)
            if self.file_monitor:
                self.file_monitor.mark_file_saving(self.file_path)
            
            with open(self.file_path, "w", encoding="utf-8") as f:
                f.write(self.toPlainText())

            self.document().setModified(False)
            self.external_change_pending = False  # Clear flag after save
            return True
        except Exception as e:
            QMessageBox.critical(self, "Error saving file", str(e))
            return False


    # =============================================================================
    # Feature: File Monitoring (handle external changes)
    # =============================================================================
    def set_file_monitor(self, monitor: FileMonitor):
        """
        Set the file monitor and connect signals.
        
        Args:
            monitor: FileMonitor instance from workspace
        """
        self.file_monitor = monitor
        
        # Connect signals
        if monitor:
            monitor.file_modified.connect(self._on_external_file_modified)
            monitor.file_deleted.connect(self._on_external_file_deleted)
    
    
    def _on_external_file_modified(self, file_path: str):
        """
        Handle external file modification.
        
        Args:
            file_path: Path to the modified file
        """
        # Only handle if this is our file
        if file_path != self.file_path:
            return
        
        # Don't prompt if we have unsaved changes - just mark it
        if self.document().isModified():
            self.external_change_pending = True
            return
        
        # Prompt user to reload
        self._prompt_reload_file()
    
    
    def _on_external_file_deleted(self, file_path: str):
        """
        Handle external file deletion.
        
        Args:
            file_path: Path to the deleted file
        """
        if file_path != self.file_path:
            return
        
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setWindowTitle("File Deleted")
        msg.setText(f"The file has been deleted externally:\n{Path(file_path).name}")
        msg.setInformativeText("Do you want to keep the editor open?")
        msg.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        msg.setDefaultButton(QMessageBox.StandardButton.Yes)
        
        result = msg.exec()
        
        if result == QMessageBox.StandardButton.No:
            # Close the editor
            self._close_editor()
    
    
    def _prompt_reload_file(self):
        """Prompt user to reload file after external modification"""
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Question)
        msg.setWindowTitle("File Changed")
        msg.setText(f"The file has been modified externally:\n{Path(self.file_path).name}")
        msg.setInformativeText("Do you want to reload it?")
        msg.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        msg.setDefaultButton(QMessageBox.StandardButton.Yes)
        
        result = msg.exec()
        
        if result == QMessageBox.StandardButton.Yes:
            self._reload_file()
        else:
            # User chose not to reload - mark as modified
            self.document().setModified(True)
    
    
    def _reload_file(self):
        """Reload file from disk"""
        if not self.file_path or not Path(self.file_path).exists():
            return
        
        # Save cursor position
        cursor = self.textCursor()
        position = cursor.position()
        
        # Reload file
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            self.blockSignals(True)
            self.setPlainText(content)
            self.blockSignals(False)
            
            # Restore cursor position (or close to it)
            cursor.setPosition(min(position, len(content)))
            self.setTextCursor(cursor)
            
            self.document().setModified(False)
            self.external_change_pending = False
            
            # Update fold regions
            if self._is_folding_enabled():
                self.folding_manager.update_regions()
            
        except Exception as e:
            QMessageBox.critical(self, "Error reloading file", str(e))
    
    
    def _close_editor(self):
        """Close this editor (notify workspace)"""
        # Find the workspace and ask it to close this editor
        parent = self.parent()
        while parent is not None:
            if hasattr(parent, "close_editor"):
                parent.close_editor(self)
                break
            parent = parent.parent()
    

    # Add check for pending changes when user tries to save:
    def check_external_changes_before_save(self) -> bool:
        """
        Check if file was modified externally before saving.
        
        Returns:
            True if safe to save, False if user cancelled
        """
        if not self.external_change_pending:
            return True
        
        if not self.file_path or not Path(self.file_path).exists():
            return True
        
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setWindowTitle("External Changes")
        msg.setText(f"The file has been modified externally:\n{Path(self.file_path).name}")
        msg.setInformativeText("Your changes may overwrite external changes. Continue saving?")
        msg.setStandardButtons(
            QMessageBox.StandardButton.Save | 
            QMessageBox.StandardButton.Cancel |
            QMessageBox.StandardButton.Open
        )
        msg.button(QMessageBox.StandardButton.Open).setText("View External Changes")
        msg.setDefaultButton(QMessageBox.StandardButton.Cancel)
        
        result = msg.exec()
        
        if result == QMessageBox.StandardButton.Save:
            self.external_change_pending = False
            return True
        elif result == QMessageBox.StandardButton.Open:
            # Show diff or reload to view
            self._show_external_changes()
            return False
        else:
            return False
    
    
    def _show_external_changes(self):
        """Show what changed externally (simple version)"""
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setWindowTitle("External Changes")
        msg.setText("To view external changes, you can:")
        msg.setInformativeText(
            "1. Save your changes to a different file\n"
            "2. Reload the file to see external changes\n"
            "3. Compare using an external diff tool"
        )
        msg.exec()

    # =============================================================================
    # Feature: Comment Toggle (Ctrl+/) - FIXED VERSION
    # =============================================================================
    def toggle_comment(self):
        cursor = self.textCursor()
        comment_prefix = self.get_comment_prefix()

        # Determine range
        if cursor.hasSelection():
            start = cursor.selectionStart()
            end = cursor.selectionEnd()

            cursor.setPosition(start)
            cursor.movePosition(QTextCursor.MoveOperation.StartOfLine)
            start_block = cursor.blockNumber()

            cursor.setPosition(end)
            end_block = cursor.blockNumber()
        else:
            start_block = end_block = cursor.blockNumber()

        document = self.document()

        # Check if all lines are already commented
        all_commented = True
        for n in range(start_block, end_block + 1):
            block = document.findBlockByNumber(n)
            text = block.text().lstrip()
            if text and not text.startswith(comment_prefix):
                all_commented = False
                break

        cursor.beginEditBlock()

        for n in range(start_block, end_block + 1):
            block_cursor = QTextCursor(document.findBlockByNumber(n))
            block_cursor.movePosition(QTextCursor.MoveOperation.StartOfLine)
            block_cursor.movePosition(QTextCursor.MoveOperation.EndOfLine, QTextCursor.MoveMode.KeepAnchor)
            line_text = block_cursor.selectedText()

            if all_commented:
                # Uncomment - FIXED: Remove comment prefix and ONE space after it
                if line_text.lstrip().startswith(comment_prefix):
                    # Find where comment starts
                    indent = len(line_text) - len(line_text.lstrip())
                    comment_start = indent

                    # Remove comment prefix
                    new_text = line_text[:comment_start] + line_text[comment_start + len(comment_prefix):]

                    # Remove ONE space after comment if it exists
                    if new_text[comment_start:comment_start + 1] == ' ':
                        new_text = new_text[:comment_start] + new_text[comment_start + 1:]

                    block_cursor.insertText(new_text)
            else:
                # Comment - add comment with space
                if line_text.strip():
                    indent = len(line_text) - len(line_text.lstrip())
                    block_cursor.insertText(indent * " " + comment_prefix + " " + line_text.lstrip())

        cursor.endEditBlock()

    def get_comment_prefix(self) -> str:
        if not self.file_path:
            return "#"

        ext = Path(self.file_path).suffix.lower()
        comment_map = {
            '.py': '#', '.sh': '#', '.bash': '#', '.yml': '#', '.yaml': '#', '.toml': '#',
            '.r': '#', '.rb': '#', '.pl': '#',
            '.js': '//', '.ts': '//', '.jsx': '//', '.tsx': '//',
            '.java': '//', '.c': '//', '.cpp': '//', '.cs': '//', '.go': '//', '.rs': '//',
            '.php': '//', '.swift': '//', '.kt': '//',
            '.html': '<!--', '.xml': '<!--',
            '.css': '/*', '.sql': '--', '.lua': '--',
        }
        return comment_map.get(ext, "#")

    def indent_selection(self):
        self._adjust_indent(add=True)

    def unindent_selection(self):
        self._adjust_indent(add=False)

    def _adjust_indent(self, add: bool):
        cursor = self.textCursor()
        document = self.document()

        if cursor.hasSelection():
            start_pos = cursor.selectionStart()
            end_pos = cursor.selectionEnd()

            cursor.setPosition(start_pos)
            cursor.movePosition(QTextCursor.MoveOperation.StartOfLine)
            start_block = cursor.blockNumber()

            cursor.setPosition(end_pos)
            if cursor.atBlockStart() and start_block != cursor.blockNumber():
                end_block = cursor.blockNumber() - 1
            else:
                end_block = cursor.blockNumber()
        else:
            start_block = end_block = cursor.blockNumber()

        cursor.beginEditBlock()

        for n in range(start_block, end_block + 1):
            block_cursor = QTextCursor(document.findBlockByNumber(n))
            block_cursor.movePosition(QTextCursor.MoveOperation.StartOfLine)
            if add:
                block_cursor.insertText("    ")
            else:
                # Remove up to 4 spaces or 1 tab
                block_cursor.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor, 4)
                selected = block_cursor.selectedText()
                if selected.startswith("    "):
                    block_cursor.removeSelectedText()
                elif selected.startswith("\t"):
                    block_cursor.movePosition(QTextCursor.MoveOperation.StartOfLine)
                    block_cursor.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor, 1)
                    block_cursor.removeSelectedText()
                else:
                    spaces = len(selected) - len(selected.lstrip(" "))
                    if spaces > 0:
                        block_cursor.movePosition(QTextCursor.MoveOperation.StartOfLine)
                        block_cursor.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor, spaces)
                        block_cursor.removeSelectedText()

        cursor.endEditBlock()


    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Tab and not event.modifiers():
            cursor = self.textCursor()

            if cursor.hasSelection():
                self.indent_selection()
            else:
                # Use stored tab_width
                col = cursor.columnNumber()
                spaces_needed = self.tab_width - (col % self.tab_width)
                cursor.insertText(' ' * spaces_needed)

            return

        elif event.key() == Qt.Key.Key_Backtab or (
            event.key() == Qt.Key.Key_Tab and event.modifiers() & Qt.KeyboardModifier.ShiftModifier
        ):
            self.unindent_selection()
            return

        super().keyPressEvent(event)

    # =============================================================================
    # Duplicate Line
    # =============================================================================

    def duplicate_line_or_selection(self):
        """Duplicate the current line or selected text"""
        cursor = self.textCursor()
        cursor.beginEditBlock()

        try:
            if cursor.hasSelection():
                self._duplicate_selection(cursor)
            else:
                self._duplicate_line(cursor)
        finally:
            cursor.endEditBlock()

        self.setTextCursor(cursor)

    def _duplicate_selection(self, cursor):
        """Duplicate the selected text"""
        selected_text = cursor.selectedText()
        selected_text = selected_text.replace('\u2029', '\n')

        selection_start = cursor.selectionStart()
        selection_end = cursor.selectionEnd()

        cursor.setPosition(selection_end)
        cursor.insertText('\n' + selected_text)

        new_end = cursor.position()
        new_start = new_end - len(selected_text)
        cursor.setPosition(new_start)
        cursor.setPosition(new_end, cursor.MoveMode.KeepAnchor)

    def _duplicate_line(self, cursor):
        """Duplicate the current line"""
        original_position = cursor.positionInBlock()

        cursor.movePosition(cursor.MoveOperation.StartOfBlock)
        cursor.movePosition(cursor.MoveOperation.EndOfBlock, cursor.MoveMode.KeepAnchor)

        line_text = cursor.selectedText()
        cursor.movePosition(cursor.MoveOperation.EndOfBlock)
        cursor.insertText('\n' + line_text)

        cursor.movePosition(cursor.MoveOperation.StartOfBlock)
        cursor.movePosition(
            cursor.MoveOperation.Right,
            cursor.MoveMode.MoveAnchor,
            min(original_position, len(line_text))
        )

    # ============================================================================
    # Add fold update methods
    # ============================================================================
    
    def _schedule_fold_update(self):
        """Schedule a fold region update (debounced)"""
        # Only update if folding is enabled
        if self._is_folding_enabled():
            # Delay update by 500ms to avoid updating on every keystroke
            self.fold_update_timer.start(500)
    
    def _update_fold_regions(self):
        """Update fold regions (called by timer)"""
        if self._is_folding_enabled():
            self.folding_manager.update_regions()
            if self.line_number_area:
                self.line_number_area.update()
    
    def _is_folding_enabled(self):
        """Check if code folding is enabled in settings"""
        # Walk up parent tree to find settings
        parent = self.parent()
        while parent is not None:
            if hasattr(parent, 'settings_manager'):
                return parent.settings_manager.get('enable_code_folding', True)
            parent = parent.parent()
        return True
    


# ============================================================================
# LineNumberArea to handle mouse clicks
# ============================================================================

# ============================================================================
# LineNumberArea to handle mouse clicks - COMPLETE FIXED VERSION
# ============================================================================

class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor
        
        # Enable mouse tracking
        self.setMouseTracking(True)
    
    def sizeHint(self):
        return QSize(self.editor.line_number_area_width(), 0)
    
    def paintEvent(self, event):
        self.editor.line_number_area_paint_event(event)
    
    # Matching simple version for mouse clicks
    def mousePressEvent(self, event):
        """Handle clicks on fold markers - ULTRA SIMPLE VERSION"""
        from PyQt6.QtCore import Qt
        
        # Only care about left clicks
        if event.button() != Qt.MouseButton.LeftButton:
            return
        
        # Only if folding is enabled
        if not self.editor._is_folding_enabled():
            return
        
        # Where did they click?
        click_y = event.pos().y()
        click_x = event.pos().x()
        
        # Go through each block to find which one they clicked
        block = self.editor.firstVisibleBlock()
        
        while block.isValid():
            # Ask Qt where this block is drawn
            where_is_block = self.editor.blockBoundingGeometry(block).translated(
                self.editor.contentOffset()
            )
            
            # Is the click on this block?
            if block.isVisible():
                if where_is_block.top() <= click_y <= where_is_block.bottom():
                    # They clicked this line!
                    
                    # Was it on the fold marker? (left 14 pixels)
                    if click_x < 14:
                        self.editor.folding_manager.toggle_fold_at_line(block.blockNumber())
                    return
            
            # Try next block
            block = block.next()
    
    
    # Also add this to the LineNumberArea class for the cursor change
    def mouseMoveEvent(self, event):
        """Change cursor when hovering over fold markers"""
        from PyQt6.QtCore import Qt
        
        if not self.editor._is_folding_enabled():
            return
        
        # Show pointing hand cursor over fold markers
        if event.pos().x() < 14:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)


class ColumnMarker(QWidget):
    """
    Column marker widget that draws a vertical line at a specified column.
    
    This provides a visual guide for line length (typically at 80 or 120 columns).
    Similar to the vertical rulers in VS Code, Sublime Text, etc.
    """
    
    def __init__(self, editor):
        """
        Initialize the ColumnMarker with the given editor instance.
        
        Args:
            editor: The CodeEditor instance that owns this marker
        """
        super().__init__(editor)
        self.editor = editor
        
        # Make widget transparent to mouse events
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        
        # Set widget to be on top but not interfere
        self.setAutoFillBackground(False)
    
    def paintEvent(self, event):
        """
        Paint the column marker line.
        
        Args:
            event: The QPaintEvent
        """
        # Get settings from editor's parent workspace
        settings = self._get_settings()
        
        if not settings.get('show_column_marker', True):
            return
        
        column_position = settings.get('column_marker_position', 80)
        
        # Calculate x position based on font metrics
        font_metrics = QFontMetricsF(self.editor.font())
        char_width = font_metrics.horizontalAdvance(' ')
        x_position = int(char_width * column_position)
        
        # Account for line number area offset
        if self.editor.line_number_area:
            x_position += self.editor.line_number_area.width()
        
        # Draw the vertical line
        painter = QPainter(self)
        painter.setPen(QColor("#3C3C3C"))  # Subtle gray color
        painter.drawLine(
            x_position,
            0,
            x_position,
            self.editor.viewport().height()
        )
    
    def _get_settings(self):
        """
        Get settings from the workspace.
        
        Returns:
            dict: Settings dictionary
        """
        # Walk up parent tree to find workspace with settings_manager
        parent = self.editor.parent()
        while parent is not None:
            if hasattr(parent, 'settings_manager'):
                return parent.settings_manager.settings
            parent = parent.parent()
        
        # Fallback to defaults
        return {
            'show_column_marker': True,
            'column_marker_position': 80
        }
