"""
Comprehensive Example Plugin for Workspace IDE

This plugin demonstrates ALL available features and hooks in the Plugin API:

✓ Basic plugin structure (PLUGIN_NAME, VERSION, etc.)
✓ Widget creation with get_widget()
✓ Plugin initialization with initialize()
✓ File tree decorators (icons, colors, badges)
✓ Gutter markers in editors
✓ Status bar widgets
✓ Context menu extensions (file tree & tabs)
✓ File event hooks (save, open, close, modify)
✓ Editor event hooks (focus, cursor movement)
✓ IDE lifecycle hooks (project/workspace open)
✓ Cache management
✓ Cleanup on unload

Use this as a reference when building your own plugins!
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QTextEdit, QGroupBox, QCheckBox, QSpinBox, QListWidget,
    QLineEdit, QPushButton as QBtn, QScrollArea
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont
from datetime import datetime
from pathlib import Path

# ============================================================================
# Plugin Metadata
# ============================================================================

PLUGIN_NAME = "Comprehensive Feature Demo"
PLUGIN_VERSION = "2.1.0"
PLUGIN_DESCRIPTION = "Demonstrates all Plugin API features and hooks"

# ============================================================================
# Global State
# ============================================================================

_api = None  # Plugin API instance
_widget = None  # Main widget instance
_hooks_registered = []  # Track registered hooks for cleanup


# ============================================================================
# Plugin Lifecycle Functions
# ============================================================================

def initialize(api):
    """
    Called when plugin is loaded
    
    This is where you should:
    - Store API reference
    - Register hooks
    - Set up initial state
    - Initialize any background processes
    """
    global _api, _hooks_registered
    _api = api
    _hooks_registered = []
    
    log("🚀 Plugin initializing...")
    
    # Register all demonstration hooks
    register_file_tree_decorators()
    register_gutter_decorators()
    register_status_bar_widgets()
    register_context_menus()
    register_file_events()
    register_editor_events()
    register_ide_events()
    
    log("✅ Plugin initialized successfully!")
    api.show_status_message("Comprehensive Demo Plugin loaded!", 3000)


def cleanup():
    """
    Called when plugin is unloaded
    
    Clean up resources:
    - Unregister hooks
    - Close connections
    - Save state
    - Clear caches
    """
    global _api, _hooks_registered
    
    if _api:
        log("🧹 Cleaning up plugin...")
        
        # Unregister all hooks
        for hook_name, callback in _hooks_registered:
            _api.unregister_hook(hook_name, callback)
        
        _hooks_registered.clear()
        _api.clear_cache()
        log("✅ Cleanup complete!")


def get_widget(parent=None):
    """
    Create and return the main plugin widget
    
    This widget will be displayed in a tab when the plugin is opened
    """
    global _widget
    _widget = ComprehensivePluginWidget(parent)
    return _widget


# ============================================================================
# Hook Registration Functions
# ============================================================================

def register_file_tree_decorators():
    """Register file tree decoration hooks"""
    
    def python_file_decorator(file_path):
        """Add Python icon to .py files"""
        from pathlib import Path
        path = Path(file_path)
        
        if path.suffix == '.py':
            from ide.core.PluginAPI import FileTreeDecoration
            decoration = FileTreeDecoration(file_path)
            decoration.prefix_icon = "🐍"
            decoration.text_color = "#4A9EFF"
            
            # Make __init__.py files bold
            if path.name == '__init__.py':
                decoration.bold = True
                decoration.tooltip = "Python package initialization file"
            
            return decoration
        return None
    
    def modified_file_decorator(file_path):
        """Add indicator for recently modified files"""
        from pathlib import Path
        import time
        
        path = Path(file_path)
        if path.exists():
            modified_time = path.stat().st_mtime
            age_hours = (time.time() - modified_time) / 3600
            
            if age_hours < 24:  # Modified in last 24 hours
                from ide.core.PluginAPI import FileTreeDecoration
                decoration = FileTreeDecoration(file_path)
                decoration.suffix_icon = "✨"
                decoration.tooltip = f"Modified {age_hours:.1f} hours ago"
                return decoration
        return None
    
    _register_hook('file_tree_decorator', python_file_decorator)
    _register_hook('file_tree_decorator', modified_file_decorator)
    log("📁 Registered file tree decorators")


def register_gutter_decorators():
    """Register editor gutter marker hooks"""
    
    def line_length_marker(editor, line_num):
        """Add markers for long lines"""
        try:
            text = editor.document().findBlockByLineNumber(line_num - 1).text()
            if len(text) > 100:
                from ide.core.PluginAPI import GutterMarker
                marker = GutterMarker(line_num)
                marker.icon = "⚠️"
                marker.color = "#FFA500"
                marker.tooltip = f"Line too long: {len(text)} characters"
                return marker
        except:
            pass
        return None
    
    _register_hook('gutter_decorator', line_length_marker)
    log("📏 Registered gutter decorators")


def register_status_bar_widgets():
    """Register status bar widgets"""
    
    def create_status_widget():
        """Create a status widget showing plugin info"""
        from PyQt6.QtWidgets import QLabel
        
        label = QLabel("🔌 Demo Active")
        label.setStyleSheet("""
            QLabel {
                color: #4A9EFF;
                padding: 2px 8px;
                background: #2D2D2D;
                border-radius: 3px;
                font-size: 11px;
            }
        """)
        
        # Update every 5 seconds
        def update_label():
            time_str = datetime.now().strftime("%H:%M:%S")
            label.setText(f"🔌 Demo | {time_str}")
        
        timer = QTimer()
        timer.timeout.connect(update_label)
        timer.start(5000)
        
        return label
    
    _register_hook('status_bar_widget', create_status_widget)
    log("📊 Registered status bar widgets")


def register_context_menus():
    """Register context menu extensions"""
    
    def add_file_menu_items(menu, file_path):
        """Add custom items to file context menu"""
        from PyQt6.QtWidgets import QMenu
        from PyQt6.QtGui import QAction
        
        # Add separator
        menu.addSeparator()
        
        # Add custom action
        action = QAction("🔍 Analyze with Demo Plugin", menu)
        action.triggered.connect(lambda: analyze_file(file_path))
        menu.addAction(action)
    
    def add_tab_menu_items(menu, editor):
        """Add custom items to tab context menu"""
        from PyQt6.QtGui import QAction
        
        action = QAction("📊 Show Editor Stats", menu)
        action.triggered.connect(lambda: show_editor_stats(editor))
        menu.addAction(action)
    
    _register_hook('context_menu_file', add_file_menu_items)
    _register_hook('context_menu_tab', add_tab_menu_items)
    log("📋 Registered context menu items")


def register_file_events():
    """Register file event hooks"""
    
    def on_save(file_path):
        """Called when a file is saved"""
        log(f"💾 File saved: {Path(file_path).name}")
        _update_event_list(f"Saved: {Path(file_path).name}")
    
    def on_open(file_path):
        """Called when a file is opened"""
        log(f"📂 File opened: {Path(file_path).name}")
        _update_event_list(f"Opened: {Path(file_path).name}")
    
    def on_close(file_path):
        """Called when a file is closed"""
        log(f"🗙 File closed: {Path(file_path).name}")
        _update_event_list(f"Closed: {Path(file_path).name}")
    
    def on_modify(file_path):
        """Called when a file is modified"""
        # Be careful with this one - it fires often!
        pass
    
    _register_hook('on_file_saved', on_save)
    _register_hook('on_file_opened', on_open)
    _register_hook('on_file_closed', on_close)
    _register_hook('on_file_modified', on_modify)
    log("📄 Registered file event hooks")


def register_editor_events():
    """Register editor event hooks"""
    
    def on_focus(editor):
        """Called when editor receives focus"""
        if hasattr(editor, 'file_path') and editor.file_path:
            log(f"🎯 Focus: {Path(editor.file_path).name}")
    
    def on_cursor_move(editor, line, column):
        """Called when cursor moves"""
        # Update cursor position display
        if _widget:
            _widget.update_cursor_position(line, column)
    
    _register_hook('on_editor_focus', on_focus)
    _register_hook('on_cursor_moved', on_cursor_move)
    log("✏️ Registered editor event hooks")


def register_ide_events():
    """Register IDE lifecycle event hooks"""
    
    def on_workspace_open():
        """Called when IDE starts"""
        log("🏢 Workspace opened!")
        if _api:
            workspace = _api.get_workspace_path()
            log(f"   Path: {workspace}")
    
    def on_project_open():
        """Called when project is activated"""
        log("📁 Project opened!")
    
    _register_hook('on_workspace_opened', on_workspace_open)
    _register_hook('on_project_opened', on_project_open)
    log("🌐 Registered IDE event hooks")


# ============================================================================
# Helper Functions
# ============================================================================

def _register_hook(hook_name, callback):
    """Register hook and track for cleanup"""
    global _api, _hooks_registered
    if _api:
        _api.register_hook(hook_name, callback)
        _hooks_registered.append((hook_name, callback))


def log(message):
    """Add message to log"""
    global _widget
    if _widget:
        _widget.add_log(message)
    print(f"[ComprehensiveDemo] {message}")


def _update_event_list(event):
    """Update event list in widget"""
    global _widget
    if _widget:
        _widget.add_event(event)


def analyze_file(file_path):
    """Example: Analyze file from context menu"""
    if _api:
        content = _api.get_file_content(file_path)
        if content:
            lines = len(content.split('\n'))
            chars = len(content)
            words = len(content.split())
            log(f"📊 Analysis of {Path(file_path).name}:")
            log(f"   Lines: {lines:,}, Words: {words:,}, Characters: {chars:,}")
            _api.show_status_message(
                f"Analyzed: {lines:,} lines, {words:,} words, {chars:,} chars", 
                4000
            )


def show_editor_stats(editor):
    """Show statistics about current editor"""
    if hasattr(editor, 'toPlainText'):
        text = editor.toPlainText()
        lines = len(text.split('\n'))
        words = len(text.split())
        chars = len(text)
        
        log(f"📊 Editor Statistics:")
        log(f"   Lines: {lines:,}")
        log(f"   Words: {words:,}")
        log(f"   Characters: {chars:,}")


# ============================================================================
# Main Plugin Widget
# ============================================================================

class ComprehensivePluginWidget(QWidget):
    """Main widget demonstrating all plugin features"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
    
    def init_ui(self):
        """Initialize user interface"""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        # Header
        header = QLabel("🔌 Comprehensive Plugin Feature Demo")
        header.setStyleSheet("""
            font-size: 20px;
            font-weight: bold;
            color: #4A9EFF;
            padding: 10px;
        """)
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)
        
        # Description
        desc = QLabel(
            "This plugin demonstrates ALL available features in the Plugin API.\n"
            "Interact with the IDE to see hooks in action!"
        )
        desc.setStyleSheet("color: #AAA; padding: 5px;")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(desc)
        
        # Main content
        content_layout = QHBoxLayout()
        
        # Left column - Controls
        left_panel = self.create_controls_panel()
        content_layout.addWidget(left_panel, 1)
        
        # Right column - Event log
        right_panel = self.create_log_panel()
        content_layout.addWidget(right_panel, 1)
        
        layout.addLayout(content_layout)
        
        # Bottom - Recent events
        events_panel = self.create_events_panel()
        layout.addWidget(events_panel)
    
    def create_controls_panel(self):
        """Create controls panel"""
        # Create scroll area for controls
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMaximumWidth(450)
        
        container = QWidget()
        main_layout = QVBoxLayout(container)
        main_layout.setSpacing(5)
        
        # File operations group
        file_group = QGroupBox("📁 File Operations")
        file_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #555;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                color: #4A9EFF;
            }
        """)
        
        file_layout = QVBoxLayout()
        
        btn_current = QPushButton("📄 Show Current File Info")
        btn_current.clicked.connect(self.test_current_file)
        file_layout.addWidget(btn_current)
        
        btn_files = QPushButton("📋 List All Open Files")
        btn_files.clicked.connect(self.test_list_files)
        file_layout.addWidget(btn_files)
        
        btn_editors = QPushButton("👁️ Show All Editors")
        btn_editors.clicked.connect(self.test_list_editors)
        file_layout.addWidget(btn_editors)
        
        file_group.setLayout(file_layout)
        main_layout.addWidget(file_group)
        
        # UI operations group
        ui_group = QGroupBox("🎨 UI Operations")
        ui_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #555;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                color: #4A9EFF;
            }
        """)
        
        ui_layout = QVBoxLayout()
        
        btn_refresh_tree = QPushButton("🔄 Refresh File Tree")
        btn_refresh_tree.clicked.connect(self.test_refresh_tree)
        ui_layout.addWidget(btn_refresh_tree)
        
        btn_refresh_editor = QPushButton("🔄 Refresh Current Editor")
        btn_refresh_editor.clicked.connect(self.test_refresh_editor)
        ui_layout.addWidget(btn_refresh_editor)
        
        btn_refresh_all = QPushButton("🔄 Refresh All Editors")
        btn_refresh_all.clicked.connect(self.test_refresh_all)
        ui_layout.addWidget(btn_refresh_all)
        
        ui_group.setLayout(ui_layout)
        main_layout.addWidget(ui_group)
        
        # Status message group
        status_group = QGroupBox("💬 Status Messages")
        status_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #555;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                color: #4A9EFF;
            }
        """)
        
        status_layout = QVBoxLayout()
        
        self.status_input = QLineEdit()
        self.status_input.setPlaceholderText("Enter status message...")
        self.status_input.setText("Hello from plugin!")
        status_layout.addWidget(self.status_input)
        
        btn_status = QPushButton("💬 Show Status Message")
        btn_status.clicked.connect(self.test_status_message)
        status_layout.addWidget(btn_status)
        
        status_group.setLayout(status_layout)
        main_layout.addWidget(status_group)
        
        # Cache operations group
        cache_group = QGroupBox("💾 Cache Operations")
        cache_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #555;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                color: #4A9EFF;
            }
        """)
        
        cache_layout = QVBoxLayout()
        
        cache_layout.addWidget(QLabel("Cache Key:"))
        self.cache_key = QLineEdit()
        self.cache_key.setPlaceholderText("my_key")
        cache_layout.addWidget(self.cache_key)
        
        cache_layout.addWidget(QLabel("Cache Value:"))
        self.cache_value = QLineEdit()
        self.cache_value.setPlaceholderText("my_value")
        cache_layout.addWidget(self.cache_value)
        
        cache_btn_layout = QHBoxLayout()
        btn_cache_set = QPushButton("💾 Set")
        btn_cache_set.clicked.connect(self.test_cache_set)
        cache_btn_layout.addWidget(btn_cache_set)
        
        btn_cache_get = QPushButton("📖 Get")
        btn_cache_get.clicked.connect(self.test_cache_get)
        cache_btn_layout.addWidget(btn_cache_get)
        
        cache_layout.addLayout(cache_btn_layout)
        
        cache_group.setLayout(cache_layout)
        main_layout.addWidget(cache_group)
        
        # Info displays
        info_group = QGroupBox("ℹ️ Live Info")
        info_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #555;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                color: #4A9EFF;
            }
        """)
        
        info_layout = QVBoxLayout()
        
        # Cursor position display
        self.cursor_label = QLabel("Cursor: Line 0, Col 0")
        self.cursor_label.setStyleSheet("""
            background: #2D2D2D;
            padding: 5px;
            border-radius: 3px;
            color: #4A9EFF;
        """)
        info_layout.addWidget(self.cursor_label)
        
        # Workspace path
        if _api:
            workspace = _api.get_workspace_path()
            workspace_label = QLabel(f"Workspace:\n{workspace}")
            workspace_label.setWordWrap(True)
            workspace_label.setStyleSheet("""
                background: #2D2D2D;
                padding: 5px;
                border-radius: 3px;
                color: #AAA;
                font-size: 10px;
            """)
            info_layout.addWidget(workspace_label)
        
        info_group.setLayout(info_layout)
        main_layout.addWidget(info_group)
        
        main_layout.addStretch()
        
        scroll.setWidget(container)
        return scroll
    
    def create_log_panel(self):
        """Create log panel"""
        group = QGroupBox("📝 Event Log")
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #555;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                color: #4A9EFF;
            }
        """)
        
        layout = QVBoxLayout()
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("""
            background: #1E1E1E;
            color: #CCC;
            border: 1px solid #555;
            font-family: 'Courier New', monospace;
            font-size: 11px;
        """)
        layout.addWidget(self.log_text)
        
        btn_clear = QPushButton("🗑️ Clear Log")
        btn_clear.clicked.connect(lambda: self.log_text.clear())
        layout.addWidget(btn_clear)
        
        group.setLayout(layout)
        return group
    
    def create_events_panel(self):
        """Create recent events panel"""
        group = QGroupBox("⚡ Recent IDE Events (via hooks)")
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #555;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                color: #4A9EFF;
            }
        """)
        
        layout = QVBoxLayout()
        
        self.event_list = QListWidget()
        self.event_list.setStyleSheet("""
            background: #1E1E1E;
            color: #CCC;
            border: 1px solid #555;
        """)
        self.event_list.setMaximumHeight(100)
        layout.addWidget(self.event_list)
        
        group.setLayout(layout)
        return group
    
    # ========================================================================
    # Test Functions
    # ========================================================================
    
    def test_current_file(self):
        """Test showing current file info"""
        if _api:
            editor = _api.get_current_editor()
            
            # Check if it's a code editor (not a plugin or other widget)
            if not editor or not hasattr(editor, 'file_path'):
                self.add_log("⚠️ Current tab is not a code editor")
                return
            
            if editor.file_path:
                file_path = Path(editor.file_path)
                text = editor.toPlainText() if hasattr(editor, 'toPlainText') else ""
                lines = len(text.split('\n')) if text else 0
                chars = len(text)
                
                self.add_log(f"📄 Current File: {file_path.name}")
                self.add_log(f"   Path: {file_path}")
                self.add_log(f"   Lines: {lines:,}")
                self.add_log(f"   Characters: {chars:,}")
                if file_path.exists():
                    self.add_log(f"   Size: {file_path.stat().st_size:,} bytes")
            else:
                self.add_log("⚠️ Current editor has no file open (untitled)")
    
    def test_list_files(self):
        """Test listing all open files"""
        if _api:
            files = _api.get_all_open_files()
            self.add_log(f"📋 Open files: {len(files)}")
            if files:
                for i, f in enumerate(files, 1):
                    self.add_log(f"   {i}. {Path(f).name}")
                    if i >= 10:
                        remaining = len(files) - i
                        if remaining > 0:
                            self.add_log(f"   ... and {remaining} more")
                        break
            else:
                self.add_log("   (No files open)")
    
    def test_list_editors(self):
        """Test listing all editor instances"""
        if _api:
            editors = _api.get_all_editors()
            self.add_log(f"👁️ Open tabs: {len(editors)}")
            
            code_editors = 0
            plugins = 0
            other = 0
            
            for i, editor in enumerate(editors, 1):
                if hasattr(editor, 'file_path') and editor.file_path:
                    self.add_log(f"   {i}. 📄 {Path(editor.file_path).name}")
                    code_editors += 1
                elif hasattr(editor, 'plugin_name'):
                    self.add_log(f"   {i}. 🔌 {editor.plugin_name}")
                    plugins += 1
                else:
                    self.add_log(f"   {i}. ❓ {type(editor).__name__}")
                    other += 1
                
                if i >= 10:
                    remaining = len(editors) - i
                    if remaining > 0:
                        self.add_log(f"   ... and {remaining} more")
                    break
            
            self.add_log(f"   Summary: {code_editors} files, {plugins} plugins, {other} other")
    
    def test_refresh_tree(self):
        """Test refreshing file tree"""
        if _api:
            _api.refresh_file_tree()
            self.add_log("🔄 File tree refreshed")
    
    def test_refresh_editor(self):
        """Test refreshing current editor"""
        if _api:
            editor = _api.get_current_editor()
            if editor and hasattr(editor, 'viewport'):
                _api.refresh_current_editor()
                self.add_log("🔄 Current editor refreshed")
            else:
                self.add_log("⚠️ Current tab is not a code editor (might be a plugin tab)")
    
    def test_refresh_all(self):
        """Test refreshing all editors"""
        if _api:
            editors = _api.get_all_editors()
            code_editors = [e for e in editors if hasattr(e, 'viewport')]
            
            if code_editors:
                _api.refresh_all_editors()
                self.add_log(f"🔄 Refreshed {len(code_editors)} code editor(s)")
            else:
                self.add_log("⚠️ No code editors open to refresh")
    
    def test_status_message(self):
        """Test showing status message"""
        if _api:
            msg = self.status_input.text() or "Hello from plugin!"
            _api.show_status_message(msg, 3000)
            self.add_log(f"💬 Status: {msg}")
    
    def test_cache_set(self):
        """Test setting cache value"""
        if _api:
            key = self.cache_key.text() or "test_key"
            value = self.cache_value.text() or "test_value"
            _api.set_cache(key, value)
            self.add_log(f"💾 Cache set: {key} = {value}")
    
    def test_cache_get(self):
        """Test getting cache value"""
        if _api:
            key = self.cache_key.text() or "test_key"
            value = _api.get_cache(key, "Not found")
            self.add_log(f"📖 Cache get: {key} = {value}")
            self.cache_value.setText(str(value))
    
    # ========================================================================
    # UI Update Functions
    # ========================================================================
    
    def add_log(self, message):
        """Add message to log"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")
        
        # Auto-scroll to bottom
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def add_event(self, event):
        """Add event to recent events list"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.event_list.insertItem(0, f"[{timestamp}] {event}")
        
        # Keep only last 20 events
        while self.event_list.count() > 20:
            self.event_list.takeItem(self.event_list.count() - 1)
    
    def update_cursor_position(self, line, column):
        """Update cursor position display"""
        self.cursor_label.setText(f"Cursor: Line {line}, Col {column}")







# """
# Comprehensive Example Plugin for Workspace IDE

