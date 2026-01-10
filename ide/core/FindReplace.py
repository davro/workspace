# ============================================================================
# FindReplace.py (Find Replace Widget)
# ============================================================================
from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLineEdit, QLabel, QPushButton,
    QCheckBox, QTextEdit, QMessageBox, QSizePolicy,
)
from PyQt6.QtGui import (
    QColor, QTextCursor, QTextDocument,
)
from PyQt6.QtCore import Qt, QRegularExpression


class FindReplaceWidget(QFrame):
    """Find and Replace panel widget"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.editor = None
        self.current_match_index = -1
        self.matches = []

        # Set size policy to prevent expansion
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMaximumHeight(110)  # ← Increased from 100
        self.setMinimumHeight(110)  # ← Increased from 100

        self.setStyleSheet("""
            QFrame {
                background-color: #2B2B2B;
                border-bottom: 1px solid #555;
            }
            QLineEdit {
                background-color: #3C3F41;
                color: #CCC;
                border: 1px solid #555;
                padding: 5px;
                border-radius: 2px;
                font-size: 13px;  /* ← Increased from 12px */
                font-family: 'Consolas', 'Monaco', 'Courier New', monospace;  /* ← Added monospace font */
            }
            QLineEdit:focus {
                border: 1px solid #4A9EFF;
            }
            QPushButton {
                background-color: #3C3F41;
                color: #CCC;
                border: 1px solid #555;
                padding: 3px 8px;
                border-radius: 2px;
                font-size: 12px;  /* ← Added explicit size */
            }
            QPushButton:hover {
                background-color: #4A4A4A;
            }
            QPushButton:pressed {
                background-color: #2A2A2A;
            }
            QCheckBox {
                color: #CCC;
                font-size: 12px;  /* ← Added explicit size */
            }
            QLabel {
                font-size: 12px;  /* ← Added for match label */
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)  # ← Increased from 3

        # Find row
        find_row = QHBoxLayout()
        self.find_input = QLineEdit()
        self.find_input.setPlaceholderText("Find")
        self.find_input.setFixedHeight(28)  # ← Increased from 24
        self.find_input.textChanged.connect(self.on_find_text_changed)
        self.find_input.returnPressed.connect(self.find_next)
        find_row.addWidget(self.find_input)

        self.match_label = QLabel("No matches")
        self.match_label.setStyleSheet("color: #999;")
        self.match_label.setFixedWidth(100)
        find_row.addWidget(self.match_label)

        prev_btn = QPushButton("↑")
        prev_btn.setToolTip("Previous (Shift+F3)")
        prev_btn.setFixedSize(28, 28)  # ← Increased from 24
        prev_btn.clicked.connect(self.find_previous)
        find_row.addWidget(prev_btn)

        next_btn = QPushButton("↓")
        next_btn.setToolTip("Next (F3)")
        next_btn.setFixedSize(28, 28)  # ← Increased from 24
        next_btn.clicked.connect(self.find_next)
        find_row.addWidget(next_btn)

        layout.addLayout(find_row)

        # Replace row
        replace_row = QHBoxLayout()
        self.replace_input = QLineEdit()
        self.replace_input.setPlaceholderText("Replace")
        self.replace_input.setFixedHeight(28)  # ← Increased from 24
        self.replace_input.returnPressed.connect(self.replace_current)
        replace_row.addWidget(self.replace_input)

        replace_btn = QPushButton("Replace")
        replace_btn.setFixedHeight(28)  # ← Increased from 24
        replace_btn.clicked.connect(self.replace_current)
        replace_row.addWidget(replace_btn)

        replace_all_btn = QPushButton("Replace All")
        replace_all_btn.setFixedHeight(28)  # ← Increased from 24
        replace_all_btn.clicked.connect(self.replace_all)
        replace_row.addWidget(replace_all_btn)

        layout.addLayout(replace_row)

        # Options row
        options_row = QHBoxLayout()
        self.case_sensitive = QCheckBox("Match Case")
        self.case_sensitive.stateChanged.connect(self.on_find_text_changed)
        options_row.addWidget(self.case_sensitive)

        self.whole_word = QCheckBox("Whole Word")
        self.whole_word.stateChanged.connect(self.on_find_text_changed)
        options_row.addWidget(self.whole_word)

        self.regex = QCheckBox("Regex")
        self.regex.stateChanged.connect(self.on_find_text_changed)
        options_row.addWidget(self.regex)

        self.in_selection = QCheckBox("In Selection")
        self.in_selection.stateChanged.connect(self.on_find_text_changed)
        options_row.addWidget(self.in_selection)

        options_row.addStretch()

        close_btn = QPushButton("✖")
        close_btn.setFixedSize(28, 28)  # ← Increased from 24
        # close_btn.clicked.connect(self.hide)
        close_btn.clicked.connect(self.close_panel)
        options_row.addWidget(close_btn)

        layout.addLayout(options_row)

        self.hide()

    def close_panel(self):
        """Close the find/replace panel"""
        self.clear_highlights()
        self.hide()
        if self.editor:
            self.editor.setFocus()

    def keyPressEvent(self, event):
        """Handle key press events"""
        if event.key() == Qt.Key.Key_Escape:
            self.clear_highlights()  # Clear highlights when closing
            self.hide()
            if self.editor:
                self.editor.setFocus()
            event.accept()
        else:
            super().keyPressEvent(event)

    def set_editor(self, editor):
        self.editor = editor
        self.clear_highlights()

    def show_find(self):
        self.show()
        self.find_input.setFocus()
        self.find_input.selectAll()
    
        if self.editor:
            cursor = self.editor.textCursor()
            if cursor.hasSelection():
                selected = cursor.selectedText()
                if '\u2029' not in selected:
                    self.find_input.setText(selected)
        
        # Always trigger search when showing the panel
        if self.find_input.text():
            self.on_find_text_changed()

    def on_find_text_changed(self):
        self.clear_highlights()
        if not self.editor or not self.find_input.text():
            self.match_label.setText("No matches")
            return

        self.find_all_matches()
        self.highlight_all_matches()

        if self.matches:
            self.current_match_index = 0
            self.highlight_current_match()
            self.match_label.setText(f"1 of {len(self.matches)}")
        else:
            self.match_label.setText("No matches")

    def find_all_matches(self):
        self.matches = []
        if not self.editor:
            return

        search_text = self.find_input.text()
        if not search_text:
            return

        flags = QTextDocument.FindFlag(0)
        if self.case_sensitive.isChecked():
            flags |= QTextDocument.FindFlag.FindCaseSensitively
        if self.whole_word.isChecked():
            flags |= QTextDocument.FindFlag.FindWholeWords

        if self.in_selection.isChecked() and self.editor.textCursor().hasSelection():
            cursor = self.editor.textCursor()
            start = cursor.selectionStart()
            end = cursor.selectionEnd()
        else:
            start = 0
            end = len(self.editor.toPlainText())

        cursor = self.editor.textCursor()
        cursor.setPosition(start)

        if self.regex.isChecked():
            regex = QRegularExpression(search_text)
            if not self.case_sensitive.isChecked():
                regex.setPatternOptions(QRegularExpression.PatternOption.CaseInsensitiveOption)

            while True:
                cursor = self.editor.document().find(regex, cursor, flags)
                if cursor.isNull() or cursor.position() > end:
                    break
                self.matches.append((cursor.selectionStart(), cursor.selectionEnd()))
        else:
            while True:
                cursor = self.editor.document().find(search_text, cursor, flags)
                if cursor.isNull() or cursor.position() > end:
                    break
                self.matches.append((cursor.selectionStart(), cursor.selectionEnd()))

    def highlight_all_matches(self):
        """Use CodeEditor's new selection system"""
        if not self.editor or not self.matches:
            if self.editor and hasattr(self.editor, 'set_find_replace_selections'):
                self.editor.set_find_replace_selections([])
            return

        extra_selections = []
        for start, end in self.matches:
            selection = QTextEdit.ExtraSelection()
            selection.cursor = self.editor.textCursor()
            selection.cursor.setPosition(start)
            selection.cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
            selection.format.setBackground(QColor("#4A4A4A"))
            extra_selections.append(selection)

        # Use CodeEditor's method to avoid overwriting current line highlight
        if hasattr(self.editor, 'set_find_replace_selections'):
            self.editor.set_find_replace_selections(extra_selections)
        else:
            # Fallback for non-split editors
            self.editor.setExtraSelections(extra_selections)

    def highlight_current_match(self):
        """Use CodeEditor's new selection system"""
        if not self.editor or not self.matches or self.current_match_index < 0:
            return
    
        start, end = self.matches[self.current_match_index]
    
        extra_selections = []
        for i, (s, e) in enumerate(self.matches):
            selection = QTextEdit.ExtraSelection()
            selection.cursor = self.editor.textCursor()
            selection.cursor.setPosition(s)
            selection.cursor.setPosition(e, QTextCursor.MoveMode.KeepAnchor)
    
            if i == self.current_match_index:
                selection.format.setBackground(QColor("#FFA500"))
            else:
                selection.format.setBackground(QColor("#4A4A4A"))
    
            extra_selections.append(selection)
    
        # Use CodeEditor's method
        if hasattr(self.editor, 'set_find_replace_selections'):
            self.editor.set_find_replace_selections(extra_selections)
        else:
            self.editor.setExtraSelections(extra_selections)
    
        cursor = self.editor.textCursor()
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
        self.editor.setTextCursor(cursor)
        
        # CHANGED: Center the cursor instead of just making it visible
        self.editor.centerCursor()  # ← Changed from ensureCursorVisible()

    def clear_highlights(self):
        """Clear find/replace highlights"""
        if self.editor:
            if hasattr(self.editor, 'set_find_replace_selections'):
                self.editor.set_find_replace_selections([])
            else:
                self.editor.setExtraSelections([])
        self.matches = []
        self.current_match_index = -1

    def find_next(self):
        # If no matches exist yet, trigger a search first
        if not self.matches and self.find_input.text():
            self.on_find_text_changed()
        
        if not self.matches:
            return
    
        self.current_match_index = (self.current_match_index + 1) % len(self.matches)
        self.highlight_current_match()
        self.match_label.setText(f"{self.current_match_index + 1} of {len(self.matches)}")

    def find_previous(self):
        # If no matches exist yet, trigger a search first
        if not self.matches and self.find_input.text():
            self.on_find_text_changed()
        
        if not self.matches:
            return
    
        self.current_match_index = (self.current_match_index - 1) % len(self.matches)
        self.highlight_current_match()
        self.match_label.setText(f"{self.current_match_index + 1} of {len(self.matches)}")

    def replace_current(self):
        if not self.matches or self.current_match_index < 0:
            return

        start, end = self.matches[self.current_match_index]
        cursor = self.editor.textCursor()
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
        cursor.insertText(self.replace_input.text())

        self.on_find_text_changed()

        if self.matches and self.current_match_index < len(self.matches):
            self.find_next()

    def replace_all(self):
        if not self.matches:
            return

        count = len(self.matches)

        for start, end in reversed(self.matches):
            cursor = self.editor.textCursor()
            cursor.setPosition(start)
            cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
            cursor.insertText(self.replace_input.text())

        self.clear_highlights()
        self.match_label.setText(f"Replaced {count} occurrence(s)")
        QMessageBox.information(self, "Replace All", f"Replaced {count} occurrence(s)")
