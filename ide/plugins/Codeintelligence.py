# ide/plugins/Codeintelligence.py

"""
Code Intelligence Plugin - Pure Class-Based Architecture

Provides symbol indexing and navigation. The UI (Symbols / References / Index)
lives in the IDE's right sidebar.
All functionality is encapsulated in the CodeIntelligencePlugin class.
"""

import os
import sys
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QCheckBox, QTabWidget
)
from PyQt6.QtCore import QThread, pyqtSignal, QTimer

# Add the Codeintelligence directory to path
plugin_dir = Path(__file__).parent
if str(plugin_dir) not in sys.path:
    sys.path.insert(0, str(plugin_dir))

from Codeintelligence.SymbolInfo import SymbolInfo
from Codeintelligence.SymbolDatabase import SymbolDatabase
from Codeintelligence.SymbolIndexer import SymbolIndexer
from Codeintelligence.NavigationManager import NavigationManager
from Codeintelligence.ReferenceTracker import ReferenceTracker
from Codeintelligence.SymbolSearchDialog import SymbolSearchDialog
from Codeintelligence.SymbolPanelWidget import SymbolPanelWidget
from Codeintelligence.ReferencesPanel import ReferencesPanel

SUPPORTED_EXTENSIONS = {'.py', '.php', '.go'}
# Directory *names* skipped while indexing (relative to each project root)
EXCLUDED_DIRS = {'venv', 'env', 'node_modules', '__pycache__', 'site-packages'}


# ============================================================================
# Main Plugin Class
# ============================================================================