# This plugin demonstrates ALL available features and hooks in the Plugin API:

# ✓ Basic plugin structure (PLUGIN_NAME, VERSION, etc.)
# ✓ Widget creation with get_widget()
# ✓ Plugin initialization with initialize()
# ✓ File tree decorators (icons, colors, badges)
# ✓ Gutter markers in editors
# ✓ Status bar widgets
# ✓ Context menu extensions (file tree & tabs)
# ✓ File event hooks (save, open, close, modify)
# ✓ Editor event hooks (focus, cursor movement)
# ✓ IDE lifecycle hooks (project/workspace open)
# ✓ Cache management
# ✓ Cleanup on unload

# Use this as a reference when building your own plugins!
# """

# from PyQt6.QtWidgets import (
    # QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    # QTextEdit, QGroupBox, QCheckBox, QSpinBox, QListWidget,
    # QLineEdit, QPushButton as QBtn, QScrollArea
# )
# from PyQt6.QtCore import Qt, QTimer
# from PyQt6.QtGui import QFont
# from datetime import datetime
# from pathlib import Path

# # ============================================================================
# # Plugin Metadata
# # ============================================================================

# PLUGIN_NAME = "Comprehensive Plugin"
# PLUGIN_VERSION = "2.1.0"
# PLUGIN_DESCRIPTION = "Demonstrates all Plugin API features and hooks"

