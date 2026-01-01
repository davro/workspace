# ide/core/PluginToolbar.py

"""
Plugin Toolbar - Shows active background plugins like Chrome extensions
"""

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QToolButton, QMenu, QLabel
from PyQt6.QtCore import Qt, pyqtSignal


class PluginToolbar(QWidget):
    """Toolbar showing active background plugins"""
    
    plugin_clicked = pyqtSignal(dict)
    
    def __init__(self, plugin_manager, plugin_ui, parent=None):
        super().__init__(parent)
        self.plugin_manager = plugin_manager
        self.plugin_ui = plugin_ui
        self.plugin_buttons = {}
        
        self.init_ui()
    
    def init_ui(self):
        """Initialize toolbar UI"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 10, 0)
        layout.setSpacing(2)
        
        # Add stretch to push buttons to the right
        layout.addStretch()
        
        self.setStyleSheet("""
            QToolButton {
                background: transparent;
                border: none;
                padding: 4px;
                margin: 0px 2px;
                border-radius: 3px;
            }
            QToolButton:hover {
                background: #3C3F41;
            }
            QToolButton:pressed {
                background: #4A4A4A;
            }
        """)
    
    def refresh_plugins(self):
        """Refresh toolbar with active background plugins"""
        # Clear existing buttons
        layout = self.layout()
        for button in self.plugin_buttons.values():
            layout.removeWidget(button)
            button.deleteLater()
        self.plugin_buttons.clear()
        
        # Get all plugins
        plugins = self.plugin_manager.scan_plugins()
        
        # Filter to only show background plugins with UI
        active_plugins = [
            p for p in plugins 
            if p.get('run_on_startup', False) and p.get('has_ui', True)
        ]
        
        # Add buttons for each active plugin
        for plugin_info in active_plugins:
            button = self.create_plugin_button(plugin_info)
            self.plugin_buttons[plugin_info['name']] = button
            layout.addWidget(button)
    
    def create_plugin_button(self, plugin_info):
        """Create a button for a plugin"""
        button = QToolButton()
        
        # Get plugin icon
        icon_text = plugin_info.get('icon', '🔌')
        button.setText(icon_text)
        button.setToolTip(f"{plugin_info['name']}\n{plugin_info.get('description', '')}")
        
        # Main action: Show UI panel
        button.clicked.connect(lambda: self.open_plugin_panel(plugin_info))
        
        # Context menu for additional actions
        button.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        button.customContextMenuRequested.connect(
            lambda pos, p=plugin_info: self.show_plugin_menu(button, p)
        )
        
        return button
    
    def open_plugin_panel(self, plugin_info):
        """Open plugin UI panel in a tab"""
        self.plugin_ui.open_plugin(plugin_info)
        self.plugin_clicked.emit(plugin_info)
    
    def show_plugin_menu(self, button, plugin_info):
        """Show context menu for plugin"""
        menu = QMenu(button)
        
        # Show UI Panel
        show_action = menu.addAction("📋 Show Panel")
        show_action.triggered.connect(lambda: self.open_plugin_panel(plugin_info))
        
        menu.addSeparator()
        
        # Reload plugin
        reload_action = menu.addAction("🔄 Reload Plugin")
        reload_action.triggered.connect(lambda: self.reload_plugin(plugin_info))
        reload_action.setToolTip("Hot reload plugin code (for development)")
        
        menu.addSeparator()
        
        # Plugin info
        info_action = menu.addAction("ℹ️ About Plugin")
        info_action.triggered.connect(lambda: self.show_plugin_info(plugin_info))
        
        # Show menu below button
        menu.exec(button.mapToGlobal(button.rect().bottomLeft()))
    
    def reload_plugin(self, plugin_info):
        """Hot reload a plugin"""
        from PyQt6.QtWidgets import QMessageBox
        
        plugin_name = plugin_info['name']
        plugin_file = plugin_info['file']
        
        try:
            # Step 1: Close any open UI tabs
            self._close_plugin_tabs(plugin_file)
            
            # Step 2: Unload the plugin
            print(f"[PluginToolbar] Unloading {plugin_name}...")
            self.plugin_manager.unload_plugin(plugin_file)
            
            # Step 3: Clear module from Python's import cache
            self._clear_module_cache(plugin_file)
            
            # Step 4: Reload the plugin
            print(f"[PluginToolbar] Reloading {plugin_name}...")
            self.plugin_manager.load_plugin(plugin_file)
            
            # Step 5: Refresh the toolbar
            self.refresh_plugins()
            
            # Success message
            msg = f"✓ Plugin '{plugin_name}' reloaded successfully!"
            print(f"[PluginToolbar] {msg}")
            
            workspace = self.plugin_ui.workspace
            if hasattr(workspace, 'status_message'):
                workspace.status_message.setText(msg)
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(3000, lambda: workspace.status_message.setText(""))
        
        except Exception as e:
            import traceback
            error_msg = f"Failed to reload plugin '{plugin_name}':\n\n{str(e)}"
            print(f"[PluginToolbar] {error_msg}")
            traceback.print_exc()
            
            QMessageBox.critical(
                self.plugin_ui.workspace,
                "Plugin Reload Failed",
                error_msg
            )
    
    def _close_plugin_tabs(self, plugin_file):
        """Close any open tabs for this plugin"""
        plugin_key = str(plugin_file)
        
        print(f"[PluginToolbar] Looking for tabs with plugin key: {plugin_key}")
        
        if not hasattr(self.plugin_ui, 'loaded_plugin_tabs'):
            print(f"[PluginToolbar] No loaded_plugin_tabs attribute")
            return
        
        if plugin_key not in self.plugin_ui.loaded_plugin_tabs:
            print(f"[PluginToolbar] Plugin tab not found in tracking")
            return
        
        plugin_widget = self.plugin_ui.loaded_plugin_tabs[plugin_key]
        print(f"[PluginToolbar] Found plugin widget: {plugin_widget}")
        
        # Get workspace
        workspace = self.plugin_ui.workspace
        
        # Try main tabs
        tab_closed = False
        if hasattr(workspace, 'tabs'):
            index = workspace.tabs.indexOf(plugin_widget)
            if index >= 0:
                print(f"[PluginToolbar] Closing tab at index {index}")
                workspace.tabs.removeTab(index)
                tab_closed = True
        
        # Try split editor groups - FIX: Use correct attribute name
        if not tab_closed and hasattr(workspace, 'split_manager'):
            print(f"[PluginToolbar] Checking split editor groups...")
            split_manager = workspace.split_manager
            
            # CORRECT: Use .groups (not .editor_groups)
            if hasattr(split_manager, 'groups'):
                all_groups = split_manager.groups
                
                for group in all_groups:
                    if hasattr(group, 'tabs'):
                        index = group.tabs.indexOf(plugin_widget)
                        
                        if index >= 0:
                            print(f"[PluginToolbar] Found in split group at index {index}")
                            group.tabs.removeTab(index)
                            tab_closed = True
                            break
            else:
                print(f"[PluginToolbar] Split manager has no 'groups' attribute")
        
        if not tab_closed:
            print(f"[PluginToolbar] Warning: Could not find tab to close")
        
        # Remove from tracking
        del self.plugin_ui.loaded_plugin_tabs[plugin_key]
        print(f"[PluginToolbar] Removed from tracking")    

    # def _close_plugin_tabs(self, plugin_file):
        # """Close any open tabs for this plugin"""
        # plugin_key = str(plugin_file)
        
        # print(f"[PluginToolbar] Looking for tabs with plugin key: {plugin_key}")
        
        # if not hasattr(self.plugin_ui, 'loaded_plugin_tabs'):
            # print(f"[PluginToolbar] No loaded_plugin_tabs attribute")
            # return
        
        # if plugin_key not in self.plugin_ui.loaded_plugin_tabs:
            # print(f"[PluginToolbar] Plugin tab not found in tracking")
            # return
        
        # plugin_widget = self.plugin_ui.loaded_plugin_tabs[plugin_key]
        # print(f"[PluginToolbar] Found plugin widget: {plugin_widget}")
        
        # # Get workspace
        # workspace = self.plugin_ui.workspace
        
        # # Try main tabs
        # tab_closed = False
        # if hasattr(workspace, 'tabs'):
            # index = workspace.tabs.indexOf(plugin_widget)
            # if index >= 0:
                # print(f"[PluginToolbar] Closing tab at index {index}")
                # workspace.tabs.removeTab(index)
                # tab_closed = True
        
        # # Try split editor groups
        # if not tab_closed and hasattr(workspace, 'split_manager'):
            # print(f"[PluginToolbar] Checking split editor groups...")
            # for group in workspace.split_manager.editor_groups:
                # index = group.tabs.indexOf(plugin_widget)
                # if index >= 0:
                    # print(f"[PluginToolbar] Found in split group at index {index}")
                    # group.tabs.removeTab(index)
                    # tab_closed = True
                    # break
        
        # if not tab_closed:
            # print(f"[PluginToolbar] Warning: Could not find tab to close")
        
        # # Remove from tracking
        # del self.plugin_ui.loaded_plugin_tabs[plugin_key]
        # print(f"[PluginToolbar] Removed from tracking")
    
    def _clear_module_cache(self, plugin_file):
        """Clear module from Python's import cache"""
        import sys
        
        module_name = plugin_file.stem
        
        # Remove from sys.modules
        modules_to_remove = [
            key for key in sys.modules.keys() 
            if key == module_name or key.startswith(f"{module_name}.")
        ]
        
        for key in modules_to_remove:
            print(f"[PluginToolbar] Clearing module cache: {key}")
            del sys.modules[key]
    
    def show_plugin_info(self, plugin_info):
        """Show plugin information dialog"""
        from PyQt6.QtWidgets import QMessageBox
        
        info_text = (
            f"<h3>{plugin_info['name']}</h3>"
            f"<p><b>Version:</b> {plugin_info.get('version', 'Unknown')}</p>"
            f"<p><b>Description:</b> {plugin_info.get('description', 'No description')}</p>"
            f"<p><b>Status:</b> ✓ Running in background</p>"
        )
        
        msg = QMessageBox(self.plugin_ui.workspace)
        msg.setWindowTitle("Plugin Information")
        msg.setTextFormat(Qt.TextFormat.RichText)
        msg.setText(info_text)
        msg.exec()

    