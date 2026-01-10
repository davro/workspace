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

"""
Main Code Editor Class
A custom QTextEdit widget with enhanced features for code editing.
"""
class CodeEditor(QPlainTextEdit, SettingsProvider):
    """
    Main Code Editor Class
    A custom QTextEdit widget with enhanced features for code editing.
    """
    
    # ========================================================================
    # Settings Descriptors - Define what settings CodeEditor uses
    # ========================================================================
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

        # Connect text changed signal for plugins
        self.textChanged.connect(self._on_text_changed)


    def _on_text_changed(self):
        """Notify plugins about text change"""
        # This allows plugins to hook into typing
        pass

    # ------------------------------------------------------------------
    # Line Number Area
    # ------------------------------------------------------------------

    def update_line_number_area_width(self, _):
        """Update the viewport margins to accommodate line numbers + gutter"""
        left_margin = self.line_number_area_width()
        self.setViewportMargins(left_margin, 0, 0, 0)

    def line_number_area_width(self):
        """Calculate the width needed for line numbers + gutter"""
        if not self.show_line_numbers or not self.line_number_area:
            return self.gutter_width

        digits = len(str(max(1, self.blockCount())))
        space = 3 + self.fontMetrics().horizontalAdvance('9') * digits + self.gutter_width
        return space

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
        """Handle resize events to update line number area"""
        super().resizeEvent(event)

        if not self.line_number_area:
            return

        cr = self.contentsRect()
        digits = len(str(max(1, self.blockCount())))
        line_number_width = 3 + self.fontMetrics().horizontalAdvance('9') * digits

        self.line_number_area.setGeometry(
            QRect(cr.left(), cr.top(), line_number_width, cr.height())
        )

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

    # ------------------------------------------------------------------
    # Modification tracking
    # ------------------------------------------------------------------
    def on_text_changed(self):
        """Notify the main window when the document's modified state changes"""
        # Find the WorkspaceIDE instance
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

            self.document().setModified(False)
            return True
        except Exception as e:
            QMessageBox.critical(self, "Error saving file", str(e))
            return False

    # =====================================================================
    # Feature: Comment Toggle (Ctrl+/) - FIXED VERSION
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

    # ============================================================================
    # Duplicate Line
    # ============================================================================

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


class LineNumberArea(QWidget):
    def __init__(self, editor):
        """
        Initialize the LineNumberArea with the given editor instance.

        Args:
            editor (QTextEdit or QPlainTextEdit): The main text editor widget that displays the code.  
                This widget is used to synchronize line numbers with the content of the editor.

        Notes:
            - The `editor` is passed to the parent class constructor to establish the widget hierarchy.
            - This method sets up the foundational configuration for line number display.
        """
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self):
        """
        Returns the size hint for the LineNumberArea widget.

        This method provides a suggested size for the LineNumberArea, with the width
        determined by the editor's line number area width. The height is set to 0,
        as the vertical size is typically managed by the parent layout or the editor's
        content height.

        Returns:
            QSize: A size with the calculated width and 0 height.
        """
        return QSize(self.editor.line_number_area_width(), 0)

    def paintEvent(self, event):
        """
        Handle the paint event for the line number area by delegating to the editor's paint method.

        This method is called when the line number area needs to be repainted. It forwards the paint event
        to the associated editor's `line_number_area_paint_event` method to ensure the line numbers
        are correctly rendered.

        :param event: The QPaintEvent containing information about the painting operation.
        :type event: PyQt6.QtWidgets.QPaint, QPaintEvent
        """
        self.editor.line_number_area_paint_event(event)