class CodeIntelligencePlugin:
    """
    Code Intelligence Plugin - All functionality in one class

    No globals, no wrapper functions - pure OOP design
    """

    PLUGIN_NAME = "Code Intelligence"
    PLUGIN_VERSION = "1.1.0"
    PLUGIN_DESCRIPTION = "Symbol indexing and code navigation"
    PLUGIN_RUN_ON_STARTUP = True
    PLUGIN_HAS_UI = True
    PLUGIN_ICON = "🧠"

    SIDEBAR_TITLE = "Code Intel"    # tab title in the right sidebar
    SIDEBAR_RETRIES = 20            # right_sidebar may not exist yet at startup

    def __init__(self, api):
        self.api = api
        self.database = None
        self.indexer = None
        self.nav_manager = None
        self.ref_tracker = None
        self.panel = None
        self.symbol_panel = None
        self.indexing_thread = None
        self.auto_index_enabled = True
        self.initialized = False
        self._sidebar_attached = False
        self._full_index_done = False   # True once the cache loaded or a full index ran

        print(f"[{self.PLUGIN_NAME}] Plugin instance created")

    def initialize(self):
        """Initialize plugin components"""
        if self.initialized:
            print(f"[{self.PLUGIN_NAME}] Already initialized")
            return

        cache_dir = self.api.app_dirs.plugin_dir("code-intelligence")
        cache_dir.mkdir(parents=True, exist_ok=True)

        self.database = SymbolDatabase(cache_dir)
        self.indexer = SymbolIndexer()
        self.nav_manager = NavigationManager(self.database, self.api)
        self.ref_tracker = ReferenceTracker(self.database, self.api)

        removed = self.database.prune_missing_files()
        self._full_index_done = self.database.get_statistics()['total_symbols'] > 0
        if removed:
            print(f"[{self.PLUGIN_NAME}] Pruned {removed} deleted files from cache")
        print(f"[{self.PLUGIN_NAME}] Plugin initialized (cache: {cache_dir})")

        # Hooks
        pid = 'code_intelligence'
        self.api.register_hook('on_file_saved', self.on_file_saved, plugin_id=pid)
        self.api.register_hook('on_file_opened', self.on_file_opened, plugin_id=pid)
        self.api.register_hook('on_file_deleted', self.on_file_deleted, plugin_id=pid)
        self.api.register_hook('on_editor_focus', self.on_editor_focus, plugin_id=pid)
        self.api.register_hook('on_workspace_opened', self.on_workspace_opened, plugin_id=pid)

        # Keyboard shortcuts
        if hasattr(self.api, 'register_keyboard_shortcut'):
            self.api.register_keyboard_shortcut('Ctrl+T', self.show_symbol_search, 'Quick Symbol Search')
            self.api.register_keyboard_shortcut('Ctrl+Shift+G', self.jump_to_definition, 'Jump to Definition')
            self.api.register_keyboard_shortcut('Ctrl+Shift+R', self.show_references, 'Find All References')

        self.initialized = True

        # Right sidebar panel (retries until the sidebar exists)
        self._install_sidebar_panel()

        # First run / empty cache: build the index in the background
        QTimer.singleShot(1500, self._startup_index)

        self.api.show_status_message("Code Intelligence initialized", 2000)

    # ------------------------------------------------------------------
    # Right sidebar
    # ------------------------------------------------------------------

    def _install_sidebar_panel(self, attempt: int = 0):
        if self._sidebar_attached or not self.initialized:
            return

        if not hasattr(self.api.ide, 'right_sidebar'):
            if attempt < self.SIDEBAR_RETRIES:
                QTimer.singleShot(500, lambda: self._install_sidebar_panel(attempt + 1))
            else:
                print(f"[{self.PLUGIN_NAME}] right_sidebar never appeared - panel not installed")
            return

        if self.panel is None:
            self.panel = CodeIntelligencePanel(self)
            self.symbol_panel = self.panel.symbols

        if self.api.add_to_right_sidebar(self.panel, self.SIDEBAR_TITLE, self.PLUGIN_ICON):
            self._sidebar_attached = True
            editor = self.api.get_current_editor()
            path = getattr(editor, 'file_path', None)
            if path:
                self._ensure_indexed(path)
                self.symbol_panel.set_file(path)

    def get_widget(self, parent=None):
        """
        Widget for the plugin host. The real UI lives in the right sidebar, so
        this is just a pointer to it (avoids two live copies of the panel).
        """
        widget = QWidget(parent)
        layout = QVBoxLayout(widget)
        label = QLabel(f"{self.PLUGIN_ICON} {self.PLUGIN_NAME} lives in the right sidebar.")
        label.setWordWrap(True)
        layout.addWidget(label)
        button = QPushButton("Show panel")
        button.clicked.connect(lambda: self.api.focus_right_sidebar_tab(self.SIDEBAR_TITLE))
        layout.addWidget(button)
        layout.addStretch()
        return widget

    def cleanup(self):
        """Cleanup plugin resources"""
        print(f"[{self.PLUGIN_NAME}] Cleaning up...")

        if self.indexing_thread and self.indexing_thread.isRunning():
            self.indexing_thread.requestInterruption()
            self.indexing_thread.wait(3000)

        if self.database:
            self.database.save_to_cache()

        if self.panel is not None and self.api:
            self.api.remove_from_right_sidebar(self.panel)
            self.panel.deleteLater()
            self.panel = None
            self.symbol_panel = None
            self._sidebar_attached = False

        if self.api:
            self.api.unregister_all_plugin_hooks('code_intelligence')

        self.initialized = False
        print(f"[{self.PLUGIN_NAME}] Cleaned up")

    # ========================================================================
    # Event Handlers
    # ========================================================================

    @staticmethod
    def _supported(file_path) -> bool:
        return Path(str(file_path)).suffix.lower() in SUPPORTED_EXTENSIONS

    def _ensure_indexed(self, file_path):
        """Index a file on demand if the database has never seen it."""
        file_path = str(file_path)
        if self.database and self._supported(file_path) \
                and not self.database.has_file(file_path) and os.path.isfile(file_path):
            self.index_file(file_path)

    def on_file_saved(self, file_path: str):
        """Handle file save - re-index if enabled"""
        if not self.auto_index_enabled or not self._supported(file_path):
            return
        self.index_file(str(file_path))
        if self.symbol_panel and self.symbol_panel.current_file == str(file_path):
            self.symbol_panel.refresh_symbols()

    def on_file_opened(self, file_path: str):
        """Handle file open - index on demand, update symbol panel"""
        self._ensure_indexed(file_path)
        if self.symbol_panel:
            self.symbol_panel.set_file(str(file_path))

    def on_file_deleted(self, file_path: str, *args):
        if self.database:
            self.database.remove_file(str(file_path))

    def on_editor_focus(self, *args):
        """Tab/editor switched - keep the Symbols tab in sync"""
        editor = self.api.get_current_editor()
        path = getattr(editor, 'file_path', None)
        if not path:
            return
        self._ensure_indexed(path)
        if self.symbol_panel and self.symbol_panel.current_file != str(path):
            self.symbol_panel.set_file(str(path))

    def on_workspace_opened(self):
        print(f"[{self.PLUGIN_NAME}] Workspace opened")
        self._install_sidebar_panel()

    # ========================================================================
    # Indexing Methods
    # ========================================================================

    def index_file(self, file_path: str):
        """Index a single file (keeps old symbols if the file doesn't parse)"""
        if not self.database or not self.indexer:
            return
        try:
            symbols = self.indexer.index_file(file_path)
            if symbols is None:          # syntax error mid-edit: keep what we had
                return
            self.database.remove_file(file_path)
            self.database.add_symbols(symbols)
            print(f"[{self.PLUGIN_NAME}] Indexed {file_path}: {len(symbols)} symbols")
        except Exception as e:
            print(f"[{self.PLUGIN_NAME}] Error indexing {file_path}: {e}")

    def _startup_index(self):
        if not self.initialized or self._full_index_done:
            return
        if self.api.get_settings().get('active_projects'):
            print(f"[{self.PLUGIN_NAME}] Empty index - indexing active projects")
            self.index_workspace()

    def index_workspace(self, rebuild: bool = False):
        """Index active projects (background thread)"""
        if self.indexing_thread and self.indexing_thread.isRunning():
            self.api.show_status_message("Indexing already running...", 2000)
            return

        active_projects = self.api.get_settings().get('active_projects', [])
        if not active_projects:
            self.api.show_status_message("No active projects selected", 3000)
            return

        if rebuild:
            self.database.clear()

        self.indexing_thread = IndexingThread(active_projects, self.indexer, self.database)
        self.indexing_thread.progress.connect(self.on_indexing_progress)
        self.indexing_thread.finished_signal.connect(self.on_indexing_complete)
        self.indexing_thread.start()

        self.api.show_status_message(f"Indexing {len(active_projects)} projects...", 2000)

    def on_indexing_progress(self, message: str):
        self.api.show_status_message(message, 1000)

    def on_indexing_complete(self, total_symbols: int):
        self._full_index_done = True
        self.api.show_status_message(f"Indexing complete: {total_symbols:,} symbols", 3000)
        if self.database:
            self.database.save_to_cache()
        if self.symbol_panel:
            self.symbol_panel.refresh_symbols()

    # ========================================================================
    # Navigation Methods
    # ========================================================================

    def show_symbol_search(self):
        """Show quick symbol search dialog"""
        if not self.database or not self.nav_manager:
            return

        dialog = SymbolSearchDialog(self.database, self.nav_manager, parent=self.api.ide)
        if dialog.exec():
            if dialog.selected_symbol:
                self.nav_manager.jump_to_symbol(dialog.selected_symbol)

    def jump_to_definition(self):
        """Jump to definition of symbol at cursor"""
        if not self.nav_manager:
            return

        ctx = self.nav_manager.get_cursor_context()
        if not ctx:
            self.api.show_status_message("No symbol at cursor", 2000)
            return

        name = ctx['name']
        self._ensure_indexed(ctx['file_path'])

        ranked = self.nav_manager.rank_definitions(name, ctx['file_path'], ctx['is_attribute'])
        if ranked:
            best_score = ranked[0][0]
            runner_up = ranked[1][0] if len(ranked) > 1 else None
            # Single hit, or one candidate clearly ahead (same file / imported from)
            if runner_up is None or best_score - runner_up >= 100:
                self.nav_manager.jump_to_symbol(ranked[0][1])
            else:
                self.nav_manager.choose_and_jump([s for _, s in ranked])
            return

        # No symbol: on an import line the target may be a module file
        if ctx['is_import']:
            files = self.nav_manager.find_module_files(ctx['dotted'])
            if len(files) == 1:
                self.nav_manager.jump_to_location(files[0], 1, 0)
                return
            if files:
                self.nav_manager.choose_file_and_open(files)
                return

        if not self._full_index_done:
            # Only the current file is known so far - build the full index now
            self.api.show_status_message(
                f"Definition not found: {name} - project not indexed yet, indexing now (try again shortly)...", 5000)
            self.index_workspace()
        else:
            stats = self.get_statistics()
            projects = len(self.api.get_settings().get('active_projects', []) or [])
            self.api.show_status_message(
                f"Definition not found: {name} ({stats['files_indexed']} files indexed "
                f"in {projects} active projects)", 4000)

    def show_references(self):
        """Find all references to the symbol at cursor and show them in the sidebar"""
        if not self.nav_manager or not self.ref_tracker:
            return

        ctx = self.nav_manager.get_cursor_context()
        if not ctx:
            self.api.show_status_message("No symbol at cursor", 2000)
            return

        name = ctx['name']
        references = self.ref_tracker.find_all_references(name)

        if self.panel is not None:
            self.panel.show_references(name, references)
            self.api.focus_right_sidebar_tab(self.SIDEBAR_TITLE)

        if references:
            files = len({r.file_path for r in references})
            self.api.show_status_message(
                f"Found {len(references)} references to '{name}' in {files} files", 3000)
        else:
            self.api.show_status_message(f"No references found for '{name}'", 2000)

    def get_statistics(self):
        """Get database statistics"""
        if self.database:
            return self.database.get_statistics()
        return {'total_symbols': 0, 'files_indexed': 0, 'classes': 0,
                'functions': 0, 'methods': 0}


