"""
Example Plugin for Workspace IDE - Comprehensive Reference

This plugin demonstrates all major features available to plugin developers:
- Plugin metadata and configuration
- Event hooks (file saved, opened, closed, etc.)
- Keyboard shortcuts
- UI widgets and layouts
- Settings persistence
- Active project monitoring
- Status bar integration
- Editor interaction

This is a fully functional plugin that shows workspace info and can be used
as a template for creating new plugins.

Author: Workspace IDE Team
Version: 1.0.0
"""

from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QTextEdit, QGroupBox, QCheckBox, QSpinBox, QListWidget,
    QTabWidget, QLineEdit, QComboBox
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont


# ============================================================================
# Plugin Class
# ============================================================================

class ExamplePlugin:
    """
    Example Plugin - Demonstrates all plugin system features
    
    This plugin shows:
    - How to structure a plugin class
    - How to use the Plugin API
    - How to create UI widgets
    - How to handle events
    - How to persist settings
    """
    
    # ========================================================================
    # Plugin Metadata (Required)
    # ========================================================================
    
    PLUGIN_NAME = "Example Plugin"
    PLUGIN_VERSION = "1.0.5"
    PLUGIN_DESCRIPTION = "Comprehensive example showing all plugin features"
    PLUGIN_RUN_ON_STARTUP = True   # Auto-start in background
    PLUGIN_HAS_UI = True            # Has a UI panel
    PLUGIN_ICON = "📚"              # Icon for toolbar
    
    # ========================================================================
    # Initialization
    # ========================================================================
    
    def __init__(self, api):
        """
        Initialize plugin instance
        
        Args:
            api: PluginAPI instance - provides access to IDE functionality
        """
        self.api = api
        self.initialized = False
        
        # Plugin state
        self.file_count = 0
        self.save_count = 0
        self.recent_files = []
        self.widget = None  # Will hold reference to UI widget
        
        # Settings (will be persisted)
        self.settings = {
            'auto_log': True,
            'max_log_entries': 50,
            'show_notifications': True
        }
        
        print(f"[{self.PLUGIN_NAME}] Instance created")
    
    def initialize(self):
        """
        Initialize plugin - called by plugin system after __init__
        
        This is where you:
        - Register event hooks
        - Register keyboard shortcuts
        - Load saved settings
        - Set up any background services
        """
        if self.initialized:
            print(f"[{self.PLUGIN_NAME}] Already initialized")
            return
        
        print(f"[{self.PLUGIN_NAME}] Initializing...")
        
        # Load saved settings (if any)
        self._load_settings()
        
        # Register event hooks
        self.api.register_hook('on_file_saved', self.on_file_saved, 
                              plugin_id='example_plugin')
        self.api.register_hook('on_file_opened', self.on_file_opened, 
                              plugin_id='example_plugin')
        self.api.register_hook('on_file_closed', self.on_file_closed, 
                              plugin_id='example_plugin')
        self.api.register_hook('on_editor_focus', self.on_editor_focus, 
                              plugin_id='example_plugin')
        
        # Register keyboard shortcuts
        self.api.register_keyboard_shortcut(
            'Ctrl+Shift+X',
            self.show_example_action,
            'Example Plugin Action'
        )
        
        self.initialized = True
        
        # Show welcome message
        if self.settings.get('show_notifications', True):
            self.api.show_status_message(f"{self.PLUGIN_NAME} initialized", 2000)
        
        print(f"[{self.PLUGIN_NAME}] Initialized")
    
    def get_widget(self, parent=None):
        """
        Return the plugin's UI widget
        
        Args:
            parent: Parent widget
        
        Returns:
            QWidget: Plugin's main UI
        """
        self.widget = ExamplePluginWidget(self, parent)
        return self.widget
    
    def cleanup(self):
        """
        Cleanup plugin resources - called when plugin is unloaded
        
        This is where you:
        - Unregister hooks (done automatically)
        - Save settings/state
        - Stop background threads
        - Release resources
        """
        print(f"[{self.PLUGIN_NAME}] Cleaning up...")
        
        # Save settings
        self._save_settings()
        
        # Unregister hooks (done automatically by plugin system)
        if self.api:
            self.api.unregister_all_plugin_hooks('example_plugin')
        
        self.initialized = False
        print(f"[{self.PLUGIN_NAME}] Cleaned up")
    
    # ========================================================================
    # Event Handlers (Hooks)
    # ========================================================================
    
    def on_file_saved(self, file_path: str):
        """
        Called when a file is saved
        
        Args:
            file_path: Path to the saved file
        """
        self.save_count += 1
        self._log_event(f"File saved: {Path(file_path).name}")
        
        # Update UI if visible
        if self.widget:
            self.widget.update_stats()
    
    def on_file_opened(self, file_path: str):
        """
        Called when a file is opened
        
        Args:
            file_path: Path to the opened file
        """
        self.file_count += 1
        self.recent_files.append(file_path)
        
        # Keep only last 10
        if len(self.recent_files) > 10:
            self.recent_files.pop(0)
        
        self._log_event(f"File opened: {Path(file_path).name}")
        
        # Update UI if visible
        if self.widget:
            self.widget.update_stats()
            self.widget.update_recent_files()
    
    def on_file_closed(self, file_path: str):
        """
        Called when a file is closed
        
        Args:
            file_path: Path to the closed file
        """
        self._log_event(f"File closed: {Path(file_path).name}")
    
    def on_editor_focus(self, editor):
        """
        Called when an editor gains focus
        
        Args:
            editor: The editor widget that gained focus
        """
        if hasattr(editor, 'file_path') and editor.file_path:
            self._log_event(f"Editor focus: {Path(editor.file_path).name}")
    
    # ========================================================================
    # Actions (Keyboard Shortcuts)
    # ========================================================================
    
    def show_example_action(self):
        """Example action triggered by Ctrl+Shift+X"""
        self.api.show_status_message("Example plugin action triggered!", 3000)
        self._log_event("Action: Keyboard shortcut triggered (Ctrl+Shift+X)")
    
    # ========================================================================
    # Helper Methods
    # ========================================================================
    
    def _log_event(self, message: str):
        """
        Log an event
        
        Args:
            message: Event message
        """
        if not self.settings.get('auto_log', True):
            return
        
        print(f"[{self.PLUGIN_NAME}] {message}")
        
        # Update UI log if visible
        if self.widget:
            self.widget.add_log_entry(message)
    
    def _load_settings(self):
        """Load saved settings from IDE settings"""
        ide_settings = self.api.get_settings()
        plugin_settings = ide_settings.get('example_plugin_settings', {})
        
        if plugin_settings:
            self.settings.update(plugin_settings)
            print(f"[{self.PLUGIN_NAME}] Loaded settings: {self.settings}")
    
    def _save_settings(self):
        """Save settings to IDE settings"""
        ide_settings = self.api.get_settings()
        ide_settings['example_plugin_settings'] = self.settings
        
        # Note: Settings are automatically saved by IDE on close
        print(f"[{self.PLUGIN_NAME}] Saved settings: {self.settings}")
    
    def get_active_projects(self):
        """Get list of active projects"""
        settings = self.api.get_settings()
        return settings.get('active_projects', [])
    
    def get_workspace_stats(self):
        """Get workspace statistics"""
        return {
            'files_opened': self.file_count,
            'files_saved': self.save_count,
            'recent_files': len(self.recent_files),
            'active_projects': len(self.get_active_projects())
        }


