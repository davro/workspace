import importlib.util
import inspect
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt

# =====================================================================
class PluginWidget(QWidget):
    """
    Wrapper widget for plugin UI
    
    Receives a plugin instance and calls its get_widget() method
    """
    
    def __init__(self, plugin_instance, parent=None):
        """
        Args:
            plugin_instance: Plugin class instance (must have get_widget() method)
        """
        super().__init__(parent)
        self.plugin = plugin_instance
        self.plugin_name = getattr(plugin_instance.__class__, 'PLUGIN_NAME', 
                                   plugin_instance.__class__.__name__)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        try:
            # Get widget from plugin instance
            plugin_widget = plugin_instance.get_widget(parent=self)
            layout.addWidget(plugin_widget)
            
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
        """Cleanup is handled by plugin manager - this is just for compatibility"""
        pass


# =====================================================================
class PluginManager:
    """
    Manages loading and tracking of IDE plugins
    
    Supports ONLY class-based plugins with this structure:
        class MyPlugin:
            PLUGIN_NAME = "..."
            def __init__(self, api): ...
            def initialize(self): ...
            def get_widget(self, parent): ...
            def cleanup(self): ...
    """
    
    def __init__(self, workspace_plugin_path, plugin_api=None):
        self.plugins_dir = workspace_plugin_path
        self.plugin_instances = {}  # Maps plugin_key -> plugin instance
        self.plugin_api = plugin_api
        
        # Create plugins directory if it doesn't exist
        if not self.plugins_dir.exists():
            self.plugins_dir.mkdir(parents=True)
    
    def set_plugin_api(self, plugin_api):
        """Set the plugin API after initialization"""
        self.plugin_api = plugin_api
    
    def scan_plugins(self):
        """
        Scan plugins directory and return list of available plugins
        
        Returns:
            list: List of plugin metadata dicts
        """
        plugins = []
        
        if not self.plugins_dir.exists():
            return plugins

        for file_path in self.plugins_dir.glob("*.py"):
            # Skip non-files and private files
            if not file_path.is_file(): 
                continue
            if file_path.name.startswith('_'):
                continue

            try:
                # Load module
                spec = importlib.util.spec_from_file_location(file_path.stem, file_path)
                if not spec or not spec.loader:
                    continue
                
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                # Find plugin class (class with PLUGIN_NAME attribute)
                plugin_class = self._find_plugin_class(module)
                
                if not plugin_class:
                    print(f"[PluginManager] Skipping {file_path.name} - no plugin class found")
                    continue
                
                # Extract metadata from class
                plugin_name           = getattr(plugin_class, 'PLUGIN_NAME', file_path.stem)
                plugin_version        = getattr(plugin_class, 'PLUGIN_VERSION', '1.0.0')
                plugin_desc           = getattr(plugin_class, 'PLUGIN_DESCRIPTION', 'No description')
                plugin_run_on_startup = getattr(plugin_class, 'PLUGIN_RUN_ON_STARTUP', False)
                plugin_has_ui         = getattr(plugin_class, 'PLUGIN_HAS_UI', True)
                plugin_icon           = getattr(plugin_class, 'PLUGIN_ICON', '🔌')
                
                # Auto-start if requested
                if plugin_run_on_startup:
                    self.load_plugin(file_path)
                
                # Add to plugins list
                plugin = {
                    'name':           plugin_name,
                    'version':        plugin_version,
                    'description':    plugin_desc,
                    'run_on_startup': plugin_run_on_startup,
                    'has_ui':         plugin_has_ui,
                    'icon':           plugin_icon,
                    'file':           file_path,
                    'module_name':    file_path.stem,
                    'class':          plugin_class
                }
                
                plugins.append(plugin)

            except Exception as e:
                import traceback
                print(f"[PluginManager] Error scanning {file_path.name}:")
                traceback.print_exc()
        
        return sorted(plugins, key=lambda x: x['name'])
    
    def _find_plugin_class(self, module):
        """
        Find the plugin class in a module
        
        Looks for a class with PLUGIN_NAME attribute
        
        Args:
            module: Python module to search
        
        Returns:
            class: Plugin class or None if not found
        """
        for name, obj in inspect.getmembers(module):
            if inspect.isclass(obj) and hasattr(obj, 'PLUGIN_NAME'):
                return obj
        
        return None
    
    def load_plugin(self, plugin_file):
        """
        Load a plugin and return its instance
        
        Args:
            plugin_file: Path to plugin file
        
        Returns:
            Plugin instance
        """
        try:
            plugin_key = str(plugin_file)
            
            # Return if already loaded
            if plugin_key in self.plugin_instances:
                return self.plugin_instances[plugin_key]
            
            # Load the module
            spec = importlib.util.spec_from_file_location(plugin_file.stem, plugin_file)
            if not spec or not spec.loader:
                raise Exception("Could not load plugin spec")
            
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Find plugin class
            plugin_class = self._find_plugin_class(module)
            
            print("################################################################################")
            print(f"[PluginManager] Auto-loading: {plugin_file}")

            if not plugin_class:
                raise Exception(f"No plugin class found in {plugin_file.name}")
            
            print(f"[PluginManager] Loading: {plugin_class.PLUGIN_NAME}")
            
            # Create instance
            plugin_instance = plugin_class(self.plugin_api)
            
            # Initialize
            plugin_instance.initialize()
            
            # Store instance
            self.plugin_instances[plugin_key] = plugin_instance
            
            return plugin_instance
            
        except Exception as e:
            import traceback
            print(f"[PluginManager] Failed to load {plugin_file.name}:")
            traceback.print_exc()
            raise Exception(f"Failed to load plugin: {str(e)}")
    
    def unload_plugin(self, plugin_file):
        """
        Unload a plugin and call its cleanup
        
        Args:
            plugin_file: Path to plugin file
        
        Returns:
            bool: True if unloaded successfully
        """
        plugin_key = str(plugin_file)
        
        if plugin_key not in self.plugin_instances:
            return False
        
        plugin_instance = self.plugin_instances[plugin_key]
        
        try:
            print(f"[PluginManager] Unloading: {plugin_instance.PLUGIN_NAME}")
            plugin_instance.cleanup()
        except Exception as e:
            print(f"[PluginManager] Error during cleanup:")
            import traceback
            traceback.print_exc()
        
        del self.plugin_instances[plugin_key]
        print(f"[PluginManager] Unloaded: {plugin_file.name}")
        return True
    
    def get_plugin_instance(self, plugin_file):
        """
        Get a loaded plugin instance
        
        Args:
            plugin_file: Path to plugin file
        
        Returns:
            Plugin instance or None if not loaded
        """
        plugin_key = str(plugin_file)
        return self.plugin_instances.get(plugin_key)
