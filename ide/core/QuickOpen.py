from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLineEdit,
    QLabel,
    QListWidget,
    QListWidgetItem,
)
from PyQt6.QtGui import QColor
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from ide.core.FileScanner import FileScannerThread


class QuickOpenDialog(QDialog):
    """Quick file open dialog with fuzzy matching"""

    def __init__(self, project_paths, parent=None):
        super().__init__(parent)
        self.project_paths = project_paths
        self.parent_ide = parent
        self.all_files = []
        self.selected_file = None
        self.scanner_thread = None

        self.setWindowTitle("Quick Open File")
        self.setModal(True)
        self.setMinimumWidth(600)
        self.setMinimumHeight(400)

        self.setStyleSheet("""
            QDialog {
                background-color: #2B2B2B;
            }
            QLineEdit {
                background-color: #3C3F41;
                color: #CCC;
                border: 2px solid #4A9EFF;
                padding: 8px;
                font-size: 14px;
                border-radius: 4px;
            }
            QListWidget {
                background-color: #313335;
                color: #CCC;
                border: 1px solid #555;
                border-radius: 4px;
                font-size: 12px;
            }
            QListWidget::item {
                padding: 6px;
                border-bottom: 1px solid #3C3F41;
            }
            QListWidget::item:selected {
                background-color: #4A9EFF;
                color: white;
            }
            QListWidget::item:hover {
                background-color: #3C3F41;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Loading files...")
        self.search_input.setEnabled(False)
        self.search_input.textChanged.connect(self.on_search_changed)
        self.search_input.returnPressed.connect(self.accept_selection)
        layout.addWidget(self.search_input)

        self.info_label = QLabel("Scanning workspace...")
        self.info_label.setStyleSheet("color: #999; font-size: 11px;")
        layout.addWidget(self.info_label)

        self.results_list = QListWidget()
        self.results_list.itemDoubleClicked.connect(self.accept_selection)
        layout.addWidget(self.results_list)

        instructions = QLabel("↑↓ Navigate • Enter Open • Esc Cancel")
        instructions.setStyleSheet("color: #666; font-size: 10px;")
        layout.addWidget(instructions)

        self.start_file_scan()

    def start_file_scan(self):
        """Start scanning files in background thread"""
        if not self.project_paths:
            self.info_label.setText("No active projects selected")
            self.search_input.setEnabled(True)
            self.search_input.setPlaceholderText("No projects to search")
            return

        self.scanner_thread = FileScannerThread(self.project_paths, max_files=20000)
        self.scanner_thread.files_found.connect(self.on_files_loaded)
        self.scanner_thread.progress.connect(self.on_scan_progress)
        self.scanner_thread.finished.connect(self.scanner_thread.deleteLater)
        self.scanner_thread.start()

    def on_scan_progress(self, message):
        """Update progress message during scan"""
        self.info_label.setText(message)

    def on_files_loaded(self, files):
        """Called when file scanning completes"""
        self.all_files = files
        self.search_input.setEnabled(True)
        self.search_input.setPlaceholderText("Type to search files... (fuzzy matching)")
        self.search_input.setFocus()
        self.on_search_changed("")

    def fuzzy_match(self, pattern, text):
        """Fuzzy match - returns score or 0"""
        pattern = pattern.lower()
        text_lower = text.lower()

        if not pattern:
            return 1

        if pattern in text_lower:
            return 1000 + (100 - text_lower.index(pattern))

        score = 0
        pattern_idx = 0
        last_match_idx = -1

        for i, char in enumerate(text_lower):
            if pattern_idx < len(pattern) and char == pattern[pattern_idx]:
                score += 10
                if i == last_match_idx + 1:
                    score += 5
                if i == 0 or text_lower[i-1] in '/_-.':
                    score += 3
                last_match_idx = i
                pattern_idx += 1

        if pattern_idx != len(pattern):
            return 0

        score += 50 - min(50, text.count('/') * 10)
        return score

    def on_search_changed(self, text):
        """Filter and display matching files"""
        self.results_list.clear()

        if not text:
            matches = self.all_files[:50]
            total = len(self.all_files)
            self.info_label.setText(f"Showing 50 of {total:,} files (type to search)")
        else:
            scored_matches = []
            for rel_path, full_path in self.all_files:
                score = self.fuzzy_match(text, rel_path)
                if score > 0:
                    scored_matches.append((score, rel_path, full_path))

            scored_matches.sort(reverse=True, key=lambda x: x[0])
            matches = [(rel, full) for score, rel, full in scored_matches[:100]]

            if scored_matches:
                self.info_label.setText(f"Found {len(scored_matches):,} matches")
            else:
                self.info_label.setText("No matches found")

        for rel_path, full_path in matches:
            item = QListWidgetItem(rel_path)
            item.setData(Qt.ItemDataRole.UserRole, full_path)

            if rel_path.endswith('.py'):
                item.setForeground(QColor("#FFC66D"))
            elif rel_path.endswith(('.js', '.ts', '.jsx', '.tsx')):
                item.setForeground(QColor("#F7CA18"))
            elif rel_path.endswith(('.html', '.css')):
                item.setForeground(QColor("#E67E22"))
            elif rel_path.endswith(('.json', '.yaml', '.yml', '.toml')):
                item.setForeground(QColor("#9B59B6"))
            elif rel_path.endswith(('.md', '.txt')):
                item.setForeground(QColor("#3498DB"))

            self.results_list.addItem(item)

        if self.results_list.count() > 0:
            self.results_list.setCurrentRow(0)

    def accept_selection(self):
        """Open the selected file"""
        current_item = self.results_list.currentItem()
        if current_item:
            self.selected_file = current_item.data(Qt.ItemDataRole.UserRole)
            self.accept()

    def keyPressEvent(self, event):
        """Handle key presses"""
        if event.key() == Qt.Key.Key_Escape:
            self.reject()
        elif event.key() in (Qt.Key.Key_Up, Qt.Key.Key_Down):
            self.results_list.keyPressEvent(event)
        elif event.key() == Qt.Key.Key_Return:
            self.accept_selection()
        else:
            self.search_input.keyPressEvent(event)
            self.search_input.setFocus()
