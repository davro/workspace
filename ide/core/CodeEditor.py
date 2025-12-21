from pathlib import Path

from PyQt6.QtWidgets import QPlainTextEdit, QWidget, QTextEdit
from PyQt6.QtGui import (
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

from ide.core.SyntaxHighlighter import PythonHighlighter

class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self):
        return QSize(self.editor.line_number_area_width(), 0)

    def paintEvent(self, event):
        self.editor.line_number_area_paint_event(event)


class CodeEditor(QPlainTextEdit):
    # def __init__(self, font_size=11, tab_width=4, 
    def __init__(self, file_path=None, font_size=11, tab_width=4, 
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

        # Font and styling
        font = QFont("Monospace", font_size)
        font.setStyleHint(QFont.StyleHint.TypeWriter)
        self.setFont(font)
        self.setStyleSheet(
            "QPlainTextEdit { background-color: #2B2B2B; color: #A9B7C6; border: none; }"
        )

        # Tab width in spaces
        #char_width = self.fontMetrics().horizontalAdvance(' ')
        #self.setTabStopDistance(tab_width * char_width)

        # Tab settings
        self.setTabStopDistance(
            QFontMetricsF(self.font()).horizontalAdvance(' ') * tab_width
        )

        # State
        self.file_path = None
        self.highlighter = None
        self.show_line_numbers = show_line_numbers
        self.gutter_width = gutter_width

        # Line number area
        #self.line_number_area = LineNumberArea(self)
        self.line_number_area = LineNumberArea(self) if show_line_numbers else None

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

        # Load file if provided
        if file_path:
            self.load_file(file_path)

    # ------------------------------------------------------------------
    # Line Number Area
    # ------------------------------------------------------------------

    def update_line_number_area_width(self, _):
        """Update the viewport margins to accommodate line numbers + gutter"""
        # Always add gutter width as left margin, even when line numbers are hidden
        left_margin = self.line_number_area_width()
        self.setViewportMargins(left_margin, 0, 0, 0)


    def line_number_area_width(self):
        """Calculate the width needed for line numbers + gutter"""
        if not self.show_line_numbers or not self.line_number_area:
            # Even without line numbers, add gutter for spacing
            return self.gutter_width
        
        digits = len(str(max(1, self.blockCount())))
        # Width = left_padding(3) + digit_width * digits + gutter_width
        space = 3 + self.fontMetrics().horizontalAdvance('9') * digits + self.gutter_width
        return space


    def update_line_number_area(self, rect, dy):
        """Update the line number area when the editor scrolls or updates"""
        # ADD THIS CHECK at the beginning
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


    def set_gutter_width(self, width):
        """
        Set the gutter width and update display
        
        Args:
            width: Gutter width in pixels
        """
        self.gutter_width = width
        self.update_line_number_area_width(0)
        if self.line_number_area:
            self.line_number_area.update()


    def set_show_line_numbers(self, show):
        """
        Toggle line numbers display
        
        Args:
            show: True to show line numbers, False to hide
        """
        self.show_line_numbers = show
        
        if show and not self.line_number_area:
            # Create line number area
            self.line_number_area = LineNumberArea(self)
            self.blockCountChanged.connect(self.update_line_number_area_width)
            self.updateRequest.connect(self.update_line_number_area)
            self.line_number_area.show()
        elif not show and self.line_number_area:
            # Hide line number area
            self.line_number_area.hide()
        
        self.update_line_number_area_width(0)


    def set_font_size(self, size):
        """
        Set font size and update display
        
        Args:
            size: Font size in points
        """
        font = self.font()
        font.setPointSize(size)
        self.setFont(font)
        
        # Update tab stops for new font size
        tab_width = int(self.tabStopDistance() / 
                       QFontMetricsF(font).horizontalAdvance(' '))
        self.setTabStopDistance(
            QFontMetricsF(font).horizontalAdvance(' ') * tab_width
        )
        
        # Update line number area
        self.update_line_number_area_width(0)
        if self.line_number_area:
            self.line_number_area.update()


    def set_tab_width(self, width):
        """
        Set tab width and update display
        
        Args:
            width: Tab width in spaces
        """
        self.setTabStopDistance(
            QFontMetricsF(self.font()).horizontalAdvance(' ') * width
        )


    def resizeEvent(self, event):
        """Handle resize events to update line number area"""
        super().resizeEvent(event)
        
        if not self.line_number_area:
            return
        
        cr = self.contentsRect()
        # Line number area width should NOT include the gutter in its geometry
        # The gutter is spacing AFTER the line numbers
        digits = len(str(max(1, self.blockCount())))
        line_number_width = 3 + self.fontMetrics().horizontalAdvance('9') * digits
        
        self.line_number_area.setGeometry(
            QRect(cr.left(), cr.top(), line_number_width, cr.height())
        )

    def paint_line_numbers(self, event):
        """Paint line numbers in the line number area"""
        # ADD THIS CHECK
        if not self.line_number_area:
            return
        
        painter = QPainter(self.line_number_area)
        painter.fillRect(event.rect(), QColor("#313335"))
        # ... rest of painting code

    def line_number_area_paint_event(self, event):
        painter = QPainter(self.line_number_area)
        painter.fillRect(event.rect(), QColor("#313335"))

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        bottom = top + self.blockBoundingRect(block).height()

        height = self.fontMetrics().height()
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                painter.setPen(QColor("#606366"))
                painter.drawText(
                    0,
                    int(top),
                    self.line_number_area.width() - 3,
                    height,
                    Qt.AlignmentFlag.AlignRight,
                    number,
                )
            block = block.next()
            top = bottom
            bottom = top + self.blockBoundingRect(block).height()
            block_number += 1

    def highlight_current_line(self):
        extra_selections = []
        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()
            selection.format.setBackground(QColor("#2F3437"))
            selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extra_selections.append(selection)
        self.setExtraSelections(extra_selections)

    # ------------------------------------------------------------------
    # Modification tracking
    # ------------------------------------------------------------------
    def on_text_changed(self):
        """Notify the main window when the document's modified state changes"""
        # Walk up the parent chain to find the WorkspaceIDE instance
        parent = self.parent()
        while parent is not None:
            if hasattr(parent, "on_editor_modified"):
                parent.on_editor_modified(self)
                break
            parent = parent.parent()

    # ------------------------------------------------------------------
    # File operations
    # ------------------------------------------------------------------
    def load_file(self, path: str) -> bool:
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()

            # Prevent textChanged signals during load (avoids false modified state)
            self.blockSignals(True)
            self.setPlainText(content)
            self.blockSignals(False)

            self.file_path = path

            # Apply syntax highlighting if it's a Python file
            if str(path).lower().endswith(".py"):
                self.highlighter = PythonHighlighter(self.document())

            # Clear Qt's built-in modified flag
            self.document().setModified(False)

            return True
        except Exception as e:
            QMessageBox.critical(self, "Error loading file", str(e))
            return False

    def save_file(self) -> bool:
        if not self.file_path:
            return False

        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                f.write(self.toPlainText())

            # Tell Qt the document is now saved → clears the modified flag
            self.document().setModified(False)

            return True
        except Exception as e:
            QMessageBox.critical(self, "Error saving file", str(e))
            return False

    # =====================================================================
    # Feature: Comment Toggle (Ctrl+/) and Indent/Unindent
    # =====================================================================
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
                # Uncomment
                if line_text.lstrip().startswith(comment_prefix):
                    idx = line_text.find(comment_prefix)
                    new_text = line_text[:idx] + line_text[idx + len(comment_prefix):]
                    if new_text.lstrip().startswith(' '):
                        new_text = new_text[:idx] + new_text[idx + 1:]
                    block_cursor.insertText(new_text)
            else:
                # Comment
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
                    # Remove as many leading spaces as possible
                    spaces = len(selected) - len(selected.lstrip(" "))
                    if spaces > 0:
                        block_cursor.movePosition(QTextCursor.MoveOperation.StartOfLine)
                        block_cursor.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor, spaces)
                        block_cursor.removeSelectedText()

        cursor.endEditBlock()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Tab and not event.modifiers():
            if self.textCursor().hasSelection():
                self.indent_selection()
                return
        elif event.key() == Qt.Key.Key_Backtab or (
            event.key() == Qt.Key.Key_Tab and event.modifiers() & Qt.KeyboardModifier.ShiftModifier
        ):
            self.unindent_selection()
            return

        super().keyPressEvent(event)


    # ============================================================================
    # Duplicate Line
    # ============================================================================
        
    def duplicate_line_or_selection(self):
        """
        Duplicate the current line or selected text
        
        Behavior:
        - If text is selected: Duplicates the selection immediately after
        - If no selection: Duplicates the current line below it
        - Cursor moves to the duplicated content
        - Preserves indentation and formatting
        """
        cursor = self.textCursor()
        
        # Start undo block for atomic operation
        cursor.beginEditBlock()
        
        try:
            if cursor.hasSelection():
                # Duplicate selected text
                self._duplicate_selection(cursor)
            else:
                # Duplicate current line
                self._duplicate_line(cursor)
        finally:
            # End undo block
            cursor.endEditBlock()
        
        # Update the cursor
        self.setTextCursor(cursor)
    
    def _duplicate_selection(self, cursor):
        """
        Duplicate the selected text
        
        Args:
            cursor: QTextCursor with selection
        """
        # Get the selected text
        selected_text = cursor.selectedText()
        
        # QTextCursor uses U+2029 (paragraph separator) for newlines
        # Convert to actual newlines for insertion
        selected_text = selected_text.replace('\u2029', '\n')
        
        # Get selection boundaries
        selection_start = cursor.selectionStart()
        selection_end = cursor.selectionEnd()
        
        # Move to end of selection
        cursor.setPosition(selection_end)
        
        # Insert newline and duplicated text
        cursor.insertText('\n' + selected_text)
        
        # Select the newly inserted text
        new_end = cursor.position()
        new_start = new_end - len(selected_text)
        cursor.setPosition(new_start)
        cursor.setPosition(new_end, cursor.MoveMode.KeepAnchor)
    
    def _duplicate_line(self, cursor):
        """
        Duplicate the current line
        
        Args:
            cursor: QTextCursor on current line
        """
        # Save current position in line
        original_position = cursor.positionInBlock()
        
        # Select the entire current line
        cursor.movePosition(cursor.MoveOperation.StartOfBlock)
        cursor.movePosition(cursor.MoveOperation.EndOfBlock, cursor.MoveMode.KeepAnchor)
        
        # Get the line text
        line_text = cursor.selectedText()
        
        # Move to end of line
        cursor.movePosition(cursor.MoveOperation.EndOfBlock)
        
        # Insert newline and duplicated line
        cursor.insertText('\n' + line_text)
        
        # Position cursor at same column in duplicated line
        cursor.movePosition(cursor.MoveOperation.StartOfBlock)
        cursor.movePosition(
            cursor.MoveOperation.Right,
            cursor.MoveMode.MoveAnchor,
            min(original_position, len(line_text))
        )
    