# # ============================================================================
# # Global State
# # ============================================================================

# _api = None  # Plugin API instance
# _widget = None  # Main widget instance
# _hooks_registered = []  # Track registered hooks for cleanup


# # ============================================================================
# # Plugin Lifecycle Functions
# # ============================================================================

# def initialize(api):
    # """
    # Called when plugin is loaded
    
    # This is where you should:
    # - Store API reference
    # - Register hooks
    # - Set up initial state
    # - Initialize any background processes
    # """
    # global _api, _hooks_registered
    # _api = api
    # _hooks_registered = []
    
    # log("🚀 Plugin initializing...")
    
    # # Register all demonstration hooks
    # register_file_tree_decorators()
    # register_gutter_decorators()
    # register_status_bar_widgets()
    # register_context_menus()
    # register_file_events()
    # register_editor_events()
    # register_ide_events()
    
    # log("✅ Plugin initialized successfully!")
    # api.show_status_message("Comprehensive Demo Plugin loaded!", 3000)


# def cleanup():
    # """
    # Called when plugin is unloaded
    
    # Clean up resources:
    # - Unregister hooks
    # - Close connections
    # - Save state
    # - Clear caches
    # """
    # global _api, _hooks_registered
    
    # if _api:
        # log("🧹 Cleaning up plugin...")
        
        # # Unregister all hooks
        # for hook_name, callback in _hooks_registered:
            # _api.unregister_hook(hook_name, callback)
        
        # _hooks_registered.clear()
        # _api.clear_cache()
        # log("✅ Cleanup complete!")


