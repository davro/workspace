# ============================================================================
# managers/menu_manager.py
# ============================================================================

from PyQt6.QtWidgets import QMenu
from PyQt6.QtGui import QAction
from PyQt6.QtCore import Qt


class MenuManager:
    """Manages menu bar and actions"""

    def __init__(self, menubar, parent):
        self.menubar = menubar
        self.parent = parent
        self.menus = {}
        self.actions = {}
        self.plugin_toolbar = None  # ← NEW

    def create_plugin_toolbar(self, plugin_manager, plugin_ui):
        """
        Create and add plugin toolbar to menu bar
        
        Args:
            plugin_manager: PluginManager instance
            plugin_ui: PluginManagerUI instance
        """
        from ide.core.PluginToolbar import PluginToolbar
        
        self.plugin_toolbar = PluginToolbar(plugin_manager, plugin_ui, self.parent)
        
        # Add as a widget to the right corner of menu bar
        self.menubar.setCornerWidget(self.plugin_toolbar, Qt.Corner.TopRightCorner)
        
        # Refresh plugins
        self.plugin_toolbar.refresh_plugins()
        
        return self.plugin_toolbar
    
    def refresh_plugin_toolbar(self):
        """Refresh the plugin toolbar"""
        if self.plugin_toolbar:
            self.plugin_toolbar.refresh_plugins()

    def create_file_menu(self):
        """Create File menu"""
        menu = self.menubar.addMenu("File")
        self.menus['file'] = menu

        self._add_action(menu, "New File", "Ctrl+N", self.parent.create_new_file_handler)
        self._add_action(menu, "New Folder", "Ctrl+Shift+N", self.parent.create_new_folder_handler)
        menu.addSeparator()
        self._add_action(menu, "Quick Open...", "Ctrl+P", self.parent.show_quick_open)
        menu.addSeparator()
        self._add_action(menu, "Save", "Ctrl+S", self.parent.save_current_file)
        self._add_action(menu, "Save All", "Ctrl+Shift+S", self.parent.save_all_files)
        menu.addSeparator()
        self._add_action(menu, "Close Tab", "Ctrl+W", self.parent.close_current_tab)
        self._add_action(menu, "Close All Tabs", "Ctrl+Shift+W", self.parent.close_all_tabs)
        menu.addSeparator()
        self._add_action(menu, "Preferences...", "Ctrl+,", self.parent.show_settings)
        menu.addSeparator()
        self._add_action(menu, "Exit", "Ctrl+Q", self.parent.close)

        return menu


    def create_file_menu_with_recent(self, recent_files_manager):
        """
        Create File menu with Recent Files submenu

        Args:
            recent_files_manager: RecentFilesManager instance
        """
        menu = self.menubar.addMenu("File")
        self.menus['file'] = menu

        self._add_action(menu, "New File", "Ctrl+N", self.parent.create_new_file_handler)
        self._add_action(menu, "New Folder", "Ctrl+Shift+N", self.parent.create_new_folder_handler)
        menu.addSeparator()
        self._add_action(menu, "Quick Open...", "Ctrl+P", self.parent.show_quick_open)

        # Add Recent Files submenu with Ctrl+R shortcut
        menu.addSeparator()
        recent_files_action = menu.addAction("Recent Files")
        recent_files_action.setShortcut("Ctrl+R")

        # Create submenu (will be populated dynamically)
        recent_menu = recent_files_manager.create_recent_files_menu(menu)
        recent_files_action.setMenu(recent_menu)

        # Store reference for dynamic updates
        self.recent_files_menu = recent_menu
        self.recent_files_action = recent_files_action

        # Refresh menu before showing (to update with latest files)
        menu.aboutToShow.connect(
            lambda: self._refresh_recent_files_menu(recent_files_manager)
        )

        menu.addSeparator()
        self._add_action(menu, "Save", "Ctrl+S", self.parent.save_current_file)
        self._add_action(menu, "Save All", "Ctrl+Shift+S", self.parent.save_all_files)
        menu.addSeparator()
        self._add_action(menu, "Close Tab", "Ctrl+W", self.parent.close_current_tab)
        self._add_action(menu, "Close All Tabs", "Ctrl+Shift+W", self.parent.close_all_tabs)
        menu.addSeparator()
        self._add_action(menu, "Preferences...", "Ctrl+,", self.parent.show_settings)
        menu.addSeparator()
        self._add_action(menu, "Exit", "Ctrl+Q", self.parent.close)

        return menu


    def create_view_menu(self):
        """Create View menu with split view options"""
        #print ("VIEW MENU")
        menu = self.menubar.addMenu("View")
        self.menus['view'] = menu
    
        # Split view submenu
        split_menu = menu.addMenu("Split Editor")
        self._add_action(split_menu, "Split Vertical", "Ctrl+\\", self.parent.split_editor_vertical)
        self._add_action(split_menu, "Split Horizontal", "Ctrl+Shift+\\", self.parent.split_editor_horizontal)
        split_menu.addSeparator()
        self._add_action(split_menu, "Move Tab to Other Group", "Ctrl+Alt+M", self.parent.move_tab_to_split)
        self._add_action(split_menu, "Focus Other Group", "Ctrl+Alt+O", self.parent.focus_other_split)
        self._add_action(split_menu, "Open in Split", "Ctrl+Alt+S", self.parent.open_in_split)
        split_menu.addSeparator()
        self._add_action(split_menu, "Close Split", "Ctrl+Alt+W", self.parent.close_editor_split)
        
        menu.addSeparator()
        # self._add_action(menu, "Toggle Explorer", "Ctrl+B", self.parent.toggle_explorer)
        # self._add_action(menu, "Toggle AI Chat", "Ctrl+L", self.parent.toggle_ollama_panel)
        self._add_action(view_menu, "Toggle Explorer", "Ctrl+B", 
                                    self.workspace.toggle_explorer)
        self._add_action(view_menu, "Toggle Right Sidebar", "Ctrl+Shift+B", 
                                    self.workspace.toggle_right_sidebar)
    
        return menu


    def _refresh_recent_files_menu(self, recent_files_manager):
        """Refresh the recent files menu with current files"""
        # Clear existing menu
        self.recent_files_menu.clear()

        # Recreate menu items
        recent_files = recent_files_manager.get_recent_files()

        if not recent_files:
            no_files_action = self.recent_files_menu.addAction("No recent files")
            no_files_action.setEnabled(False)
        else:
            # Add files with shortcuts
            for i, file_path in enumerate(recent_files[:9]):
                from pathlib import Path
                from PyQt6.QtGui import QAction, QKeySequence

                path = Path(file_path)
                action = QAction(f"📄 {path.name}", self.parent)

                if i < 9:
                    action.setShortcut(QKeySequence(f"Ctrl+{i+1}"))

                action.setToolTip(str(path))
                action.triggered.connect(
                    lambda checked=False, p=file_path: recent_files_manager._open_recent_file(p)
                )
                self.recent_files_menu.addAction(action)

            # Add remaining files without shortcuts
            if len(recent_files) > 9:
                self.recent_files_menu.addSeparator()
                for file_path in recent_files[9:]:
                    from pathlib import Path
                    from PyQt6.QtGui import QAction

                    path = Path(file_path)
                    action = QAction(f"📄 {path.name}", self.parent)
                    action.setToolTip(str(path))
                    action.triggered.connect(
                        lambda checked=False, p=file_path: recent_files_manager._open_recent_file(p)
                    )
                    self.recent_files_menu.addAction(action)

        # Add clear option
        self.recent_files_menu.addSeparator()
        clear_action = self.recent_files_menu.addAction("Clear Recent Files")
        clear_action.triggered.connect(recent_files_manager._clear_and_update_menu)



    def create_edit_menu(self):
        """Create Edit menu"""
        menu = self.menubar.addMenu("Edit")
        self.menus['edit'] = menu

        self._add_action(menu, "Undo", "Ctrl+Z", self.parent.undo_current)
        self._add_action(menu, "Redo", "Ctrl+Shift+Z", self.parent.redo_current)
        menu.addSeparator()
        self._add_action(menu, "Cut", "Ctrl+X", self.parent.cut_current)
        self._add_action(menu, "Copy", "Ctrl+C", self.parent.copy_current)
        self._add_action(menu, "Paste", "Ctrl+V", self.parent.paste_current)
        menu.addSeparator()
        self._add_action(menu, "Duplicate Line", "Ctrl+D", self.parent.duplicate_line)
        menu.addSeparator()
        self._add_action(menu, "Toggle Comment", "Ctrl+/", self.parent.toggle_comment)
        self._add_action(menu, "Find", "Ctrl+F", self.parent.show_find_replace)
        self._add_action(menu, "Replace", "Ctrl+H", self.parent.show_find_replace)

        return menu

    # def create_view_menu(self):
        # """Create View menu"""
        # menu = self.menubar.addMenu("View")
        # self.menus['view'] = menu

        # self._add_action(menu, "Toggle Explorer", "Ctrl+B", self.parent.toggle_explorer)
        # self._add_action(menu, "Toggle AI Chat", "Ctrl+L", self.parent.toggle_ollama_panel)

        # return menu

    def create_go_menu(self):
        """Create Go menu"""
        menu = self.menubar.addMenu("Go")
        self.menus['go'] = menu

        self._add_action(menu, "Go to File...", None, self.parent.show_quick_open)
        self._add_action(menu, "Go to Line...", "Ctrl+G", self.parent.go_to_line)

        return menu

    def create_run_menu(self):
        """Create Run menu"""
        menu = self.menubar.addMenu("Run")
        self.menus['run'] = menu

        self._add_action(menu, "Run Current File", "F5", self.parent.run_current_file)

        return menu

    def create_help_menu(self):
        """Create Help menu"""
        menu = self.menubar.addMenu("Help")
        self.menus['help'] = menu

        self._add_action(menu, "About Workspace IDE", None, self.parent.show_about)
        self._add_action(menu, "Documentation", "F1", self.parent.show_documentation)
        self._add_action(menu, "Changelog", "F2", self.parent.show_changelog)
        menu.addSeparator()
        self._add_action(menu, "Keyboard Shortcuts", "Ctrl+K Ctrl+S", self.parent.show_keyboard_shortcuts)

        return menu

    def _add_action(self, menu, text, shortcut, callback):
        """Helper to add an action to a menu"""
        action = QAction(text, self.parent)
        if shortcut:
            action.setShortcut(shortcut)
        action.triggered.connect(callback)
        menu.addAction(action)
        self.actions[text] = action
        return action

    def style_menubar(self):
        """Apply stylesheet to menubar"""
        self.menubar.setStyleSheet("""
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


