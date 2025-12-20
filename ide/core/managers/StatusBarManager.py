# ============================================================================
# managers/statusbar_manager.py
# ============================================================================

from pathlib import Path
from PyQt6.QtWidgets import QLabel, QStatusBar
from ide.core.CodeEditor import CodeEditor


class StatusBarManager:
    """Manages status bar updates and information display"""

    def __init__(self, status_bar, parent):
        self.status_bar = status_bar
        self.parent = parent

        # Create status bar widgets
        self.status_message = QLabel("")
        self.line_col_label = QLabel("Ln 1, Col 1")
        self.encoding_label = QLabel("UTF-8")
        self.eol_label = QLabel("LF")
        self.language_label = QLabel("Plain Text")

        self._setup_status_bar()

    def _setup_status_bar(self):
        """Initialize status bar widgets"""
        self.status_bar.addWidget(self.status_message)
        self.status_bar.addPermanentWidget(QLabel("  "))

        self.line_col_label.setStyleSheet("color: #CCC; padding: 0 10px;")
        self.status_bar.addPermanentWidget(self.line_col_label)

        self.encoding_label.setStyleSheet("color: #CCC; padding: 0 10px;")
        self.status_bar.addPermanentWidget(self.encoding_label)

        self.eol_label.setStyleSheet("color: #CCC; padding: 0 10px;")
        self.status_bar.addPermanentWidget(self.eol_label)

        self.language_label.setStyleSheet("color: #CCC; padding: 0 10px;")
        self.status_bar.addPermanentWidget(self.language_label)

    def update_cursor_position(self, editor):
        """Update cursor position display"""
        if isinstance(editor, CodeEditor):
            cursor = editor.textCursor()
            line = cursor.blockNumber() + 1
            col = cursor.columnNumber() + 1
            self.line_col_label.setText(f"Ln {line}, Col {col}")

    def update_file_info(self, editor):
        """Update file information in status bar"""
        if not isinstance(editor, CodeEditor) or not editor.file_path:
            self.language_label.setText("Plain Text")
            self.eol_label.setText("LF")
            self.encoding_label.setText("UTF-8")
            self.line_col_label.setText("Ln 1, Col 1")
            return

        file_path = Path(editor.file_path)
        ext = file_path.suffix.lower()

        # Language detection
        language_map = {
            '.py': 'Python', '.js': 'JavaScript', '.ts': 'TypeScript',
            '.html': 'HTML', '.css': 'CSS', '.json': 'JSON',
            '.xml': 'XML', '.md': 'Markdown', '.txt': 'Plain Text',
            '.sh': 'Shell Script', '.bash': 'Bash', '.php': 'PHP',
            '.java': 'Java', '.c': 'C', '.cpp': 'C++',
            '.h': 'C/C++ Header', '.rs': 'Rust', '.go': 'Go',
            '.rb': 'Ruby', '.sql': 'SQL', '.yaml': 'YAML',
            '.yml': 'YAML', '.toml': 'TOML', '.ini': 'INI',
            '.cfg': 'Config', '.conf': 'Config', '.csv': 'CSV',
        }

        self.language_label.setText(language_map.get(ext, 'Plain Text'))

        # EOL detection
        try:
            with open(editor.file_path, 'rb') as f:
                content = f.read(1024)
                if b'\r\n' in content:
                    self.eol_label.setText("CRLF")
                elif b'\r' in content:
                    self.eol_label.setText("CR")
                else:
                    self.eol_label.setText("LF")
        except:
            self.eol_label.setText("LF")

        self.encoding_label.setText("UTF-8")
        self.update_cursor_position(editor)


