import importlib.util
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt

# =====================================================================
class PluginWidget(QWidget):
    """Base wrapper for plugin widgets loaded in tabs"""
    
    def __init__(self, plugin_module, plugin_api, parent=None):
        super().__init__(parent)
        self.plugin_module = plugin_module
        self.plugin_api = plugin_api
        self.plugin_name = getattr(plugin_module, 'PLUGIN_NAME', 'Unknown Plugin')
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        try:
            # Initialize plugin if it has init function
            if hasattr(plugin_module, 'initialize') and plugin_api:
                plugin_module.initialize(plugin_api)
            
            # Try to get the main widget from plugin
            if hasattr(plugin_module, 'get_widget'):
                plugin_widget = plugin_module.get_widget(parent=self)
                layout.addWidget(plugin_widget)
            else:
                error_label = QLabel(f"⚠️ Plugin '{self.plugin_name}' has no get_widget() function")
                error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                error_label.setStyleSheet("color: #E74C3C; font-size: 14px;")
                layout.addWidget(error_label)
        except Exception as e:
            import traceback
            error_msg = f"⚠️ Error loading plugin:\n{str(e)}\n\n{traceback.format_exc()}"
            error_label = QLabel(error_msg)
            error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            error_label.setStyleSheet("color: #E74C3C; font-size: 11px;")
            error_label.setWordWrap(True)
            layout.addWidget(error_label)
            print(f"[PluginWidget] Error loading {self.plugin_name}:")
            traceback.print_exc()
    
    def cleanup(self):
        """Cleanup plugin when widget is destroyed"""
        try:
            if hasattr(self.plugin_module, 'cleanup'):
                self.plugin_module.cleanup()
        except Exception as e:
            print(f"Error during plugin cleanup: {e}")


