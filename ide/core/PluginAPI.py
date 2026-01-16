# ============================================================================
# PluginAPI.py in ide/core/
# ============================================================================

"""
Plugin API for deep editor integration
Allows plugins to hook into IDE functionality and extend behavior
"""

from typing import Callable, List, Any, Optional, Dict
from pathlib import Path


class PluginAPI:
    """
    API exposed to plugins for IDE integration

    Plugins can register hooks to:
    - Decorate file tree items (icons, colors)
    - Add gutter markers in editors
    - Add status bar widgets
    - Add context menu items
    - React to file events
    - React to editor events
    - React to IDE lifecycle events
    """

    def __init__(self, workspace_ide):
        """
        Initialize Plugin API

        Args:
            workspace_ide: Main WorkspaceIDE instance
        """
        self.ide = workspace_ide
        # print (f"workspace_ide: {workspace_ide}")

        # Hook registry
        self.hooks: Dict[str, List[Callable]] = {
            # Visual decorations
            'file_tree_decorator': [],      # Decorate file tree items (icons, colors)
            'gutter_decorator': [],         # Add markers in editor gutter

            # UI extensions
            'status_bar_widget': [],        # Add widgets to status bar
            'context_menu_file': [],        # Add file context menu items
            'context_menu_tab': [],         # Add tab context menu items
            'toolbar_actions': [],          # Add toolbar buttons

            # File events
            'on_file_saved': [],            # Called when file is saved
            'on_file_opened': [],           # Called when file is opened
            'on_file_closed': [],           # Called when file is closed
            'on_file_modified': [],         # Called when file is modified
            'on_file_created': [],          # Called when file is created
            'on_file_deleted': [],          # Called when file is deleted
            'on_file_renamed': [],          # Called when file is renamed

            # Editor events
            'on_editor_focus': [],          # Called when editor gets focus
            'on_cursor_moved': [],          # Called when cursor moves
            'on_selection_changed': [],     # Called when selection changes
            'on_text_changed': [],          # Called when text changes

            # IDE events
            'on_project_opened': [],        # Called when project is activated
            'on_workspace_opened': [],      # Called when IDE starts
            'on_workspace_closed': [],      # Called when IDE closes
        }

        # Cache for hook results
        self._cache: Dict[str, Any] = {}

        # Plugin metadata tracking
        self._plugins: Dict[str, Dict[str, Any]] = {}

        self._shortcuts: dict[str, object] = {}

    # =========================================================================
    # Hook Registration
    # =========================================================================

    def register_hook(self, hook_name: str, callback: Callable, plugin_id: Optional[str] = None) -> bool:
        """
        Register a callback for a hook

        Args:
            hook_name: Name of the hook
            callback: Function to call when hook is triggered
            plugin_id: Optional plugin identifier for tracking

        Returns:
            True if registered successfully
        """
        if hook_name not in self.hooks:
            print(f"[PluginAPI] Unknown hook: {hook_name}")
            print(f"[PluginAPI] Available hooks: {', '.join(self.hooks.keys())}")
            return False

        self.hooks[hook_name].append(callback)

        if plugin_id:
            if plugin_id not in self._plugins:
                self._plugins[plugin_id] = {'hooks': []}
            self._plugins[plugin_id]['hooks'].append((hook_name, callback))

        print(f"[PluginAPI] Registered hook: {hook_name}" +
              (f" (plugin: {plugin_id})" if plugin_id else ""))
        return True

    def unregister_hook(self, hook_name: str, callback: Callable) -> bool:
        """
        Unregister a callback from a hook

        Args:
            hook_name: Name of the hook
            callback: Function to remove

        Returns:
            True if unregistered successfully
        """
        if hook_name in self.hooks and callback in self.hooks[hook_name]:
            self.hooks[hook_name].remove(callback)
            print(f"[PluginAPI] Unregistered hook: {hook_name}")
            return True
        return False

    def unregister_all_plugin_hooks(self, plugin_id: str) -> int:
        """
        Unregister all hooks for a specific plugin

        Args:
            plugin_id: Plugin identifier

        Returns:
            Number of hooks unregistered
        """
        if plugin_id not in self._plugins:
            return 0

        count = 0
        for hook_name, callback in self._plugins[plugin_id]['hooks']:
            if self.unregister_hook(hook_name, callback):
                count += 1

        del self._plugins[plugin_id]
        return count

    def trigger_hook(self, hook_name: str, *args, **kwargs) -> List[Any]:
        """
        Trigger all callbacks for a hook

        Args:
            hook_name: Name of the hook
            *args: Positional arguments for callbacks
            **kwargs: Keyword arguments for callbacks

        Returns:
            List of results from all callbacks
        """
        results = []

        for callback in self.hooks.get(hook_name, []):
            try:
                result = callback(*args, **kwargs)
                if result is not None:
                    results.append(result)
            except Exception as e:
                print(f"[PluginAPI] Error in {hook_name}: {e}")
                import traceback
                traceback.print_exc()

        return results

    def get_hook_count(self, hook_name: Optional[str] = None) -> int:
        """
        Get number of registered hooks

        Args:
            hook_name: Specific hook name, or None for all hooks

        Returns:
            Count of registered hooks
        """
        if hook_name:
            return len(self.hooks.get(hook_name, []))
        return sum(len(callbacks) for callbacks in self.hooks.values())

    def list_hooks(self) -> Dict[str, int]:
        """
        List all hooks and their callback counts

        Returns:
            Dictionary of hook names to callback counts
        """
        return {name: len(callbacks) for name, callbacks in self.hooks.items()}


    # ========================================================================
    # Settings Support
    # ========================================================================
    
    def register_settings_provider(self, provider_class):
        """
        Register a settings provider (plugin class with SETTINGS_DESCRIPTORS)
        
        Args:
            provider_class: A class inheriting from SettingsProvider
        """
        if hasattr(self.ide, 'settings_manager'):
            self.ide.settings_manager.register_provider(provider_class)
            print(f"[PluginAPI] Registered settings provider: {provider_class.__name__}")
            
            # Reload settings to include new defaults
            self.ide.settings_manager.load()
            
            return True
        else:
            print(f"[PluginAPI] WARNING: Cannot register settings (no settings_manager)")
            return False
    
    def get_settings(self):
        """Get current IDE settings as dict"""
        if hasattr(self.ide, 'settings_manager'):
            return self.ide.settings_manager.settings
        return {}

    # def get_settings(self) -> Dict[str, Any]:
        # """
        # Get IDE settings

        # Returns:
            # Dictionary of settings
        # """
        # if hasattr(self.ide, 'settings_manager'):
            # return self.ide.settings_manager.settings
        # return {}

    def get_setting(self, key, default=None):
        """Get a specific setting value"""
        if hasattr(self.ide, 'settings_manager'):
            return self.ide.settings_manager.get(key, default)
        return default
    
    def set_setting(self, key, value):
        """Set a setting value (does not save automatically)"""
        if hasattr(self.ide, 'settings_manager'):
            self.ide.settings_manager.set(key, value)
            return True
        return False

    # =========================================================================
    # IDE Access Methods
    # =========================================================================

    def get_current_editor(self):
        """
        Get currently active editor

        Returns:
            Current editor widget or None
        """
        return self.ide.get_current_editor()

    def get_workspace_path(self) -> Path:
        """
        Get workspace root path

        Returns:
            Path object for workspace directory
        """
        return self.ide.workspace_path

    def get_file_tree(self):
        """
        Get file tree widget

        Returns:
            File tree widget
        """
        return self.ide.tree

    def get_status_bar(self):
        """
        Get status bar

        Returns:
            QStatusBar widget
        """
        return self.ide.statusBar()

    def get_all_open_files(self) -> List[str]:
        """
        Get list of all open file paths

        Returns:
            List of file paths as strings
        """
        if hasattr(self.ide, 'split_manager'):
            editors = self.ide.split_manager.get_all_editors()
            return [e.file_path for e in editors if hasattr(e, 'file_path') and e.file_path]
        return []

    def get_all_editors(self) -> List[Any]:
        """
        Get all open editor widgets

        Returns:
            List of editor widgets
        """
        if hasattr(self.ide, 'split_manager'):
            return self.ide.split_manager.get_all_editors()
        return []

    # =========================================================================
    # UI Manipulation Methods
    # =========================================================================

    def show_status_message(self, message: str, timeout: int = 3000):
        """
        Show message in status bar

        Args:
            message: Message to display
            timeout: Time in milliseconds before clearing (0 = permanent)
        """
        if hasattr(self.ide, 'status_message'):
            self.ide.status_message.setText(message)
            if timeout > 0:
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(timeout, lambda: self.ide.status_message.setText(""))
        else:
            self.ide.statusBar().showMessage(message, timeout)

    def refresh_file_tree(self):
        """Force refresh of file tree display"""
        if hasattr(self.ide, 'tree'):
            self.ide.tree.viewport().update()

    def refresh_current_editor(self):
        """Force refresh of current editor"""
        editor = self.get_current_editor()
        if editor and hasattr(editor, 'viewport'):
            editor.viewport().update()

    def refresh_all_editors(self):
        """Force refresh of all open editors"""
        for editor in self.get_all_editors():
            if editor and hasattr(editor, 'viewport'):
                editor.viewport().update()

    def add_status_bar_widget(self, widget, permanent: bool = False):
        """
        Add widget to status bar

        Args:
            widget: QWidget to add
            permanent: If True, adds to permanent section (right side)
        """
        if permanent:
            self.ide.statusBar().addPermanentWidget(widget)
        else:
            self.ide.statusBar().addWidget(widget)

    def remove_status_bar_widget(self, widget):
        """
        Remove widget from status bar

        Args:
            widget: QWidget to remove
        """
        self.ide.statusBar().removeWidget(widget)

    # =========================================================================
    # File Operations
    # =========================================================================

    def open_file(self, file_path: str):
        """
        Open a file in the editor

        Args:
            file_path: Path to file to open
        """
        from pathlib import Path
        path = Path(file_path)
        if path.exists() and path.is_file():
            if hasattr(self.ide, 'tab_manager') and hasattr(self.ide, 'settings_manager'):
                self.ide.tab_manager.open_file_by_path(
                    path,
                    self.ide.settings_manager.settings
                )

    def get_file_content(self, file_path: str) -> Optional[str]:
        """
        Get content of a file

        Args:
            file_path: Path to file

        Returns:
            File content or None if error
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            print(f"[PluginAPI] Error reading {file_path}: {e}")
            return None

    def save_file_content(self, file_path: str, content: str) -> bool:
        """
        Save content to a file

        Args:
            file_path: Path to file
            content: Content to write

        Returns:
            True if successful
        """
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        except Exception as e:
            print(f"[PluginAPI] Error writing {file_path}: {e}")
            return False

    def close_file(self, file_path: str) -> bool:
        """
        Close a file in the editor

        Args:
            file_path: Path to file to close

        Returns:
            True if closed successfully
        """
        # Implementation depends on tab manager
        # This is a placeholder
        return False

    # =========================================================================
    # Context Menu Extensions
    # =========================================================================

    def add_file_context_menu_action(self, text: str, callback: Callable):
        """
        Add action to file tree context menu

        Args:
            text: Menu item text
            callback: Function to call (receives file_path)
        """
        def menu_handler(menu, path):
            from PyQt6.QtGui import QAction
            action = QAction(text, menu)
            action.triggered.connect(lambda: callback(path))
            menu.addAction(action)

        self.register_hook('context_menu_file', menu_handler)

    def add_tab_context_menu_action(self, text: str, callback: Callable):
        """
        Add action to tab context menu

        Args:
            text: Menu item text
            callback: Function to call (receives editor)
        """
        def menu_handler(menu, editor):
            from PyQt6.QtGui import QAction
            action = QAction(text, menu)
            action.triggered.connect(lambda: callback(editor))
            menu.addAction(action)

        self.register_hook('context_menu_tab', menu_handler)

    # =========================================================================
    # Cache Management
    # =========================================================================

    def set_cache(self, key: str, value: Any):
        """
        Store value in plugin cache

        Args:
            key: Cache key
            value: Value to store
        """
        self._cache[key] = value

    def get_cache(self, key: str, default: Any = None) -> Any:
        """
        Get value from plugin cache

        Args:
            key: Cache key
            default: Default value if key not found

        Returns:
            Cached value or default
        """
        return self._cache.get(key, default)

    def clear_cache(self, key: Optional[str] = None):
        """
        Clear plugin cache

        Args:
            key: Specific key to clear, or None to clear all
        """
        if key:
            self._cache.pop(key, None)
        else:
            self._cache.clear()

    def cache_exists(self, key: str) -> bool:
        """
        Check if cache key exists

        Args:
            key: Cache key to check

        Returns:
            True if key exists
        """
        return key in self._cache

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def log(self, message: str, level: str = "INFO"):
        """
        Log a message

        Args:
            message: Message to log
            level: Log level (INFO, WARNING, ERROR)
        """
        print(f"[PluginAPI:{level}] {message}")

    def get_api_version(self) -> str:
        """
        Get Plugin API version

        Returns:
            Version string
        """
        return "2.0.0"

    # def register_keyboard_shortcut(self, shortcut: str, callback: Callable, description: str = ""):

        # from PyQt6.QtGui import QShortcut, QKeySequence

        # qs = QShortcut(QKeySequence(shortcut), self.ide)
        # qs.activated.connect(callback)

        # print(f"[PluginAPI] Registered keyboard shortcut: {shortcut} - {description}")
        # return qs


    def register_keyboard_shortcut(
        self,
        shortcut: str,
        callback: Callable,
        description: str = ""
    ):
        # """
        # Register global keyboard shortcut with safe a callback for replacing previously 
        # registered shortcuts as stop Qt keeping the old QShortcut alive and the new one 
        # getting garbage-collected or you end up with conflicting shortcuts bound.

        # Args:
            # shortcut: Key sequence (e.g., "Ctrl+T", "Ctrl+Shift+F")
            # callback: Function to call when shortcut is triggered
            # description: Optional description of what the shortcut does
        # """
        from PyQt6.QtGui import QShortcut, QKeySequence
        from PyQt6.QtCore import Qt

        try:
            # Remove existing shortcut if reloading
            if shortcut in self._shortcuts:
                old = self._shortcuts.pop(shortcut)
                old.activated.disconnect()
                old.setEnabled(False)
                old.deleteLater()
                print(f"[PluginAPI] Replaced existing shortcut: {shortcut}")

            qs = QShortcut(QKeySequence(shortcut), self.ide)
            qs.setContext(Qt.ShortcutContext.ApplicationShortcut)

            def safe_callback():
                try:
                    callback()
                except Exception as e:
                    import traceback
                    print(f"[Shortcut Error] {shortcut}: {e}")
                    traceback.print_exc()

            qs.activated.connect(safe_callback)
            self._shortcuts[shortcut] = qs

            print(f"[PluginAPI] Registered shortcut: {shortcut} - {description}")
            return qs

        except Exception as e:
            import traceback
            print(f"[PluginAPI] Failed to register shortcut {shortcut}")
            traceback.print_exc()
            return None



    # ============================================================================
    # BONUS: Useful helper methods for plugins
    # ============================================================================
    
    def get_main_window(self):
        """
        Get reference to main IDE window
        
        Returns:
            Workspace: Main IDE window instance
        """
        return self.ide
    
    
    def get_current_editor(self):
        """
        Get the currently active editor
        
        Returns:
            CodeEditor or None: Current editor widget
        """
        if hasattr(self.ide, 'get_current_editor'):
            return self.ide.get_current_editor()
        return None
    
    def get_workspace_path(self):
        """
        Get workspace root path
        
        Returns:
            Path: Workspace directory path
        """
        if hasattr(self.ide, 'workspace_path'):
            return self.ide.workspace_path
        return None
    
    
    def show_status_message(self, message: str, timeout: int = 2000):
        """
        Show message in status bar
        
        Args:
            message: Message to display
            timeout: How long to show (milliseconds)
        """
        if hasattr(self.ide, 'status_message'):
            self.ide.status_message.setText(message)
            
            if timeout > 0:
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(timeout, lambda: self.ide.status_message.setText(""))
    
    
    def register_keyboard_shortcut(self, key_sequence: str, callback, description: str = ""):
        """
        Register a keyboard shortcut
        
        Args:
            key_sequence: Key combination (e.g., "Ctrl+Shift+X")
            callback: Function to call when triggered
            description: Description for documentation
        
        Returns:
            bool: True if registered successfully
        
        Example:
            >>> api.register_keyboard_shortcut(
            ...     "Ctrl+Shift+X",
            ...     self.my_action,
            ...     "My Plugin Action"
            ... )
        """
        from PyQt6.QtGui import QShortcut, QKeySequence
        
        try:
            # Create a safe wrapper that catches exceptions
            def safe_callback():
                try:
                    callback()
                except Exception as e:
                    print(f"[Shortcut Error] {key_sequence}: {e}")
                    import traceback
                    traceback.print_exc()
            
            # Create and store shortcut
            shortcut = QShortcut(QKeySequence(key_sequence), self.ide)
            shortcut.activated.connect(safe_callback)
            
            # Store reference to prevent garbage collection
            self._shortcuts[key_sequence] = shortcut
            
            print(f"[PluginAPI] Registered shortcut: {key_sequence} - {description}")
            return True
            
        except Exception as e:
            print(f"[PluginAPI] Failed to register shortcut {key_sequence}: {e}")
            return False



        
    # ============================================================================
    # ADD THESE METHODS TO PluginAPI CLASS
    # ============================================================================

    
    # def add_to_right_sidebar(self, widget, title: str, icon: str = "") -> bool:
        # """
        # Add a plugin widget to the right sidebar
        
        # Args:
            # widget: QWidget to add as a tab
            # title: Tab title
            # icon: Optional emoji/icon prefix
        
        # Returns:
            # bool: True if added successfully
        
        # Example:
            # >>> widget = MyPluginWidget()
            # >>> api.add_to_right_sidebar(widget, "My Tool", "🔧")
        # """
        # if hasattr(self.ide, 'right_sidebar'):
            # tab_title = f"{icon} {title}" if icon else title
            # index = self.ide.right_sidebar.addTab(widget, tab_title)
            # return True
        
        # print(f"[PluginAPI] Warning: right_sidebar not found in IDE")
        # return False

    def add_to_right_sidebar(self, widget, title: str, icon: str = "") -> bool:
        """
        Add a plugin widget to the right sidebar
        
        Args:
            widget: QWidget to add as a tab
            title: Tab title
            icon: Optional emoji/icon prefix
        
        Returns:
            bool: True if added successfully
        
        Example:
            >>> widget = MyPluginWidget()
            >>> api.add_to_right_sidebar(widget, "My Tool", "🔧")
        """
        if not hasattr(self.ide, 'right_sidebar'):
            print(f"[PluginAPI] Warning: right_sidebar not found in IDE")
            return False
        
        sidebar = self.ide.right_sidebar
        tab_title = f"{icon} {title}" if icon else title
        
        # **FIX: Check if tab already exists and remove it**
        for i in range(sidebar.count()):
            existing_title = sidebar.tabText(i)
            # Match by title (with or without icon)
            if existing_title == tab_title or existing_title.endswith(title):
                print(f"[PluginAPI] Removing duplicate tab: {existing_title}")
                old_widget = sidebar.widget(i)
                sidebar.removeTab(i)
                # Clean up old widget
                if old_widget:
                    old_widget.deleteLater()
                break
        
        # Add the new tab
        index = sidebar.addTab(widget, tab_title)
        print(f"[PluginAPI] Added tab to right sidebar: {tab_title} (index {index})")
        return True    

    
    def remove_from_right_sidebar(self, widget) -> bool:
        """
        Remove a plugin widget from the right sidebar
        
        Args:
            widget: The widget to remove
        
        Returns:
            bool: True if removed successfully
        """
        if hasattr(self.ide, 'right_sidebar'):
            sidebar = self.ide.right_sidebar
            
            # Find the tab index
            for i in range(sidebar.count()):
                if sidebar.widget(i) == widget:
                    sidebar.removeTab(i)
                    return True
        
        return False
    
    
    def get_right_sidebar_visible(self) -> bool:
        """
        Check if right sidebar is visible
        
        Returns:
            bool: True if visible, False otherwise
        """
        if hasattr(self.ide, 'main_splitter'):
            right_sidebar = self.ide.main_splitter.widget(2)
            return right_sidebar.isVisible() if right_sidebar else False
        return False
    
    
    def set_right_sidebar_visible(self, visible: bool):
        """
        Show or hide the right sidebar
        
        Args:
            visible: True to show, False to hide
        """
        if hasattr(self.ide, 'main_splitter'):
            # Right sidebar is widget(2) in main_splitter
            right_sidebar = self.ide.main_splitter.widget(2)
            
            if right_sidebar:
                if visible:
                    right_sidebar.show()
                    # Adjust splitter sizes
                    sizes = self.ide.main_splitter.sizes()
                    total = sum(sizes)
                    self.ide.main_splitter.setSizes([
                        int(total * 0.15),  # Left sidebar
                        int(total * 0.55),  # Editor
                        int(total * 0.30)   # Right sidebar
                    ])
                else:
                    right_sidebar.hide()
    
    
    def focus_right_sidebar_tab(self, title: str) -> bool:
        """
        Switch to a specific tab in right sidebar by title
        
        Args:
            title: Tab title (or partial match)
        
        Returns:
            bool: True if tab found and focused
        
        Example:
            >>> api.focus_right_sidebar_tab("AI")  # Focus the AI tab
        """
        if hasattr(self.ide, 'right_sidebar'):
            sidebar = self.ide.right_sidebar
            
            for i in range(sidebar.count()):
                tab_text = sidebar.tabText(i)
                if title.lower() in tab_text.lower():
                    sidebar.setCurrentIndex(i)
                    self.set_right_sidebar_visible(True)
                    return True
        
        return False

    
    # ============================================================================
    # OPTIONAL: Add Menu Item Support
    # ============================================================================
    
    def add_menu_action(self, menu_path: str, action_name: str, callback, 
                       shortcut: str = None) -> bool:
        """
        Add a menu item to IDE menus
        
        Args:
            menu_path: Menu path like "View" or "Edit/Advanced"
            action_name: Name of the action
            callback: Function to call when triggered
            shortcut: Optional keyboard shortcut
        
        Returns:
            bool: True if added successfully
        
        Example:
            >>> api.add_menu_action("View", "Toggle AI Panel", self.toggle_panel, "Ctrl+L")
        """
        if not hasattr(self.workspace, 'menuBar'):
            return False
        
        menubar = self.workspace.menuBar()
        
        # Split path (e.g., "Edit/Advanced" -> ["Edit", "Advanced"])
        parts = menu_path.split('/')
        
        # Find or create menu
        current_menu = None
        
        # Find top-level menu
        for action in menubar.actions():
            if action.text() == parts[0]:
                current_menu = action.menu()
                break
        
        if not current_menu:
            # Create new top-level menu
            current_menu = menubar.addMenu(parts[0])
        
        # Navigate submenus
        for part in parts[1:]:
            found = False
            for action in current_menu.actions():
                if action.menu() and action.text() == part:
                    current_menu = action.menu()
                    found = True
                    break
            
            if not found:
                # Create submenu
                current_menu = current_menu.addMenu(part)
        
        # Add the action
        from PyQt6.QtGui import QAction
        action = QAction(action_name, self.workspace)
        action.triggered.connect(callback)
        
        if shortcut:
            action.setShortcut(shortcut)
        
        current_menu.addAction(action)
        
        return True
    
    
    # ============================================================================
    # EXAMPLE: Context Menu Support (Advanced)
    # ============================================================================
    
    def add_editor_context_menu_item(self, label: str, callback, condition=None):
        """
        Add item to editor context menu
        
        Args:
            label: Menu item label
            callback: Function called with (editor, position)
            condition: Optional function to check if item should show
        
        Example:
            >>> def my_action(editor, pos):
            ...     print(f"Action on {editor.file_path}")
            >>> 
            >>> api.add_editor_context_menu_item(
            ...     "AI: Explain Selection",
            ...     my_action,
            ...     condition=lambda e: e.textCursor().hasSelection()
            ... )
        """
        # Store for later use
        if not hasattr(self, '_context_menu_items'):
            self._context_menu_items = []
        
        self._context_menu_items.append({
            'label': label,
            'callback': callback,
            'condition': condition
        })



