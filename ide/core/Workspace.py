# ============================================================================
# Workspace.py (Main Class)
# ============================================================================

"""
Workspace - Acts as an orchestrator
All heavy lifting is delegated to manager classes
"""

# Import Python classes
import sys
from pathlib import Path

# Import PyQt6 classes
from PyQt6.QtWidgets import (
    QMainWindow, QApplication, QWidget, QMenu, QVBoxLayout, QHBoxLayout, 
    QSplitter, QTabWidget, QTreeView, QLabel, QMessageBox, QDialog, 
    QInputDialog, QSpacerItem, QGridLayout
)

from PyQt6.QtGui import QFileSystemModel, QShortcut, QKeySequence, QTextCursor
from PyQt6.QtCore import Qt, QTimer

# Import IDE Core classes
from ide import VERSION, WORKSPACE_PATH
from ide.core.Plugin import PluginManager
from ide.core.PluginAPI import PluginAPI
from ide.core.FindReplace import FindReplaceWidget
from ide.core.QuickOpen import QuickOpenDialog
from ide.core.Settings import SettingsDialog
from ide.core.SettingDescriptor import SettingType, SettingsProvider, SettingDescriptor
from ide.core.Document import DocumentDialog
from ide.core.TabBar import StyledTabWidget
from ide.core.TabSwitcher import TabSwitcherDialog
from ide.core.ProjectsPanel import ProjectsPanel
from ide.core.PluginManagerUI import PluginManagerUI
from ide.core.CodeEditor import CodeEditor
from ide.core.DragDropTreeView import DragDropTreeView
from ide.core.CombinedTreeDelegate import CombinedTreeDelegate
from ide.core.OutlineWidget import OutlineWidget

# Import IDE Core managers classes
from ide.core.managers.FileManager import FileManager
from ide.core.managers.TabManager import TabManager
from ide.core.managers.SessionManager import SessionManager
from ide.core.managers.StatusBarManager import StatusBarManager
from ide.core.managers.SettingsManager import SettingsManager
from ide.core.managers.MenuManager import MenuManager
from ide.core.managers.RecentFilesManager import RecentFilesManager
from ide.core.managers.SplitEditorManager import SplitEditorManager
from ide.core.managers.TabOrderManager import TabOrderManager