# ============================================================================
# Plugin UI Widget
# ============================================================================

class ExamplePluginWidget(QWidget):
    """
    Plugin UI Widget
    
    This demonstrates:
    - Creating a tabbed interface
    - Using various Qt widgets
    - Updating UI in response to events
    - Interacting with plugin instance
    """
    
    def __init__(self, plugin, parent=None):
        super().__init__(parent)
        self.plugin = plugin
        
        self.init_ui()
        
        # Auto-update timer
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_stats)
        self.update_timer.start(2000)  # Update every 2 seconds
    
    def init_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout(self)
        
        # ===== Header =====
        header = QLabel(f"{self.plugin.PLUGIN_ICON} {self.plugin.PLUGIN_NAME} ({self.plugin.PLUGIN_VERSION})")
        header.setStyleSheet("""
            font-size: 20px; 
            font-weight: bold; 
            color: #4A9EFF;
            padding: 10px;
        """)
        layout.addWidget(header)
        
        # ===== Tab Widget =====
        tabs = QTabWidget()
        
        # Dashboard Tab
        tabs.addTab(self.create_dashboard_tab(), "📊 Dashboard")
        
        # Activity Log Tab
        tabs.addTab(self.create_log_tab(), "📋 Activity Log")
        
        # Settings Tab
        tabs.addTab(self.create_settings_tab(), "⚙️ Settings")
        
        # Help Tab
        tabs.addTab(self.create_help_tab(), "❓ Help")
        
        layout.addWidget(tabs)
    
    # ========================================================================
    # Tab Creation Methods
    # ========================================================================

    def create_dashboard_tab(self):
        """Create dashboard tab showing workspace info"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(10)  # Add spacing between groups
        
        # ===== Statistics Group =====
        stats_group = QGroupBox("📊 Workspace Statistics")
        stats_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #555;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 5px;
                color: #4A9EFF;
            }
        """)
        stats_layout = QVBoxLayout(stats_group)
        
        self.stats_label = QLabel()
        self.stats_label.setStyleSheet("""
            color: #CCC; 
            padding: 10px;
            background: #2D2D2D;
            border-radius: 5px;
        """)
        self.stats_label.setWordWrap(True)
        stats_layout.addWidget(self.stats_label)
        
        layout.addWidget(stats_group)
        
        # ===== Active Projects Group =====
        projects_group = QGroupBox("📁 Active Projects")
        projects_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #555;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 5px;
                color: #4A9EFF;
            }
        """)
        projects_layout = QVBoxLayout(projects_group)
        
        self.projects_list = QListWidget()
        self.projects_list.setMaximumHeight(120)  # Reduced from 150
        self.projects_list.setStyleSheet("""
            QListWidget {
                background: #2D2D2D;
                color: #CCC;
                border: 1px solid #555;
                border-radius: 3px;
                padding: 5px;
            }
            QListWidget::item {
                padding: 4px;
            }
            QListWidget::item:hover {
                background: #3C3F41;
            }
        """)
        projects_layout.addWidget(self.projects_list)
        
        layout.addWidget(projects_group)
        
        # ===== Recent Files Group =====
        recent_group = QGroupBox("📄 Recent Files")
        recent_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #555;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 5px;
                color: #4A9EFF;
            }
        """)
        recent_layout = QVBoxLayout(recent_group)
        
        self.recent_list = QListWidget()
        self.recent_list.setMaximumHeight(120)  # Reduced from 150
        self.recent_list.setStyleSheet("""
            QListWidget {
                background: #2D2D2D;
                color: #CCC;
                border: 1px solid #555;
                border-radius: 3px;
                padding: 5px;
            }
            QListWidget::item {
                padding: 4px;
            }
            QListWidget::item:hover {
                background: #3C3F41;
            }
        """)
        recent_layout.addWidget(self.recent_list)
        
        layout.addWidget(recent_group)
        
        # ===== Action Buttons =====
        button_layout = QHBoxLayout()
        
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 16px;
                background: #3C3F41;
                border: 1px solid #555;
                border-radius: 3px;
            }
            QPushButton:hover {
                background: #4A4A4A;
            }
        """)
        refresh_btn.clicked.connect(self.refresh_all)
        button_layout.addWidget(refresh_btn)
        
        test_action_btn = QPushButton("🧪 Test Action")
        test_action_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 16px;
                background: #3C3F41;
                border: 1px solid #555;
                border-radius: 3px;
            }
            QPushButton:hover {
                background: #4A4A4A;
            }
        """)
        test_action_btn.clicked.connect(self.plugin.show_example_action)
        button_layout.addWidget(test_action_btn)
        
        button_layout.addStretch()
        
        layout.addLayout(button_layout)
        
        layout.addStretch()
        
        # Initial update
        self.update_stats()
        self.update_projects()
        self.update_recent_files()
        
        return widget
    
    # def create_dashboard_tab(self):
        # """Create dashboard tab showing workspace info"""
        # widget = QWidget()
        # layout = QVBoxLayout(widget)
        
        # # ===== Statistics Group =====
        # stats_group = QGroupBox("📊 Workspace Statistics")
        # stats_layout = QVBoxLayout(stats_group)
        
        # self.stats_label = QLabel()
        # self.stats_label.setStyleSheet("""
            # color: #CCC; 
            # padding: 10px;
            # background: #2D2D2D;
            # border-radius: 5px;
        # """)
        # stats_layout.addWidget(self.stats_label)
        
        # layout.addWidget(stats_group)
        
        # # ===== Active Projects Group =====
        # projects_group = QGroupBox("📁 Active Projects")
        # projects_layout = QVBoxLayout(projects_group)
        
        # self.projects_list = QListWidget()
        # self.projects_list.setMaximumHeight(150)
        # self.projects_list.setStyleSheet("""
            # background: #2D2D2D;
            # color: #CCC;
            # border: 1px solid #555;
        # """)
        # projects_layout.addWidget(self.projects_list)
        
        # layout.addWidget(projects_group)
        
        # # ===== Recent Files Group =====
        # recent_group = QGroupBox("📄 Recent Files")
        # recent_layout = QVBoxLayout(recent_group)
        
        # self.recent_list = QListWidget()
        # self.recent_list.setMaximumHeight(150)
        # self.recent_list.setStyleSheet("""
            # background: #2D2D2D;
            # color: #CCC;
            # border: 1px solid #555;
        # """)
        # recent_layout.addWidget(self.recent_list)
        
        # layout.addWidget(recent_group)
        
        # # ===== Action Buttons =====
        # button_layout = QHBoxLayout()
        
        # refresh_btn = QPushButton("🔄 Refresh")
        # refresh_btn.clicked.connect(self.refresh_all)
        # button_layout.addWidget(refresh_btn)
        
        # test_action_btn = QPushButton("🧪 Test Action")
        # test_action_btn.clicked.connect(self.plugin.show_example_action)
        # button_layout.addWidget(test_action_btn)
        
        # layout.addLayout(button_layout)
        
        # layout.addStretch()
        
        # # Initial update
        # self.update_stats()
        # self.update_projects()
        # self.update_recent_files()
        
        # return widget
    
    def create_log_tab(self):
        """Create activity log tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Info label
        info = QLabel("Activity log shows events as they happen:")
        info.setStyleSheet("color: #AAA; padding: 5px;")
        layout.addWidget(info)
        
        # Log display
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
        
        # Control buttons
        button_layout = QHBoxLayout()
        
        clear_btn = QPushButton("🗑️ Clear Log")
        clear_btn.clicked.connect(self.log_text.clear)
        button_layout.addWidget(clear_btn)
        
        button_layout.addStretch()
        
        layout.addLayout(button_layout)
        
        return widget
    
    def create_settings_tab(self):
        """Create settings tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Settings group
        settings_group = QGroupBox("⚙️ Plugin Settings")
        settings_layout = QVBoxLayout(settings_group)
        
        # Auto-log checkbox
        self.auto_log_cb = QCheckBox("Enable automatic event logging")
        self.auto_log_cb.setChecked(self.plugin.settings.get('auto_log', True))
        self.auto_log_cb.stateChanged.connect(self.on_auto_log_changed)
        settings_layout.addWidget(self.auto_log_cb)
        
        # Max log entries
        log_layout = QHBoxLayout()
        log_layout.addWidget(QLabel("Maximum log entries:"))
        self.max_log_spin = QSpinBox()
        self.max_log_spin.setRange(10, 1000)
        self.max_log_spin.setValue(self.plugin.settings.get('max_log_entries', 50))
        self.max_log_spin.valueChanged.connect(self.on_max_log_changed)
        log_layout.addWidget(self.max_log_spin)
        log_layout.addStretch()
        settings_layout.addLayout(log_layout)
        
        # Show notifications
        self.notifications_cb = QCheckBox("Show status bar notifications")
        self.notifications_cb.setChecked(self.plugin.settings.get('show_notifications', True))
        self.notifications_cb.stateChanged.connect(self.on_notifications_changed)
        settings_layout.addWidget(self.notifications_cb)
        
        layout.addWidget(settings_group)
        
        # Save button
        save_btn = QPushButton("💾 Save Settings")
        save_btn.clicked.connect(self.save_settings)
        layout.addWidget(save_btn)
        
        layout.addStretch()
        
        return widget
    
    def create_help_tab(self):
        """Create help/documentation tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        help_text = QTextEdit()
        help_text.setReadOnly(True)
        help_text.setStyleSheet("""
            background: #2D2D2D;
            color: #CCC;
            border: 1px solid #555;
            padding: 10px;
        """)
        
        help_content = f"""
