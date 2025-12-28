# ============================================================================
# PluginManagerUI.py - Updated to use PluginAPI
# ============================================================================

"""
Plugin Manager UI - Handles plugin discovery and loading
Updated to properly pass PluginAPI to plugins
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
            plugin_api: PluginAPI instance (this is what plugins need!)
        """
        self.workspace = workspace_ide
        self.plugin_manager = plugin_manager
        self.plugin_api = plugin_api  # Store the API to pass to plugins
        self.loaded_plugin_tabs = {}
    
    def create_plugin_menu(self, menubar):
        """Create plugins menu"""
        plugins_menu = menubar.addMenu("Plugins")
        
        # Browse plugins action
        browse_action = plugins_menu.addAction("📦 Browse Plugins...")
        browse_action.triggered.connect(self.show_plugin_browser)
        
        plugins_menu.addSeparator()
        
        # Refresh plugins submenu
        self.plugins_submenu = plugins_menu.addMenu("🔌 Open Plugin")
        self.refresh_plugin_submenu()
        
        return plugins_menu
    
    def refresh_plugin_submenu(self):
        """Refresh the plugins submenu with available plugins"""
        self.plugins_submenu.clear()
        
        plugins = self.plugin_manager.scan_plugins()
        
        if not plugins:
            no_plugins = self.plugins_submenu.addAction("(No plugins found)")
            no_plugins.setEnabled(False)
            return
        
        for plugin_info in plugins:
            action = self.plugins_submenu.addAction(plugin_info['name'])
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
            # Load the plugin module
            plugin_module = self.plugin_manager.load_plugin(plugin_file)
            
            # Create plugin widget - PASS plugin_api HERE!
            plugin_widget = PluginWidget(
                plugin_module, 
                self.plugin_api,  # This is the key fix!
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
                                     "2. Define PLUGIN_NAME and get_widget() function\n"
                                     "3. Optionally define initialize(api) for API access")
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
        
        details = f"""
<h3>{plugin_info['name']}</h3>

<p><b>Version:</b> {plugin_info['version']}</p>
<p><b>File:</b> {plugin_info['file'].name}</p>
<p><b>Path:</b> {plugin_info['file']}</p>

<h4>Description:</h4>
<p>{plugin_info.get('description', 'No description available')}</p>

<h4>Usage:</h4>
<p>Click "Open Plugin" to load this plugin in a new tab.</p>
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




# import platform
# import subprocess

# from PyQt6.QtWidgets import QMessageBox, QMenu
# from PyQt6.QtCore import QTimer, Qt

# from ide.core.Plugin import PluginWidget, PluginManager


# class PluginManagerUI:
    # """Handles all plugin-related menu and actions for the IDE"""

    # def __init__(self, ide):
        # self.ide = ide
        # self.plugin_manager = PluginManager(ide.workspace_path)

    # def create_plugin_menu(self, menubar):
        # plugins_menu = menubar.addMenu("Plugins")
        # self.rebuild_plugin_menu(plugins_menu)
        # return plugins_menu

    # def rebuild_plugin_menu(self, plugins_menu):
        # plugins_menu.clear()
        # available_plugins = self.plugin_manager.scan_plugins()

        # if not available_plugins:
            # no_plugins_action = plugins_menu.addAction("No plugins found")
            # no_plugins_action.setEnabled(False)
            # plugins_menu.addSeparator()
        # else:
            # for plugin_info in available_plugins:
                # action = plugins_menu.addAction(f"🔌 {plugin_info['name']}")
                # action.triggered.connect(
                    # lambda checked, p=plugin_info: self.open_plugin(p)
                # )
            # plugins_menu.addSeparator()

        # refresh_action = plugins_menu.addAction("🔄 Refresh Plugin List")
        # refresh_action.triggered.connect(lambda: self.rebuild_plugin_menu(plugins_menu))

        # plugins_menu.addSeparator()

        # open_folder_action = plugins_menu.addAction("📁 Open Plugins Folder")
        # open_folder_action.triggered.connect(self.open_plugins_folder)

        # plugins_menu.addSeparator()

        # help_action = plugins_menu.addAction("❓ Plugin Development Guide")
        # help_action.triggered.connect(self.show_plugin_help)

    # def open_plugin(self, plugin_info):
        # try:
            # plugin_name = plugin_info['name']
            # # Prevent duplicate tabs
            # for i in range(self.ide.tabs.count()):
                # widget = self.ide.tabs.widget(i)
                # if isinstance(widget, PluginWidget) and widget.plugin_name == plugin_name:
                    # self.ide.tabs.setCurrentIndex(i)
                    # self.ide.status_message.setText(f"Plugin '{plugin_name}' already open")
                    # QTimer.singleShot(2000, lambda: self.ide.status_message.setText(""))
                    # return

            # plugin_module = self.plugin_manager.load_plugin(plugin_info['file'])
            # plugin_widget = PluginWidget(plugin_module, self.ide)

            # tab_index = self.ide.tabs.addTab(plugin_widget, f"🔌 {plugin_name}")
            # self.ide.tabs.setTabToolTip(tab_index, f"{plugin_name} v{plugin_info['version']}")
            # self.ide.tabs.setCurrentIndex(tab_index)

            # self.ide.status_message.setText(f"Loaded plugin: {plugin_name}")
            # QTimer.singleShot(3000, lambda: self.ide.status_message.setText(""))

        # except Exception as e:
            # QMessageBox.critical(
                # self.ide,
                # "Plugin Load Error",
                # f"Failed to load plugin '{plugin_info['name']}':\n\n{str(e)}"
            # )

    # def open_plugins_folder(self):
        # plugins_dir = self.plugin_manager.plugins_dir
        # try:
            # if platform.system() == 'Darwin':
                # subprocess.run(['open', str(plugins_dir)])
            # elif platform.system() == 'Windows':
                # subprocess.run(['explorer', str(plugins_dir)])
            # else:
                # subprocess.run(['xdg-open', str(plugins_dir)])
        # except Exception:
            # QMessageBox.information(
                # self.ide,
                # "Plugins Folder",
                # f"Plugins folder location:\n\n{plugins_dir}"
            # )

    # def show_plugin_help(self):
        # help_text = """
# <h3>🔌 Plugin Development Guide</h3>
# <h4>Plugin Structure</h4>
# <p>Plugins are Python files placed in the <code>workspace/plugins</code> directory.</p>
# <h4>Minimum Required Components</h4>
# <pre><code>PLUGIN_NAME = "My Plugin"
# PLUGIN_VERSION = "1.0.0"

# def get_widget(parent=None):
    # '''Returns a QWidget to display'''
    # widget = QWidget(parent)
    # # Build your UI here
    # return widget
# </code></pre>
# <h4>Example Plugin</h4>
# <p>Check out <code>example_plugin.py</code> in your plugins folder for a complete example.</p>
# <h4>Tips</h4>
# <ul>
# <li>Refresh the plugin list after creating new plugins</li>
# <li>Plugin tabs can be closed like any other tab</li>
# <li>You can open multiple instances of the same plugin</li>
# </ul>
# """
        # msg = QMessageBox(self.ide)
        # msg.setWindowTitle("Plugin Development Guide")
        # msg.setTextFormat(Qt.TextFormat.RichText)
        # msg.setText(help_text)
        # msg.exec()