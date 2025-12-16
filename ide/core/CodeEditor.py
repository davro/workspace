from pathlib import Path

from PyQt6.QtWidgets import QPlainTextEdit, QMessageBox
from PyQt6.QtGui import (
    QFont,
    QPainter,
    QColor,
    QTextCursor,
    QTextFormat,
    QTextOption,
    QFontMetrics,
)
from PyQt6.QtCore import Qt, QRect
from PyQt6.QtWidgets import QMessageBox, QSpacerItem, QGridLayout, QWidget, QVBoxLayout, QLabel, QMessageBox, QTextEdit

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
    def __init__(self, font_size=11, tab_width=4, show_line_numbers=True):
        super().__init__()
        self.setFont(QFont("Monospace", font_size))
        self.setStyleSheet("QPlainTextEdit { background-color: #2B2B2B; color: #A9B7C6; border: none; }")

        #self.setTabStopDistance(tab_width * 10)
	   # Calculate correct tab width in pixels
        char_width = self.fontMetrics().horizontalAdvance(' ')
        self.setTabStopDistance(tab_width * char_width)

        self.file_path = None
        self.highlighter = None
        self.is_modified = False
        self.show_line_numbers = show_line_numbers

        self.line_number_area = LineNumberArea(self)
        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.cursorPositionChanged.connect(self.highlight_current_line)
        self.update_line_number_area_width(0)

        self.textChanged.connect(self.mark_modified)

    def line_number_area_width(self):
        if not self.show_line_numbers:
            return 0

        digits = len(str(max(1, self.blockCount())))
        space = 3 + self.fontMetrics().horizontalAdvance('9') * digits
        return space

    def update_line_number_area_width(self, _):
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def update_line_number_area(self, rect, dy):
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())

        if rect.contains(self.viewport().rect()):
            self.update_line_number_area_width(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.line_number_area.setGeometry(cr.left(), cr.top(), self.line_number_area_width(), cr.height())

    def line_number_area_paint_event(self, event):
        painter = QPainter(self.line_number_area)
        painter.fillRect(event.rect(), QColor("#313335"))

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        bottom = top + self.blockBoundingRect(block).height()

        height = self.fontMetrics().height()
        while block.isValid() and (top <= event.rect().bottom()):
            if block.isVisible() and (bottom >= event.rect().top()):
                number = str(block_number + 1)
                painter.setPen(QColor("#606366"))
                painter.drawText(0, int(top), self.line_number_area.width() - 3, height,
                               Qt.AlignmentFlag.AlignRight, number)

            block = block.next()
            top = bottom
            bottom = top + self.blockBoundingRect(block).height()
            block_number += 1

    def highlight_current_line(self):
        extra_selections = []

        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()
            line_color = QColor("#2F3437")
            selection.format.setBackground(line_color)
            selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extra_selections.append(selection)

        self.setExtraSelections(extra_selections)

    def mark_modified(self):
        """Mark editor as modified and trigger signal"""
        if not self.is_modified:
            self.is_modified = True
            # Emit a custom signal or call parent to update UI
            parent = self.parent()
            if parent and hasattr(parent, 'parent') and hasattr(parent.parent(), 'on_editor_modified'):
                parent.parent().on_editor_modified(self)

    def load_file(self, path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                self.setPlainText(f.read())
            self.file_path = path
            if path.endswith(".py"):
                self.highlighter = PythonHighlighter(self.document())
            self.is_modified = False
            return True
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            return False

    def save_file(self):
        if not self.file_path:
            return False
        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                f.write(self.toPlainText())
            self.is_modified = False
            return True
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            return False


	# =====================================================================
	# Feature: Comment Toggle (Ctrl+/) Indent/Unindent
	# =====================================================================
    def toggle_comment(self):
        """Toggle comments on selected lines or current line"""
        cursor = self.textCursor()

        # Determine comment syntax based on file extension
        comment_prefix = self.get_comment_prefix()

        # Get selection or current line
        if cursor.hasSelection():
            start = cursor.selectionStart()
            end = cursor.selectionEnd()

            # Move to start of selection
            cursor.setPosition(start)
            cursor.movePosition(QTextCursor.MoveOperation.StartOfLine)
            start_block = cursor.blockNumber()

            # Move to end of selection
            cursor.setPosition(end)
            end_block = cursor.blockNumber()
        else:
            # Just current line
            start_block = cursor.blockNumber()
            end_block = start_block

        # Check if all lines are commented
        document = self.document()
        all_commented = True

        for block_num in range(start_block, end_block + 1):
            block = document.findBlockByNumber(block_num)
            text = block.text()
            stripped = text.lstrip()
            if stripped and not stripped.startswith(comment_prefix):
                all_commented = False
                break

        # Toggle comments
        cursor.beginEditBlock()

        for block_num in range(start_block, end_block + 1):
            cursor = QTextCursor(document.findBlockByNumber(block_num))
            cursor.movePosition(QTextCursor.MoveOperation.StartOfLine)
            cursor.movePosition(QTextCursor.MoveOperation.EndOfLine, QTextCursor.MoveMode.KeepAnchor)

            line_text = cursor.selectedText()

            if all_commented:
                # Remove comment
                stripped = line_text.lstrip()
                if stripped.startswith(comment_prefix):
                    # Find where comment starts
                    comment_index = line_text.find(comment_prefix)
                    new_text = line_text[:comment_index] + line_text[comment_index + len(comment_prefix):]
                    # Remove one space after comment if present
                    if new_text[comment_index:comment_index+1] == ' ':
                        new_text = new_text[:comment_index] + new_text[comment_index+1:]
                    cursor.insertText(new_text)
            else:
                # Add comment
                if line_text.strip():  # Only comment non-empty lines
                    # Find first non-whitespace character
                    stripped = line_text.lstrip()
                    indent = line_text[:len(line_text) - len(stripped)]
                    new_text = indent + comment_prefix + ' ' + stripped
                    cursor.insertText(new_text)

        cursor.endEditBlock()

    def get_comment_prefix(self):
        """Get comment prefix based on file extension"""
        if not self.file_path:
            return '#'

        ext = Path(self.file_path).suffix.lower()

        comment_map = {
            '.py': '#',
            '.sh': '#',
            '.bash': '#',
            '.yml': '#',
            '.yaml': '#',
            '.toml': '#',
            '.r': '#',
            '.rb': '#',
            '.pl': '#',
            '.js': '//',
            '.ts': '//',
            '.jsx': '//',
            '.tsx': '//',
            '.java': '//',
            '.c': '//',
            '.cpp': '//',
            '.cs': '//',
            '.go': '//',
            '.rs': '//',
            '.php': '//',
            '.swift': '//',
            '.kt': '//',
            '.html': '<!--',
            '.xml': '<!--',
            '.css': '/*',
            '.sql': '--',
            '.lua': '--',
        }

        return comment_map.get(ext, '#')

    def indent_selection(self):
        """Indent selected lines or current line"""
        cursor = self.textCursor()

        if cursor.hasSelection():
            start = cursor.selectionStart()
            end = cursor.selectionEnd()

            cursor.setPosition(start)
            cursor.movePosition(QTextCursor.MoveOperation.StartOfLine)
            start_block = cursor.blockNumber()

            cursor.setPosition(end)
            # If selection ends at start of line, don't include that line
            if cursor.columnNumber() == 0 and start_block != cursor.blockNumber():
                end_block = cursor.blockNumber() - 1
            else:
                end_block = cursor.blockNumber()
        else:
            start_block = cursor.blockNumber()
            end_block = start_block

        document = self.document()
        cursor.beginEditBlock()

        for block_num in range(start_block, end_block + 1):
            cursor = QTextCursor(document.findBlockByNumber(block_num))
            cursor.movePosition(QTextCursor.MoveOperation.StartOfLine)
            cursor.insertText('    ')  # Insert 4 spaces

        cursor.endEditBlock()

    def unindent_selection(self):
        """Unindent selected lines or current line"""
        cursor = self.textCursor()

        if cursor.hasSelection():
            start = cursor.selectionStart()
            end = cursor.selectionEnd()

            cursor.setPosition(start)
            cursor.movePosition(QTextCursor.MoveOperation.StartOfLine)
            start_block = cursor.blockNumber()

            cursor.setPosition(end)
            if cursor.columnNumber() == 0 and start_block != cursor.blockNumber():
                end_block = cursor.blockNumber() - 1
            else:
                end_block = cursor.blockNumber()
        else:
            start_block = cursor.blockNumber()
            end_block = start_block

        document = self.document()
        cursor.beginEditBlock()

        for block_num in range(start_block, end_block + 1):
            cursor = QTextCursor(document.findBlockByNumber(block_num))
            cursor.movePosition(QTextCursor.MoveOperation.StartOfLine)
            cursor.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor, 4)

            selected = cursor.selectedText()
            # Remove up to 4 spaces/tabs
            if selected.startswith('    '):
                cursor.removeSelectedText()
            elif selected.startswith('\t'):
                cursor.movePosition(QTextCursor.MoveOperation.StartOfLine)
                cursor.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor, 1)
                cursor.removeSelectedText()
            elif selected.startswith('   '):
                cursor.movePosition(QTextCursor.MoveOperation.StartOfLine)
                cursor.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor, 3)
                cursor.removeSelectedText()
            elif selected.startswith('  '):
                cursor.movePosition(QTextCursor.MoveOperation.StartOfLine)
                cursor.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor, 2)
                cursor.removeSelectedText()
            elif selected.startswith(' '):
                cursor.movePosition(QTextCursor.MoveOperation.StartOfLine)
                cursor.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor, 1)
                cursor.removeSelectedText()

        cursor.endEditBlock()

    def keyPressEvent(self, event):
        """Override to handle Tab and Shift+Tab for indenting"""
        if event.key() == Qt.Key.Key_Tab and not event.modifiers():
            # Tab key pressed
            if self.textCursor().hasSelection():
                self.indent_selection()
                return
        elif event.key() == Qt.Key.Key_Backtab or (event.key() == Qt.Key.Key_Tab and event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
            # Shift+Tab pressed
            self.unindent_selection()
            return

        # Default behavior for other keys
        super().keyPressEvent(event)