# ============================================================================
# Background Indexing Thread
# ============================================================================

class IndexingThread(QThread):
    """Background thread for indexing active projects"""

    progress = pyqtSignal(str)
    finished_signal = pyqtSignal(int)

    def __init__(self, project_paths: list, indexer: SymbolIndexer, database: SymbolDatabase):
        super().__init__()
        self.project_paths = [Path(p) for p in project_paths]
        self.indexer = indexer
        self.database = database

    def _collect_files(self):
        """Walk projects, pruning excluded directories instead of descending into them."""
        files, seen = [], set()
        for project in self.project_paths:
            if not project.exists():
                continue
            for root, dirs, names in os.walk(project):
                dirs[:] = [d for d in dirs if not d.startswith('.') and d not in EXCLUDED_DIRS]
                for name in names:
                    if Path(name).suffix.lower() in SUPPORTED_EXTENSIONS:
                        path = os.path.join(root, name)
                        if path not in seen:
                            seen.add(path)
                            files.append(path)
            if self.isInterruptionRequested():
                break
        return files

    def run(self):
        """Index all supported files in active projects"""
        total_symbols = 0
        files_indexed = 0

        files = self._collect_files()

        for i, path in enumerate(files, 1):
            if self.isInterruptionRequested():
                break
            try:
                symbols = self.indexer.index_file(path)
                if symbols is None:      # unparseable: keep any earlier symbols
                    continue
                self.database.remove_file(path)
                self.database.add_symbols(symbols)
                total_symbols += len(symbols)
                files_indexed += 1
                if i % 10 == 0:
                    self.progress.emit(f"Indexing: {i}/{len(files)} files...")
            except Exception as e:
                print(f"[IndexingThread] Error indexing {path}: {e}")

        self.finished_signal.emit(total_symbols)


