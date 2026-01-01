# ide/plugins/Codeintelligence.py

"""
Code Intelligence Plugin - Pure Class-Based Architecture

Provides comprehensive symbol indexing and navigation.
All functionality is encapsulated in the CodeIntelligencePlugin class.
"""

from pathlib import Path
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QCheckBox
from PyQt6.QtCore import QThread, pyqtSignal, QTimer

# Import Code Intelligence components
import sys
from pathlib import Path

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


# ============================================================================
# Main Plugin Class
# ============================================================================

class CodeIntelligencePlugin:
    """
    Code Intelligence Plugin - All functionality in one class
    
    No globals, no wrapper functions - pure OOP design
    """
    
    # Plugin metadata (class attributes)
    PLUGIN_NAME = "Code Intelligence"
    PLUGIN_VERSION = "1.0.0"
    PLUGIN_DESCRIPTION = "Symbol indexing and code navigation"
    PLUGIN_RUN_ON_STARTUP = True
    PLUGIN_HAS_UI = True
    PLUGIN_ICON = "🧠"
    
    def __init__(self, api):
        """
        Initialize plugin instance
        
        Args:
            api: PluginAPI instance for IDE integration
        """
        self.api = api
        self.database = None
        self.indexer = None
        self.nav_manager = None
        self.ref_tracker = None
        self.symbol_panel = None
        self.indexing_thread = None
        self.auto_index_enabled = True
        self.initialized = False
        
        print(f"[{self.PLUGIN_NAME}] Plugin instance created")
    
    def initialize(self):
        """Initialize plugin components"""
        if self.initialized:
            print(f"[{self.PLUGIN_NAME}] Already initialized")
            return
        
        # Initialize components
        cache_dir = self.api.get_workspace_path() / ".code_intelligence"
        cache_dir.mkdir(exist_ok=True)
        
        self.database = SymbolDatabase(cache_dir)
        self.indexer = SymbolIndexer()
        self.nav_manager = NavigationManager(self.database, self.api)
        self.ref_tracker = ReferenceTracker(self.database)
        
        print(f"[{self.PLUGIN_NAME}] Plugin initialized")
        
        # Register hooks
        self.api.register_hook('on_file_saved', self.on_file_saved, plugin_id='code_intelligence')
        self.api.register_hook('on_file_opened', self.on_file_opened, plugin_id='code_intelligence')
        self.api.register_hook('on_workspace_opened', self.on_workspace_opened, plugin_id='code_intelligence')
        
        # Register keyboard shortcuts
        if hasattr(self.api, 'register_keyboard_shortcut'):
            self.api.register_keyboard_shortcut('Ctrl+T', self.show_symbol_search, 'Quick Symbol Search')
            self.api.register_keyboard_shortcut('Ctrl+Shift+G', self.jump_to_definition, 'Jump to Definition')
            self.api.register_keyboard_shortcut('Ctrl+Shift+R', self.show_references, 'Find All References')
        
        self.api.show_status_message("Code Intelligence initialized", 2000)
        
        self.initialized = True
    
    def get_widget(self, parent=None):
        """Return plugin UI widget"""
        return CodeIntelligenceWidget(self, parent)
    
    def cleanup(self):
        """Cleanup plugin resources"""
        print(f"[{self.PLUGIN_NAME}] Cleaning up...")
        
        if self.database:
            self.database.save_to_cache()
            print(f"[{self.PLUGIN_NAME}] Saved symbol cache")
        
        if self.indexing_thread and self.indexing_thread.isRunning():
            print(f"[{self.PLUGIN_NAME}] Stopping indexing thread...")
            self.indexing_thread.terminate()
            self.indexing_thread.wait()
        
        if self.api:
            self.api.unregister_all_plugin_hooks('code_intelligence')
        
        self.initialized = False
        print(f"[{self.PLUGIN_NAME}] Cleaned up")
    
    # ========================================================================
    # Event Handlers
    # ========================================================================
    
    def on_file_saved(self, file_path: str):
        """Handle file save - re-index if enabled"""
        if not self.auto_index_enabled:
            return
        
        self.index_file(file_path)
        
        if self.symbol_panel and self.symbol_panel.current_file == file_path:
            self.symbol_panel.refresh_symbols()
    
    def on_file_opened(self, file_path: str):
        """Handle file open - update symbol panel"""
        if self.symbol_panel:
            self.symbol_panel.set_file(file_path)
    
    def on_workspace_opened(self):
        """Handle workspace open"""
        print(f"[{self.PLUGIN_NAME}] Workspace opened")
    
    # ========================================================================
    # Indexing Methods
    # ========================================================================
    
    def index_file(self, file_path: str):
        """Index a single file"""
        if not self.database or not self.indexer:
            return
        
        try:
            self.database.remove_file(file_path)
            symbols = self.indexer.index_file(file_path)
            self.database.add_symbols(symbols)
            print(f"[{self.PLUGIN_NAME}] Indexed {file_path}: {len(symbols)} symbols")
        except Exception as e:
            print(f"[{self.PLUGIN_NAME}] Error indexing {file_path}: {e}")
    
    def index_workspace(self):
        """Index active projects (background thread)"""
        settings = self.api.get_settings()
        active_projects = settings.get('active_projects', [])
        
        if not active_projects:
            self.api.show_status_message("No active projects selected", 3000)
            return
        
        self.indexing_thread = IndexingThread(active_projects, self.indexer, self.database)
        self.indexing_thread.progress.connect(self.on_indexing_progress)
        self.indexing_thread.finished_signal.connect(self.on_indexing_complete)
        self.indexing_thread.start()
        
        self.api.show_status_message(f"Indexing {len(active_projects)} projects...", 2000)
    
    def on_indexing_progress(self, message: str):
        """Handle indexing progress"""
        self.api.show_status_message(message, 1000)
    
    def on_indexing_complete(self, total_symbols: int):
        """Handle indexing completion"""
        self.api.show_status_message(f"Indexing complete: {total_symbols:,} symbols", 3000)
        
        if self.database:
            self.database.save_to_cache()
    
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
        
        result = self.nav_manager.get_symbol_at_cursor()
        if not result:
            self.api.show_status_message("No symbol at cursor", 2000)
            return
        
        symbol_name, file_path, line, column = result
        definition = self.nav_manager.find_definition(symbol_name, file_path)
        
        if definition:
            self.nav_manager.jump_to_symbol(definition)
        else:
            self.api.show_status_message(f"Definition not found: {symbol_name}", 2000)
    
    def show_references(self):
        """Show all references to symbol at cursor"""
        if not self.nav_manager or not self.ref_tracker:
            return
        
        result = self.nav_manager.get_symbol_at_cursor()
        if not result:
            self.api.show_status_message("No symbol at cursor", 2000)
            return
        
        symbol_name, file_path, line, column = result
        references = self.ref_tracker.find_all_references(symbol_name)
        
        if references:
            self.api.show_status_message(f"Found {len(references)} references to '{symbol_name}'", 3000)
        else:
            self.api.show_status_message(f"No references found for '{symbol_name}'", 2000)
    
    def get_statistics(self):
        """Get database statistics"""
        if self.database:
            return self.database.get_statistics()
        return {
            'total_symbols': 0,
            'files_indexed': 0,
            'classes': 0,
            'functions': 0,
            'methods': 0
        }


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
    
    def run(self):
        """Index all Python files in active projects"""
        total_symbols = 0
        files_indexed = 0
        
        indexed_files = []
        for project_path in self.project_paths:
            if project_path.exists():
                indexed_files.extend(list(project_path.rglob('*.py')))
                indexed_files.extend(list(project_path.rglob('*.php')))
                indexed_files.extend(list(project_path.rglob('*.go')))
        
        for i, file_path in enumerate(indexed_files, 1):
            if any(part.startswith('.') for part in file_path.parts):
                continue
            
            if 'venv' in file_path.parts or 'env' in file_path.parts or '__pycache__' in file_path.parts:
                continue
            
            try:
                self.database.remove_file(str(file_path))
                symbols = self.indexer.index_file(str(file_path))
                self.database.add_symbols(symbols)
                
                total_symbols += len(symbols)
                files_indexed += 1
                
                if i % 10 == 0:
                    self.progress.emit(f"Indexing: {files_indexed}/{len(indexed_files)} files...")
            
            except Exception as e:
                print(f"[IndexingThread] Error indexing {file_path}: {e}")
        
        self.finished_signal.emit(total_symbols)