# def get_widget(parent=None):
    # """
    # Create and return the main plugin widget
    
    # This widget will be displayed in a tab when the plugin is opened
    # """
    # global _widget
    # _widget = ComprehensivePluginWidget(parent)
    # return _widget


# # ============================================================================
# # Hook Registration Functions
# # ============================================================================

# def register_file_tree_decorators():
    # """Register file tree decoration hooks"""
    
    # def python_file_decorator(file_path):
        # """Add Python icon to .py files"""
        # from pathlib import Path
        # path = Path(file_path)
        
        # if path.suffix == '.py':
            # from ide.core.PluginAPI import FileTreeDecoration
            # decoration = FileTreeDecoration(file_path)
            # decoration.prefix_icon = "🐍"
            # decoration.text_color = "#4A9EFF"
            
            # # Make __init__.py files bold
            # if path.name == '__init__.py':
                # decoration.bold = True
                # decoration.tooltip = "Python package initialization file"
            
            # return decoration
        # return None
    
    # def modified_file_decorator(file_path):
        # """Add indicator for recently modified files"""
        # from pathlib import Path
        # import time
        
        # path = Path(file_path)
        # if path.exists():
            # modified_time = path.stat().st_mtime
            # age_hours = (time.time() - modified_time) / 3600
            
            # if age_hours < 24:  # Modified in last 24 hours
                # from ide.core.PluginAPI import FileTreeDecoration
                # decoration = FileTreeDecoration(file_path)
                # decoration.suffix_icon = "✨"
                # decoration.tooltip = f"Modified {age_hours:.1f} hours ago"
                # return decoration
        # return None
    
    # _register_hook('file_tree_decorator', python_file_decorator)
    # _register_hook('file_tree_decorator', modified_file_decorator)
    # log("📁 Registered file tree decorators")