# =====================================================================
class PluginManager:
    """Manages loading and tracking of IDE plugins"""
    
    def __init__(self, workspace_path, plugin_api=None):
        self.workspace_path = workspace_path
        self.plugins_dir = workspace_path / "ide/plugins"
        self.loaded_plugins = {}
        self.plugin_api = plugin_api
        
        # Create plugins directory if it doesn't exist
        if not self.plugins_dir.exists():
            self.plugins_dir.mkdir(parents=True)
            self.create_example_plugin()
    
    def set_plugin_api(self, plugin_api):
        """Set the plugin API after initialization"""
        self.plugin_api = plugin_api
    
    def create_example_plugin(self):
        """Create an example plugin to show structure"""
        example_plugin = '''"""
Example Plugin for Workspace IDE - Basic Template

This is a minimal plugin showing the basic structure.
For a comprehensive example with all features, see comprehensive_example.py

Plugin structure:
- PLUGIN_NAME: Display name for the plugin
- PLUGIN_VERSION: Plugin version
- get_widget(parent): Returns a QWidget to display in tab
- initialize(api): Optional - Called when plugin loads
- cleanup(): Optional - Called when plugin unloads
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QTextEdit
from PyQt6.QtCore import Qt

PLUGIN_NAME = "Example Plugin"
PLUGIN_VERSION = "1.0.0"


def get_widget(parent=None):
    """
    This function must return a QWidget that will be displayed in the editor tab.
    
    Args:
        parent: Parent widget (usually None or the tab widget)
    
    Returns:
        QWidget: Your plugin's main widget
    """
    widget = QWidget(parent)
    layout = QVBoxLayout(widget)
    
    # Add your plugin UI here
    title = QLabel("🔌 Example Plugin")
    title.setStyleSheet("font-size: 18px; font-weight: bold; color: #4A9EFF;")
    title.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(title)
    
    info = QLabel(
        "This is a basic example plugin.\\n\\n"
        "Create your own plugin by copying this file and modifying it.\\n"
        "Your plugin must have:\\n"
        "  • PLUGIN_NAME constant\\n"
        "  • get_widget() function that returns a QWidget\\n\\n"
        "For advanced features, see comprehensive_example.py"
    )
    info.setStyleSheet("color: #CCC; padding: 20px;")
    info.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(info)
    
    # Example interactive element
    button = QPushButton("Click Me!")
    button.clicked.connect(lambda: text_area.append("Button clicked!\\n"))
    layout.addWidget(button)
    
    text_area = QTextEdit()
    text_area.setPlaceholderText("Plugin output will appear here...")
    text_area.setStyleSheet("background: #1E1E1E; color: #CCC; border: 1px solid #555;")
    layout.addWidget(text_area)
    
    return widget


# Optional: Initialize plugin with API access
def initialize(api):
    """
    Called when plugin is loaded (optional)
    
    Args:
        api: PluginAPI instance for IDE integration
    """
    pass


# Optional: Cleanup when plugin is unloaded
def cleanup():
    """Called when plugin is unloaded (optional)"""
    pass
'''
        
        example_file = self.plugins_dir / "example.py"
        if not example_file.exists():
            with open(example_file, 'w', encoding='utf-8') as f:
                f.write(example_plugin)
    
    def scan_plugins(self):
        """Scan plugins directory and return list of available plugins"""
        plugins = []
        
        if not self.plugins_dir.exists():
            return plugins
        
        for file_path in self.plugins_dir.glob("*.py"):
            if file_path.name.startswith('_'):
                continue
            
            try:
                # Load module to get plugin info
                spec = importlib.util.spec_from_file_location(file_path.stem, file_path)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    
                    plugin_name = getattr(module, 'PLUGIN_NAME', file_path.stem)
                    plugin_version = getattr(module, 'PLUGIN_VERSION', 'Unknown')
                    plugin_desc = getattr(module, 'PLUGIN_DESCRIPTION', 'No description')
                    
                    plugins.append({
                        'name': plugin_name,
                        'version': plugin_version,
                        'description': plugin_desc,
                        'file': file_path,
                        'module_name': file_path.stem
                    })
            except Exception as e:
                print(f"Error scanning plugin {file_path.name}: {e}")
        
        return sorted(plugins, key=lambda x: x['name'])
    
    def load_plugin(self, plugin_file):
        """Load a plugin module"""
        try:
            # Check if already loaded
            if str(plugin_file) in self.loaded_plugins:
                return self.loaded_plugins[str(plugin_file)]
            
            # Load the plugin module
            spec = importlib.util.spec_from_file_location(plugin_file.stem, plugin_file)
            if not spec or not spec.loader:
                raise Exception("Could not load plugin spec")
            
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Verify plugin has required components
            if not hasattr(module, 'get_widget'):
                raise Exception("Plugin missing get_widget() function")
            
            # Initialize plugin if it has initialize function
            if hasattr(module, 'initialize') and self.plugin_api:
                module.initialize(self.plugin_api)
            
            self.loaded_plugins[str(plugin_file)] = module
            return module
            
        except Exception as e:
            raise Exception(f"Failed to load plugin: {str(e)}")
    
    def unload_plugin(self, plugin_file):
        """Unload a plugin and call its cleanup"""
        plugin_key = str(plugin_file)
        if plugin_key in self.loaded_plugins:
            module = self.loaded_plugins[plugin_key]
            try:
                if hasattr(module, 'cleanup'):
                    module.cleanup()
            except Exception as e:
                print(f"Error during plugin cleanup: {e}")
            
            del self.loaded_plugins[plugin_key]
            return True
        return False




# import importlib.util
# from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel

# # =====================================================================
# class PluginWidget(QWidget):
    # """Base wrapper for plugin widgets loaded in tabs"""
    
    # def __init__(self, plugin_module, parent=None):
        # super().__init__(parent)
        # self.plugin_module = plugin_module
        # self.plugin_name = getattr(plugin_module, 'PLUGIN_NAME', 'Unknown Plugin')
        
        # layout = QVBoxLayout(self)
        # layout.setContentsMargins(0, 0, 0, 0)
        
        # try:
            # # Try to get the main widget from plugin
            # if hasattr(plugin_module, 'get_widget'):
                # plugin_widget = plugin_module.get_widget(parent=self)
                # layout.addWidget(plugin_widget)
            # else:
                # error_label = QLabel(f"⚠️ Plugin '{self.plugin_name}' has no get_widget() function")
                # error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                # error_label.setStyleSheet("color: #E74C3C; font-size: 14px;")
                # layout.addWidget(error_label)
        # except Exception as e:
            # error_label = QLabel(f"⚠️ Error loading plugin:\n{str(e)}")
            # error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            # error_label.setStyleSheet("color: #E74C3C; font-size: 14px;")
            # layout.addWidget(error_label)



# # =====================================================================
# class PluginManager:
    # """Manages loading and tracking of IDE plugins"""
    
    # def __init__(self, workspace_path):
        # self.workspace_path = workspace_path
        # self.plugins_dir = workspace_path / "ide/plugins"
        # self.loaded_plugins = {}
        
        # # Create plugins directory if it doesn't exist
        # if not self.plugins_dir.exists():
            # self.plugins_dir.mkdir(parents=True)
            # self.create_example_plugin()
    
    # def create_example_plugin(self):
        # """Create an example plugin to show structure"""
        # example_plugin = '''"""