class Workspace(QMainWindow, SettingsProvider):
    """
    WorkspaceIDE - Main orchestrator class

    This class now delegates responsibilities to manager classes:
    - FileManager: File operations
    - TabManager: Tab operations
    - SessionManager: Session save/restore
    - StatusBarManager: Status bar updates
    - SettingsManager: Settings persistence
    - MenuManager: Menu creation
    """

    SETTINGS_DESCRIPTORS = [
        SettingDescriptor(
            key='explorer_width',
            label='Explorer Width',
            setting_type=SettingType.INTEGER,
            default=300,
            min_value=150,
            max_value=600,
            suffix=' px',
            description='Width of the file explorer panel',
            section='Layout'
        ),
        SettingDescriptor(
            key='terminal_height',
            label='Terminal Height',
            setting_type=SettingType.INTEGER,
            default=200,
            min_value=100,
            max_value=600,
            suffix=' px',
            description='Height of the terminal panel',
            section='Layout'
        ),
        SettingDescriptor(
            key='restore_session',
            label='Restore Open Tabs on Startup',
            setting_type=SettingType.BOOLEAN,
            default=True,
            description='Automatically reopen files from last session',
            section='General'
        ),
        SettingDescriptor(
            key='auto_save',
            label='Auto-save on Tab Switch',
            setting_type=SettingType.BOOLEAN,
            default=False,
            description='Automatically save files when switching tabs',
            section='General'
        ),
    ]

    def __init__(self):
        super().__init__()

        # Auto-detect from current working directory
        cwd = Path.cwd()

        # Check if CWD looks like a workspace directory
        self.workspace_path = Path.home() / WORKSPACE_PATH
        self.workspace_plugin_path = cwd  / "ide/plugins"
        print(f"ℹ️  Using IDE from: {cwd}")
        print(f"ℹ️  Using IDE plugins from: {self.workspace_plugin_path}")
        print(f"ℹ️  Using workspace data from: {self.workspace_path}")

        # Initialize paths
        self.config_file  = self.workspace_path / ".workspace_ide_config.json"
        self.session_file = self.workspace_path / ".workspace_ide_session.json"

        # Quick open cache
        self.quick_open_cache = []
        self.quick_open_cache_projects = set()
        self.quick_open_cache_time = 0

        # Initialize managers
        self.settings_manager = SettingsManager(self.config_file)

        # Initialize Plugin API/Manager System
        self.plugin_api = PluginAPI(self)
        # print (f"{self.plugin_api._plugins}")

        # Create Plugin Manager (manages plugin files on disk)
        self.plugin_manager = PluginManager(self.workspace_plugin_path, self.plugin_api)
        # self.plugin_manager.scan_plugins()

        # Initialize split manager
        self.split_manager = SplitEditorManager(self)

        # Build UI first
        self.init_ui()

        # Initialize other managers (need UI components first)
        self.file_manager         = FileManager(self.workspace_path, self)
        self.tab_manager          = TabManager(self.tabs, self)
        self.session_manager      = SessionManager(self.session_file, self)
        self.statusbar_manager    = StatusBarManager(self.statusBar(), self)
        self.recent_files_manager = RecentFilesManager(self.settings_manager, self)
        self.menu_manager         = MenuManager(self.menuBar(), self)
        self.tab_order_manager    = TabOrderManager()


        # Register all components that have settings
        self.settings_manager.register_provider(Workspace)
        self.settings_manager.register_provider(CodeEditor)
        self.settings_manager.register_provider(SettingsDialog)
        # self.settings_manager.register_provider(OllamaIntegration)
        
        # Load settings (will use defaults for first run)
        self.settings_manager.load()


        # Expose status_message for compatibility
        self.status_message = self.statusbar_manager.status_message

        # Setup menus
        self._create_menus()

        # Create plugin toolbar AFTER menus
        self.menu_manager.create_plugin_toolbar(self.plugin_manager, self.plugin_ui)

        # Initialize workspace
        self.ensure_workspace()

        # Restore session if enabled
        if self.settings_manager.get('restore_session', True):
            self.session_manager.restore_session(
                self.tab_manager,
                self.settings_manager.settings
            )

        # Restore active projects
        active_projects = self.settings_manager.get('active_projects', [])
        if active_projects:
            self.projects_panel.set_active_projects(active_projects)
            self.update_tree_highlighting()

        # Apply layout
        self.apply_initial_layout()

        # Setup auto-save timer (every 30 seconds)
        self.auto_save_timer = QTimer(self)
        self.auto_save_timer.timeout.connect(self.auto_save_session)
        self.auto_save_timer.start(30000)
        
        # Track if session needs saving (optimization)
        self.session_dirty = False

        # Apply initial settings
        self.apply_settings()


    def apply_settings(self):
        """
        Apply current settings to workspace components.
        
        This method is called:
        - During initialization (__init__)
        - After user changes settings in the settings dialog
        - When settings are programmatically updated
        """
        
        # ========================================================================
        # Layout Settings (from Workspace SETTINGS_DESCRIPTORS)
        # ========================================================================
        
        # Explorer Width
        explorer_width = self.settings_manager.get('explorer_width', 300)
        if hasattr(self, 'main_splitter'):
            left_widget = self.main_splitter.widget(0)
            if left_widget:
                left_widget.setMaximumWidth(explorer_width + 150)  # Allow some flexibility
                # Update splitter sizes if needed
                sizes = self.main_splitter.sizes()
                if sizes[0] != explorer_width:
                    total = sum(sizes)
                    remaining = total - explorer_width
                    self.main_splitter.setSizes([explorer_width, remaining, 0])
        
        # Terminal Height (not currently used, but ready for when you add terminal)
        terminal_height = self.settings_manager.get('terminal_height', 200)
        if hasattr(self, 'terminal') and self.terminal is not None:
            self.terminal.setFixedHeight(terminal_height)
        
        # ========================================================================
        # General Settings (from Workspace SETTINGS_DESCRIPTORS)
        # ========================================================================
        
        # Restore Session - only affects startup, cache the value
        self._restore_session = self.settings_manager.get('restore_session', True)
        
        # Auto-save on Tab Switch - cache for quick access
        self._auto_save_enabled = self.settings_manager.get('auto_save', False)
        
        # ========================================================================
        # Editor Settings (from CodeEditor - when you implement it)
        # Apply to all open editors
        # ========================================================================
        
        editor_font_size = self.settings_manager.get('editor_font_size', 10)
        tab_width = self.settings_manager.get('tab_width', 4)
        show_line_numbers = self.settings_manager.get('show_line_numbers', True)
        gutter_width = self.settings_manager.get('gutter_width', 10)
        
        # Apply to all tabs in the current tab widget
        if hasattr(self, 'tabs'):
            for i in range(self.tabs.count()):
                editor = self.tabs.widget(i)
                if isinstance(editor, CodeEditor):
                    # Update editor settings
                    if hasattr(editor, 'set_font_size'):
                        editor.set_font_size(editor_font_size)
                    if hasattr(editor, 'set_tab_width'):
                        editor.set_tab_width(tab_width)
                    if hasattr(editor, 'set_show_line_numbers'):
                        editor.set_show_line_numbers(show_line_numbers)
                    if hasattr(editor, 'set_gutter_width'):
                        editor.set_gutter_width(gutter_width)
        
        # If using split editor manager, apply to all groups
        if hasattr(self, 'split_manager'):
            for editor in self.split_manager.get_all_editors():
                if isinstance(editor, CodeEditor):
                    if hasattr(editor, 'set_font_size'):
                        editor.set_font_size(editor_font_size)
                    if hasattr(editor, 'set_tab_width'):
                        editor.set_tab_width(tab_width)
                    if hasattr(editor, 'set_show_line_numbers'):
                        editor.set_show_line_numbers(show_line_numbers)
                    if hasattr(editor, 'set_gutter_width'):
                        editor.set_gutter_width(gutter_width)
    
    def should_restore_session(self):
        """Check if we should restore the session on startup"""
        if hasattr(self, '_restore_session'):
            return self._restore_session
        return self.settings_manager.get('restore_session', True)
    
    
    def should_auto_save(self):
        """Check if auto-save is enabled for tab switching"""
        if hasattr(self, '_auto_save_enabled'):
            return self._auto_save_enabled
        return self.settings_manager.get('auto_save', False)

    def init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle(f"Workspace IDE ({VERSION})")
        self.resize(1600, 900)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        # Main horizontal splitter: [Left Sidebar | Editor | Right Sidebar]
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(self.main_splitter)

        # LEFT SIDEBAR - EDITOR - LEFT SIDEBAR
        self._create_left_sidebar()
        self._create_editor_area()
        self._create_right_sidebar()

        # Set initial splitter proportions
        self.main_splitter.setStretchFactor(0, 1)  # Left
        self.main_splitter.setStretchFactor(1, 4)  # Center
        self.main_splitter.setStretchFactor(2, 0)  # Right (hidden)

        # PluginManagerUI Pass both plugin_manager AND plugin_api
        self.plugin_ui = PluginManagerUI(self, self.plugin_manager, self.plugin_api)

        # Setup keyboard shortcuts
        self._setup_shortcuts()

        self.main_splitter.widget(2).hide()

    def _create_left_sidebar(self):
        """Create left sidebar with file explorer and projects"""
        left_tabs = QTabWidget()
        left_tabs.setMaximumWidth(450)

        # File Explorer
        explorer_widget = QWidget()
        explorer_layout = QVBoxLayout(explorer_widget)
        explorer_layout.setContentsMargins(5, 5, 5, 5)

        explorer_label = QLabel("File Explorer")
        explorer_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        explorer_layout.addWidget(explorer_label)

        self.file_model = QFileSystemModel()
        self.file_model.setRootPath(str(self.workspace_path))

        # Create tree view
        self.tree = DragDropTreeView()
        self.tree.setModel(self.file_model)
        self.tree.setRootIndex(self.file_model.index(str(self.workspace_path)))

        # Use combined delegate (replaces both FileIconDelegate and ProjectHighlightDelegate)
        self.tree_delegate = CombinedTreeDelegate(self.file_model, self.tree)
        self.tree.setItemDelegate(self.tree_delegate)

        self.tree.setColumnWidth(0, 450)
        for i in range(1, 4):
            self.tree.setColumnHidden(i, True)

        self.tree.doubleClicked.connect(self.open_file)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.show_explorer_context_menu)

        explorer_layout.addWidget(self.tree)
        left_tabs.addTab(explorer_widget, "📁 Files")

        # Projects Panel
        self.projects_panel = ProjectsPanel(self.workspace_path, self)
        self.projects_panel.projects_changed.connect(self.update_tree_highlighting)
        left_tabs.addTab(self.projects_panel, "📦 Projects")

        self.main_splitter.addWidget(left_tabs)


    def handle_file_moved(self, old_path: str, new_path: str):
        """
        Handle when a file is moved - update open tabs
    
        Args:
            old_path: Original file path
            new_path: New file path
        """
        # Find any open tabs with the old path
        for i in range(self.tabs.count()):
            editor = self.tabs.widget(i)
            if isinstance(editor, CodeEditor) and hasattr(editor, 'file_path') and editor.file_path == old_path:
                # Update the file path
                editor.file_path = new_path
    
                # Update tab title
                new_name = Path(new_path).name
                self.tabs.setTabText(i, new_name)
                self.tabs.setTabToolTip(i, new_path)
    
                # Show notification
                self.status_message.setText(f"Updated tab: {new_name}")
                
                # Mark session dirty
                self.mark_session_dirty()


    def _create_editor_area(self):
        """Create center editor area"""
        editor_container = QWidget()
        editor_layout = QVBoxLayout(editor_container)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        editor_layout.setSpacing(0)

        # Find/Replace widget
        self.find_replace = FindReplaceWidget()
        editor_layout.addWidget(self.find_replace)

        # Initialize split editor manager
        # This creates the initial editor group and returns its tab widget
        self.tabs = self.split_manager.initialize(editor_layout)

        # Setup tab event handlers
        # These are still needed for the primary group
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)

        # BUG CLOSES MUTIPLE TABS AFTER TAB CLOSE
        #self.tabs.tabCloseRequested.connect(lambda idx: self.tab_manager.close_tab(idx)) 

        self.tabs.currentChanged.connect(self.on_editor_tab_changed)
        self.tabs.tabBar().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tabs.tabBar().customContextMenuRequested.connect(self.show_tab_context_menu)

        self.main_splitter.addWidget(editor_container)


    def _create_right_sidebar(self):
        """Create right sidebar with Outline (AI moved to plugin)"""
    
        # Create tab widget for right sidebar
        right_tabs = QTabWidget()
        right_tabs.setMinimumWidth(300)
    
        # Outline tab
        self.outline_widget = OutlineWidget(parent=self)
        right_tabs.addTab(self.outline_widget, "📋 Outline")

        self.main_splitter.addWidget(right_tabs)
        
        # Store reference for plugins to use
        self.right_sidebar = right_tabs


    def _setup_shortcuts(self):
        """Setup keyboard shortcuts"""

        shortcuts = [
            ("F3", self.find_next),
            ("Shift+F3", self.find_previous),
            ("Ctrl+Tab", self.show_tab_switcher),
            ("Ctrl+Shift+Tab", self.cycle_tabs_backward),
        ]

        for key, callback in shortcuts:
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.activated.connect(callback)


    def split_editor_vertical(self):
        self.split_manager.split_vertical()


    def split_editor_horizontal(self):
        self.split_manager.split_horizontal()


    def close_editor_split(self):
        self.split_manager.close_split()


    def move_tab_to_split(self):
        self.split_manager.move_tab_to_other_group()


    def focus_other_split(self):
        self.split_manager.focus_other_group()


    def open_in_split(self):
        """Open current file in split view"""
        # Get the active group's current editor
        active_group = self.split_manager.get_active_group()
        current_editor = active_group.get_current_editor()

        if isinstance(current_editor, CodeEditor) and current_editor.file_path:
            self.split_manager.open_file_in_split(current_editor.file_path)
        else:
            QMessageBox.information(
                self,
                "No File",
                "No file is currently open to split."
            )

    def cycle_tabs_backward(self):
        """Cycle backwards through tabs in recent order (no popup)"""
        if self.tabs.count() < 2:
            return

        current_index = self.tabs.currentIndex()
        recent_order = self.tab_order_manager.get_recent_order(current_index)

        # Get next tab in recent order (backwards = second item, or wrap to last)
        if len(recent_order) > 1:
            next_tab = recent_order[-1]  # Last in recent order = oldest
            self.tabs.setCurrentIndex(next_tab)
            self.tab_order_manager.record_access(next_tab)

    def _create_menus(self):
        """Create all menus using MenuManager"""
        self.menu_manager.style_menubar()
        #self.menu_manager.create_file_menu()
        # REPLACE create_file_menu() with:
        self.menu_manager.create_file_menu_with_recent(self.recent_files_manager)

        self.menu_manager.create_edit_menu()

        # Selection menu
        selection_menu = self.menuBar().addMenu("Selection")
        self.menu_manager._add_action(selection_menu, "Select All", "Ctrl+A", self.select_all_current)

        self.menu_manager.create_view_menu()

        # Create View menu manually (without Ollama)
        #view_menu = self.menuBar().addMenu("View")
        #self.menu_manager._add_action(view_menu, "Toggle Explorer", "Ctrl+B", self.toggle_explorer)
        # Note: Toggle AI Panel is now handled by OllamaPlugin via Ctrl+L

        self.menu_manager.create_go_menu()
        self.menu_manager.create_run_menu()

        # Plugins menu
        self.plugins_menu = self.plugin_ui.create_plugin_menu(self.menuBar())

        self.menu_manager.create_help_menu()

    # =====================================================================
    # Manager Delegation Methods
    # =====================================================================

    def create_new_file_handler(self):
        """Handler for creating new file"""
        file_path = self.file_manager.create_new_file(self.workspace_path)
        if file_path:
            self.tab_manager.open_file_by_path(
                file_path,
                self.settings_manager.settings
            )


    def create_new_folder_handler(self):
        """Handler for creating new folder"""
        self.file_manager.create_new_folder(self.workspace_path)

    # =====================================================================
    # File Operations
    # =====================================================================

    # =====================================================================
    # Update save_current_file to trigger hook
    # =====================================================================

    def save_current_file(self):
        """Save current file"""
        current_widget = self.get_current_editor()
        if isinstance(current_widget, CodeEditor):
            if current_widget.save_file():
                current_widget.document().setModified(False)
                self.on_editor_modified(current_widget)
                self.status_message.setText("File saved")
                QTimer.singleShot(2000, lambda: self.status_message.setText(""))
    
                # Trigger plugin hook
                if hasattr(current_widget, 'file_path') and current_widget.file_path:
                    self.trigger_file_saved(current_widget.file_path)
                
                # Refresh outline after save
                if hasattr(self, 'outline_widget'):
                    self.outline_widget.refresh_outline()


    def save_all_files(self):
        """Save all modified files across all editor groups"""
        if hasattr(self, 'split_manager'):
            # Save across all groups
            saved_count = 0
            for editor in self.split_manager.get_all_editors():
                if editor.document().isModified():
                    if editor.save_file():
                        editor.document().setModified(False)
                        self.on_editor_modified(editor)
                        saved_count += 1
    
            if saved_count > 0:
                self.status_message.setText(f"Saved {saved_count} file(s)")
                QTimer.singleShot(3000, lambda: self.status_message.setText(""))
                
                # Refresh outline for current editor
                if hasattr(self, 'outline_widget'):
                    current_editor = self.get_current_editor()
                    if isinstance(current_editor, CodeEditor):
                        self.outline_widget.refresh_outline()
        else:
            self.tab_manager.save_all_tabs()


    def close_current_tab(self):
        """Close current tab"""
        if self.tabs.count() > 0:
            self.tab_manager.close_tab(self.tabs.currentIndex())
            self.mark_session_dirty()
    
    
    def close_all_tabs(self):
        """Close all tabs"""
        self.tab_manager.close_all_tabs()
        self.mark_session_dirty()

    # =====================================================================
    # Helper Methods
    # =====================================================================

    def get_current_editor(self):
        """Get the current editor from the active split group"""
        if hasattr(self, 'split_manager'):
            active_group = self.split_manager.get_active_group()
            editor = active_group.get_current_editor()

            # Update outline when editor changes
            if hasattr(self, 'outline_widget') and isinstance(editor, CodeEditor):
                self.outline_widget.set_editor(editor)

            return editor
        else:
            return self.tabs.currentWidget()

    # =====================================================================
    # File Explorer Context Menu
    # =====================================================================

    def show_explorer_context_menu(self, position):
        """Show context menu for file explorer"""


        index = self.tree.indexAt(position)
        menu = QMenu()

        if index.isValid():
            path = Path(self.file_model.filePath(index))

            if path.is_dir():
                new_file_action = menu.addAction("New File")
                new_folder_action = menu.addAction("New Folder")

                menu.addSeparator()

                copy_path_action = menu.addAction("📋 Copy Path")
                copy_relative_path_action = menu.addAction("📋 Copy Relative Path")

                menu.addSeparator()

                rename_action = menu.addAction("Rename")

                menu.addSeparator()

                delete_action = menu.addAction("Delete")

                action = menu.exec(self.tree.viewport().mapToGlobal(position))

                if action == new_file_action:
                    file_path = self.file_manager.create_new_file(path)
                    if file_path:
                        self.tab_manager.open_file_by_path(
                            file_path,
                            self.settings_manager.settings
                        )
                elif action == new_folder_action:
                    self.file_manager.create_new_folder(path)
                elif action == rename_action:
                    self.file_manager.rename_item(path, self.tab_manager)
                elif action == delete_action:
                    self.file_manager.delete_item(path, self.tab_manager)
            else:
                open_action = menu.addAction("Open")
                menu.addSeparator()
                rename_action = menu.addAction("Rename")
                menu.addSeparator()
                delete_action = menu.addAction("Delete")

                action = menu.exec(self.tree.viewport().mapToGlobal(position))

                if action == open_action:
                    self.tab_manager.open_file_by_path(
                        path,
                        self.settings_manager.settings
                    )
                elif action == rename_action:
                    self.file_manager.rename_item(path, self.tab_manager)
                elif action == delete_action:
                    self.file_manager.delete_item(path, self.tab_manager)
        else:
            new_folder_action = menu.addAction("New Folder")
            new_file_action = menu.addAction("New File")

            action = menu.exec(self.tree.viewport().mapToGlobal(position))

            if action == new_folder_action:
                self.file_manager.create_new_folder(self.workspace_path)
            elif action == new_file_action:
                file_path = self.file_manager.create_new_file(self.workspace_path)
                if file_path:
                    self.tab_manager.open_file_by_path(
                        file_path,
                        self.settings_manager.settings
                    )

    # =====================================================================
    # Tab Context Menu
    # =====================================================================

    def show_tab_context_menu(self, position):
        """Show context menu for tabs"""


        #print(f"Context menu position: {position}")
        tab_index = self.tabs.tabBar().tabAt(position)

        #print(f"Tab index: {tab_index}")
        #if tab_index < 0:
        #    print("No tab at position")
        #    return

        editor = self.tabs.widget(tab_index)
        #print(f"Editor type: {type(editor)}")
        #print(f"Has file_path: {hasattr(editor, 'file_path')}")
        #if hasattr(editor, 'file_path'):
        #    print(f"File path: {editor.file_path}")

        # Check if it's a valid editor with file path
        if not isinstance(editor, CodeEditor):
            return
        if not hasattr(editor, 'file_path') or not editor.file_path:
            return

        menu = QMenu(self)

        # ai_menu = menu.addMenu("🤖 AI Actions")
        # send_all_action = ai_menu.addAction("Send Entire File to Ollama")
        # send_selection_action = ai_menu.addAction("Send Selection to Ollama")
        # menu.addSeparator()

        copy_path_action = menu.addAction("📋 Copy File Path")
        copy_relative_path_action = menu.addAction("📋 Copy Relative Path")
        menu.addSeparator()

        save_action = menu.addAction("💾 Save")
        close_action = menu.addAction("✖️ Close")
        close_others_action = menu.addAction("Close Others")
        close_all_action = menu.addAction("Close All")

        action = menu.exec(self.tabs.tabBar().mapToGlobal(position))

        # Handlers
        if action == copy_path_action:
            self.copy_file_path_to_clipboard(editor.file_path, relative=False)
        elif action == copy_relative_path_action:
            self.copy_file_path_to_clipboard(editor.file_path, relative=True)
        # elif action == send_all_action:
            # self.tab_manager.send_tab_to_ollama(tab_index, send_all=True)
        # elif action == send_selection_action:
            # self.tab_manager.send_tab_to_ollama(tab_index, send_all=False)
        elif action == save_action:
            self.tab_manager.save_tab(tab_index)
        elif action == close_action:
            self.tab_manager.close_tab(tab_index)
        elif action == close_others_action:
            self.tab_manager.close_other_tabs(tab_index)
        elif action == close_all_action:
            self.tab_manager.close_all_tabs()

    # =====================================================================
    # Editor Event Handlers
    # =====================================================================

    # =====================================================================
    # open_file to trigger hook
    # =====================================================================

    def open_file(self, index):
        """Open file from tree view double-click"""
        path = self.file_model.filePath(index)
        p = Path(path)
        if p.is_file():
            self.tab_manager.open_file_by_path(
                p,
                self.settings_manager.settings
            )
    
            # Trigger plugin hook
            self.trigger_file_opened(str(p))
            
            # Mark session dirty
            self.mark_session_dirty()

    # =====================================================================
    # Update on_editor_tab_changed to trigger hooks
    # =====================================================================

    def on_editor_tab_changed(self, index):
        """Handle tab change"""
        if index >= 0:
            # Track tab access
            self.tab_order_manager.record_access(index)
    
            editor = self.tabs.widget(index)
            if isinstance(editor, CodeEditor):
                self.find_replace.set_editor(editor)
                self.statusbar_manager.update_file_info(editor)
    
                # Disconnect any existing connections first
                try:
                    editor.cursorPositionChanged.disconnect()
                except:
                    pass
    
                # Connect cursor position updates
                editor.cursorPositionChanged.connect(
                    lambda: self.statusbar_manager.update_cursor_position(editor)
                )
    
                # Connect cursor hook
                editor.cursorPositionChanged.connect(
                    lambda: self._on_cursor_position_changed(editor)
                )
    
                # Update outline when tab changes
                if hasattr(self, 'outline_widget'):
                    self.outline_widget.set_editor(editor)
    
                # Trigger focus hook
                self.trigger_editor_focus(editor)
                
                # Mark session as dirty
                self.mark_session_dirty()


    def _on_cursor_position_changed(self, editor):
        """Handle cursor position change"""
        if isinstance(editor, CodeEditor):
            cursor = editor.textCursor()
            line = cursor.blockNumber() + 1
            column = cursor.columnNumber() + 1
            self.trigger_cursor_moved(editor, line, column)


    def on_editor_modified(self, editor):
        """Handle editor modification"""
        index = self.tabs.indexOf(editor)
        if index != -1:
            self.tabs.set_tab_modified(index, editor.document().isModified())


    # =====================================================================
    # Quick Open
    # =====================================================================

    def show_quick_open(self):
        """Show quick open dialog"""
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
        cache_valid = (
            cache_age < 30 and
            self.quick_open_cache and
            set(active_projects) == self.quick_open_cache_projects
        )

        if cache_valid:
            dialog = QuickOpenDialog(active_projects, self)
            dialog.all_files = self.quick_open_cache
            dialog.search_input.setEnabled(True)
            dialog.search_input.setPlaceholderText("Type to search files... (fuzzy matching)")
            dialog.info_label.setText(f"Showing 50 of {len(self.quick_open_cache):,} files (type to search)")
            dialog.search_input.setFocus()
            dialog.on_search_changed("")

            if dialog.exec() == QDialog.DialogCode.Accepted and dialog.selected_file:
                self.tab_manager.open_file_by_path(
                    Path(dialog.selected_file),
                    self.settings_manager.settings
                )
        else:
            dialog = QuickOpenDialog(active_projects, self)

            def cache_files(files):
                self.quick_open_cache = files
                self.quick_open_cache_projects = set(active_projects)
                self.quick_open_cache_time = time.time()

            if dialog.scanner_thread:
                dialog.scanner_thread.files_found.connect(cache_files)

            if dialog.exec() == QDialog.DialogCode.Accepted and dialog.selected_file:
                self.tab_manager.open_file_by_path(
                    Path(dialog.selected_file),
                    self.settings_manager.settings
                )


    # =====================================================================
    # Find/Replace Operations
    # =====================================================================

    def show_find_replace(self):
        """Show find/replace widget"""
        current_widget = self.get_current_editor()
        if isinstance(current_widget, CodeEditor):
            self.find_replace.set_editor(current_widget)
            self.find_replace.show_find()

    def find_next(self):
        """Find next occurrence"""
        if self.find_replace.isVisible():
            self.find_replace.find_next()

    def find_previous(self):
        """Find previous occurrence"""
        if self.find_replace.isVisible():
            self.find_replace.find_previous()


    # =====================================================================
    # Edit Operations
    # =====================================================================

    def toggle_comment(self):
        """Toggle comments in current editor"""
        current_widget = self.get_current_editor()
        if isinstance(current_widget, CodeEditor):
            current_widget.toggle_comment()

    def duplicate_line(self):
        """Duplicate current line or selection"""
        current_widget = self.get_current_editor()
        if isinstance(current_widget, CodeEditor):
            current_widget.duplicate_line_or_selection()

    def undo_current(self):
        """Undo in current editor"""
        current_widget = self.get_current_editor()
        if isinstance(current_widget, CodeEditor):
            current_widget.undo()

    def redo_current(self):
        """Redo in current editor"""
        current_widget = self.get_current_editor()
        if isinstance(current_widget, CodeEditor):
            current_widget.redo()

    def cut_current(self):
        """Cut in current editor"""
        current_widget = self.get_current_editor()
        if isinstance(current_widget, CodeEditor):
            current_widget.cut()

    def copy_current(self):
        """Copy in current editor"""
        current_widget = self.get_current_editor()
        if isinstance(current_widget, CodeEditor):
            current_widget.copy()

    def paste_current(self):
        """Paste in current editor"""
        current_widget = self.get_current_editor()
        if isinstance(current_widget, CodeEditor):
            current_widget.paste()

    def select_all_current(self):
        """Select all in current editor"""
        current_widget = self.get_current_editor()
        if isinstance(current_widget, CodeEditor):
            current_widget.selectAll()

    # =====================================================================
    # View Operations
    # =====================================================================

    def toggle_explorer(self):
        """Toggle file explorer visibility"""
        explorer_widget = self.main_splitter.widget(0)
        explorer_widget.setVisible(not explorer_widget.isVisible())

    # def show_ollama_panel(self):
        # """Show Ollama panel if hidden"""
        # if not self.ollama_panel_visible:
            # self.toggle_ollama_panel()

    def toggle_right_sidebar(self):
        """Toggle right sidebar visibility"""
        right_sidebar = self.main_splitter.widget(2)
        
        if right_sidebar.isVisible():
            right_sidebar.hide()
        else:
            right_sidebar.show()
            # Adjust sizes
            sizes = self.main_splitter.sizes()
            total = sum(sizes)
            self.main_splitter.setSizes([
                int(total * 0.15),
                int(total * 0.55),
                int(total * 0.30)
            ])

    def update_outline_for_active_editor(self):
        """Update outline when active editor changes in split view"""
        current_widget = self.get_current_editor()
        if isinstance(current_widget, CodeEditor) and hasattr(self, 'outline_widget'):
            self.outline_widget.set_editor(current_widget)

    # =====================================================================
    # Navigation
    # =====================================================================

    def go_to_line(self):
        """Go to line dialog"""
        current_widget = self.get_current_editor()
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
            cursor.movePosition(
                QTextCursor.MoveOperation.Down,
                QTextCursor.MoveMode.MoveAnchor,
                line_number - 1
            )
            current_widget.setTextCursor(cursor)
            current_widget.ensureCursorVisible()

    # =====================================================================
    # Run Operations
    # =====================================================================

    def run_current_file(self):
        """Run the current file"""
        import subprocess
        import webbrowser

        current_widget = self.get_current_editor()
        if not isinstance(current_widget, CodeEditor) or not current_widget.file_path:
            QMessageBox.warning(self, "No File", "No file open to run")
            return

        file_path = Path(current_widget.file_path).resolve()

        # Determine command based on file type
        command_map = {
            '.py': f'python3 "{file_path}"',
            '.php': f'php "{file_path}"',
            '.js': f'node "{file_path}"',
            '.cjs': f'node "{file_path}"',
            '.mjs': f'node "{file_path}"',
            '.sh': f'bash "{file_path}"'
        }

        if file_path.suffix in {'.html', '.htm'}:
            webbrowser.open(file_path.as_uri())
            self.status_message.setText(f"Opened {file_path.name} in browser")
            QTimer.singleShot(3000, lambda: self.status_message.setText(""))
            return

        command = command_map.get(file_path.suffix)

        if command is None:
            QMessageBox.information(
                self,
                "Run File",
                f"Don't know how to run {file_path.suffix} files automatically.\n\n"
                f"You can run it manually in a terminal:\n\n{file_path}"
            )
            return

        self.open_external_terminal(str(file_path.parent), command)

        if command:
            self.status_message.setText(f"Running {file_path.name}...")
            QTimer.singleShot(4000, lambda: self.status_message.setText(""))


    def open_external_terminal(self, directory=None, command=None):
        """Open external terminal"""
        import os
        import subprocess
        import shutil

        if directory is None:
            directory = str(self.workspace_path)

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
            else:  # Linux
                terminals = [
                    ('gnome-terminal', '--working-directory'),
                    ('konsole', '--workdir'),
                    ('xfce4-terminal', '--working-directory'),
                ]

                for term, flag in terminals:
                    try:
                        if command:
                            subprocess.Popen([term, flag, directory, '--', 'bash', '-c', f'{command} && exec bash'])
                        else:
                            subprocess.Popen([term, flag, directory])
                        return
                    except FileNotFoundError:
                        continue

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open terminal: {str(e)}")



    # ============================================================================
    # Status Message Helper Methods (keep these)
    # ============================================================================
    
    def show_status_message(self, message: str, timeout: int = 3000):
        """
        Show a status bar message
        
        Args:
            message: Message to display
            timeout: Time in milliseconds before clearing (0 = don't clear)
        """
        if hasattr(self, 'status_message'):
            self.status_message.setText(message)
        
        if timeout > 0:
            QTimer.singleShot(timeout, lambda: self.clear_status_message())
    
    
    def clear_status_message(self):
        """Clear the status bar message"""
        if hasattr(self, 'status_message'):
            self.status_message.setText("")
    
    # ============================================================================
    # Settings Dialog Method
    # ============================================================================
    
    def show_settings(self):
        """Show settings dialog and apply changes"""
        dialog = SettingsDialog(self.settings_manager, parent=self)
        
        if dialog.exec():
            new_settings = dialog.get_settings()
            self.settings_manager.update(new_settings)
            self.settings_manager.save()
            
            # Apply settings immediately
            self.apply_settings()
            
            # Show confirmation
            self.show_status_message("Settings saved and applied", 3000)



    def show_documentation(self):
        """Show documentation"""
        readme_path = self.workspace_path / "README.md"
        dialog = DocumentDialog(readme_path, self)
        dialog.exec()

    def show_changelog(self):
        """Show changelog"""
        path = self.workspace_path / "CHANGELOG.md"
        dialog = DocumentDialog(path, self)
        dialog.exec()

    def show_about(self):
        """Show about dialog"""
        QMessageBox.about(
            self,
            "About Workspace IDE",
            "<h3>Workspace IDE with Ollama</h3>"
            f"<p>Version {VERSION}</p>"
            "<p>A modern Python IDE with integrated AI assistance.</p>"
            "<p><b>Features:</b></p>"
            "<ul>"
            "<li>Multi-file editing with syntax highlighting</li>"
            "<li>Integrated AI chat</li>"
            "<li>Quick file search (Ctrl+P)</li>"
            "<li>Find & replace with regex support</li>"
            "<li>Session restoration</li>"
            "</ul>"
            "<p>Built with PyQt6 - Refactored Architecture</p>"
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
<tr><td><b>Ctrl+D</b></td><td>Duplicate Line/Selection</td></tr>
<tr><td><b>Ctrl+F</b></td><td>Find</td></tr>
<tr><td><b>Ctrl+H</b></td><td>Replace</td></tr>
<tr><td><b>F3</b></td><td>Find Next</td></tr>
<tr><td><b>Shift+F3</b></td><td>Find Previous</td></tr>
<tr><td><b>Ctrl+/</b></td><td>Toggle Comment</td></tr>
</table>

<h4>View</h4>
<table style="width: 100%">
<tr><td><b>Ctrl+B</b></td><td>Toggle Explorer</td></tr>
<tr><td><b>Ctrl+L</b></td><td>Toggle AI Chat</td></tr>
</table>

<h4>Navigation</h4>
<table style="width: 100%">
<tr><td><b>Ctrl+G</b></td><td>Go to Line</td></tr>
<tr><td><b>Ctrl+P</b></td><td>Go to File</td></tr>
<tr><td><b>Ctrl+Tab</b></td><td>Tab Switcher (Recent Order)</td></tr>
<tr><td><b>Ctrl+Shift+Tab</b></td><td>Tab Switcher (Reverse)</td></tr>
<tr><td><b>↑↓ in Switcher</b></td><td>Navigate Tabs</td></tr>
<tr><td><b>Enter in Switcher</b></td><td>Select Tab</td></tr>
<tr><td><b>Esc in Switcher</b></td><td>Cancel</td></tr>
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

        spacer = QSpacerItem(500, 0)
        layout = msg_box.layout()
        if isinstance(layout, QGridLayout):
            layout.addItem(spacer, layout.rowCount(), 0, 1, layout.columnCount())

        msg_box.exec()

    # =====================================================================
    # Project Management
    # =====================================================================

    def update_tree_highlighting(self):
        """Update project highlighting in tree view"""
        active_projects = self.projects_panel.get_active_projects()
        self.tree_delegate.set_active_projects(active_projects)
        self.tree.viewport().update()

    # =====================================================================
    # Layout & Session Management
    # =====================================================================

    def ensure_workspace(self):
        """Ensure workspace directory exists"""
        if not self.workspace_path.exists():
            self.workspace_path.mkdir(parents=True)

    def apply_initial_layout(self):
        """Apply initial layout from settings"""
        if hasattr(self, 'saved_main_sizes') and self.saved_main_sizes:
            self.main_splitter.setSizes(self.saved_main_sizes)
        else:
            explorer_width = self.settings_manager.get('explorer_width', 300)
            total_width = self.main_splitter.width()
            if total_width > explorer_width:
                self.main_splitter.setSizes([
                    explorer_width,
                    total_width - explorer_width,
                    0
                ])


    # ============================================================================
    # Utility methods
    # ============================================================================

    def copy_file_path_to_clipboard(self, file_path, relative=False):
        """
        Copy file path to clipboard

        Args:
            file_path: Absolute path to the file
            relative: If True, copy path relative to workspace
        """
        path = Path(file_path)

        if relative:
            try:
                # Get path relative to workspace
                relative_path = path.relative_to(self.workspace_path)
                path_to_copy = str(relative_path)
                path_type = "Relative path"
            except ValueError:
                # File is outside workspace, use absolute
                path_to_copy = str(path)
                path_type = "Absolute path (file outside workspace)"
        else:
            path_to_copy = str(path)
            path_type = "File path"

        # Copy to clipboard
        clipboard = QApplication.clipboard()
        clipboard.setText(path_to_copy)

        # Show confirmation in status bar
        self.status_message.setText(f"{path_type} copied: {path_to_copy}")
        QTimer.singleShot(3000, lambda: self.status_message.setText(""))

    def show_tab_switcher(self):
        """Show the tab switcher dialog"""

        # print(f"[DEBUG] show_tab_switcher called")
        # print(f"[DEBUG] Tab count: {self.tabs.count()}")

        #if self.tabs.count() < 2:
            # No point showing switcher with 0 or 1 tabs
            # print(f"[DEBUG] Not enough tabs, returning")
            #return

        # Get recent order
        current_index = self.tabs.currentIndex()
        recent_order = self.tab_order_manager.get_recent_order(current_index)

        # print(f"[DEBUG] Current index: {current_index}")
        # print(f"[DEBUG] Recent order: {recent_order}")

        # Show switcher dialog
        dialog = TabSwitcherDialog(self, self.tabs, recent_order)

        # print(f"[DEBUG] Dialog created, showing...")

        if dialog.exec() == QDialog.DialogCode.Accepted:
            if dialog.selected_tab is not None:
                # print(f"[DEBUG] Switching to tab: {dialog.selected_tab}")
                self.tabs.setCurrentIndex(dialog.selected_tab)
                self.tab_order_manager.record_access(dialog.selected_tab)
        #else:
            # print(f"[DEBUG] Dialog rejected/cancelled")


    # ============================================================================
    # Optional: Add hook trigger methods to Workspace class
    # These allow the IDE to notify plugins about events
    # ============================================================================

    def trigger_file_saved(self, file_path: str):
        """Trigger file saved hook"""
        if hasattr(self, 'plugin_api'):
            self.plugin_api.trigger_hook('on_file_saved', file_path)

    def trigger_file_opened(self, file_path: str):
        """Trigger file opened hook"""
        if hasattr(self, 'plugin_api'):
            self.plugin_api.trigger_hook('on_file_opened', file_path)

    def trigger_file_closed(self, file_path: str):
        """Trigger file closed hook"""
        if hasattr(self, 'plugin_api'):
            self.plugin_api.trigger_hook('on_file_closed', file_path)

    def trigger_editor_focus(self, editor):
        """Trigger editor focus hook"""
        if hasattr(self, 'plugin_api'):
            self.plugin_api.trigger_hook('on_editor_focus', editor)

    def trigger_cursor_moved(self, editor, line: int, column: int):
        """Trigger cursor moved hook"""
        if hasattr(self, 'plugin_api'):
            self.plugin_api.trigger_hook('on_cursor_moved', editor, line, column)


    # =====================================================================
    # Application Lifecycle
    # =====================================================================

    def closeEvent(self, event):
        """Handle application close"""

        # Cleanup outline widget
        if hasattr(self, 'outline_widget'):
            self.outline_widget.cleanup()

        # Trigger workspace closing hook
        if hasattr(self, 'plugin_api'):
            self.plugin_api.trigger_hook('on_workspace_closed')

        # Save active projects
        self.settings_manager.set(
            'active_projects',
            self.projects_panel.get_active_projects()
        )
        self.settings_manager.save()

        # Stop auto-save timer
        if hasattr(self, 'auto_save_timer'):
            self.auto_save_timer.stop()

        # Save session if enabled
        if self.settings_manager.get('restore_session', True):
            self.session_manager.save_session(self.tabs, self.main_splitter)

        # Check for unsaved files
        unsaved_files = []
        for i in range(self.tabs.count()):
            editor = self.tabs.widget(i)
            if isinstance(editor, CodeEditor) and editor.document().isModified():
                unsaved_files.append(Path(editor.file_path).name)

        if unsaved_files:
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                f"You have unsaved changes in:\n{', '.join(unsaved_files)}\n\n"
                "Save before closing?",
                QMessageBox.StandardButton.Save |
                QMessageBox.StandardButton.Discard |
                QMessageBox.StandardButton.Cancel
            )

            if reply == QMessageBox.StandardButton.Save:
                self.tab_manager.save_all_tabs()
                event.accept()
            elif reply == QMessageBox.StandardButton.Discard:
                event.accept()
            else:
                event.ignore()
                return

        event.accept()


    # =====================================================================
    # Application Session
    # =====================================================================

    def auto_save_session(self):
        """Auto-save session if changes detected"""
        if self.settings_manager.get('restore_session', True) and self.session_dirty:
            self.session_manager.save_session(self.tabs, self.main_splitter)
            self.session_dirty = False
    
    def mark_session_dirty(self):
        """Mark session as needing save"""
        self.session_dirty = True


    def changeEvent(self, event):
        """Save on minimize/deactivate"""
        super().changeEvent(event)
        if event.type() == event.Type.WindowStateChange:
            if self.isMinimized():
                self.auto_save_session()