#!/usr/bin/env python3
"""
Workspace IDE - Cursor-Style Layout
Ollama Chat on the right side, no embedded terminal
"""
import subprocess
import os
import sys
import json
import time
import shutil
import platform
import subprocess
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTabWidget,
    QSplitter,
    QTreeView,
    QLabel,
    QStatusBar,
    QMenu,
    QMenuBar,
    QMessageBox,
    QInputDialog,
    QLineEdit,
    QSpacerItem,
    QGridLayout,
	QDialog,

)
from PyQt6.QtGui import (
    QAction,
    QKeySequence,
    QShortcut,
    QFont,
    QFileSystemModel,
    QTextCursor,
)
from PyQt6.QtCore import (
    Qt,
    QTimer,
)

from PyQt6.QtWidgets import QApplication
QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)

from ide import VERSION, WORKSPACE_PATH
from ide.core.CodeEditor import CodeEditor
from ide.core.Plugin import PluginWidget, PluginManager
from ide.core.FindReplace import FindReplaceWidget
from ide.core.QuickOpen import QuickOpenDialog
from ide.core.Settings import SettingsDialog
from ide.core.Ollama import OllamaWorker, OllamaChatWidget
from ide.core.Document import DocumentDialog
from ide.core.TabBar import StyledTabBar, StyledTabWidget
from ide.core.FileScanner import FileScannerThread
from ide.core.ProjectsPanel import ProjectsPanel, ProjectHighlightDelegate
from ide.core.PluginManagerUI import PluginManagerUI


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
        self.plugin_ui = PluginManagerUI(self)

        self.init_ui()
        self.ensure_workspace()

        if self.settings.get('restore_session', True):
            self.restore_session()

        active_projects = self.settings.get('active_projects', [])
        if active_projects:
            self.projects_panel.set_active_projects(active_projects)
            self.update_tree_highlighting()

        self.apply_initial_layout()

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
            self.show_ollama_panel()
            self.status_message.setText(f"Sent {len(text_to_send)} characters to Ollama")
            QTimer.singleShot(3000, lambda: self.status_message.setText(""))

    # def save_tab(self, tab_index):
        # editor = self.tabs.widget(tab_index)
        # if isinstance(editor, CodeEditor):
            # if editor.save_file():
                # editor.is_modified = False
                # self.status_message.setText("File saved")
                # QTimer.singleShot(2000, lambda: self.status_message.setText(""))
                # title = self.tabs.tabText(tab_index)
                # if title.startswith('● '):
                    # self.tabs.setTabText(tab_index, title[2:])

    def save_tab(self, tab_index):
        editor = self.tabs.widget(tab_index)
        if isinstance(editor, CodeEditor):
            if editor.save_file():  # This should call document().setModified(False)
                # Force clear just in case
                editor.document().setModified(False)

                # Trigger update (this will now correctly remove the dot)
                self.on_editor_modified(editor)

                self.status_message.setText("File saved")
                QTimer.singleShot(2000, lambda: self.status_message.setText(""))


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
            if isinstance(editor, CodeEditor) and editor.document().isModified():
            #if isinstance(editor, CodeEditor) and editor.is_modified:
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
        index = self.tabs.indexOf(editor)
        if index != -1:
            self.tabs.set_tab_modified(index, editor.document().isModified())


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
        self.setWindowTitle(f"Workspace IDE ({VERSION})")
        self.resize(1600, 900)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        # Menu bar
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

        toggle_ai_action = QAction("Toggle AI Chat", self)
        toggle_ai_action.setShortcut("Ctrl+L")
        toggle_ai_action.triggered.connect(self.toggle_ollama_panel)
        view_menu.addAction(toggle_ai_action)

        # Go menu
        go_menu = menubar.addMenu("Go")

        go_to_file_action = QAction("Go to File...", self)
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
        #terminal_menu = menubar.addMenu("Terminal")
        #open_terminal_action = QAction("Open External Terminal", self)
        #open_terminal_action.setShortcut("Ctrl+Shift+T")
        #open_terminal_action.triggered.connect(self.open_external_terminal(str(self.workspace_path)))
        #terminal_menu.addAction(open_terminal_action)

        self.plugins_menu = self.plugin_ui.create_plugin_menu(menubar)

        # Help menu
        help_menu = menubar.addMenu("Help")

        about_action = QAction("About Workspace IDE", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

        documentation_action = QAction("Documentation", self)
        documentation_action.triggered.connect(self.show_documentation)
        documentation_action.setShortcut("F1")
        help_menu.addAction(documentation_action)

        changelog_action = QAction("Changelog", self)
        changelog_action.triggered.connect(self.show_changelog)
        changelog_action.setShortcut("F2")
        help_menu.addAction(changelog_action)

        help_menu.addSeparator()

        keyboard_shortcuts_action = QAction("Keyboard Shortcuts", self)
        keyboard_shortcuts_action.setShortcut("Ctrl+K Ctrl+S")
        keyboard_shortcuts_action.triggered.connect(self.show_keyboard_shortcuts)
        help_menu.addAction(keyboard_shortcuts_action)

        # Main horizontal splitter: [Left Sidebar | Editor | Right Sidebar]
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(self.main_splitter)

        # LEFT SIDEBAR - Files & Projects
        left_tabs = QTabWidget()
        left_tabs.setMaximumWidth(450)

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

        self.tree.setColumnWidth(0, 450)
        self.tree.setColumnHidden(1, True)
        self.tree.setColumnHidden(2, True)
        self.tree.setColumnHidden(3, True)

        self.tree.doubleClicked.connect(self.open_file)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.show_explorer_context_menu)

        explorer_layout.addWidget(self.tree)
        left_tabs.addTab(explorer_widget, "📁 Files")

        self.projects_panel = ProjectsPanel(self.workspace_path, self)
        self.projects_panel.projects_changed.connect(self.update_tree_highlighting)
        left_tabs.addTab(self.projects_panel, "📦 Projects")

        self.main_splitter.addWidget(left_tabs)

        # CENTER - Editor
        editor_container = QWidget()
        editor_layout = QVBoxLayout(editor_container)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        editor_layout.setSpacing(0)

        self.find_replace = FindReplaceWidget()
        editor_layout.addWidget(self.find_replace)

        self.tabs = StyledTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.on_editor_tab_changed)
        self.tabs.tabBar().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tabs.tabBar().customContextMenuRequested.connect(self.show_tab_context_menu)

        editor_layout.addWidget(self.tabs)

        self.main_splitter.addWidget(editor_container)

        # RIGHT SIDEBAR - Ollama Chat (like Cursor)
        self.ollama_widget = OllamaChatWidget(parent=self)
        self.ollama_widget.setMinimumWidth(300)

        # Add header to Ollama panel
        ollama_container = QWidget()
        ollama_layout = QVBoxLayout(ollama_container)
        ollama_layout.setContentsMargins(5, 5, 5, 5)
        ollama_layout.setSpacing(5)

        ollama_header = QLabel("🤖 AI Chat")
        ollama_header.setStyleSheet("font-weight: bold; font-size: 14px; padding: 5px;")
        ollama_layout.addWidget(ollama_header)
        ollama_layout.addWidget(self.ollama_widget)

        self.main_splitter.addWidget(ollama_container)

        # Set splitter proportions: [Left:1 | Center:4 | Right:1.5]
        self.main_splitter.setStretchFactor(0, 1)
        self.main_splitter.setStretchFactor(1, 4)
        self.main_splitter.setStretchFactor(2, 0)  # Start hidden

        # Shortcuts
        send_shortcut = QShortcut(QKeySequence("Ctrl+Shift+O"), self)
        send_shortcut.activated.connect(self.send_to_ollama)

        find_next_shortcut = QShortcut(QKeySequence("F3"), self)
        find_next_shortcut.activated.connect(self.find_next)

        find_prev_shortcut = QShortcut(QKeySequence("Shift+F3"), self)
        find_prev_shortcut.activated.connect(self.find_previous)

        # Status Bar
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

        # Hide Ollama panel by default
        self.ollama_panel_visible = False
        ollama_container.hide()

    def toggle_ollama_panel(self):
        """Toggle Ollama chat panel visibility"""
        ollama_container = self.main_splitter.widget(2)

        if self.ollama_panel_visible:
            ollama_container.hide()
            self.ollama_panel_visible = False
        else:
            ollama_container.show()
            self.ollama_panel_visible = True
            # Restore reasonable size
            sizes = self.main_splitter.sizes()
            total = sum(sizes)
            self.main_splitter.setSizes([
                int(total * 0.15),  # Left
                int(total * 0.55),  # Center
                int(total * 0.30)   # Right
            ])

    def show_ollama_panel(self):
        """Show Ollama panel if hidden"""
        if not self.ollama_panel_visible:
            self.toggle_ollama_panel()


    def ensure_workspace(self):
        if not self.workspace_path.exists():
            self.workspace_path.mkdir(parents=True)

    def show_explorer_context_menu(self, position):
        index = self.tree.indexAt(position)
        menu = QMenu()

        if index.isValid():
            path = Path(self.file_model.filePath(index))

            if path.is_dir():
                new_file_action = menu.addAction("ðŸ“„ New File")
                new_folder_action = menu.addAction("ðŸ“ New Folder")
                menu.addSeparator()
                rename_action = menu.addAction("âœï¸ Rename")
                menu.addSeparator()
                delete_action = menu.addAction("ðŸ—‘ï¸ Delete")

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
                open_action = menu.addAction("ðŸ“‚ Open")
                menu.addSeparator()
                rename_action = menu.addAction("âœï¸ Rename")
                menu.addSeparator()
                delete_action = menu.addAction("ðŸ—‘ï¸ Delete")

                action = menu.exec(self.tree.viewport().mapToGlobal(position))

                if action == open_action:
                    self.open_file_by_path(path)
                elif action == rename_action:
                    self.rename_item(path)
                elif action == delete_action:
                    self.delete_item(path)
        else:
            new_folder_action = menu.addAction("ðŸ“ New Folder")
            new_file_action = menu.addAction("ðŸ“„ New File")

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
            editor.textChanged.connect(lambda: self.on_editor_modified(editor))
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
            editor.textChanged.connect(lambda: self.on_editor_modified(editor))
            self.tabs.setCurrentWidget(editor)


    def close_tab(self, index):
        editor = self.tabs.widget(index)
        if isinstance(editor, CodeEditor) and editor.document().isModified():
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                f"Save changes to {self.tabs.tabText(index)}?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel
            )
            if reply == QMessageBox.StandardButton.Yes:
                editor.save_file()
            elif reply == QMessageBox.StandardButton.Cancel:
                return

        self.tabs.removeTab(index)

    def save_current_file(self):
        w = self.tabs.currentWidget()
        if isinstance(w, CodeEditor):
            if w.save_file():
                w.document().setModified(False)
                self.on_editor_modified(w)  # Force update title

                self.status_message.setText("File saved")
                QTimer.singleShot(2000, lambda: self.status_message.setText(""))

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
            self.main_splitter.setSizes(self.saved_right_sizes)
        else:
            terminal_height = self.settings.get('terminal_height', 200)
            total_height = self.main_splitter.height()
            if total_height > terminal_height:
                self.main_splitter.setSizes([total_height - terminal_height, terminal_height])

    def apply_settings(self):
        explorer_width = self.settings.get('explorer_width', 300)
        current_sizes = self.main_splitter.sizes()
        total = sum(current_sizes)
        self.main_splitter.setSizes([explorer_width, total - explorer_width])

        terminal_height = self.settings.get('terminal_height', 200)
        current_sizes = self.main_splitter.sizes()
        total = sum(current_sizes)
        self.main_splitter.setSizes([total - terminal_height, terminal_height])

        editor_font_size = self.settings.get('editor_font_size', 11)
        for i in range(self.tabs.count()):
            editor = self.tabs.widget(i)
            if isinstance(editor, CodeEditor):
                font = editor.font()
                font.setPointSize(editor_font_size)
                editor.setFont(font)

    def save_session(self):
        open_files = []
        active_index = self.tabs.currentIndex()

        for i in range(self.tabs.count()):
            editor = self.tabs.widget(i)
            if isinstance(editor, CodeEditor) and editor.file_path:
                open_files.append(editor.file_path)

        main_sizes = self.main_splitter.sizes()
        right_sizes = self.main_splitter.sizes()

        session_data = {
            'open_files': open_files,
            'active_index': active_index,
            'main_splitter_sizes': main_sizes,
            'main_splitter_sizes': right_sizes,
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

                file_path_obj = Path(file_path)
                if file_path_obj.exists():
                    editor = CodeEditor(
                        font_size=editor_font_size,
                        tab_width=tab_width,
                        show_line_numbers=show_line_numbers
                    )

                    # Block signals during initial setup to prevent false modified signals
                    editor.blockSignals(True)

                    if editor.load_file(file_path):
                        tab_index = self.tabs.addTab(editor, file_path_obj.name)
                        self.tabs.setTabToolTip(tab_index, file_path)

                        # Restore cursor position
                        cursor = editor.textCursor()
                        cursor.movePosition(QTextCursor.MoveOperation.Start)
                        cursor.movePosition(
                            QTextCursor.MoveOperation.Down,
                            QTextCursor.MoveMode.MoveAnchor,
                            cursor_line
                        )
                        cursor.movePosition(
                            QTextCursor.MoveOperation.Right,
                            QTextCursor.MoveMode.MoveAnchor,
                            cursor_column
                        )
                        editor.setTextCursor(cursor)

                        # Explicitly clear modified flag (defensive)
                        editor.document().setModified(False)

                        # Restore scroll position after widget is shown
                        def restore_scroll(ed=editor, pos=scroll_position):
                            scrollbar = ed.verticalScrollBar()
                            scrollbar.setValue(pos)

                        QTimer.singleShot(50, restore_scroll)

                    # Re-enable signals now that setup is complete
                    editor.blockSignals(False)

                    # Connect textChanged only after unblocking and setup
                    #editor.textChanged.connect(
                    #    lambda e=editor: self.on_editor_modified(e) if e.document().isModified() else None
                    #)
                    editor.textChanged.connect(lambda: self.on_editor_modified(editor))

            if 0 <= active_index < self.tabs.count():
                self.tabs.setCurrentIndex(active_index)

            self.saved_main_sizes = session_data.get('main_splitter_sizes', None)
            self.saved_right_sizes = session_data.get('right_splitter_sizes', None)  # Fixed typo if present

            if self.tabs.count() > 0:
                self.status_message.setText(f"Restored {self.tabs.count()} file(s) with positions")
                QTimer.singleShot(3000, lambda: self.status_message.setText(""))

        except Exception as e:
            print(f"Error restoring session: {e}")


    def closeEvent(self, event):
        self.settings['active_projects'] = self.projects_panel.get_active_projects()
        self.save_settings()

        #if hasattr(self.terminal, 'backend'):
        #    self.terminal.backend.stop()

        if self.settings.get('restore_session', True):
            self.save_session()

        unsaved_files = []
        for i in range(self.tabs.count()):
            editor = self.tabs.widget(i)
            if isinstance(editor, CodeEditor) and editor.document().isModified():
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
                    #if isinstance(editor, CodeEditor) and editor.is_modified:
                    if isinstance(editor, CodeEditor) and editor.document().isModified():
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
        saved_count = 0
        for i in range(self.tabs.count()):
            editor = self.tabs.widget(i)
            if isinstance(editor, CodeEditor) and editor.document().isModified():
                if editor.save_file():
                    self.on_editor_modified(editor)
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
        terminal_widget = self.main_splitter.widget(1)
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
        """Run the current file in an external terminal"""
        current_widget = self.tabs.currentWidget()
        if not isinstance(current_widget, CodeEditor) or not current_widget.file_path:
            QMessageBox.warning(self, "No File", "No file open to run")
            return

        file_path = Path(current_widget.file_path).resolve()

        # Determine the command based on file type
        if file_path.suffix == '.py':
            command = f"python3 \"{file_path}\""
        elif file_path.suffix in {'.php'}:
            command = f"php \"{file_path}\""
        elif file_path.suffix in {'.js', '.cjs', '.mjs'}:
            command = f"node \"{file_path}\""
        elif file_path.suffix == '.sh':
            command = f"bash \"{file_path}\""
        elif file_path.suffix in {'.html', '.htm'}:
            # Open in default browser
            import webbrowser
            webbrowser.open(file_path.as_uri())
            self.status_message.setText(f"Opened {file_path.name} in browser")
            QTimer.singleShot(3000, lambda: self.status_message.setText(""))
            return
        else:
            QMessageBox.information(
                self,
                "Run File",
                f"Don't know how to run {file_path.suffix} files automatically.\n\n"
                f"You can run it manually in a terminal:\n\n{file_path}"
            )
            # Still open terminal in the file's directory for convenience
            command = None
        # If no specific command, just open terminal in the file's directory
        if command is None:
            directory = file_path.parent
        else:
            directory = file_path.parent

        self.open_external_terminal(str(directory), command)

        if command:
            self.status_message.setText(f"Running {file_path.name}...")
            QTimer.singleShot(4000, lambda: self.status_message.setText(""))

    def clear_terminal(self):
        """Clear terminal output"""
        self.terminal.clear()
        #self.terminal.append("=== Simple Terminal ===\n")
        #self.terminal.show_prompt()

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


    def open_external_terminal(self, directory=None, command=None):
        """Open system's default terminal in the given directory, optionally running a command"""
        if directory is None:
            from ide import WORKSPACE_PATH
            directory = str(Path.home() / WORKSPACE_PATH)

        directory = str(Path(directory).resolve())

        if not os.path.isdir(directory):
            QMessageBox.warning(self, "Terminal", f"Directory does not exist: {directory}")
            return

        try:
            if os.name == 'nt':  # Windows
                if command:
                    subprocess.Popen(['wt', 'new-tab', '--title', 'Run', 'cmd', '/c', command + ' & pause'], cwd=directory)
                else:
                    subprocess.Popen(['wt', '-d', directory])
            elif sys.platform == 'darwin':  # macOS
                if command:
                    script = f'''
                    tell application "Terminal"
                        do script "cd \\"{directory}\\" && {command} && exec $SHELL"
                        activate
                    end tell
                    '''
                else:
                    script = f'''
                    tell application "Terminal"
                        do script "cd \\"{directory}\\""
                        activate
                    end tell
                    '''
                subprocess.Popen(['osascript', '-e', script])
            else:  # Linux / Unix
                launched = False

                # Try common terminals that support --working-directory
                for term, flag in [
                    ('gnome-terminal', '--working-directory'),
                    ('konsole', '--workdir'),
                    ('xfce4-terminal', '--working-directory'),
                    ('tilix', '--working-directory'),
                    ('kitty', '--directory'),
                    ('alacritty', '--working-directory'),
                    ('terminator', '--working-directory'),
                ]:
                    try:
                        if command:
                            # Run command and keep terminal open
                            subprocess.Popen([term, flag, directory, '--', 'bash', '-c', f'{command} && exec bash'])
                        else:
                            subprocess.Popen([term, flag, directory])
                        launched = True
                        break
                    except FileNotFoundError:
                        continue

                # Special handling for gnome-terminal if above didn't work (older versions)
                if not launched and shutil.which('gnome-terminal'):
                    try:
                        if command:
                            full_cmd = f"cd '{directory}' && {command} && exec bash"
                            subprocess.Popen(['gnome-terminal', '--', 'bash', '-c', full_cmd])
                        else:
                            subprocess.Popen(['gnome-terminal', '--working-directory=' + directory])
                        launched = True
                    except:
                        pass

                # Fallback: xterm or similar
                if not launched:
                    try:
                        if command:
                            subprocess.Popen(['xterm', '-e', f'cd "{directory}" && {command} && exec $SHELL'])
                        else:
                            subprocess.Popen(['xterm', '-hold', '-e', f'cd "{directory}" && exec $SHELL'])
                        launched = True
                    except FileNotFoundError:
                        pass

                if not launched:
                    QMessageBox.warning(self, "Terminal", "Could not find a supported terminal emulator.")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open terminal: {str(e)}")


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    ide = WorkspaceIDE()
    ide.show()

	# delay the execution of the `apply_initial_layout()
    from PyQt6.QtCore import QTimer
    QTimer.singleShot(100, ide.apply_initial_layout)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