# Example Plugin for Workspace IDE

# Plugin structure:
# - PLUGIN_NAME: Display name for the plugin
# - PLUGIN_VERSION: Plugin version
# - get_widget(parent): Returns a QWidget to display in tab
# """

# from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QTextEdit
# from PyQt6.QtCore import Qt

# PLUGIN_NAME = "Example Plugin"
# PLUGIN_VERSION = "1.0.0"


# def get_widget(parent=None):
    # """
    # This function must return a QWidget that will be displayed in the editor tab.
    
    # Args:
        # parent: Parent widget (usually None or the tab widget)
    
    # Returns:
        # QWidget: Your plugin's main widget
    # """
    # widget = QWidget(parent)
    # layout = QVBoxLayout(widget)
    
    # # Add your plugin UI here
    # title = QLabel("🔌 Example Plugin")
    # title.setStyleSheet("font-size: 18px; font-weight: bold; color: #4A9EFF;")
    # title.setAlignment(Qt.AlignmentFlag.AlignCenter)
    # layout.addWidget(title)
    
    # info = QLabel(
        # "This is an example plugin.\\n\\n"
        # "Create your own plugin by copying this file and modifying it.\\n"
        # "Your plugin must have:\\n"
        # "  • PLUGIN_NAME constant\\n"
        # "  • get_widget() function that returns a QWidget"
    # )
    # info.setStyleSheet("color: #CCC; padding: 20px;")
    # info.setAlignment(Qt.AlignmentFlag.AlignCenter)
    # layout.addWidget(info)
    
    # # Example interactive element
    # button = QPushButton("Click Me!")
    # button.clicked.connect(lambda: text_area.append("Button clicked!\\n"))
    # layout.addWidget(button)
    
    # text_area = QTextEdit()
    # text_area.setPlaceholderText("Plugin output will appear here...")
    # text_area.setStyleSheet("background: #1E1E1E; color: #CCC; border: 1px solid #555;")
    # layout.addWidget(text_area)
    
    # return widget


# # Optional: Add cleanup function if needed
# def cleanup():
    # """Called when plugin is unloaded (optional)"""
    # pass
# '''
        
        # # example_file = self.plugins_dir / "example_plugin.py"
        # example_file = self.plugins_dir / "example.py"
        # if not example_file.exists():
            # with open(example_file, 'w', encoding='utf-8') as f:
                # f.write(example_plugin)
    
    # def scan_plugins(self):
        # """Scan plugins directory and return list of available plugins"""
        # plugins = []
        
        # if not self.plugins_dir.exists():
            # return plugins
        
        # for file_path in self.plugins_dir.glob("*.py"):
            # if file_path.name.startswith('_'):
                # continue
            
            # try:
                # # Load module to get plugin info
                # spec = importlib.util.spec_from_file_location(file_path.stem, file_path)
                # if spec and spec.loader:
                    # module = importlib.util.module_from_spec(spec)
                    # spec.loader.exec_module(module)
                    
                    # plugin_name = getattr(module, 'PLUGIN_NAME', file_path.stem)
                    # plugin_version = getattr(module, 'PLUGIN_VERSION', 'Unknown')
                    
                    # plugins.append({
                        # 'name': plugin_name,
                        # 'version': plugin_version,
                        # 'file': file_path,
                        # 'module_name': file_path.stem
                    # })
            # except Exception as e:
                # print(f"Error scanning plugin {file_path.name}: {e}")
        
        # return sorted(plugins, key=lambda x: x['name'])
    
    # def load_plugin(self, plugin_file):
        # """Load a plugin module"""
        # try:
            # # Check if already loaded
            # if str(plugin_file) in self.loaded_plugins:
                # return self.loaded_plugins[str(plugin_file)]
            
            # # Load the plugin module
            # spec = importlib.util.spec_from_file_location(plugin_file.stem, plugin_file)
            # if not spec or not spec.loader:
                # raise Exception("Could not load plugin spec")
            
            # module = importlib.util.module_from_spec(spec)
            # spec.loader.exec_module(module)
            
            # # Verify plugin has required components
            # if not hasattr(module, 'get_widget'):
                # raise Exception("Plugin missing get_widget() function")
            
            # self.loaded_plugins[str(plugin_file)] = module
            # return module
            
        # except Exception as e:
            # raise Exception(f"Failed to load plugin: {str(e)}")

