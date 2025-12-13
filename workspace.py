#!/usr/bin/env python3
"""
Workspace IDE - Integrated with Ollama
Fixed: Active tab highlighting and full path tooltips
"""

import sys
import os
import subprocess
import json
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QTreeView, QTabWidget, QPlainTextEdit,
    QPushButton, QLabel, QMessageBox, QTextEdit, QTextBrowser, QToolBar, QStatusBar,
    QSizePolicy, QMenu, QInputDialog, QLineEdit, QComboBox, QDialog,
    QSpinBox, QCheckBox, QFormLayout, QDialogButtonBox, QFrame, QListWidget,
    QListWidgetItem, QScrollArea, QStyledItemDelegate, QTabBar
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSettings, QPoint, QRegularExpression, QSize, QTimer
from PyQt6.QtGui import QFont, QColor, QTextCharFormat, QSyntaxHighlighter, QAction, QFileSystemModel, QTextCursor, QTextDocument, QPainter, QTextFormat, QShortcut, QKeySequence
from PyQt6.QtWidgets import QMessageBox, QSpacerItem, QGridLayout

VERSION = "0.0.1"
WORKSPACE_PATH = "workspace"

# ---------------------- Custom Tab Bar with Styling ----------------------
class StyledTabBar(QTabBar):
    """Custom tab bar with active/inactive styling and modified indicators"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDrawBase(False)
        self.setExpanding(False)
        self.modified_tabs = set()  # Track which tabs are modified

        # Apply comprehensive stylesheet
        self.setStyleSheet("""
            QTabBar::tab {
                background-color: #2B2B2B;
                color: #999999;
                border: none;
                border-bottom: 2px solid transparent;
                padding: 8px 24px 8px 16px;
                margin-right: 2px;
                min-width: 80px;
            }

            QTabBar::tab:selected {
                background-color: #2B2B2B;
                color: #4A9EFF;
                font-weight: bold;
                border-bottom: 2px solid #4A9EFF;
            }

            QTabBar::tab:!selected:hover {
                background-color: #3C3F41;
                color: #CCCCCC;
            }

            QTabBar::tab:selected:hover {
                background-color: #2B2B2B;
                color: #4A9EFF;
            }

            QTabBar::close-button {
                subcontrol-position: right;
                margin: 2px;
                width: 14px;
                height: 14px;
                border-radius: 7px;
                background-color: #555555;
            }

            QTabBar::close-button:hover {
                background-color: #E74C3C;
            }
        """)

    def set_tab_modified(self, index, modified):
        """Mark a tab as modified or unmodified"""
        if modified:
            self.modified_tabs.add(index)
        else:
            self.modified_tabs.discard(index)
        self.update()  # Trigger repaint

    def tabRemoved(self, index):
        """Clean up modified tabs tracking when tab is removed"""
        # Shift indices down for tabs after the removed one
        new_modified = set()
        for i in self.modified_tabs:
            if i < index:
                new_modified.add(i)
            elif i > index:
                new_modified.add(i - 1)
        self.modified_tabs = new_modified
        super().tabRemoved(index)

    def paintEvent(self, event):
        """Custom paint to show modified indicator"""
        super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw modified indicators
        for index in range(self.count()):
            if index in self.modified_tabs:
                rect = self.tabRect(index)

                # Draw a filled circle (dot) on the left side of the tab
                center_x = rect.left() + 10
                center_y = rect.center().y()
                radius = 4

                # Choose color based on whether tab is selected
                if index == self.currentIndex():
                    painter.setBrush(QColor("#4A9EFF"))  # Blue for active modified tab
                    painter.setPen(QColor("#4A9EFF"))
                else:
                    painter.setBrush(QColor("#FF6B6B"))  # Red for inactive modified tab
                    painter.setPen(QColor("#FF6B6B"))

                painter.drawEllipse(center_x - radius, center_y - radius, radius * 2, radius * 2)

        painter.end()


class StyledTabWidget(QTabWidget):
    """Custom tab widget with styled tab bar"""

    def __init__(self, parent=None):
        super().__init__(parent)

        # Replace default tab bar with custom one
        self.custom_tab_bar = StyledTabBar(self)
        self.setTabBar(self.custom_tab_bar)

        # Style the tab widget itself
        self.setStyleSheet("""
            QTabWidget::pane {
                border: none;
                background-color: #2B2B2B;
            }

            QTabWidget::tab-bar {
                alignment: left;
            }
        """)

        # Enable tooltips
        self.setMouseTracking(True)
        self.tabBar().setMouseTracking(True)

    def set_tab_modified(self, index, modified):
        """Mark a tab as modified"""
        self.custom_tab_bar.set_tab_modified(index, modified)


# ---------------------- Custom Tree View Delegate ----------------------
class ProjectHighlightDelegate(QStyledItemDelegate):
    """Custom delegate to highlight active projects in tree view"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.active_projects = set()

    def set_active_projects(self, projects):
        """Update list of active projects"""
        self.active_projects = set(str(Path(p).name) for p in projects)

    def paint(self, painter, option, index):
        """Custom paint to highlight active projects"""
        model = index.model()
        file_path = model.filePath(index)
        path = Path(file_path)

        parent_path = path.parent
        workspace_path = Path.home() / WORKSPACE_PATH

        is_project = (parent_path == workspace_path and
                     path.is_dir() and
                     path.name in self.active_projects)

        if is_project:
            painter.save()
            bg_color = QColor("#2D5A2D")
            painter.fillRect(option.rect, bg_color)
            painter.setPen(QColor("#7FFF7F"))
            text = index.data(Qt.ItemDataRole.DisplayRole)
            font = option.font
            font.setBold(True)
            painter.setFont(font)
            text_rect = option.rect.adjusted(5, 0, 0, 0)
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter, text)
            painter.restore()
        else:
            super().paint(painter, option, index)


# ---------------------- Projects Panel ----------------------
class ProjectsPanel(QWidget):
    """Panel showing workspace projects that can be activated"""

    project_selected = pyqtSignal(str)
    projects_changed = pyqtSignal()

    def __init__(self, workspace_path, parent=None):
        super().__init__(parent)
        self.workspace_path = workspace_path
        self.active_projects = set()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        header = QHBoxLayout()
        title = QLabel("Active Projects")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        header.addWidget(title)

        refresh_btn = QPushButton("↻")
        refresh_btn.setFixedWidth(30)
        refresh_btn.setToolTip("Refresh project list")
        refresh_btn.clicked.connect(self.scan_projects)
        header.addWidget(refresh_btn)

        layout.addLayout(header)

        self.info_label = QLabel("Check projects to include in Quick Open (Ctrl+P)")
        self.info_label.setStyleSheet("color: #999; font-size: 10px;")
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)

        self.projects_list = QListWidget()
        self.projects_list.itemChanged.connect(self.on_project_toggled)
        layout.addWidget(self.projects_list)

        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet("color: #666; font-size: 10px;")
        layout.addWidget(self.stats_label)

        self.scan_projects()

    def scan_projects(self):
        """Scan workspace for project directories"""
        self.projects_list.clear()

        if not self.workspace_path.exists():
            return

        projects = []
        for item in self.workspace_path.iterdir():
            if item.is_dir() and not item.name.startswith('.'):
                projects.append(item)

        projects.sort(key=lambda p: p.name.lower())

        for project_path in projects:
            item = QListWidgetItem(project_path.name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)

            if str(project_path) in self.active_projects:
                item.setCheckState(Qt.CheckState.Checked)
            else:
                item.setCheckState(Qt.CheckState.Unchecked)

            item.setData(Qt.ItemDataRole.UserRole, str(project_path))

            try:
                file_count = sum(1 for _ in project_path.rglob('*') if _.is_file())
                item.setToolTip(f"{project_path}\n~{file_count} files")
            except:
                item.setToolTip(str(project_path))

            self.projects_list.addItem(item)

        self.update_stats()

    def on_project_toggled(self, item):
        """Handle project checkbox toggle"""
        project_path = item.data(Qt.ItemDataRole.UserRole)

        if item.checkState() == Qt.CheckState.Checked:
            self.active_projects.add(project_path)
        else:
            self.active_projects.discard(project_path)

        self.update_stats()
        self.project_selected.emit(project_path)
        self.projects_changed.emit()

    def update_stats(self):
        """Update statistics label"""
        total = self.projects_list.count()
        active = len(self.active_projects)
        self.stats_label.setText(f"{active} of {total} projects active")

    def get_active_projects(self):
        """Get list of active project paths"""
        return list(self.active_projects)

    def set_active_projects(self, projects):
        """Set which projects are active"""
        self.active_projects = set(projects)
        for i in range(self.projects_list.count()):
            item = self.projects_list.item(i)
            project_path = item.data(Qt.ItemDataRole.UserRole)
            if project_path in self.active_projects:
                item.setCheckState(Qt.CheckState.Checked)
            else:
                item.setCheckState(Qt.CheckState.Unchecked)
        self.update_stats()
        self.projects_changed.emit()


# ---------------------- File Scanner Thread ----------------------
class FileScannerThread(QThread):
    """Background thread to scan workspace files"""
    files_found = pyqtSignal(list)
    progress = pyqtSignal(str)

    def __init__(self, project_paths, max_files=20000):
        super().__init__()
        self.project_paths = project_paths
        self.max_files = max_files

    def run(self):
        """Scan files in background"""
        files = []

        ignore_dirs = {'.git', '__pycache__', 'node_modules', '.venv', 'venv',
                      'workspace-env', '.idea', '.vscode', 'dist', 'build',
                      '.pytest_cache', '.mypy_cache', 'eggs', '.eggs', 'env',
                      'site-packages', '.tox'}

        ignore_exts = {'.pyc', '.pyo', '.so', '.dylib', '.dll', '.exe', '.o', '.a',
                      '.class', '.jar', '.war', '.log', '.tmp', '.cache'}

        for project_path in self.project_paths:
            project_path = Path(project_path)
            if not project_path.exists():
                continue

            self.progress.emit(f"Scanning {project_path.name}...")

            for root, dirs, filenames in os.walk(project_path):
                if len(files) >= self.max_files:
                    self.progress.emit(f"Reached limit of {self.max_files} files")
                    files.sort()
                    self.files_found.emit(files)
                    return

                dirs[:] = [d for d in dirs if d not in ignore_dirs and not d.startswith('.')]

                for file in filenames:
                    if file.startswith('.') or any(file.endswith(ext) for ext in ignore_exts):
                        continue

                    full_path = Path(root) / file
                    try:
                        if full_path.stat().st_size > 10_000_000:
                            continue

                        rel_path = full_path.relative_to(project_path.parent)
                        files.append((str(rel_path), str(full_path)))
                    except (ValueError, OSError):
                        continue

        files.sort()
        self.files_found.emit(files)