# def register_gutter_decorators():
    # """Register editor gutter marker hooks"""
    
    # def line_length_marker(editor, line_num):
        # """Add markers for long lines"""
        # try:
            # text = editor.document().findBlockByLineNumber(line_num - 1).text()
            # if len(text) > 100:
                # from ide.core.PluginAPI import GutterMarker
                # marker = GutterMarker(line_num)
                # marker.icon = "⚠️"
                # marker.color = "#FFA500"
                # marker.tooltip = f"Line too long: {len(text)} characters"
                # return marker
        # except:
            # pass
        # return None
    
    # _register_hook('gutter_decorator', line_length_marker)
    # log("📏 Registered gutter decorators")


# def register_status_bar_widgets():
    # """Register status bar widgets"""
    
    # def create_status_widget():
        # """Create a status widget showing plugin info"""
        # from PyQt6.QtWidgets import QLabel
        
        # label = QLabel("🔌 Demo Active")
        # label.setStyleSheet("""
            # QLabel {
                # color: #4A9EFF;
                # padding: 2px 8px;
                # background: #2D2D2D;
                # border-radius: 3px;
                # font-size: 11px;
            # }
        # """)
        
        # # Update every 5 seconds
        # def update_label():
            # time_str = datetime.now().strftime("%H:%M:%S")
            # label.setText(f"🔌 Demo | {time_str}")
        
        # timer = QTimer()
        # timer.timeout.connect(update_label)
        # timer.start(5000)
        
        # return label
    
    # _register_hook('status_bar_widget', create_status_widget)
    # log("📊 Registered status bar widgets")


# def register_context_menus():
    # """Register context menu extensions"""
    
    # def add_file_menu_items(menu, file_path):
        # """Add custom items to file context menu"""
        # from PyQt6.QtWidgets import QMenu
        # from PyQt6.QtGui import QAction
        
        # # Add separator
        # menu.addSeparator()
        
        # # Add custom action
        # action = QAction("🔍 Analyze with Demo Plugin", menu)
        # action.triggered.connect(lambda: analyze_file(file_path))
        # menu.addAction(action)
    
    # def add_tab_menu_items(menu, editor):
        # """Add custom items to tab context menu"""
        # from PyQt6.QtGui import QAction
        
        # action = QAction("📊 Show Editor Stats", menu)
        # action.triggered.connect(lambda: show_editor_stats(editor))
        # menu.addAction(action)
    
    # _register_hook('context_menu_file', add_file_menu_items)
    # _register_hook('context_menu_tab', add_tab_menu_items)
    # log("📋 Registered context menu items")