<h2>{self.plugin.PLUGIN_ICON} {self.plugin.PLUGIN_NAME}</h2>
<p><b>Version:</b> {self.plugin.PLUGIN_VERSION}</p>

<h3>📖 About</h3>
<p>{self.plugin.PLUGIN_DESCRIPTION}</p>

<h3>✨ Features</h3>
<ul>
<li><b>Dashboard:</b> Shows workspace statistics, active projects, and recent files</li>
<li><b>Activity Log:</b> Monitors and logs IDE events in real-time</li>
<li><b>Event Hooks:</b> Responds to file save, open, and close events</li>
<li><b>Keyboard Shortcuts:</b> Press Ctrl+Shift+X to trigger example action</li>
<li><b>Hot Reload:</b> Right-click toolbar icon → Reload Plugin</li>
</ul>

<h3>⌨️ Keyboard Shortcuts</h3>
<ul>
<li><b>Ctrl+Shift+X:</b> Trigger example action</li>
</ul>

<h3>🔧 Settings</h3>
<p>Configure plugin behavior in the Settings tab:</p>
<ul>
<li><b>Auto-logging:</b> Enable/disable automatic event logging</li>
<li><b>Max log entries:</b> Limit the number of log entries kept</li>
<li><b>Notifications:</b> Show/hide status bar notifications</li>
</ul>

