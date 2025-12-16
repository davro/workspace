import platform
import subprocess

from PyQt6.QtWidgets import QMessageBox, QMenu
from PyQt6.QtCore import QTimer, Qt

from ide.core.Plugin import PluginWidget, PluginManager


class PluginManagerUI:
    """Handles all plugin-related menu and actions for the IDE"""

    def __init__(self, ide):
        self.ide = ide
        self.plugin_manager = PluginManager(ide.workspace_path)

    def create_plugin_menu(self, menubar):
        plugins_menu = menubar.addMenu("Plugins")
        self.rebuild_plugin_menu(plugins_menu)
        return plugins_menu

    def rebuild_plugin_menu(self, plugins_menu):
        plugins_menu.clear()
        available_plugins = self.plugin_manager.scan_plugins()

        if not available_plugins:
            no_plugins_action = plugins_menu.addAction("No plugins found")
            no_plugins_action.setEnabled(False)
            plugins_menu.addSeparator()
        else:
            for plugin_info in available_plugins:
                action = plugins_menu.addAction(f"🔌 {plugin_info['name']}")
                action.triggered.connect(
                    lambda checked, p=plugin_info: self.open_plugin(p)
                )
            plugins_menu.addSeparator()

        refresh_action = plugins_menu.addAction("🔄 Refresh Plugin List")
        refresh_action.triggered.connect(lambda: self.rebuild_plugin_menu(plugins_menu))

        plugins_menu.addSeparator()

        open_folder_action = plugins_menu.addAction("📁 Open Plugins Folder")
        open_folder_action.triggered.connect(self.open_plugins_folder)

        plugins_menu.addSeparator()

        help_action = plugins_menu.addAction("❓ Plugin Development Guide")
        help_action.triggered.connect(self.show_plugin_help)

    def open_plugin(self, plugin_info):
        try:
            plugin_name = plugin_info['name']
            # Prevent duplicate tabs
            for i in range(self.ide.tabs.count()):
                widget = self.ide.tabs.widget(i)
                if isinstance(widget, PluginWidget) and widget.plugin_name == plugin_name:
                    self.ide.tabs.setCurrentIndex(i)
                    self.ide.status_message.setText(f"Plugin '{plugin_name}' already open")
                    QTimer.singleShot(2000, lambda: self.ide.status_message.setText(""))
                    return

            plugin_module = self.plugin_manager.load_plugin(plugin_info['file'])
            plugin_widget = PluginWidget(plugin_module, self.ide)

            tab_index = self.ide.tabs.addTab(plugin_widget, f"🔌 {plugin_name}")
            self.ide.tabs.setTabToolTip(tab_index, f"{plugin_name} v{plugin_info['version']}")
            self.ide.tabs.setCurrentIndex(tab_index)

            self.ide.status_message.setText(f"Loaded plugin: {plugin_name}")
            QTimer.singleShot(3000, lambda: self.ide.status_message.setText(""))

        except Exception as e:
            QMessageBox.critical(
                self.ide,
                "Plugin Load Error",
                f"Failed to load plugin '{plugin_info['name']}':\n\n{str(e)}"
            )

    def open_plugins_folder(self):
        plugins_dir = self.plugin_manager.plugins_dir
        try:
            if platform.system() == 'Darwin':
                subprocess.run(['open', str(plugins_dir)])
            elif platform.system() == 'Windows':
                subprocess.run(['explorer', str(plugins_dir)])
            else:
                subprocess.run(['xdg-open', str(plugins_dir)])
        except Exception:
            QMessageBox.information(
                self.ide,
                "Plugins Folder",
                f"Plugins folder location:\n\n{plugins_dir}"
            )

    def show_plugin_help(self):
        help_text = """
<h3>🔌 Plugin Development Guide</h3>
<h4>Plugin Structure</h4>
<p>Plugins are Python files placed in the <code>workspace/plugins</code> directory.</p>
<h4>Minimum Required Components</h4>
<pre><code>PLUGIN_NAME = "My Plugin"
PLUGIN_VERSION = "1.0.0"

def get_widget(parent=None):
    '''Returns a QWidget to display'''
    widget = QWidget(parent)
    # Build your UI here
    return widget
</code></pre>
<h4>Example Plugin</h4>
<p>Check out <code>example_plugin.py</code> in your plugins folder for a complete example.</p>
<h4>Tips</h4>
<ul>
<li>Refresh the plugin list after creating new plugins</li>
<li>Plugin tabs can be closed like any other tab</li>
<li>You can open multiple instances of the same plugin</li>
</ul>
"""
        msg = QMessageBox(self.ide)
        msg.setWindowTitle("Plugin Development Guide")
        msg.setTextFormat(Qt.TextFormat.RichText)
        msg.setText(help_text)
        msg.exec()