# def register_file_events():
    # """Register file event hooks"""
    
    # def on_save(file_path):
        # """Called when a file is saved"""
        # log(f"💾 File saved: {Path(file_path).name}")
        # _update_event_list(f"Saved: {Path(file_path).name}")
    
    # def on_open(file_path):
        # """Called when a file is opened"""
        # log(f"📂 File opened: {Path(file_path).name}")
        # _update_event_list(f"Opened: {Path(file_path).name}")
    
    # def on_close(file_path):
        # """Called when a file is closed"""
        # log(f"🗙 File closed: {Path(file_path).name}")
        # _update_event_list(f"Closed: {Path(file_path).name}")
    
    # def on_modify(file_path):
        # """Called when a file is modified"""
        # # Be careful with this one - it fires often!
        # pass
    
    # _register_hook('on_file_saved', on_save)
    # _register_hook('on_file_opened', on_open)
    # _register_hook('on_file_closed', on_close)
    # _register_hook('on_file_modified', on_modify)
    # log("📄 Registered file event hooks")


# def register_editor_events():
    # """Register editor event hooks"""
    
    # def on_focus(editor):
        # """Called when editor receives focus"""
        # if hasattr(editor, 'file_path') and editor.file_path:
            # log(f"🎯 Focus: {Path(editor.file_path).name}")
    
    # def on_cursor_move(editor, line, column):
        # """Called when cursor moves"""
        # # Update cursor position display
        # if _widget:
            # _widget.update_cursor_position(line, column)
    
    # _register_hook('on_editor_focus', on_focus)
    # _register_hook('on_cursor_moved', on_cursor_move)
    # log("✏️ Registered editor event hooks")


# def register_ide_events():
    # """Register IDE lifecycle event hooks"""
    
    # def on_workspace_open():
        # """Called when IDE starts"""
        # log("🏢 Workspace opened!")
        # if _api:
            # workspace = _api.get_workspace_path()
            # log(f"   Path: {workspace}")
    
    # def on_project_open():
        # """Called when project is activated"""
        # log("📁 Project opened!")
    
    # _register_hook('on_workspace_opened', on_workspace_open)
    # _register_hook('on_project_opened', on_project_open)
    # log("🌐 Registered IDE event hooks")


# # ============================================================================
# # Helper Functions
# # ============================================================================

# def _register_hook(hook_name, callback):
    # """Register hook and track for cleanup"""
    # global _api, _hooks_registered
    # if _api:
        # _api.register_hook(hook_name, callback)
        # _hooks_registered.append((hook_name, callback))


# def log(message):
    # """Add message to log"""
    # global _widget
    # if _widget:
        # _widget.add_log(message)
    # print(f"[ComprehensiveDemo] {message}")


# def _update_event_list(event):
    # """Update event list in widget"""
    # global _widget
    # if _widget:
        # _widget.add_event(event)


# def analyze_file(file_path):
    # """Example: Analyze file from context menu"""
    # if _api:
        # content = _api.get_file_content(file_path)
        # if content:
            # lines = len(content.split('\n'))
            # chars = len(content)
            # words = len(content.split())
            # log(f"📊 Analysis of {Path(file_path).name}:")
            # log(f"   Lines: {lines:,}, Words: {words:,}, Characters: {chars:,}")
            # _api.show_status_message(
                # f"Analyzed: {lines:,} lines, {words:,} words, {chars:,} chars", 
                # 4000
            # )


# def show_editor_stats(editor):
    # """Show statistics about current editor"""
    # if hasattr(editor, 'toPlainText'):
        # text = editor.toPlainText()
        # lines = len(text.split('\n'))
        # words = len(text.split())
        # chars = len(text)
        
        # log(f"📊 Editor Statistics:")
        # log(f"   Lines: {lines:,}")
        # log(f"   Words: {words:,}")
        # log(f"   Characters: {chars:,}")


# # ============================================================================
# # Main Plugin Widget
# # ============================================================================