# ---------------------- Quick Open Dialog ----------------------
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


# ---------------------- Settings Dialog ----------------------
class SettingsDialog(QDialog):
    """Settings dialog for IDE configuration"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("IDE Settings")
        self.setMinimumWidth(500)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.explorer_width = QSpinBox()
        self.explorer_width.setRange(150, 500)
        self.explorer_width.setValue(300)
        self.explorer_width.setSuffix(" px")
        form.addRow("Explorer Width:", self.explorer_width)

        self.terminal_height = QSpinBox()
        self.terminal_height.setRange(100, 600)
        self.terminal_height.setValue(200)
        self.terminal_height.setSuffix(" px")
        form.addRow("Terminal Height:", self.terminal_height)

        self.editor_font_size = QSpinBox()
        self.editor_font_size.setRange(8, 24)
        self.editor_font_size.setValue(11)
        form.addRow("Editor Font Size:", self.editor_font_size)

        self.terminal_font_size = QSpinBox()
        self.terminal_font_size.setRange(8, 18)
        self.terminal_font_size.setValue(10)
        form.addRow("Terminal Font Size:", self.terminal_font_size)

        self.tab_width = QSpinBox()
        self.tab_width.setRange(2, 8)
        self.tab_width.setValue(4)
        self.tab_width.setSuffix(" spaces")
        form.addRow("Tab Width:", self.tab_width)

        self.restore_session = QCheckBox()
        self.restore_session.setChecked(True)
        form.addRow("Restore Open Tabs:", self.restore_session)

        self.show_line_numbers = QCheckBox()
        self.show_line_numbers.setChecked(True)
        form.addRow("Show Line Numbers:", self.show_line_numbers)

        self.auto_save = QCheckBox()
        self.auto_save.setChecked(False)
        form.addRow("Auto-save on Tab Switch:", self.auto_save)

        self.ollama_timeout = QSpinBox()
        self.ollama_timeout.setRange(30, 600)
        self.ollama_timeout.setValue(180)
        self.ollama_timeout.setSuffix(" seconds")
        form.addRow("Ollama Timeout:", self.ollama_timeout)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_settings(self):
        """Return current settings as dict"""
        return {
            'explorer_width': self.explorer_width.value(),
            'terminal_height': self.terminal_height.value(),
            'editor_font_size': self.editor_font_size.value(),
            'terminal_font_size': self.terminal_font_size.value(),
            'tab_width': self.tab_width.value(),
            'restore_session': self.restore_session.isChecked(),
            'show_line_numbers': self.show_line_numbers.isChecked(),
            'auto_save': self.auto_save.isChecked(),
            'ollama_timeout': self.ollama_timeout.value()
        }

    def set_settings(self, settings):
        """Load settings into dialog"""
        self.explorer_width.setValue(settings.get('explorer_width', 300))
        self.terminal_height.setValue(settings.get('terminal_height', 200))
        self.editor_font_size.setValue(settings.get('editor_font_size', 11))
        self.terminal_font_size.setValue(settings.get('terminal_font_size', 10))
        self.tab_width.setValue(settings.get('tab_width', 4))
        self.restore_session.setChecked(settings.get('restore_session', True))
        self.show_line_numbers.setChecked(settings.get('show_line_numbers', True))
        self.auto_save.setChecked(settings.get('auto_save', False))
        self.ollama_timeout.setValue(settings.get('ollama_timeout', 180))



class DocumentDialog(QDialog):
    """Dialog to display README.md documentation"""

    def __init__(self, readme_path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Workspace IDE")
        self.setMinimumWidth(800)
        self.setMinimumHeight(800)

        # Apply dark theme styling
        self.setStyleSheet("""
            QDialog {
                background-color: #2B2B2B;
            }
            QTextBrowser {
                background-color: #1E1E1E;
                color: #CCCCCC;
                border: 1px solid #3C3F41;
                padding: 15px;
                font-size: 15px;
            }
            QPushButton {
                background-color: #3C3F41;
                color: #CCC;
                border: 1px solid #555;
                padding: 6px 20px;
                border-radius: 3px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #4A9EFF;
                color: white;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # Header
        header = QLabel("📖 Workspace IDE")
        header.setStyleSheet("font-size: 16px; font-weight: bold; color: #4A9EFF; padding: 5px;")
        layout.addWidget(header)

        # Text browser to display markdown (with HTML rendering)
        #self.text_browser = QTextEdit()
        #self.text_browser.setReadOnly(True)
        self.text_browser = QTextBrowser()
        self.text_browser.setOpenExternalLinks(True)  # Optional: allows clicking links

        layout.addWidget(self.text_browser)

        # Load and display README
        self.load_readme(readme_path)

        # Close button
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

    def load_readme(self, readme_path):
        """Load and display README.md file"""
        try:
            if not readme_path.exists():
                self.text_browser.setHtml(
                    "<h2 style='color: #E74C3C;'>⚠️ README.md Not Found</h2>"
                    f"<p>The documentation file was not found at:</p>"
                    f"<p><code>{readme_path}</code></p>"
                    "<p>Please create a README.md file in your workspace root directory.</p>"
                )
                return

            with open(readme_path, 'r', encoding='utf-8') as f:
                markdown_content = f.read()

            # Convert markdown to HTML
            html_content = self.markdown_to_html(markdown_content)

            # Apply custom styling to the HTML
            styled_html = f"""
            <html>
            <head>
                <style>
                    body {{
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif;
                        line-height: 1.6;
                        color: #CCCCCC;
                    }}
                    h1 {{
                        color: #4A9EFF;
                        border-bottom: 2px solid #4A9EFF;
                        padding-bottom: 10px;
                        margin-top: 24px;
                        margin-bottom: 16px;
                    }}
                    h2 {{
                        color: #5DADE2;
                        margin-top: 24px;
                        margin-bottom: 12px;
                    }}
                    h3 {{
                        color: #7FB3D5;
                        margin-top: 20px;
                        margin-bottom: 10px;
                    }}
                    h4 {{
                        color: #85C1E9;
                        margin-top: 16px;
                        margin-bottom: 8px;
                    }}
                    code {{
                        background-color: #3C3F41;
                        padding: 2px 6px;
                        border-radius: 3px;
                        color: #FFC66D;
                        font-family: 'Courier New', monospace;
                        font-size: 0.9em;
                    }}
                    pre {{
                        background-color: #1E1E1E;
                        border: 1px solid #3C3F41;
                        border-radius: 5px;
                        padding: 15px;
                        overflow-x: auto;
                        margin: 12px 0;
                        line-height: 1.4;
                    }}
                    pre code {{
                        background: none;
                        padding: 0;
                        color: #A9B7C6;
                        display: block;
                    }}
                    a {{ color: #4A9EFF; text-decoration: none; }}
                    a:hover {{ text-decoration: underline; }}
                    ul, ol {{
                        margin-left: 20px;
                        margin-top: 8px;
                        margin-bottom: 8px;
                        padding-left: 20px;
                    }}
                    li {{
                        margin: 2px 0;
                        padding: 0;
                        line-height: 1.5;
                    }}
                    li p {{
                        margin: 0;
                        padding: 0;
                    }}
                    blockquote {{
                        border-left: 4px solid #4A9EFF;
                        padding-left: 15px;
                        margin-left: 0;
                        margin-top: 12px;
                        margin-bottom: 12px;
                        color: #999;
                        font-style: italic;
                    }}
                    table {{
                        border-collapse: collapse;
                        width: 100%;
                        margin: 15px 0;
                    }}
                    th, td {{
                        border: 1px solid #3C3F41;
                        padding: 10px;
                        text-align: left;
                    }}
                    th {{
                        background-color: #3C3F41;
                        color: #4A9EFF;
                        font-weight: bold;
                    }}
                    img {{
                        max-width: 100%;
                        height: auto;
                        display: inline-block;
                        margin: 2px;
                    }}
                    hr {{
                        border: none;
                        border-top: 1px solid #3C3F41;
                        margin: 20px 0;
                    }}
                    p {{
                        margin: 8px 0;
                    }}
                </style>
            </head>
            <body>
                {html_content}
            </body>
            </html>
            """

            self.text_browser.setHtml(styled_html)

        except Exception as e:
            self.text_browser.setHtml(
                f"<h2 style='color: #E74C3C;'>⚠️ Error Loading Documentation</h2>"
                f"<p>An error occurred while loading the README.md file:</p>"
                f"<p><code>{str(e)}</code></p>"
            )


    def markdown_to_html(self, markdown_text):
        """Convert markdown to HTML using markdown library with better list handling"""
        try:
            import markdown

            html = markdown.markdown(
                markdown_text,
                extensions=[
                    'fenced_code',
                    'tables',
                    'extra',
                    'nl2br',                    # Converts newlines to <br> (good for simple line breaks)
                    'sane_lists'                # THIS IS THE KEY: removes <p> tags inside list items
                ]
            )

            return html

        except ImportError:
            return """
                <h2 style='color: #E74C3C;'>⚠️ Markdown Package Required</h2>
                <p>The <code>markdown</code> package is required to display documentation.</p>
                <p><strong>To install it, run:</strong></p>
                <pre><code>pip install markdown</code></pre>
                <p>After installation, restart the IDE and try again.</p>
            """




# ---------------------- Syntax Highlighter ----------------------
class PythonHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.keywords = [
            'False', 'None', 'True', 'and', 'as', 'assert', 'async', 'await',
            'break', 'class', 'continue', 'def', 'del', 'elif', 'else', 'except',
            'finally', 'for', 'from', 'global', 'if', 'import', 'in', 'is',
            'lambda', 'nonlocal', 'not', 'or', 'pass', 'raise', 'return',
            'try', 'while', 'with', 'yield'
        ]
        self.keyword_format = QTextCharFormat()
        self.keyword_format.setForeground(QColor("#CC7832"))
        self.string_format = QTextCharFormat()
        self.string_format.setForeground(QColor("#6A8759"))
        self.comment_format = QTextCharFormat()
        self.comment_format.setForeground(QColor("#808080"))

    def highlightBlock(self, text):
        for keyword in self.keywords:
            start = 0
            while True:
                index = text.find(keyword, start)
                if index == -1:
                    break
                if (index == 0 or not text[index - 1].isalnum()) and (
                    index + len(keyword) == len(text)
                    or not text[index + len(keyword)].isalnum()
                ):
                    self.setFormat(index, len(keyword), self.keyword_format)
                start = index + 1

        for quote in ['"', "'"]:
            start = 0
            while True:
                start = text.find(quote, start)
                if start == -1:
                    break
                end = text.find(quote, start + 1)
                if end == -1:
                    break
                self.setFormat(start, end - start + 1, self.string_format)
                start = end + 1

        comment_index = text.find('#')
        if comment_index >= 0:
            self.setFormat(comment_index, len(text) - comment_index, self.comment_format)


# ---------------------- Terminal Widget ----------------------
class Terminal(QTextEdit):
    def __init__(self, font_size=10):
        super().__init__()
        self.setFont(QFont("Monospace", font_size))
        self.setStyleSheet("QTextEdit { background-color: #1E1E1E; color: #CCCCCC; border: none; }")
        self.current_dir = str(Path.home() / WORKSPACE_PATH)
        self.command_history = []
        self.history_index = -1

        self.append("=== Simple Terminal ===\n")
        self.append("Note: This is a basic terminal. For complex programs, use a real terminal.\n\n")
        self.append(f"Working directory: {self.current_dir}\n\n")
        self.show_prompt()

    def show_prompt(self):
        self.append(f"{self.current_dir}$ ")
        self.command_start_pos = self.textCursor().position()

    def execute_command(self, command):
        command = command.strip()
        if not command:
            self.show_prompt()
            return

        self.command_history.append(command)
        self.history_index = len(self.command_history)

        if command.startswith("cd "):
            target = command[3:].strip()
            if target:
                try:
                    if target.startswith("~"):
                        target = str(Path.home()) + target[1:]
                    p = Path(target)
                    if not p.is_absolute():
                        p = Path(self.current_dir) / p
                    p = p.resolve()
                    if p.exists() and p.is_dir():
                        self.current_dir = str(p)
                        self.append("\n")
                    else:
                        self.append(f"\ncd: no such directory: {target}\n")
                except Exception as e:
                    self.append(f"\ncd error: {e}\n")
            self.show_prompt()
            return

        if command == "clear":
            self.clear()
            self.append("=== Simple Terminal ===\n")
            self.show_prompt()
            return

        if command == "pwd":
            self.append(f"\n{self.current_dir}\n")
            self.show_prompt()
            return

        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=self.current_dir,
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.stdout:
                self.append("\n" + result.stdout)
            if result.stderr:
                self.append(result.stderr)
        except subprocess.TimeoutExpired:
            self.append("\n[Command timed out after 10 seconds]\n")
        except Exception as e:
            self.append(f"\nError: {e}\n")

        self.show_prompt()

    def keyPressEvent(self, event):
        cursor_pos = self.textCursor().position()

        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            cursor = self.textCursor()
            cursor.setPosition(self.command_start_pos)
            cursor.movePosition(QTextCursor.MoveOperation.End, QTextCursor.MoveMode.KeepAnchor)
            cmd = cursor.selectedText()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self.setTextCursor(cursor)
            self.execute_command(cmd)
            return

        elif event.key() == Qt.Key.Key_Backspace:
            if cursor_pos > self.command_start_pos:
                super().keyPressEvent(event)
            return

        elif event.key() == Qt.Key.Key_Up:
            if self.command_history and self.history_index > 0:
                self.history_index -= 1
                self.replace_command(self.command_history[self.history_index])
            return

        elif event.key() == Qt.Key.Key_Down:
            if self.command_history and self.history_index < len(self.command_history) - 1:
                self.history_index += 1
                self.replace_command(self.command_history[self.history_index])
            return

        super().keyPressEvent(event)

    def replace_command(self, text):
        cursor = self.textCursor()
        cursor.setPosition(self.command_start_pos)
        cursor.movePosition(QTextCursor.MoveOperation.End, QTextCursor.MoveMode.KeepAnchor)
        cursor.removeSelectedText()
        cursor.insertText(text)


# ---------------------- Find & Replace Widget ----------------------
class FindReplaceWidget(QFrame):
    """Find and Replace panel widget"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.editor = None
        self.current_match_index = -1
        self.matches = []

        self.setStyleSheet("""
            QFrame {
                background-color: #2B2B2B;
                border-bottom: 1px solid #555;
            }
            QLineEdit {
                background-color: #3C3F41;
                color: #CCC;
                border: 1px solid #555;
                padding: 3px;
                border-radius: 2px;
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
            }
            QPushButton:hover {
                background-color: #4A4A4A;
            }
            QPushButton:pressed {
                background-color: #2A2A2A;
            }
            QCheckBox {
                color: #CCC;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(3)

        find_row = QHBoxLayout()
        self.find_input = QLineEdit()
        self.find_input.setPlaceholderText("Find")
        self.find_input.textChanged.connect(self.on_find_text_changed)
        self.find_input.returnPressed.connect(self.find_next)
        find_row.addWidget(self.find_input)

        self.match_label = QLabel("No matches")
        self.match_label.setStyleSheet("color: #999;")
        find_row.addWidget(self.match_label)

        prev_btn = QPushButton("↑")
        prev_btn.setToolTip("Previous (Shift+F3)")
        prev_btn.clicked.connect(self.find_previous)
        find_row.addWidget(prev_btn)

        next_btn = QPushButton("↓")
        next_btn.setToolTip("Next (F3)")
        next_btn.clicked.connect(self.find_next)
        find_row.addWidget(next_btn)

        layout.addLayout(find_row)

        replace_row = QHBoxLayout()
        self.replace_input = QLineEdit()
        self.replace_input.setPlaceholderText("Replace")
        self.replace_input.returnPressed.connect(self.replace_current)
        replace_row.addWidget(self.replace_input)

        replace_btn = QPushButton("Replace")
        replace_btn.clicked.connect(self.replace_current)
        replace_row.addWidget(replace_btn)

        replace_all_btn = QPushButton("Replace All")
        replace_all_btn.clicked.connect(self.replace_all)
        replace_row.addWidget(replace_all_btn)

        layout.addLayout(replace_row)

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
        close_btn.setFixedWidth(25)
        close_btn.clicked.connect(self.hide)
        options_row.addWidget(close_btn)

        layout.addLayout(options_row)

        self.hide()

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
        if not self.editor or not self.matches:
            return

        extra_selections = []
        for start, end in self.matches:
            selection = QTextEdit.ExtraSelection()
            selection.cursor = self.editor.textCursor()
            selection.cursor.setPosition(start)
            selection.cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
            selection.format.setBackground(QColor("#4A4A4A"))
            extra_selections.append(selection)

        self.editor.setExtraSelections(extra_selections)

    def highlight_current_match(self):
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

        self.editor.setExtraSelections(extra_selections)

        cursor = self.editor.textCursor()
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
        self.editor.setTextCursor(cursor)
        self.editor.ensureCursorVisible()

    def clear_highlights(self):
        if self.editor:
            self.editor.setExtraSelections([])
        self.matches = []
        self.current_match_index = -1

    def find_next(self):
        if not self.matches:
            return

        self.current_match_index = (self.current_match_index + 1) % len(self.matches)
        self.highlight_current_match()
        self.match_label.setText(f"{self.current_match_index + 1} of {len(self.matches)}")

    def find_previous(self):
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


class OllamaWorker(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, model, prompt, timeout=180):
        super().__init__()
        self.model = model
        self.prompt = prompt
        self.timeout = timeout

    def run(self):
        try:
            result = subprocess.run(
                ["ollama", "run", self.model, self.prompt],
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            self.finished.emit(result.stdout.strip())
        except subprocess.TimeoutExpired:
            self.error.emit(f"Ollama request timed out after {self.timeout} seconds")
        except Exception as e:
            self.error.emit(str(e))


class OllamaChatWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_ide = parent
        layout = QVBoxLayout(self)

        top_bar = QHBoxLayout()
        top_bar.addWidget(QLabel("Model:"))

        self.model_box = QComboBox()
        top_bar.addWidget(self.model_box)

        self.refresh_btn = QPushButton("Refresh Models")
        self.refresh_btn.clicked.connect(self.refresh_models)
        top_bar.addWidget(self.refresh_btn)

        self.ps_btn = QPushButton("Show Loaded Models")
        self.ps_btn.clicked.connect(self.show_ollama_ps)
        top_bar.addWidget(self.ps_btn)

        top_bar.addStretch()

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #999;")
        top_bar.addWidget(self.status_label)

        layout.addLayout(top_bar)

        self.chat = QTextEdit()
        self.chat.setReadOnly(True)
        self.chat.setStyleSheet("background:#1E1E1E;color:#CCC;")
        layout.addWidget(self.chat)

        bottom = QHBoxLayout()
        self.input = QLineEdit()
        self.input.returnPressed.connect(self.send_message)
        bottom.addWidget(self.input)
        self.send_btn = QPushButton("Send")
        self.send_btn.clicked.connect(self.send_message)
        bottom.addWidget(self.send_btn)
        layout.addLayout(bottom)

        self.worker = None
        self.refresh_models()

    def get_timeout(self):
        if self.parent_ide and hasattr(self.parent_ide, 'settings'):
            return self.parent_ide.settings.get('ollama_timeout', 180)
        return 180

    def show_ollama_ps(self):
        try:
            result = subprocess.run(
                ["ollama", "ps"],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.stdout.strip():
                self.chat.append("\n=== Currently Loaded Models ===\n")
                self.chat.append(result.stdout)
                self.chat.append("================================\n")
            else:
                self.chat.append("\n=== No models currently loaded ===\n")
        except Exception as e:
            self.chat.append(f"\nError checking loaded models: {e}\n")

    def refresh_models(self):
        self.model_box.clear()
        try:
            r = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=5)
            lines = [l.strip() for l in r.stdout.splitlines() if l.strip()]
            if len(lines) > 1:
                for line in lines[1:]:
                    parts = line.split()
                    if parts:
                        self.model_box.addItem(parts[0])
            if self.model_box.count() == 0:
                self.model_box.addItem("No models found")
        except Exception:
            self.model_box.addItem("ollama not available")

    def send_message(self):
        text = self.input.text().strip()
        if not text:
            return

        model = self.model_box.currentText()
        if model in ["No models found", "ollama not available"]:
            self.chat.append("Error: No valid Ollama model selected\n")
            return

        self.chat.append(f"You: {text}\n")
        self.input.clear()
        self.send_btn.setEnabled(False)
        self.status_label.setText("⏳ Waiting...")
        self.chat.append("Ollama: [thinking...]\n")

        timeout = self.get_timeout()
        self.worker = OllamaWorker(model, text, timeout)
        self.worker.finished.connect(self.handle_response)
        self.worker.error.connect(self.handle_error)
        self.worker.start()

    def send_text_message(self, text):
        if not text.strip():
            return

        model = self.model_box.currentText()
        if model in ["No models found", "ollama not available"]:
            self.chat.append("Error: No valid Ollama model selected\n")
            return

        self.chat.append(f"You: {text}\n")
        self.send_btn.setEnabled(False)
        self.status_label.setText("⏳ Waiting...")
        self.chat.append("Ollama: [thinking...]\n")

        timeout = self.get_timeout()
        self.worker = OllamaWorker(model, text, timeout)
        self.worker.finished.connect(self.handle_response)
        self.worker.error.connect(self.handle_error)
        self.worker.start()

    def handle_response(self, response):
        text = self.chat.toPlainText()
        lines = text.split('\n')
        if lines and '[thinking...]' in lines[-2]:
            lines = lines[:-2]
            self.chat.setPlainText('\n'.join(lines))

        self.chat.append(f"Ollama: {response}\n")
        self.send_btn.setEnabled(True)
        self.status_label.setText("✓ Ready")

    def handle_error(self, error_msg):
        text = self.chat.toPlainText()
        lines = text.split('\n')
        if lines and '[thinking...]' in lines[-2]:
            lines = lines[:-2]
            self.chat.setPlainText('\n'.join(lines))

        self.chat.append(f"Error: {error_msg}\n")
        self.send_btn.setEnabled(True)
        self.status_label.setText("✗ Error")


class WorkspaceIDE(QMainWindow):
    def __init__(self):
        super().__init__()
        self.workspace_path = Path.home() / WORKSPACE_PATH
        self.current_project = None
        self.config_file = self.workspace_path / ".workspace_ide_config.json"
        self.session_file = self.workspace_path / ".workspace_ide_session.json"

        self.quick_open_cache = []
        self.quick_open_cache_projects = set()
        self.quick_open_cache_time = 0

        self.settings = self.load_settings()

        self.init_ui()
        self.ensure_workspace()

        if self.settings.get('restore_session', True):
            self.restore_session()

        active_projects = self.settings.get('active_projects', [])
        if active_projects:
            self.projects_panel.set_active_projects(active_projects)
            self.update_tree_highlighting()

        self.apply_initial_layout()

# =====================================================================
# PART 2: Add this method to the WorkspaceIDE class
# Add it near the end with other menu action methods (around line 2350)
# =====================================================================

    def show_documentation(self):
        """Show documentation from README.md"""
        readme_path = self.workspace_path / "README.md"
        dialog = DocumentDialog(readme_path, self)
        dialog.exec()

    def show_changelog(self):
        """Show documentation from CHANGELOG.md"""
        path = self.workspace_path / "CHANGELOG.md"
        dialog = DocumentDialog(path, self)
        dialog.exec()

    def update_tree_highlighting(self):
        active_projects = self.projects_panel.get_active_projects()
        self.tree_delegate.set_active_projects(active_projects)
        self.tree.viewport().update()

    def show_tab_context_menu(self, position):
        tab_index = self.tabs.tabBar().tabAt(position)
        if tab_index < 0:
            return

        menu = QMenu(self)

        ai_menu = menu.addMenu("🤖 AI Actions")
        send_all_action = ai_menu.addAction("Send Entire File to Ollama")
        send_selection_action = ai_menu.addAction("Send Selection to Ollama")

        menu.addSeparator()

        save_action = menu.addAction("💾 Save")
        close_action = menu.addAction("✖️ Close")
        close_others_action = menu.addAction("Close Others")
        close_all_action = menu.addAction("Close All")

        action = menu.exec(self.tabs.tabBar().mapToGlobal(position))

        if action == send_all_action:
            self.send_tab_to_ollama(tab_index, send_all=True)
        elif action == send_selection_action:
            self.send_tab_to_ollama(tab_index, send_all=False)
        elif action == save_action:
            self.save_tab(tab_index)
        elif action == close_action:
            self.close_tab(tab_index)
        elif action == close_others_action:
            self.close_other_tabs(tab_index)
        elif action == close_all_action:
            self.close_all_tabs()

    def send_tab_to_ollama(self, tab_index, send_all=False):
        editor = self.tabs.widget(tab_index)
        if not isinstance(editor, CodeEditor):
            return

        if send_all:
            text_to_send = editor.toPlainText()
            text_type = "entire file"
        else:
            cursor = editor.textCursor()
            if cursor.hasSelection():
                text_to_send = cursor.selectedText().replace('\u2029', '\n')
                text_type = "selected text"
            else:
                QMessageBox.warning(
                    self,
                    "No Selection",
                    "Please select some text first, or use 'Send Entire File to Ollama'."
                )
                return

        if not text_to_send.strip():
            QMessageBox.warning(self, "No Text", "No text to send.")
            return

        prompt, ok = QInputDialog.getText(
            self,
            "Send to Ollama",
            f"Enter your instruction for Ollama:\n(Sending {text_type}, {len(text_to_send)} characters)",
            QLineEdit.EchoMode.Normal,
            "Explain this code:"
        )

        if ok and prompt.strip():
            full_message = f"{prompt}\n\n```\n{text_to_send}\n```"
            self.ollama_widget.send_text_message(full_message)
            self.bottom_tabs.setCurrentIndex(1)
            self.status_message.setText(f"Sent {len(text_to_send)} characters to Ollama")
            QTimer.singleShot(3000, lambda: self.status_message.setText(""))

    def save_tab(self, tab_index):
        editor = self.tabs.widget(tab_index)
        if isinstance(editor, CodeEditor):
            if editor.save_file():
                editor.is_modified = False
                self.status_message.setText("File saved")
                QTimer.singleShot(2000, lambda: self.status_message.setText(""))
                title = self.tabs.tabText(tab_index)
                if title.startswith('● '):
                    self.tabs.setTabText(tab_index, title[2:])

    def close_other_tabs(self, keep_index):
        indices_to_close = []
        for i in range(self.tabs.count()):
            if i != keep_index:
                indices_to_close.append(i)

        for i in reversed(indices_to_close):
            self.close_tab(i)

    def close_all_tabs(self):
        while self.tabs.count() > 0:
            editor = self.tabs.widget(0)
            if isinstance(editor, CodeEditor) and editor.is_modified:
                reply = QMessageBox.question(
                    self, "Unsaved Changes",
                    f"Save changes to {Path(editor.file_path).name}?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel
                )
                if reply == QMessageBox.StandardButton.Yes:
                    editor.save_file()
                elif reply == QMessageBox.StandardButton.Cancel:
                    break
            self.tabs.removeTab(0)

    def on_editor_tab_changed(self, index):
        if index >= 0:
            editor = self.tabs.widget(index)
            if isinstance(editor, CodeEditor):
                self.find_replace.set_editor(editor)
                self.update_status_bar()
                editor.cursorPositionChanged.connect(self.update_cursor_position)

    def on_editor_modified(self, editor):
        for i in range(self.tabs.count()):
            if self.tabs.widget(i) == editor:
                current_text = self.tabs.tabText(i)
                if editor.is_modified and not current_text.startswith('● '):
                    self.tabs.setTabText(i, f"● {current_text}")
                elif not editor.is_modified and current_text.startswith('● '):
                    self.tabs.setTabText(i, current_text[2:])
                break

    def update_cursor_position(self):
        current_widget = self.tabs.currentWidget()
        if isinstance(current_widget, CodeEditor):
            cursor = current_widget.textCursor()
            line = cursor.blockNumber() + 1
            col = cursor.columnNumber() + 1
            self.line_col_label.setText(f"Ln {line}, Col {col}")

    def update_status_bar(self):
        current_widget = self.tabs.currentWidget()
        if isinstance(current_widget, CodeEditor) and current_widget.file_path:
            file_path = Path(current_widget.file_path)
            ext = file_path.suffix.lower()

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

            language = language_map.get(ext, 'Plain Text')
            self.language_label.setText(language)

            try:
                with open(current_widget.file_path, 'rb') as f:
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
            self.update_cursor_position()
        else:
            self.language_label.setText("Plain Text")
            self.eol_label.setText("LF")
            self.encoding_label.setText("UTF-8")
            self.line_col_label.setText("Ln 1, Col 1")

    def show_find_replace(self):
        current_widget = self.tabs.currentWidget()
        if isinstance(current_widget, CodeEditor):
            self.find_replace.set_editor(current_widget)
            self.find_replace.show_find()

    def find_next(self):
        if self.find_replace.isVisible():
            self.find_replace.find_next()

    def find_previous(self):
        if self.find_replace.isVisible():
            self.find_replace.find_previous()

    def show_quick_open(self):
        active_projects = self.projects_panel.get_active_projects()

        if not active_projects:
            QMessageBox.information(
                self,
                "No Active Projects",
                "Please activate at least one project in the Projects tab.\n\n"
                "Click the '📦 Projects' tab on the left and check the projects you want to search."
            )
            return

        import time

        cache_age = time.time() - self.quick_open_cache_time
        cache_valid = (cache_age < 30 and
                      self.quick_open_cache and
                      set(active_projects) == self.quick_open_cache_projects)

        if cache_valid:
            dialog = QuickOpenDialog(active_projects, self)
            dialog.all_files = self.quick_open_cache
            dialog.search_input.setEnabled(True)
            dialog.search_input.setPlaceholderText("Type to search files... (fuzzy matching)")
            dialog.info_label.setText(f"Showing 50 of {len(self.quick_open_cache):,} files (type to search)")
            dialog.search_input.setFocus()
            dialog.on_search_changed("")

            if dialog.exec() == QDialog.DialogCode.Accepted and dialog.selected_file:
                self.open_file_by_path(Path(dialog.selected_file))
        else:
            dialog = QuickOpenDialog(active_projects, self)

            def cache_files(files):
                self.quick_open_cache = files
                self.quick_open_cache_projects = set(active_projects)
                self.quick_open_cache_time = time.time()

            if dialog.scanner_thread:
                dialog.scanner_thread.files_found.connect(cache_files)

            if dialog.exec() == QDialog.DialogCode.Accepted and dialog.selected_file:
                self.open_file_by_path(Path(dialog.selected_file))

    def init_ui(self):
        self.setWindowTitle("Workspace IDE with Ollama")
        self.resize(1400, 900)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        # Menu bar (replaces toolbar)
        menubar = self.menuBar()
        menubar.setStyleSheet("""
            QMenuBar {
                background-color: #2B2B2B;
                color: #CCCCCC;
                border-bottom: 1px solid #1E1E1E;
                padding: 2px;
            }
            QMenuBar::item {
                padding: 4px 12px;
                background-color: transparent;
            }
            QMenuBar::item:selected {
                background-color: #3C3F41;
            }
            QMenuBar::item:pressed {
                background-color: #4A4A4A;
            }
            QMenu {
                background-color: #2B2B2B;
                color: #CCCCCC;
                border: 1px solid #3C3F41;
            }
            QMenu::item {
                padding: 6px 30px 6px 20px;
            }
            QMenu::item:selected {
                background-color: #4A9EFF;
                color: white;
            }
            QMenu::separator {
                height: 1px;
                background-color: #3C3F41;
                margin: 4px 0px;
            }
        """)

        # File menu
        file_menu = menubar.addMenu("File")

        new_file_action = QAction("New File", self)
        new_file_action.setShortcut("Ctrl+N")
        new_file_action.triggered.connect(lambda: self.create_new_file(self.workspace_path))
        file_menu.addAction(new_file_action)

        new_dir_action = QAction("New Folder", self)
        new_dir_action.setShortcut("Ctrl+Shift+N")
        new_dir_action.triggered.connect(lambda: self.create_new_folder(self.workspace_path))
        file_menu.addAction(new_dir_action)

        file_menu.addSeparator()

        open_action = QAction("Quick Open...", self)
        open_action.setShortcut("Ctrl+P")
        open_action.triggered.connect(self.show_quick_open)
        file_menu.addAction(open_action)

        file_menu.addSeparator()

        save_action = QAction("Save", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self.save_current_file)
        file_menu.addAction(save_action)

        save_all_action = QAction("Save All", self)
        save_all_action.setShortcut("Ctrl+Shift+S")
        save_all_action.triggered.connect(self.save_all_files)
        file_menu.addAction(save_all_action)

        file_menu.addSeparator()

        close_tab_action = QAction("Close Tab", self)
        close_tab_action.setShortcut("Ctrl+W")
        close_tab_action.triggered.connect(lambda: self.close_tab(self.tabs.currentIndex()) if self.tabs.count() > 0 else None)
        file_menu.addAction(close_tab_action)

        close_all_action = QAction("Close All Tabs", self)
        close_all_action.setShortcut("Ctrl+Shift+W")
        close_all_action.triggered.connect(self.close_all_tabs)
        file_menu.addAction(close_all_action)

        file_menu.addSeparator()

        preferences_action = QAction("Preferences...", self)
        preferences_action.setShortcut("Ctrl+,")
        preferences_action.triggered.connect(self.show_settings)
        file_menu.addAction(preferences_action)

        file_menu.addSeparator()

        exit_action = QAction("Exit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Edit menu
        edit_menu = menubar.addMenu("Edit")

        undo_action = QAction("Undo", self)
        undo_action.setShortcut("Ctrl+Z")
        undo_action.triggered.connect(self.undo_current)
        edit_menu.addAction(undo_action)

        redo_action = QAction("Redo", self)
        redo_action.setShortcut("Ctrl+Shift+Z")
        redo_action.triggered.connect(self.redo_current)
        edit_menu.addAction(redo_action)

        edit_menu.addSeparator()

        cut_action = QAction("Cut", self)
        cut_action.setShortcut("Ctrl+X")
        cut_action.triggered.connect(self.cut_current)
        edit_menu.addAction(cut_action)

        copy_action = QAction("Copy", self)
        copy_action.setShortcut("Ctrl+C")
        copy_action.triggered.connect(self.copy_current)
        edit_menu.addAction(copy_action)

        paste_action = QAction("Paste", self)
        paste_action.setShortcut("Ctrl+V")
        paste_action.triggered.connect(self.paste_current)
        edit_menu.addAction(paste_action)

        edit_menu.addSeparator()

        comment_action = QAction("Toggle Comment", self)
        comment_action.setShortcut("Ctrl+/")
        comment_action.triggered.connect(self.toggle_comment)
        edit_menu.addAction(comment_action)

        indent_action = QAction("Indent", self)
        indent_action.setShortcut("Tab")
        indent_action.triggered.connect(self.indent_lines)
        edit_menu.addAction(indent_action)

        unindent_action = QAction("Unindent", self)
        unindent_action.setShortcut("Shift+Tab")
        unindent_action.triggered.connect(self.unindent_lines)
        edit_menu.addAction(unindent_action)

        edit_menu.addSeparator()

        find_action = QAction("Find", self)
        find_action.setShortcut("Ctrl+F")
        find_action.triggered.connect(self.show_find_replace)
        edit_menu.addAction(find_action)

        replace_action = QAction("Replace", self)
        replace_action.setShortcut("Ctrl+H")
        replace_action.triggered.connect(self.show_find_replace)
        edit_menu.addAction(replace_action)

        # Selection menu
        selection_menu = menubar.addMenu("Selection")

        select_all_action = QAction("Select All", self)
        select_all_action.setShortcut("Ctrl+A")
        select_all_action.triggered.connect(self.select_all_current)
        selection_menu.addAction(select_all_action)

        # View menu
        view_menu = menubar.addMenu("View")

        toggle_explorer_action = QAction("Toggle Explorer", self)
        toggle_explorer_action.setShortcut("Ctrl+B")
        toggle_explorer_action.triggered.connect(self.toggle_explorer)
        view_menu.addAction(toggle_explorer_action)

        toggle_terminal_action = QAction("Toggle Terminal", self)
        toggle_terminal_action.setShortcut("Ctrl+`")
        toggle_terminal_action.triggered.connect(self.toggle_terminal)
        view_menu.addAction(toggle_terminal_action)

        # Go menu
        go_menu = menubar.addMenu("Go")

        go_to_file_action = QAction("Go to File...", self)
        #go_to_file_action.setShortcut("Ctrl+P")
        go_to_file_action.triggered.connect(self.show_quick_open)
        go_menu.addAction(go_to_file_action)

        go_to_line_action = QAction("Go to Line...", self)
        go_to_line_action.setShortcut("Ctrl+G")
        go_to_line_action.triggered.connect(self.go_to_line)
        go_menu.addAction(go_to_line_action)

        # Run menu
        run_menu = menubar.addMenu("Run")

        run_file_action = QAction("Run Current File", self)
        run_file_action.setShortcut("F5")
        run_file_action.triggered.connect(self.run_current_file)
        run_menu.addAction(run_file_action)

        # Terminal menu
        terminal_menu = menubar.addMenu("Terminal")

        # new_terminal_action = QAction("New Terminal", self)
        # new_terminal_action.setShortcut("Ctrl+Shift+`")
        # new_terminal_action.triggered.connect(lambda: self.bottom_tabs.setCurrentIndex(0))
        # terminal_menu.addAction(new_terminal_action)

        clear_terminal_action = QAction("Clear Terminal", self)
        clear_terminal_action.triggered.connect(self.clear_terminal)
        terminal_menu.addAction(clear_terminal_action)

        # Help menu
        help_menu = menubar.addMenu("Help")

        about_action = QAction("About Workspace IDE", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

        documentation_action = QAction("Documentation", self)
        #documentation_action.triggered.connect(self.show_about)
        documentation_action.triggered.connect(self.show_documentation)
        documentation_action.setShortcut("F1")
        help_menu.addAction(documentation_action)

        changelog_action = QAction("Changelog", self)
        #documentation_action.triggered.connect(self.show_about)
        changelog_action.triggered.connect(self.show_changelog)
        changelog_action.setShortcut("F2")
        help_menu.addAction(changelog_action)

        help_menu.addSeparator()

        keyboard_shortcuts_action = QAction("Keyboard Shortcuts", self)
        keyboard_shortcuts_action.setShortcut("Ctrl+K Ctrl+S")
        keyboard_shortcuts_action.triggered.connect(self.show_keyboard_shortcuts)
        help_menu.addAction(keyboard_shortcuts_action)


        # Comment toggle shortcut
        #omment_shortcut = QShortcut(QKeySequence("Ctrl+/"), self)
        #comment_shortcut.activated.connect(self.toggle_comment)
        # Indent/Unindent shortcuts are handled in CodeEditor.keyPressEvent
        # Tab = indent, Shift+Tab = unindent


        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(self.main_splitter)

        left_tabs = QTabWidget()
        left_tabs.setMaximumWidth(350)

        explorer_widget = QWidget()
        explorer_layout = QVBoxLayout(explorer_widget)
        explorer_layout.setContentsMargins(5, 5, 5, 5)

        explorer_label = QLabel("File Explorer")
        explorer_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        explorer_layout.addWidget(explorer_label)

        self.file_model = QFileSystemModel()
        self.file_model.setRootPath(str(self.workspace_path))

        self.tree = QTreeView()
        self.tree.setModel(self.file_model)
        self.tree.setRootIndex(self.file_model.index(str(self.workspace_path)))

        self.tree_delegate = ProjectHighlightDelegate(self.tree)
        self.tree.setItemDelegate(self.tree_delegate)

        self.tree.setColumnWidth(0, 200)
        self.tree.setColumnWidth(1, 70)
        self.tree.setColumnWidth(2, 80)
        self.tree.setColumnWidth(3, 100)

        self.tree.doubleClicked.connect(self.open_file)

        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.show_explorer_context_menu)

        explorer_layout.addWidget(self.tree)
        left_tabs.addTab(explorer_widget, "📁 Files")

        self.projects_panel = ProjectsPanel(self.workspace_path, self)
        self.projects_panel.projects_changed.connect(self.update_tree_highlighting)
        left_tabs.addTab(self.projects_panel, "📦 Projects")

        self.main_splitter.addWidget(left_tabs)

        self.right_splitter = QSplitter(Qt.Orientation.Vertical)
        self.main_splitter.addWidget(self.right_splitter)

        # Use custom styled tab widget
        self.tabs = StyledTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.on_editor_tab_changed)

        self.tabs.tabBar().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tabs.tabBar().customContextMenuRequested.connect(self.show_tab_context_menu)

        from PyQt6.QtGui import QShortcut, QKeySequence
        send_shortcut = QShortcut(QKeySequence("Ctrl+Shift+O"), self)
        send_shortcut.activated.connect(self.send_to_ollama)

        # Triggering QAction::event: Ambiguous shortcut overload: Ctrl+F
        #find_shortcut = QShortcut(QKeySequence("Ctrl+F"), self)
        #find_shortcut.activated.connect(self.show_find_replace)

        find_next_shortcut = QShortcut(QKeySequence("F3"), self)
        find_next_shortcut.activated.connect(self.find_next)

        find_prev_shortcut = QShortcut(QKeySequence("Shift+F3"), self)
        find_prev_shortcut.activated.connect(self.find_previous)

        replace_shortcut = QShortcut(QKeySequence("Ctrl+H"), self)
        replace_shortcut.activated.connect(self.show_find_replace)

        # Triggering QAction::event: Ambiguous shortcut overload: Ctrl+P
        #quick_open_shortcut = QShortcut(QKeySequence("Ctrl+P"), self)
        #quick_open_shortcut.activated.connect(self.show_quick_open)

        editor_container = QWidget()
        editor_layout = QVBoxLayout(editor_container)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        editor_layout.setSpacing(0)

        self.find_replace = FindReplaceWidget()
        editor_layout.addWidget(self.find_replace)

        editor_layout.addWidget(self.tabs)

        self.right_splitter.addWidget(editor_container)

        self.bottom_tabs = QTabWidget()
        terminal_font_size = self.settings.get('terminal_font_size', 10)
        self.terminal = Terminal(font_size=terminal_font_size)
        self.bottom_tabs.addTab(self.terminal, "Terminal")

        self.ollama_widget = OllamaChatWidget(parent=self)
        self.bottom_tabs.addTab(self.ollama_widget, "Ollama Chat")

        self.right_splitter.addWidget(self.bottom_tabs)

        self.main_splitter.setStretchFactor(0, 1)
        self.main_splitter.setStretchFactor(1, 4)

        self.right_splitter.setStretchFactor(0, 3)
        self.right_splitter.setStretchFactor(1, 1)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        self.status_message = QLabel("")
        self.status_bar.addWidget(self.status_message)

        self.status_bar.addPermanentWidget(QLabel("  "))

        self.line_col_label = QLabel("Ln 1, Col 1")
        self.line_col_label.setStyleSheet("color: #CCC; padding: 0 10px;")
        self.status_bar.addPermanentWidget(self.line_col_label)

        self.encoding_label = QLabel("UTF-8")
        self.encoding_label.setStyleSheet("color: #CCC; padding: 0 10px;")
        self.status_bar.addPermanentWidget(self.encoding_label)

        self.eol_label = QLabel("LF")
        self.eol_label.setStyleSheet("color: #CCC; padding: 0 10px;")
        self.status_bar.addPermanentWidget(self.eol_label)

        self.language_label = QLabel("Plain Text")
        self.language_label.setStyleSheet("color: #CCC; padding: 0 10px;")
        self.status_bar.addPermanentWidget(self.language_label)

    def ensure_workspace(self):
        if not self.workspace_path.exists():
            self.workspace_path.mkdir(parents=True)

    def show_explorer_context_menu(self, position):
        index = self.tree.indexAt(position)
        menu = QMenu()

        if index.isValid():
            path = Path(self.file_model.filePath(index))

            if path.is_dir():
                new_file_action = menu.addAction("📄 New File")
                new_folder_action = menu.addAction("📁 New Folder")
                menu.addSeparator()
                rename_action = menu.addAction("✏️ Rename")
                menu.addSeparator()
                delete_action = menu.addAction("🗑️ Delete")

                action = menu.exec(self.tree.viewport().mapToGlobal(position))

                if action == new_file_action:
                    self.create_new_file(path)
                elif action == new_folder_action:
                    self.create_new_folder(path)
                elif action == rename_action:
                    self.rename_item(path)
                elif action == delete_action:
                    self.delete_item(path)
            else:
                open_action = menu.addAction("📂 Open")
                menu.addSeparator()
                rename_action = menu.addAction("✏️ Rename")
                menu.addSeparator()
                delete_action = menu.addAction("🗑️ Delete")

                action = menu.exec(self.tree.viewport().mapToGlobal(position))

                if action == open_action:
                    self.open_file_by_path(path)
                elif action == rename_action:
                    self.rename_item(path)
                elif action == delete_action:
                    self.delete_item(path)
        else:
            new_folder_action = menu.addAction("📁 New Folder")
            new_file_action = menu.addAction("📄 New File")

            action = menu.exec(self.tree.viewport().mapToGlobal(position))

            if action == new_folder_action:
                self.create_new_folder(self.workspace_path)
            elif action == new_file_action:
                self.create_new_file(self.workspace_path)

    def create_new_file(self, parent_dir):
        name, ok = QInputDialog.getText(
            self,
            "New File",
            "Enter file name:",
            QLineEdit.EchoMode.Normal
        )

        if ok and name:
            if not name.strip():
                QMessageBox.warning(self, "Invalid Name", "File name cannot be empty")
                return

            file_path = parent_dir / name
            try:
                if file_path.exists():
                    QMessageBox.warning(self, "Error", f"'{name}' already exists")
                    return

                file_path.touch()
                self.status_message.setText(f"Created file: {name}")
                QTimer.singleShot(3000, lambda: self.status_message.setText(""))

                self.open_file_by_path(file_path)

            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not create file: {e}")

    def create_new_folder(self, parent_dir):
        name, ok = QInputDialog.getText(
            self,
            "New Folder",
            "Enter folder name:",
            QLineEdit.EchoMode.Normal
        )

        if ok and name:
            if not name.strip():
                QMessageBox.warning(self, "Invalid Name", "Folder name cannot be empty")
                return

            folder_path = parent_dir / name
            try:
                if folder_path.exists():
                    QMessageBox.warning(self, "Error", f"'{name}' already exists")
                    return

                folder_path.mkdir()
                self.status_message.setText(f"Created folder: {name}")
                QTimer.singleShot(3000, lambda: self.status_message.setText(""))

            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not create folder: {e}")

    def rename_item(self, path):
        old_name = path.name
        new_name, ok = QInputDialog.getText(
            self,
            "Rename",
            f"Rename '{old_name}' to:",
            QLineEdit.EchoMode.Normal,
            old_name
        )

        if ok and new_name:
            if not new_name.strip():
                QMessageBox.warning(self, "Invalid Name", "Name cannot be empty")
                return

            if new_name == old_name:
                return

            new_path = path.parent / new_name
            try:
                if new_path.exists():
                    QMessageBox.warning(self, "Error", f"'{new_name}' already exists")
                    return

                if path.is_file():
                    for i in range(self.tabs.count()):
                        editor = self.tabs.widget(i)
                        if isinstance(editor, CodeEditor) and editor.file_path == str(path):
                            self.tabs.removeTab(i)
                            break

                path.rename(new_path)
                self.status_message.setText(f"Renamed '{old_name}' to '{new_name}'")
                QTimer.singleShot(3000, lambda: self.status_message.setText(""))

                if new_path.is_file():
                    self.open_file_by_path(new_path)

            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not rename: {e}")

    def delete_item(self, path):
        item_type = "folder" if path.is_dir() else "file"

        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to delete this {item_type}?\n\n{path.name}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                if path.is_file():
                    for i in range(self.tabs.count()):
                        editor = self.tabs.widget(i)
                        if isinstance(editor, CodeEditor) and editor.file_path == str(path):
                            self.tabs.removeTab(i)
                            break

                if path.is_dir():
                    import shutil
                    shutil.rmtree(path)
                else:
                    path.unlink()

                self.status_message.setText(f"Deleted: {path.name}")
                QTimer.singleShot(3000, lambda: self.status_message.setText(""))

            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not delete: {e}")

    def open_file_by_path(self, path):
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if isinstance(w, CodeEditor) and w.file_path == str(path):
                self.tabs.setCurrentIndex(i)
                return

        editor_font_size = self.settings.get('editor_font_size', 11)
        tab_width = self.settings.get('tab_width', 4)
        show_line_numbers = self.settings.get('show_line_numbers', True)
        editor = CodeEditor(font_size=editor_font_size, tab_width=tab_width, show_line_numbers=show_line_numbers)
        if editor.load_file(str(path)):
            tab_index = self.tabs.addTab(editor, path.name)

            # Set tooltip with full path
            self.tabs.setTabToolTip(tab_index, str(path))

            # Connect text changed signal to track modifications
            def on_text_changed():
                if editor.is_modified:
                    self.on_editor_modified(editor)

            editor.textChanged.connect(on_text_changed)

            self.tabs.setCurrentWidget(editor)
            self.update_status_bar()

    def open_file(self, index):
        path = self.file_model.filePath(index)
        p = Path(path)
        if not p.is_file():
            return

        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if isinstance(w, CodeEditor) and w.file_path == path:
                self.tabs.setCurrentIndex(i)
                return

        editor_font_size = self.settings.get('editor_font_size', 11)
        tab_width = self.settings.get('tab_width', 4)
        show_line_numbers = self.settings.get('show_line_numbers', True)
        editor = CodeEditor(font_size=editor_font_size, tab_width=tab_width, show_line_numbers=show_line_numbers)
        if editor.load_file(path):
            tab_index = self.tabs.addTab(editor, p.name)

            # Set tooltip with full path
            self.tabs.setTabToolTip(tab_index, path)

            # Connect text changed signal to track modifications
            def on_text_changed():
                if editor.is_modified:
                    self.on_editor_modified(editor)

            editor.textChanged.connect(on_text_changed)

            self.tabs.setCurrentWidget(editor)

    def close_tab(self, index):
        editor = self.tabs.widget(index)
        if isinstance(editor, CodeEditor) and editor.is_modified:
            title = self.tabs.tabText(index)

            reply = QMessageBox.question(
                self, "Unsaved Changes",
                f"Save changes to {title}?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel
            )
            if reply == QMessageBox.StandardButton.Yes:
                editor.save_file()
                editor.is_modified = False
            elif reply == QMessageBox.StandardButton.Cancel:
                return

        self.tabs.removeTab(index)

    def save_current_file(self):
        w = self.tabs.currentWidget()
        if isinstance(w, CodeEditor):
            if w.save_file():
                w.is_modified = False
                self.status_message.setText("File saved")
                QTimer.singleShot(2000, lambda: self.status_message.setText(""))
                idx = self.tabs.currentIndex()
                title = self.tabs.tabText(idx)
                if title.startswith('● '):
                    self.tabs.setTabText(idx, title[2:])

    def send_to_ollama(self):
        current_widget = self.tabs.currentWidget()

        if not isinstance(current_widget, CodeEditor):
            QMessageBox.warning(
                self,
                "No Editor",
                "Please open a file first before sending to Ollama."
            )
            return

        cursor = current_widget.textCursor()
        if cursor.hasSelection():
            text_to_send = cursor.selectedText().replace('\u2029', '\n')
            text_type = "selected text"
        else:
            text_to_send = current_widget.toPlainText()
            text_type = "entire file"

        if not text_to_send.strip():
            QMessageBox.warning(
                self,
                "No Text",
                "No text to send. Please select some text or make sure the file has content."
            )
            return

        prompt, ok = QInputDialog.getText(
            self,
            "Send to Ollama",
            f"Enter your instruction for Ollama:\n(Sending {text_type}, {len(text_to_send)} characters)",
            QLineEdit.EchoMode.Normal,
            "Explain this code:"
        )

        if ok and prompt.strip():
            full_message = f"{prompt}\n\n```\n{text_to_send}\n```"

            self.ollama_widget.send_text_message(full_message)

            self.bottom_tabs.setCurrentIndex(1)

            self.status_message.setText(f"Sent {len(text_to_send)} characters to Ollama")
            QTimer.singleShot(3000, lambda: self.status_message.setText(""))

    def load_settings(self):
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {
            'explorer_width': 300,
            'terminal_height': 200,
            'editor_font_size': 11,
            'terminal_font_size': 10,
            'tab_width': 4,
            'restore_session': True,
            'show_line_numbers': True,
            'auto_save': False,
            'ollama_timeout': 180,
            'active_projects': []
        }

    def save_settings(self):
        self.settings['active_projects'] = self.projects_panel.get_active_projects()

        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.settings, f, indent=2)
        except Exception as e:
            print(f"Error saving settings: {e}")

    def show_settings(self):
        dialog = SettingsDialog(self)
        dialog.set_settings(self.settings)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.settings = dialog.get_settings()
            self.save_settings()
            self.apply_settings()
            QMessageBox.information(
                self,
                "Settings Saved",
                "Settings have been saved. Some changes may require restart."
            )

    def apply_initial_layout(self):
        if hasattr(self, 'saved_main_sizes') and self.saved_main_sizes:
            self.main_splitter.setSizes(self.saved_main_sizes)
        else:
            explorer_width = self.settings.get('explorer_width', 300)
            total_width = self.main_splitter.width()
            if total_width > explorer_width:
                self.main_splitter.setSizes([explorer_width, total_width - explorer_width])

        if hasattr(self, 'saved_right_sizes') and self.saved_right_sizes:
            self.right_splitter.setSizes(self.saved_right_sizes)
        else:
            terminal_height = self.settings.get('terminal_height', 200)
            total_height = self.right_splitter.height()
            if total_height > terminal_height:
                self.right_splitter.setSizes([total_height - terminal_height, terminal_height])

    def apply_settings(self):
        explorer_width = self.settings.get('explorer_width', 300)
        current_sizes = self.main_splitter.sizes()
        total = sum(current_sizes)
        self.main_splitter.setSizes([explorer_width, total - explorer_width])

        terminal_height = self.settings.get('terminal_height', 200)
        current_sizes = self.right_splitter.sizes()
        total = sum(current_sizes)
        self.right_splitter.setSizes([total - terminal_height, terminal_height])

        editor_font_size = self.settings.get('editor_font_size', 11)
        for i in range(self.tabs.count()):
            editor = self.tabs.widget(i)
            if isinstance(editor, CodeEditor):
                font = editor.font()
                font.setPointSize(editor_font_size)
                editor.setFont(font)

        terminal_font_size = self.settings.get('terminal_font_size', 10)
        font = self.terminal.font()
        font.setPointSize(terminal_font_size)
        self.terminal.setFont(font)

    def save_session(self):
        open_files = []
        active_index = self.tabs.currentIndex()

        for i in range(self.tabs.count()):
            editor = self.tabs.widget(i)
            if isinstance(editor, CodeEditor) and editor.file_path:
                open_files.append(editor.file_path)

        main_sizes = self.main_splitter.sizes()
        right_sizes = self.right_splitter.sizes()

        session_data = {
            'open_files': open_files,
            'active_index': active_index,
            'main_splitter_sizes': main_sizes,
            'right_splitter_sizes': right_sizes,
            'window_geometry': {
                'x': self.x(),
                'y': self.y(),
                'width': self.width(),
                'height': self.height(),
                'maximized': self.isMaximized()
            }
        }

        try:
            with open(self.session_file, 'w') as f:
                json.dump(session_data, f, indent=2)
        except Exception as e:
            print(f"Error saving session: {e}")

    def restore_session(self):
        if not self.session_file.exists():
            return

        try:
            with open(self.session_file, 'r') as f:
                session_data = json.load(f)

            open_files = session_data.get('open_files', [])
            active_index = session_data.get('active_index', 0)

            editor_font_size = self.settings.get('editor_font_size', 11)
            tab_width = self.settings.get('tab_width', 4)
            show_line_numbers = self.settings.get('show_line_numbers', True)

            geom = session_data.get('window_geometry', {})
            if geom:
                if not geom.get('maximized', False):
                    self.setGeometry(
                        geom.get('x', 100),
                        geom.get('y', 100),
                        geom.get('width', 1400),
                        geom.get('height', 900)
                    )
                else:
                    self.showMaximized()

            for file_info in open_files:
                # Handle both old format (string) and new format (dict)
                if isinstance(file_info, str):
                    file_path = file_info
                    cursor_line = 0
                    cursor_column = 0
                    scroll_position = 0
                else:
                    file_path = file_info.get('path')
                    cursor_line = file_info.get('cursor_line', 0)
                    cursor_column = file_info.get('cursor_column', 0)
                    scroll_position = file_info.get('scroll_position', 0)

                if Path(file_path).exists():
                    editor = CodeEditor(font_size=editor_font_size, tab_width=tab_width, show_line_numbers=show_line_numbers)
                    if editor.load_file(file_path):
                        tab_index = self.tabs.addTab(editor, Path(file_path).name)
                        # Set tooltip with full path
                        self.tabs.setTabToolTip(tab_index, file_path)

                        # Restore cursor position
                        cursor = editor.textCursor()
                        cursor.movePosition(QTextCursor.MoveOperation.Start)
                        cursor.movePosition(QTextCursor.MoveOperation.Down, QTextCursor.MoveMode.MoveAnchor, cursor_line)
                        cursor.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.MoveAnchor, cursor_column)
                        editor.setTextCursor(cursor)

                        # Restore scroll position (must be done after widget is shown)
                        def restore_scroll(ed=editor, pos=scroll_position):
                            scrollbar = ed.verticalScrollBar()
                            scrollbar.setValue(pos)

                        # Use QTimer to restore scroll after layout is complete
                        QTimer.singleShot(50, restore_scroll)

                        # Connect text changed signal
                        def on_text_changed(e=editor):
                            if e.is_modified:
                                self.on_editor_modified(e)

                        editor.textChanged.connect(on_text_changed)

            if 0 <= active_index < self.tabs.count():
                self.tabs.setCurrentIndex(active_index)

            self.saved_main_sizes = session_data.get('main_splitter_sizes', None)
            self.saved_right_sizes = session_data.get('right_splitter_sizes', None)

            if self.tabs.count() > 0:
                self.status_message.setText(f"Restored {self.tabs.count()} file(s) with positions")
                QTimer.singleShot(3000, lambda: self.status_message.setText(""))

        except Exception as e:
            print(f"Error restoring session: {e}")

    def closeEvent(self, event):
        self.settings['active_projects'] = self.projects_panel.get_active_projects()
        self.save_settings()

        if self.settings.get('restore_session', True):
            self.save_session()

        unsaved_files = []
        for i in range(self.tabs.count()):
            editor = self.tabs.widget(i)
            if isinstance(editor, CodeEditor) and editor.is_modified:
                unsaved_files.append(Path(editor.file_path).name)

        if unsaved_files:
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                f"You have unsaved changes in:\n{', '.join(unsaved_files)}\n\nSave before closing?",
                QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel
            )

            if reply == QMessageBox.StandardButton.Save:
                for i in range(self.tabs.count()):
                    editor = self.tabs.widget(i)
                    if isinstance(editor, CodeEditor) and editor.is_modified:
                        editor.save_file()
                event.accept()
            elif reply == QMessageBox.StandardButton.Discard:
                event.accept()
            else:
                event.ignore()
                return

        event.accept()

    # ---------------------- Menu Action Implementations ----------------------

    def save_all_files(self):
        """Save all open modified files"""
        saved_count = 0
        for i in range(self.tabs.count()):
            editor = self.tabs.widget(i)
            if isinstance(editor, CodeEditor) and editor.is_modified:
                if editor.save_file():
                    editor.is_modified = False
                    self.tabs.set_tab_modified(i, False)
                    saved_count += 1

        if saved_count > 0:
            self.status_message.setText(f"Saved {saved_count} file(s)")
            QTimer.singleShot(3000, lambda: self.status_message.setText(""))
        else:
            self.status_message.setText("No files to save")
            QTimer.singleShot(2000, lambda: self.status_message.setText(""))

    def undo_current(self):
        """Undo in current editor"""
        current_widget = self.tabs.currentWidget()
        if isinstance(current_widget, CodeEditor):
            current_widget.undo()

    def redo_current(self):
        """Redo in current editor"""
        current_widget = self.tabs.currentWidget()
        if isinstance(current_widget, CodeEditor):
            current_widget.redo()

    def cut_current(self):
        """Cut in current editor"""
        current_widget = self.tabs.currentWidget()
        if isinstance(current_widget, CodeEditor):
            current_widget.cut()

    def copy_current(self):
        """Copy in current editor"""
        current_widget = self.tabs.currentWidget()
        if isinstance(current_widget, CodeEditor):
            current_widget.copy()

    def paste_current(self):
        """Paste in current editor"""
        current_widget = self.tabs.currentWidget()
        if isinstance(current_widget, CodeEditor):
            current_widget.paste()

    def select_all_current(self):
        """Select all in current editor"""
        current_widget = self.tabs.currentWidget()
        if isinstance(current_widget, CodeEditor):
            current_widget.selectAll()

    def toggle_explorer(self):
        """Toggle file explorer visibility"""
        explorer_widget = self.main_splitter.widget(0)
        if explorer_widget.isVisible():
            explorer_widget.hide()
        else:
            explorer_widget.show()

    def toggle_terminal(self):
        """Toggle terminal visibility"""
        terminal_widget = self.right_splitter.widget(1)
        if terminal_widget.isVisible():
            terminal_widget.hide()
        else:
            terminal_widget.show()

    def go_to_line(self):
        """Go to line dialog"""
        current_widget = self.tabs.currentWidget()
        if not isinstance(current_widget, CodeEditor):
            return

        line_number, ok = QInputDialog.getInt(
            self,
            "Go to Line",
            "Enter line number:",
            1,
            1,
            current_widget.blockCount()
        )

        if ok:
            cursor = current_widget.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            cursor.movePosition(QTextCursor.MoveOperation.Down, QTextCursor.MoveMode.MoveAnchor, line_number - 1)
            current_widget.setTextCursor(cursor)
            current_widget.ensureCursorVisible()

    def run_current_file(self):
        """Run the current file"""
        current_widget = self.tabs.currentWidget()
        if not isinstance(current_widget, CodeEditor) or not current_widget.file_path:
            QMessageBox.warning(self, "No File", "No file open to run")
            return

        file_path = Path(current_widget.file_path)

        # Switch to terminal
        self.bottom_tabs.setCurrentIndex(0)

        # Run based on file type
        if file_path.suffix == '.py':
            command = f"python3 {file_path}"
        elif file_path.suffix == '.js':
            command = f"node {file_path}"
        elif file_path.suffix == '.sh':
            command = f"bash {file_path}"
        else:
            QMessageBox.information(
                self,
                "Run File",
                f"Don't know how to run {file_path.suffix} files.\n\nPlease run manually in the terminal."
            )
            return

        # Execute in terminal
        self.terminal.append(f"\n{command}\n")
        self.terminal.execute_command(command)

    def clear_terminal(self):
        """Clear terminal output"""
        self.terminal.clear()
        self.terminal.append("=== Simple Terminal ===\n")
        self.terminal.show_prompt()

    def show_about(self):
        """Show about dialog"""
        QMessageBox.about(
            self,
            "About Workspace IDE",
            "<h3>Workspace IDE with Ollama</h3>"
            f"<p>Version {VERSION} </p>"
            "<p>A modern Python IDE with integrated AI assistance.</p>"
            "<p><b>Features:</b></p>"
            "<ul>"
            "<li>Multi-file editing with syntax highlighting</li>"
            "<li>Integrated terminal</li>"
            "<li>Ollama AI chat integration</li>"
            "<li>Quick file search (Ctrl+P)</li>"
            "<li>Find & replace with regex support</li>"
            "<li>Session restoration</li>"
            "</ul>"
            "<p>Built with PyQt6</p>"
        )

    def show_keyboard_shortcuts(self):
        """Show keyboard shortcuts dialog"""
        shortcuts_text = """
<h3>Keyboard Shortcuts</h3>

<h4>File Operations</h4>
<table style="width: 100%">
<tr><td><b>Ctrl+N</b></td><td>New File</td></tr>
<tr><td><b>Ctrl+Shift+N</b></td><td>New Folder</td></tr>
<tr><td><b>Ctrl+P</b></td><td>Quick Open</td></tr>
<tr><td><b>Ctrl+S</b></td><td>Save</td></tr>
<tr><td><b>Ctrl+Shift+S</b></td><td>Save All</td></tr>
<tr><td><b>Ctrl+W</b></td><td>Close Tab</td></tr>
<tr><td><b>Ctrl+Shift+W</b></td><td>Close All Tabs</td></tr>
<tr><td><b>Ctrl+Q</b></td><td>Exit</td></tr>
</table>

<h4>Edit Operations</h4>
<table style="width: 100%">
<tr><td><b>Ctrl+Z</b></td><td>Undo</td></tr>
<tr><td><b>Ctrl+Shift+Z</b></td><td>Redo</td></tr>
<tr><td><b>Ctrl+X</b></td><td>Cut</td></tr>
<tr><td><b>Ctrl+C</b></td><td>Copy</td></tr>
<tr><td><b>Ctrl+V</b></td><td>Paste</td></tr>
<tr><td><b>Ctrl+A</b></td><td>Select All</td></tr>
<tr><td><b>Ctrl+F</b></td><td>Find</td></tr>
<tr><td><b>Ctrl+H</b></td><td>Replace</td></tr>
<tr><td><b>F3</b></td><td>Find Next</td></tr>
<tr><td><b>Shift+F3</b></td><td>Find Previous</td></tr>
</table>

<h4>View</h4>
<table style="width: 100%">
<tr><td><b>Ctrl+B</b></td><td>Toggle Explorer</td></tr>
<tr><td><b>Ctrl+`</b></td><td>Toggle Terminal</td></tr>
</table>

<h4>Navigation</h4>
<table style="width: 100%">
<tr><td><b>Ctrl+G</b></td><td>Go to Line</td></tr>
<tr><td><b>Ctrl+P</b></td><td>Go to File</td></tr>
</table>

<h4>Run</h4>
<table style="width: 100%">
<tr><td><b>F5</b></td><td>Run Current File</td></tr>
</table>

<h4>AI Features</h4>
<table style="width: 100%">
<tr><td><b>Ctrl+Shift+O</b></td><td>Send to Ollama</td></tr>
</table>

<h4>Preferences</h4>
<table style="width: 100%">
<tr><td><b>Ctrl+,</b></td><td>Open Preferences</td></tr>
</table>
"""

        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Keyboard Shortcuts")
        msg_box.setTextFormat(Qt.TextFormat.RichText)
        msg_box.setText(shortcuts_text)

        # Force a wider dialog by adding a horizontal spacer to the internal layout
        spacer = QSpacerItem(500, 0)  # Adjust 500 to your desired minimum width (e.g., 600, 800)
        layout = msg_box.layout()  # This is a QGridLayout
        if isinstance(layout, QGridLayout):
            layout.addItem(spacer, layout.rowCount(), 0, 1, layout.columnCount())

        msg_box.exec()


    def toggle_comment(self):
        """Toggle comments in current editor"""
        current_widget = self.tabs.currentWidget()
        if isinstance(current_widget, CodeEditor):
            current_widget.toggle_comment()

    def indent_lines(self):
        """Indent selected lines in current editor"""
        current_widget = self.tabs.currentWidget()
        if isinstance(current_widget, CodeEditor):
            current_widget.indent_selection()

    def unindent_lines(self):
        """Unindent selected lines in current editor"""
        current_widget = self.tabs.currentWidget()
        if isinstance(current_widget, CodeEditor):
            current_widget.unindent_selection()


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    ide = WorkspaceIDE()
    ide.show()

    from PyQt6.QtCore import QTimer
    QTimer.singleShot(100, ide.apply_initial_layout)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
