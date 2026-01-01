# ide/core/PluginManagerUI.py - Updated for pure class-based plugins

"""
Plugin Manager UI - Handles plugin discovery and loading
Pure class-based plugins only
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QLabel,
    QPushButton, QTextEdit, QWidget, QMessageBox, QListWidgetItem
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from pathlib import Path

from ide.core.Plugin import PluginWidget


class PluginManagerUI:
    """Manages plugin UI and loading"""
    
    def __init__(self, workspace_ide, plugin_manager, plugin_api):
        """
        Initialize Plugin Manager UI
        
        Args:
            workspace_ide: Main workspace IDE instance
            plugin_manager: PluginManager instance
            plugin_api: PluginAPI instance
        """
        self.workspace = workspace_ide
        self.plugin_manager = plugin_manager
        self.plugin_api = plugin_api
        self.loaded_plugin_tabs = {}
    
    def create_plugin_menu(self, menubar):
        """Create plugins menu"""
        plugins_menu = menubar.addMenu("Plugins")
        
        # Browse plugins action
        browse_action = plugins_menu.addAction("📦 Browse Plugins...")
        browse_action.triggered.connect(self.show_plugin_browser)
        
        plugins_menu.addSeparator()
        
        # Reload all plugins (for development)
        reload_all_action = plugins_menu.addAction("🔄 Reload All Plugins")
        reload_all_action.triggered.connect(self.reload_all_plugins)
        reload_all_action.setToolTip("Hot reload all background plugins (for development)")
        
        plugins_menu.addSeparator()
        
        # Refresh plugins submenu
        self.plugins_submenu = plugins_menu.addMenu("🔌 Open Plugin")
        self.refresh_plugin_submenu()
        
        return plugins_menu
    
    def refresh_plugin_submenu(self):
        """Refresh the plugins submenu with available plugins"""
        self.plugins_submenu.clear()
        
        plugins = self.plugin_manager.scan_plugins()
        
        # Filter to only show plugins with UI
        ui_plugins = [p for p in plugins if p.get('has_ui', True)]
        
        if not ui_plugins:
            no_plugins = self.plugins_submenu.addAction("(No plugin panels)")
            no_plugins.setEnabled(False)
            return
        
        for plugin_info in ui_plugins:
            # Show status if plugin is running in background
            status = " ✓" if plugin_info.get('run_on_startup', False) else ""
            action = self.plugins_submenu.addAction(f"{plugin_info['name']}{status}")
            action.triggered.connect(
                lambda checked, p=plugin_info: self.open_plugin(p)
            )
    
    def show_plugin_browser(self):
        """Show plugin browser dialog"""
        dialog = PluginBrowserDialog(self.plugin_manager, self)
        dialog.exec()
    
    def open_plugin(self, plugin_info):
        """
        Open a plugin in a new tab
        
        Args:
            plugin_info: Dictionary with plugin information
        """
        plugin_file = plugin_info['file']
        plugin_name = plugin_info['name']
        
        # Check if already open
        if str(plugin_file) in self.loaded_plugin_tabs:
            # Switch to existing tab
            existing_tab = self.loaded_plugin_tabs[str(plugin_file)]
            index = self.workspace.tabs.indexOf(existing_tab)
            if index >= 0:
                self.workspace.tabs.setCurrentIndex(index)
                return
        
        try:
            # Load or get the plugin instance
            plugin_instance = self.plugin_manager.load_plugin(plugin_file)
            
            # Create plugin widget wrapper - PASS INSTANCE ONLY!
            plugin_widget = PluginWidget(
                plugin_instance,  # Just the instance!
                parent=self.workspace.tabs
            )
            
            # Add to tabs
            index = self.workspace.tabs.addTab(plugin_widget, f"🔌 {plugin_name}")
            self.workspace.tabs.setCurrentIndex(index)
            
            # Track the tab
            self.loaded_plugin_tabs[str(plugin_file)] = plugin_widget
            
            # Show success message
            self.workspace.status_message.setText(f"Loaded plugin: {plugin_name}")
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(3000, lambda: self.workspace.status_message.setText(""))
            
        except Exception as e:
            import traceback
            error_msg = f"Failed to load plugin '{plugin_name}':\n{str(e)}\n\n{traceback.format_exc()}"
            print(f"[PluginManagerUI] {error_msg}")
            QMessageBox.critical(
                self.workspace,
                "Plugin Load Error",
                f"Failed to load plugin '{plugin_name}':\n\n{str(e)}"
            )

    def reload_all_plugins(self):
        """Reload all background plugins"""
        from PyQt6.QtWidgets import QMessageBox
        
        plugins = self.plugin_manager.scan_plugins()
        background_plugins = [p for p in plugins if p.get('run_on_startup', False)]
        
        if not background_plugins:
            QMessageBox.information(
                self.workspace,
                "No Background Plugins",
                "No background plugins to reload."
            )
            return
        
        success_count = 0
        failed = []
        
        for plugin_info in background_plugins:
            try:
                print(f"[PluginManagerUI] Reloading {plugin_info['name']}...")
                
                # Close tabs - use the toolbar's method which is now fixed
                if hasattr(self.workspace.menu_manager, 'plugin_toolbar'):
                    toolbar = self.workspace.menu_manager.plugin_toolbar
                    toolbar._close_plugin_tabs(plugin_info['file'])
                
                # Unload
                self.plugin_manager.unload_plugin(plugin_info['file'])
                
                # Clear cache
                import sys
                module_name = plugin_info['file'].stem
                modules_to_remove = [k for k in sys.modules.keys() 
                                    if k == module_name or k.startswith(f"{module_name}.")]
                for key in modules_to_remove:
                    del sys.modules[key]
                
                # Reload
                self.plugin_manager.load_plugin(plugin_info['file'])
                
                success_count += 1
                
            except Exception as e:
                import traceback
                print(f"[PluginManagerUI] Failed to reload {plugin_info['name']}:")
                traceback.print_exc()
                failed.append((plugin_info['name'], str(e)))
        
        # Refresh toolbar
        if hasattr(self.workspace.menu_manager, 'plugin_toolbar'):
            self.workspace.menu_manager.plugin_toolbar.refresh_plugins()
        
        # Show results
        if failed:
            msg = f"Reloaded {success_count} plugin(s)\n\nFailed:\n"
            msg += "\n".join(f"• {name}: {err}" for name, err in failed)
            QMessageBox.warning(self.workspace, "Reload Complete (with errors)", msg)
        else:
            msg = f"✓ Successfully reloaded {success_count} plugin(s)"
            QMessageBox.information(self.workspace, "Reload Complete", msg)
            self.workspace.status_message.setText(msg)
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(3000, lambda: self.workspace.status_message.setText(""))

    # def reload_all_plugins(self):
        # """Reload all background plugins"""
        # from PyQt6.QtWidgets import QMessageBox
        
        # plugins = self.plugin_manager.scan_plugins()
        # background_plugins = [p for p in plugins if p.get('run_on_startup', False)]
        
        # if not background_plugins:
            # QMessageBox.information(
                # self.workspace,
                # "No Background Plugins",
                # "No background plugins to reload."
            # )
            # return
        
        # success_count = 0
        # failed = []
        
        # for plugin_info in background_plugins:
            # try:
                # print(f"[PluginManagerUI] Reloading {plugin_info['name']}...")
                
                # # Close tabs
                # if hasattr(self.workspace.menu_manager, 'plugin_toolbar'):
                    # toolbar = self.workspace.menu_manager.plugin_toolbar
                    # toolbar._close_plugin_tabs(plugin_info['file'])
                
                # # Unload
                # self.plugin_manager.unload_plugin(plugin_info['file'])
                
                # # Clear cache
                # import sys
                # module_name = plugin_info['file'].stem
                # modules_to_remove = [k for k in sys.modules.keys() 
                                    # if k == module_name or k.startswith(f"{module_name}.")]
                # for key in modules_to_remove:
                    # del sys.modules[key]
                
                # # Reload
                # self.plugin_manager.load_plugin(plugin_info['file'])
                
                # success_count += 1
                
            # except Exception as e:
                # print(f"[PluginManagerUI] Failed to reload {plugin_info['name']}: {e}")
                # failed.append((plugin_info['name'], str(e)))
        
        # # Refresh toolbar
        # if hasattr(self.workspace.menu_manager, 'plugin_toolbar'):
            # self.workspace.menu_manager.plugin_toolbar.refresh_plugins()
        
        # # Show results
        # if failed:
            # msg = f"Reloaded {success_count} plugin(s)\n\nFailed:\n"
            # msg += "\n".join(f"• {name}: {err}" for name, err in failed)
            # QMessageBox.warning(self.workspace, "Reload Complete (with errors)", msg)
        # else:
            # msg = f"✓ Successfully reloaded {success_count} plugin(s)"
            # QMessageBox.information(self.workspace, "Reload Complete", msg)
            # self.workspace.status_message.setText(msg)
            # from PyQt6.QtCore import QTimer
            # QTimer.singleShot(3000, lambda: self.workspace.status_message.setText(""))


class PluginBrowserDialog(QDialog):
    """Dialog for browsing and managing plugins"""
    
    def __init__(self, plugin_manager, plugin_ui, parent=None):
        super().__init__(parent)
        self.plugin_manager = plugin_manager
        self.plugin_ui = plugin_ui
        self.init_ui()
    
    def init_ui(self):
        """Initialize UI"""
        self.setWindowTitle("Plugin Browser")
        self.resize(700, 500)
        
        layout = QHBoxLayout(self)
        
        # Left side - plugin list
        left_layout = QVBoxLayout()
        
        list_label = QLabel("Available Plugins:")
        list_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        left_layout.addWidget(list_label)
        
        self.plugin_list = QListWidget()
        self.plugin_list.currentItemChanged.connect(self.on_plugin_selected)
        left_layout.addWidget(self.plugin_list)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.open_button = QPushButton("Open Plugin")
        self.open_button.clicked.connect(self.open_selected_plugin)
        self.open_button.setEnabled(False)
        button_layout.addWidget(self.open_button)
        
        refresh_button = QPushButton("🔄 Refresh")
        refresh_button.clicked.connect(self.refresh_plugins)
        button_layout.addWidget(refresh_button)
        
        left_layout.addLayout(button_layout)
        
        layout.addLayout(left_layout, 1)
        
        # Right side - plugin details
        right_layout = QVBoxLayout()
        
        details_label = QLabel("Plugin Details:")
        details_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        right_layout.addWidget(details_label)
        
        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        self.details_text.setStyleSheet("""
            QTextEdit {
                background: #2D2D2D;
                color: #CCC;
                border: 1px solid #555;
                padding: 10px;
                font-family: 'Courier New', monospace;
            }
        """)
        right_layout.addWidget(self.details_text)
        
        layout.addLayout(right_layout, 1)
        
        # Load plugins
        self.refresh_plugins()
    
    def refresh_plugins(self):
        """Refresh plugin list"""
        self.plugin_list.clear()
        self.details_text.clear()
        
        plugins = self.plugin_manager.scan_plugins()
        
        if not plugins:
            self.details_text.setText("No plugins found.\n\nTo create a plugin:\n"
                                     "1. Create a .py file in ide/plugins/\n"
                                     "2. Define a class with PLUGIN_NAME attribute\n"
                                     "3. Implement __init__, initialize, get_widget, cleanup")
            return
        
        for plugin_info in plugins:
            item = QListWidgetItem(f"🔌 {plugin_info['name']}")
            item.setData(Qt.ItemDataRole.UserRole, plugin_info)
            self.plugin_list.addItem(item)
        
        # Select first plugin
        if self.plugin_list.count() > 0:
            self.plugin_list.setCurrentRow(0)
    
    def on_plugin_selected(self, current, previous):
        """Handle plugin selection"""
        if not current:
            self.open_button.setEnabled(False)
            self.details_text.clear()
            return
        
        self.open_button.setEnabled(True)
        
        plugin_info = current.data(Qt.ItemDataRole.UserRole)
        
        # Build status info
        status_parts = []
        if plugin_info.get('run_on_startup', False):
            status_parts.append("✓ Running in background")
        if plugin_info.get('has_ui', True):
            status_parts.append("📋 Has control panel")
        
        status_html = "<br>".join(status_parts) if status_parts else "Inactive"
        
        details = f"""
<h3>{plugin_info['name']}</h3>

<p><b>Version:</b> {plugin_info['version']}</p>
<p><b>Status:</b> {status_html}</p>
<p><b>File:</b> {plugin_info['file'].name}</p>

<h4>Description:</h4>
<p>{plugin_info.get('description', 'No description available')}</p>

<h4>Usage:</h4>
<p>Click "Open Plugin" to show the control panel in a new tab.</p>
"""
        
        self.details_text.setHtml(details)
    
    def open_selected_plugin(self):
        """Open the currently selected plugin"""
        current_item = self.plugin_list.currentItem()
        if not current_item:
            return
        
        plugin_info = current_item.data(Qt.ItemDataRole.UserRole)
        self.plugin_ui.open_plugin(plugin_info)
        self.accept()