# ============================================================================
# Plugin UI Widget
# ============================================================================

class CodeIntelligenceWidget(QWidget):
    """Main plugin control panel - receives plugin instance"""
    
    def __init__(self, plugin, parent=None):
        super().__init__(parent)
        self.plugin = plugin  # Reference to plugin instance
        self.stats_label = None
        self.projects_label = None
        
        self.init_ui()
        
        # Update stats every 2 seconds
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_statistics)
        self.update_timer.start(2000)
    
    def init_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout(self)
        
        # Header
        header = QLabel(f"{self.plugin.PLUGIN_ICON} {self.plugin.PLUGIN_NAME} ({self.plugin.PLUGIN_VERSION})")
        header.setStyleSheet("font-size: 18px; font-weight: bold; color: #4A9EFF; padding: 10px;")
        layout.addWidget(header)
        
        # Description
        desc = QLabel(
            "Symbol indexing and code navigation system.\n\n"
            "Features:\n"
            "• Jump to definition (Ctrl+Shift+G)\n"
            "• Quick symbol search (Ctrl+T)\n"
            "• Find all references\n"
            "• Auto-index on save"
        )
        desc.setStyleSheet("color: #CCC; padding: 10px;")
        layout.addWidget(desc)
        
        # Statistics
        self.stats_label = QLabel()
        self.stats_label.setStyleSheet("color: #AAA; padding: 10px; background: #2D2D2D; border-radius: 5px;")
        self.stats_label.setWordWrap(True)
        layout.addWidget(self.stats_label)
        
        # Active projects
        self.projects_label = QLabel()
        self.projects_label.setStyleSheet("color: #AAA; padding: 10px; background: #2D2D2D; border-radius: 5px; margin-top: 5px;")
        self.projects_label.setWordWrap(True)
        layout.addWidget(self.projects_label)
        
        # Initial update
        self.update_statistics()
        
        # Actions
        actions_layout = QVBoxLayout()
        
        btn_index = QPushButton("🔄 Index Active Projects")
        btn_index.clicked.connect(self.on_index_workspace)
        btn_index.setStyleSheet("padding: 10px;")
        actions_layout.addWidget(btn_index)
        
        btn_search = QPushButton("🔍 Quick Symbol Search (Ctrl+T)")
        btn_search.clicked.connect(self.plugin.show_symbol_search)
        btn_search.setStyleSheet("padding: 10px;")
        actions_layout.addWidget(btn_search)
        
        btn_jump = QPushButton("🎯 Jump to Definition (Ctrl+Shift+G)")
        btn_jump.clicked.connect(self.plugin.jump_to_definition)
        btn_jump.setStyleSheet("padding: 10px;")
        actions_layout.addWidget(btn_jump)
        
        btn_refs = QPushButton("📋 Find All References")
        btn_refs.clicked.connect(self.plugin.show_references)
        btn_refs.setStyleSheet("padding: 10px;")
        actions_layout.addWidget(btn_refs)
        
        layout.addLayout(actions_layout)
        
        # Settings
        settings_layout = QVBoxLayout()
        
        self.auto_index_checkbox = QCheckBox("Auto-index on save")
        self.auto_index_checkbox.setChecked(self.plugin.auto_index_enabled)
        self.auto_index_checkbox.stateChanged.connect(self.on_auto_index_changed)
        settings_layout.addWidget(self.auto_index_checkbox)
        
        layout.addLayout(settings_layout)
        
        layout.addStretch()
    
    def update_statistics(self):
        """Update statistics display"""
        stats = self.plugin.get_statistics()
        
        stats_text = (
            f"📊 <b>Statistics:</b><br>"
            f"&nbsp;&nbsp;• Total symbols: {stats['total_symbols']:,}<br>"
            f"&nbsp;&nbsp;• Files indexed: {stats['files_indexed']:,}<br>"
            f"&nbsp;&nbsp;• Classes: {stats['classes']:,}<br>"
            f"&nbsp;&nbsp;• Functions: {stats['functions']:,}<br>"
            f"&nbsp;&nbsp;• Methods: {stats['methods']:,}"
        )
        self.stats_label.setText(stats_text)
        
        # Show active projects
        settings = self.plugin.api.get_settings()
        active_projects = settings.get('active_projects', [])
        if active_projects:
            project_names = [Path(p).name for p in active_projects]
            projects_text = (
                f"📁 <b>Active Projects ({len(active_projects)}):</b><br>"
                f"&nbsp;&nbsp;• " + "<br>&nbsp;&nbsp;• ".join(project_names)
            )
            self.projects_label.setText(projects_text)
        else:
            self.projects_label.setText("⚠️ No active projects selected")
    
    def on_index_workspace(self):
        """Handle index workspace button"""
        self.plugin.index_workspace()
        QTimer.singleShot(1000, self.update_statistics)
    
    def on_auto_index_changed(self, state):
        """Handle auto-index checkbox"""
        self.plugin.auto_index_enabled = (state == 2)
        print(f"[{self.plugin.PLUGIN_NAME}] Auto-index: {self.plugin.auto_index_enabled}")