# class ComprehensivePluginWidget(QWidget):
    # """Main widget demonstrating all plugin features"""
    
    # def __init__(self, parent=None):
        # super().__init__(parent)
        # self.init_ui()
    
    # def init_ui(self):
        # """Initialize user interface"""
        # layout = QVBoxLayout(self)
        # layout.setSpacing(10)
        
        # # Header
        # header = QLabel("🔌 Comprehensive Plugin Feature Demo")
        # header.setStyleSheet("""
            # font-size: 20px;
            # font-weight: bold;
            # color: #4A9EFF;
            # padding: 10px;
        # """)
        # header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # layout.addWidget(header)
        
        # # Description
        # desc = QLabel(
            # "This plugin demonstrates ALL available features in the Plugin API.\n"
            # "Interact with the IDE to see hooks in action!"
        # )
        # desc.setStyleSheet("color: #AAA; padding: 5px;")
        # desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # layout.addWidget(desc)
        
        # # Main content
        # content_layout = QHBoxLayout()
        
        # # Left column - Controls
        # left_panel = self.create_controls_panel()
        # content_layout.addWidget(left_panel, 1)
        
        # # Right column - Event log
        # right_panel = self.create_log_panel()
        # content_layout.addWidget(right_panel, 1)
        
        # layout.addLayout(content_layout)
        
        # # Bottom - Recent events
        # events_panel = self.create_events_panel()
        # layout.addWidget(events_panel)
    
    # def create_controls_panel(self):
        # """Create controls panel"""
        # # Create scroll area for controls
        # scroll = QScrollArea()
        # scroll.setWidgetResizable(True)
        # scroll.setMaximumWidth(450)
        
        # container = QWidget()
        # main_layout = QVBoxLayout(container)
        # main_layout.setSpacing(5)
        
        # # File operations group
        # file_group = QGroupBox("📁 File Operations")
        # file_group.setStyleSheet("""
            # QGroupBox {
                # font-weight: bold;
                # border: 1px solid #555;
                # border-radius: 5px;
                # margin-top: 10px;
                # padding-top: 10px;
            # }
            # QGroupBox::title {
                # color: #4A9EFF;
            # }
        # """)
        
        # file_layout = QVBoxLayout()
        
        # btn_current = QPushButton("📄 Show Current File Info")
        # btn_current.clicked.connect(self.test_current_file)
        # file_layout.addWidget(btn_current)
        
        # btn_files = QPushButton("📋 List All Open Files")
        # btn_files.clicked.connect(self.test_list_files)
        # file_layout.addWidget(btn_files)
        
        # btn_editors = QPushButton("👁️ Show All Editors")
        # btn_editors.clicked.connect(self.test_list_editors)
        # file_layout.addWidget(btn_editors)
        
        # file_group.setLayout(file_layout)
        # main_layout.addWidget(file_group)
        
        # # UI operations group
        # ui_group = QGroupBox("🎨 UI Operations")
        # ui_group.setStyleSheet("""
            # QGroupBox {
                # font-weight: bold;
                # border: 1px solid #555;
                # border-radius: 5px;
                # margin-top: 10px;
                # padding-top: 10px;
            # }
            # QGroupBox::title {
                # color: #4A9EFF;
            # }
        # """)
        
        # ui_layout = QVBoxLayout()
        
        # btn_refresh_tree = QPushButton("🔄 Refresh File Tree")
        # btn_refresh_tree.clicked.connect(self.test_refresh_tree)
        # ui_layout.addWidget(btn_refresh_tree)
        
        # btn_refresh_editor = QPushButton("🔄 Refresh Current Editor")
        # btn_refresh_editor.clicked.connect(self.test_refresh_editor)
        # ui_layout.addWidget(btn_refresh_editor)
        
        # btn_refresh_all = QPushButton("🔄 Refresh All Editors")
        # btn_refresh_all.clicked.connect(self.test_refresh_all)
        # ui_layout.addWidget(btn_refresh_all)
        
        # ui_group.setLayout(ui_layout)
        # main_layout.addWidget(ui_group)
        
        # # Status message group
        # status_group = QGroupBox("💬 Status Messages")
        # status_group.setStyleSheet("""
            # QGroupBox {
                # font-weight: bold;
                # border: 1px solid #555;
                # border-radius: 5px;
                # margin-top: 10px;
                # padding-top: 10px;
            # }
            # QGroupBox::title {
                # color: #4A9EFF;
            # }
        # """)
        
        # status_layout = QVBoxLayout()
        
        # self.status_input = QLineEdit()
        # self.status_input.setPlaceholderText("Enter status message...")
        # self.status_input.setText("Hello from plugin!")
        # status_layout.addWidget(self.status_input)
        
        # btn_status = QPushButton("💬 Show Status Message")
        # btn_status.clicked.connect(self.test_status_message)
        # status_layout.addWidget(btn_status)
        
        # status_group.setLayout(status_layout)
        # main_layout.addWidget(status_group)
        
        # # Cache operations group
        # cache_group = QGroupBox("💾 Cache Operations")
        # cache_group.setStyleSheet("""
            # QGroupBox {
                # font-weight: bold;
                # border: 1px solid #555;
                # border-radius: 5px;
                # margin-top: 10px;
                # padding-top: 10px;
            # }
            # QGroupBox::title {
                # color: #4A9EFF;
            # }
        # """)
        
        # cache_layout = QVBoxLayout()
        
        # cache_layout.addWidget(QLabel("Cache Key:"))
        # self.cache_key = QLineEdit()
        # self.cache_key.setPlaceholderText("my_key")
        # cache_layout.addWidget(self.cache_key)
        
        # cache_layout.addWidget(QLabel("Cache Value:"))
        # self.cache_value = QLineEdit()
        # self.cache_value.setPlaceholderText("my_value")
        # cache_layout.addWidget(self.cache_value)
        
        # cache_btn_layout = QHBoxLayout()
        # btn_cache_set = QPushButton("💾 Set")
        # btn_cache_set.clicked.connect(self.test_cache_set)
        # cache_btn_layout.addWidget(btn_cache_set)
        
        # btn_cache_get = QPushButton("📖 Get")
        # btn_cache_get.clicked.connect(self.test_cache_get)
        # cache_btn_layout.addWidget(btn_cache_get)
        
        # cache_layout.addLayout(cache_btn_layout)
        
        # cache_group.setLayout(cache_layout)
        # main_layout.addWidget(cache_group)
        
        # # Info displays
        # info_group = QGroupBox("ℹ️ Live Info")
        # info_group.setStyleSheet("""
            # QGroupBox {
                # font-weight: bold;
                # border: 1px solid #555;
                # border-radius: 5px;
                # margin-top: 10px;
                # padding-top: 10px;
            # }
            # QGroupBox::title {
                # color: #4A9EFF;
            # }
        # """)
        
        # info_layout = QVBoxLayout()
        
        # # Cursor position display
        # self.cursor_label = QLabel("Cursor: Line 0, Col 0")
        # self.cursor_label.setStyleSheet("""
            # background: #2D2D2D;
            # padding: 5px;
            # border-radius: 3px;
            # color: #4A9EFF;
        # """)
        # info_layout.addWidget(self.cursor_label)
        
        # # Workspace path
        # if _api:
            # workspace = _api.get_workspace_path()
            # workspace_label = QLabel(f"Workspace:\n{workspace}")
            # workspace_label.setWordWrap(True)
            # workspace_label.setStyleSheet("""
                # background: #2D2D2D;
                # padding: 5px;
                # border-radius: 3px;
                # color: #AAA;
                # font-size: 10px;
            # """)
            # info_layout.addWidget(workspace_label)
        
        # info_group.setLayout(info_layout)
        # main_layout.addWidget(info_group)
        
        # main_layout.addStretch()
        
        # scroll.setWidget(container)
        # return scroll
    
    # def create_log_panel(self):
        # """Create log panel"""
        # group = QGroupBox("📝 Event Log")
        # group.setStyleSheet("""
            # QGroupBox {
                # font-weight: bold;
                # border: 1px solid #555;
                # border-radius: 5px;
                # margin-top: 10px;
                # padding-top: 10px;
            # }
            # QGroupBox::title {
                # color: #4A9EFF;
            # }
        # """)
        
        # layout = QVBoxLayout()
        
        # self.log_text = QTextEdit()
        # self.log_text.setReadOnly(True)
        # self.log_text.setStyleSheet("""
            # background: #1E1E1E;
            # color: #CCC;
            # border: 1px solid #555;
            # font-family: 'Courier New', monospace;
            # font-size: 11px;
        # """)
        # layout.addWidget(self.log_text)
        
        # btn_clear = QPushButton("🗑️ Clear Log")
        # btn_clear.clicked.connect(lambda: self.log_text.clear())
        # layout.addWidget(btn_clear)
        
        # group.setLayout(layout)
        # return group
    
    # def create_events_panel(self):
        # """Create recent events panel"""
        # group = QGroupBox("⚡ Recent IDE Events (via hooks)")
        # group.setStyleSheet("""
            # QGroupBox {
                # font-weight: bold;
                # border: 1px solid #555;
                # border-radius: 5px;
                # margin-top: 10px;
                # padding-top: 10px;
            # }
            # QGroupBox::title {
                # color: #4A9EFF;
            # }
        # """)
        
        # layout = QVBoxLayout()
        
        # self.event_list = QListWidget()
        # self.event_list.setStyleSheet("""
            # background: #1E1E1E;
            # color: #CCC;
            # border: 1px solid #555;
        # """)
        # self.event_list.setMaximumHeight(200)
        # layout.addWidget(self.event_list)
        
        # group.setLayout(layout)
        # return group
    
    # # ========================================================================
    # # Test Functions
    # # ========================================================================
    
    # def test_current_file(self):
        # """Test showing current file info"""
        # if _api:
            # editor = _api.get_current_editor()
            # if editor and hasattr(editor, 'file_path') and editor.file_path:
                # file_path = Path(editor.file_path)
                # text = editor.toPlainText() if hasattr(editor, 'toPlainText') else ""
                # lines = len(text.split('\n')) if text else 0
                # chars = len(text)
                
                # self.add_log(f"📄 Current File: {file_path.name}")
                # self.add_log(f"   Path: {file_path}")
                # self.add_log(f"   Lines: {lines:,}")
                # self.add_log(f"   Characters: {chars:,}")
                # self.add_log(f"   Size: {file_path.stat().st_size:,} bytes" if file_path.exists() else "")
            # else:
                # self.add_log("⚠️ No file currently open")
    
    # def test_list_files(self):
        # """Test listing all open files"""
        # if _api:
            # files = _api.get_all_open_files()
            # self.add_log(f"📋 Open files: {len(files)}")
            # if files:
                # for i, f in enumerate(files, 1):
                    # self.add_log(f"   {i}. {Path(f).name}")
                    # if i >= 10:
                        # remaining = len(files) - i
                        # if remaining > 0:
                            # self.add_log(f"   ... and {remaining} more")
                        # break
            # else:
                # self.add_log("   (No files open)")
    
    # def test_list_editors(self):
        # """Test listing all editor instances"""
        # if _api:
            # editors = _api.get_all_editors()
            # self.add_log(f"👁️ Open editors: {len(editors)}")
            # for i, editor in enumerate(editors, 1):
                # if hasattr(editor, 'file_path') and editor.file_path:
                    # self.add_log(f"   {i}. {Path(editor.file_path).name}")
                # else:
                    # self.add_log(f"   {i}. (Untitled)")
                # if i >= 10:
                    # remaining = len(editors) - i
                    # if remaining > 0:
                        # self.add_log(f"   ... and {remaining} more")
                    # break
    
    # def test_refresh_tree(self):
        # """Test refreshing file tree"""
        # if _api:
            # _api.refresh_file_tree()
            # self.add_log("🔄 File tree refreshed")
    
    # def test_refresh_editor(self):
        # """Test refreshing current editor"""
        # if _api:
            # _api.refresh_current_editor()
            # self.add_log("🔄 Current editor refreshed")
    
    # def test_refresh_all(self):
        # """Test refreshing all editors"""
        # if _api:
            # _api.refresh_all_editors()
            # self.add_log("🔄 All editors refreshed")
    
    # def test_status_message(self):
        # """Test showing status message"""
        # if _api:
            # msg = self.status_input.text() or "Hello from plugin!"
            # _api.show_status_message(msg, 3000)
            # self.add_log(f"💬 Status: {msg}")
    
    # def test_cache_set(self):
        # """Test setting cache value"""
        # if _api:
            # key = self.cache_key.text() or "test_key"
            # value = self.cache_value.text() or "test_value"
            # _api.set_cache(key, value)
            # self.add_log(f"💾 Cache set: {key} = {value}")
    
    # def test_cache_get(self):
        # """Test getting cache value"""
        # if _api:
            # key = self.cache_key.text() or "test_key"
            # value = _api.get_cache(key, "Not found")
            # self.add_log(f"📖 Cache get: {key} = {value}")
            # self.cache_value.setText(str(value))
    
    # # ========================================================================
    # # UI Update Functions
    # # ========================================================================
    
    # def add_log(self, message):
        # """Add message to log"""
        # timestamp = datetime.now().strftime("%H:%M:%S")
        # self.log_text.append(f"[{timestamp}] {message}")
        
        # # Auto-scroll to bottom
        # scrollbar = self.log_text.verticalScrollBar()
        # scrollbar.setValue(scrollbar.maximum())
    
    # def add_event(self, event):
        # """Add event to recent events list"""
        # timestamp = datetime.now().strftime("%H:%M:%S")
        # self.event_list.insertItem(0, f"[{timestamp}] {event}")
        
        # # Keep only last 20 events
        # while self.event_list.count() > 20:
            # self.event_list.takeItem(self.event_list.count() - 1)
    
    # def update_cursor_position(self, line, column):
        # """Update cursor position display"""
        # self.cursor_label.setText(f"Cursor: Line {line}, Col {column}")