# ============================================================================
# FileTreeDecoration - Result object for file tree decorators
# ============================================================================

class FileTreeDecoration:
    """
    Decoration information for file tree items
    Used by file_tree_decorator hooks

    Example:
        decoration = FileTreeDecoration(file_path)
        decoration.prefix_icon = "🐍"
        decoration.text_color = "#4A9EFF"
        decoration.bold = True
        return decoration
    """

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.prefix_icon: Optional[str]      = None  # Icon before filename (emoji/unicode)
        self.suffix_icon: Optional[str]      = None  # Icon after filename (emoji/unicode)
        self.text_color: Optional[str]       = None  # Text color (hex format: #RRGGBB)
        self.background_color: Optional[str] = None  # Background color (hex format: #RRGGBB)
        self.tooltip: Optional[str]          = None  # Additional tooltip text
        self.bold: bool                      = False # Make text bold
        self.italic: bool                    = False # Make text italic
        self.underline: bool                 = False # Underline text

    def __repr__(self):
        return f"FileTreeDecoration({self.file_path})"


# ============================================================================
# GutterMarker - Result object for gutter decorators
# ============================================================================

class GutterMarker:
    """
    Marker information for editor gutter
    Used by gutter_decorator hooks

    Example:
        marker = GutterMarker(line_number)
        marker.icon = "⚠️"
        marker.color = "#FFA500"
        marker.tooltip = "Warning: Line too long"
        return marker
    """

    def __init__(self, line: int):
        self.line                               = line # Line number (1-based)
        self.icon: Optional[str]                = None # Emoji or unicode icon
        self.color: Optional[str]               = None # Marker color (hex format: #RRGGBB)
        self.tooltip: Optional[str]             = None # Hover tooltip
        self.click_callback: Optional[Callable] = None # Called on click with (line,)
        self.priority: int                      = 0    # Display priority (higher = more important)

    def __repr__(self):
        return f"GutterMarker(line={self.line}, icon={self.icon})"


# ============================================================================
# StatusBarWidget - Result object for status bar widgets
# ============================================================================

class StatusBarWidget:
    """
    Widget information for status bar
    Used by status_bar_widget hooks

    Example:
        from PyQt6.QtWidgets import QLabel
        widget = QLabel("My Plugin")
        info = StatusBarWidget(widget)
        info.permanent = True
        return info
    """

    def __init__(self, widget):
        self.widget = widget                        # QWidget to display
        self.permanent: bool = False                # If True, shown on right side
        self.stretch: int = 0                       # Stretch factor

    def __repr__(self):
        return f"StatusBarWidget(permanent={self.permanent})"

