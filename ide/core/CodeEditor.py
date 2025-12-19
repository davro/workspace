from pathlib import Path

from PyQt6.QtWidgets import QPlainTextEdit, QMessageBox, QWidget, QTextEdit
from PyQt6.QtGui import (
    QFont,
    QPainter,
    QColor,
    QTextCursor,
    QTextFormat,
    QTextOption,
)
from PyQt6.QtCore import Qt, QSize, QRect

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

        # Font and styling
        font = QFont("Monospace", font_size)
        font.setStyleHint(QFont.StyleHint.TypeWriter)
        self.setFont(font)
        self.setStyleSheet(
            "QPlainTextEdit { background-color: #2B2B2B; color: #A9B7C6; border: none; }"
        )

        # Tab width in spaces
        char_width = self.fontMetrics().horizontalAdvance(' ')
        self.setTabStopDistance(tab_width * char_width)

        # State
        self.file_path = None
        self.highlighter = None
        self.show_line_numbers = show_line_numbers

        # Line number area
        self.line_number_area = LineNumberArea(self)

        # Connections for line numbers and highlighting
        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.cursorPositionChanged.connect(self.highlight_current_line)
        self.update_line_number_area_width(0)

        # Notify parent IDE whenever the document modified state changes
        self.textChanged.connect(self.on_text_changed)

    # ------------------------------------------------------------------
    # Line Number Area
    # ------------------------------------------------------------------
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
            self.line_number_area.update(
                0, rect.y(), self.line_number_area.width(), rect.height()
            )
        if rect.contains(self.viewport().rect()):
            self.update_line_number_area_width(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        width = self.line_number_area_width()
        self.line_number_area.setGeometry(cr.left(), cr.top(), width, cr.height())

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