<h3>💡 For Plugin Developers</h3>
<p>This plugin demonstrates:</p>
<ul>
<li>Plugin class structure and metadata</li>
<li>Event hook registration and handling</li>
<li>Keyboard shortcut registration</li>
<li>UI widget creation with tabs and layouts</li>
<li>Settings persistence</li>
<li>API usage (status messages, workspace info, etc.)</li>
</ul>

<p><i>Copy this plugin as a starting point for your own plugins!</i></p>

<h3>🐛 Testing Hot Reload</h3>
<ol>
<li>Edit ide/plugins/ExamplePlugin.py</li>
<li>Right-click the {self.plugin.PLUGIN_ICON} icon in the toolbar</li>
<li>Click "🔄 Reload Plugin"</li>
<li>Changes appear immediately!</li>
</ol>
"""
        
        help_text.setHtml(help_content)
        layout.addWidget(help_text)
        
        return widget
    
    # ========================================================================
    # Update Methods
    # ========================================================================
    
    def update_stats(self):
        """Update statistics display"""
        stats = self.plugin.get_workspace_stats()
        
        stats_html = f"""
<b>Workspace Activity:</b><br>
&nbsp;&nbsp;• Files Opened: {stats['files_opened']}<br>
&nbsp;&nbsp;• Files Saved: {stats['files_saved']}<br>
&nbsp;&nbsp;• Recent Files: {stats['recent_files']}<br>
&nbsp;&nbsp;• Active Projects: {stats['active_projects']}
"""
        
        self.stats_label.setText(stats_html)
    
    def update_projects(self):
        """Update active projects list"""
        self.projects_list.clear()
        
        active_projects = self.plugin.get_active_projects()
        
        if not active_projects:
            self.projects_list.addItem("No active projects")
        else:
            for project_path in active_projects:
                project_name = Path(project_path).name
                self.projects_list.addItem(f"📁 {project_name}")
    
    def update_recent_files(self):
        """Update recent files list"""
        self.recent_list.clear()
        
        if not self.plugin.recent_files:
            self.recent_list.addItem("No recent files")
        else:
            for file_path in reversed(self.plugin.recent_files):
                file_name = Path(file_path).name
                self.recent_list.addItem(f"📄 {file_name}")
    
    def refresh_all(self):
        """Refresh all displays"""
        self.update_stats()
        self.update_projects()
        self.update_recent_files()
        self.plugin.api.show_status_message("Refreshed plugin data", 2000)
    
    def add_log_entry(self, message: str):
        """Add entry to activity log"""
        from datetime import datetime
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")
        
        # Limit log size
        max_entries = self.plugin.settings.get('max_log_entries', 50)
        
        # Keep only last N lines
        text = self.log_text.toPlainText()
        lines = text.split('\n')
        if len(lines) > max_entries:
            self.log_text.setPlainText('\n'.join(lines[-max_entries:]))
    
    # ========================================================================
    # Settings Handlers
    # ========================================================================
    
    def on_auto_log_changed(self, state):
        """Handle auto-log checkbox change"""
        self.plugin.settings['auto_log'] = (state == 2)
    
    def on_max_log_changed(self, value):
        """Handle max log entries change"""
        self.plugin.settings['max_log_entries'] = value
    
    def on_notifications_changed(self, state):
        """Handle notifications checkbox change"""
        self.plugin.settings['show_notifications'] = (state == 2)
    
    def save_settings(self):
        """Save settings"""
        self.plugin._save_settings()
        self.plugin.api.show_status_message("Settings saved", 2000)
        self.add_log_entry("Settings saved")