# ============================================================================
# Plugin UI
# ============================================================================

class CodeIntelligencePanel(QTabWidget):
    """Right-sidebar panel: Symbols | References | Index"""

    def __init__(self, plugin, parent=None):
        super().__init__(parent)
        self.plugin = plugin

        self.symbols = SymbolPanelWidget(plugin.database, plugin.nav_manager)
        self.references = ReferencesPanel(plugin.nav_manager)
        self.control = CodeIntelligenceWidget(plugin)

        self.addTab(self.symbols, "Symbols")
        self.addTab(self.references, "Refs")
        self.addTab(self.control, "Index")

    def show_references(self, symbol_name: str, references: list):
        self.references.show_results(symbol_name, references)
        self.setCurrentWidget(self.references)


class CodeIntelligenceWidget(QWidget):
    """Index control panel - statistics, projects and actions"""

    def __init__(self, plugin, parent=None):
        super().__init__(parent)
        self.plugin = plugin
        self.stats_label = None
        self.projects_label = None

        self.init_ui()

        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.update_statistics)
        self.update_timer.start(3000)

    def init_ui(self):
        layout = QVBoxLayout(self)

        header = QLabel(f"{self.plugin.PLUGIN_ICON} {self.plugin.PLUGIN_NAME} ({self.plugin.PLUGIN_VERSION})")
        header.setStyleSheet("font-size: 16px; font-weight: bold; color: #4A9EFF; padding: 6px;")
        header.setWordWrap(True)
        layout.addWidget(header)

        desc = QLabel(
            "• Jump to definition (Ctrl+Shift+G)\n"
            "• Quick symbol search (Ctrl+T)\n"
            "• Find all references (Ctrl+Shift+R)\n"
            "• Auto-index on save"
        )
        desc.setStyleSheet("color: #CCC; padding: 6px;")
        layout.addWidget(desc)

        self.stats_label = QLabel()
        self.stats_label.setStyleSheet("color: #AAA; padding: 8px; background: #2D2D2D; border-radius: 5px;")
        self.stats_label.setWordWrap(True)
        layout.addWidget(self.stats_label)

        self.projects_label = QLabel()
        self.projects_label.setStyleSheet("color: #AAA; padding: 8px; background: #2D2D2D; border-radius: 5px; margin-top: 5px;")
        self.projects_label.setWordWrap(True)
        layout.addWidget(self.projects_label)

        self.update_statistics()

        btn_index = QPushButton("🔄 Index Active Projects")
        btn_index.clicked.connect(self.on_index_workspace)
        layout.addWidget(btn_index)

        btn_rebuild = QPushButton("🧹 Clear && Rebuild Index")
        btn_rebuild.clicked.connect(self.on_rebuild)
        layout.addWidget(btn_rebuild)

        btn_search = QPushButton("🔍 Quick Symbol Search (Ctrl+T)")
        btn_search.clicked.connect(self.plugin.show_symbol_search)
        layout.addWidget(btn_search)

        btn_jump = QPushButton("🎯 Jump to Definition (Ctrl+Shift+G)")
        btn_jump.clicked.connect(self.plugin.jump_to_definition)
        layout.addWidget(btn_jump)

        btn_refs = QPushButton("📋 Find All References (Ctrl+Shift+R)")
        btn_refs.clicked.connect(self.plugin.show_references)
        layout.addWidget(btn_refs)

        self.auto_index_checkbox = QCheckBox("Auto-index on save")
        self.auto_index_checkbox.setChecked(self.plugin.auto_index_enabled)
        self.auto_index_checkbox.toggled.connect(self.on_auto_index_changed)
        layout.addWidget(self.auto_index_checkbox)

        layout.addStretch()

    def update_statistics(self):
        """Update statistics display (skipped while the tab isn't visible)"""
        if not self.isVisible() and self.stats_label.text():
            return
        stats = self.plugin.get_statistics()

        self.stats_label.setText(
            f"📊 <b>Statistics:</b><br>"
            f"&nbsp;&nbsp;• Total symbols: {stats['total_symbols']:,}<br>"
            f"&nbsp;&nbsp;• Files indexed: {stats['files_indexed']:,}<br>"
            f"&nbsp;&nbsp;• Classes: {stats['classes']:,}<br>"
            f"&nbsp;&nbsp;• Functions: {stats['functions']:,}<br>"
            f"&nbsp;&nbsp;• Methods: {stats['methods']:,}"
        )

        active_projects = self.plugin.api.get_settings().get('active_projects', [])
        if active_projects:
            names = [Path(p).name for p in active_projects]
            self.projects_label.setText(
                f"📁 <b>Active Projects ({len(active_projects)}):</b><br>"
                f"&nbsp;&nbsp;• " + "<br>&nbsp;&nbsp;• ".join(names)
            )
        else:
            self.projects_label.setText("⚠️ No active projects selected")

    def on_index_workspace(self):
        self.plugin.index_workspace()
        QTimer.singleShot(1000, self.update_statistics)

    def on_rebuild(self):
        self.plugin.index_workspace(rebuild=True)
        QTimer.singleShot(1000, self.update_statistics)

    def on_auto_index_changed(self, checked: bool):
        self.plugin.auto_index_enabled = checked
        print(f"[{self.plugin.PLUGIN_NAME}] Auto-index: {checked}")