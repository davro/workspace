# ide/plugins/CronManager.py

"""
Cron Manager Plugin - Pure Class-Based Architecture

Provides cron task management, crontab editing, and data directory monitoring.
All functionality is encapsulated in the CronManagerPlugin class.
"""

from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QTableWidget, QTableWidgetItem, QDialog, QLineEdit, QTextEdit,
    QComboBox, QMessageBox, QFileDialog, QTreeWidget, QTreeWidgetItem,
    QSplitter, QCheckBox, QSpinBox
)
from PyQt6.QtCore import QThread, pyqtSignal, QTimer, Qt
from PyQt6.QtGui import QFont
import subprocess
import re
from datetime import datetime
import os


# ============================================================================
# Cron Task Data Models
# ============================================================================

class CronTask:
    """Represents a single cron task"""
    
    def __init__(self, schedule: str, command: str, comment: str = "", enabled: bool = True):
        self.schedule = schedule  # e.g., "0 * * * *"
        self.command = command
        self.comment = comment
        self.enabled = enabled
        self.last_run = None
        self.next_run = None
    
    def to_crontab_line(self) -> str:
        """Convert to crontab format"""
        line = ""
        if self.comment:
            line += f"# {self.comment}\n"
        
        prefix = "" if self.enabled else "# "
        line += f"{prefix}{self.schedule} {self.command}"
        return line
    
    def get_human_schedule(self) -> str:
        """Convert cron schedule to human-readable format"""
        parts = self.schedule.split()
        if len(parts) != 5:
            return self.schedule
        
        minute, hour, day, month, weekday = parts
        
        # Common patterns
        if self.schedule == "* * * * *":
            return "Every minute"
        elif self.schedule == "0 * * * *":
            return "Every hour"
        elif self.schedule == "0 0 * * *":
            return "Daily at midnight"
        elif self.schedule == "0 0 * * 0":
            return "Weekly on Sunday"
        elif self.schedule == "0 0 1 * *":
            return "Monthly on the 1st"
        elif minute.startswith("*/"):
            return f"Every {minute[2:]} minutes"
        elif hour.startswith("*/"):
            return f"Every {hour[2:]} hours"
        else:
            return f"At {hour}:{minute}" if hour != "*" and minute != "*" else self.schedule


class CronManager:
    """Manages crontab operations"""
    
    def __init__(self):
        self.tasks = []
        self.raw_crontab = ""
    
    def load_crontab(self) -> bool:
        """Load current user's crontab"""
        try:
            result = subprocess.run(
                ['crontab', '-l'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                self.raw_crontab = result.stdout
                self.parse_crontab(self.raw_crontab)
                return True
            else:
                # No crontab exists yet
                self.raw_crontab = ""
                self.tasks = []
                return True
                
        except Exception as e:
            print(f"[CronManager] Error loading crontab: {e}")
            return False
    
    def parse_crontab(self, content: str):
        """Parse crontab content into CronTask objects"""
        self.tasks = []
        current_comment = ""
        
        for line in content.split('\n'):
            line = line.strip()
            
            if not line:
                current_comment = ""
                continue
            
            # Comment line
            if line.startswith('#'):
                current_comment = line[1:].strip()
                continue
            
            # Parse cron line
            match = re.match(r'^([\d\*\/,\-]+\s+[\d\*\/,\-]+\s+[\d\*\/,\-]+\s+[\d\*\/,\-]+\s+[\d\*\/,\-]+)\s+(.+)$', line)
            if match:
                schedule = match.group(1)
                command = match.group(2)
                task = CronTask(schedule, command, current_comment, enabled=True)
                self.tasks.append(task)
                current_comment = ""
    
    def save_crontab(self) -> bool:
        """Save tasks back to crontab"""
        try:
            # Build crontab content
            lines = []
            for task in self.tasks:
                lines.append(task.to_crontab_line())
            
            content = '\n'.join(lines) + '\n'
            
            # Write to crontab
            process = subprocess.Popen(
                ['crontab', '-'],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            stdout, stderr = process.communicate(input=content, timeout=5)
            
            if process.returncode == 0:
                self.raw_crontab = content
                return True
            else:
                print(f"[CronManager] Error saving crontab: {stderr}")
                return False
                
        except Exception as e:
            print(f"[CronManager] Error saving crontab: {e}")
            return False
    
    def add_task(self, task: CronTask):
        """Add a new task"""
        self.tasks.append(task)
    
    def remove_task(self, index: int):
        """Remove a task by index"""
        if 0 <= index < len(self.tasks):
            del self.tasks[index]
    
    def get_task(self, index: int) -> CronTask:
        """Get task by index"""
        if 0 <= index < len(self.tasks):
            return self.tasks[index]
        return None


class DataDirectoryMonitor:
    """Monitors ~/workspace/data directory"""
    
    def __init__(self, data_path: Path):
        self.data_path = data_path
        self.file_stats = {}
    
    def scan_directory(self) -> dict:
        """Scan data directory and return statistics"""
        if not self.data_path.exists():
            return {
                'total_files': 0,
                'total_size': 0,
                'file_types': {},
                'recent_files': []
            }
        
        files = []
        total_size = 0
        file_types = {}
        
        for file_path in self.data_path.rglob('*'):
            if file_path.is_file():
                size = file_path.stat().st_size
                total_size += size
                
                ext = file_path.suffix or 'no extension'
                file_types[ext] = file_types.get(ext, 0) + 1
                
                files.append({
                    'path': file_path,
                    'size': size,
                    'modified': datetime.fromtimestamp(file_path.stat().st_mtime)
                })
        
        # Sort by modified time
        files.sort(key=lambda x: x['modified'], reverse=True)
        
        return {
            'total_files': len(files),
            'total_size': total_size,
            'file_types': file_types,
            'recent_files': files[:10]
        }


# ============================================================================
# Main Plugin Class
# ============================================================================

class CronManagerPlugin:
    """
    Cron Manager Plugin - All functionality in one class
    
    Manages cron tasks and monitors data directory
    """
    
    # Plugin metadata
    PLUGIN_NAME = "Cron Manager"
    PLUGIN_VERSION = "1.0.0"
    PLUGIN_DESCRIPTION = "Manage cron tasks and monitor data directory"
    PLUGIN_RUN_ON_STARTUP = True
    PLUGIN_HAS_UI = True
    PLUGIN_ICON = "⏰"
    
    def __init__(self, api):
        """Initialize plugin instance"""
        self.api = api
        self.cron_manager = CronManager()
        self.data_monitor = None
        self.data_path = Path.home() / "workspace" / "data"
        self.initialized = False
        
        print(f"[{self.PLUGIN_NAME}] Plugin instance created")
    
    def initialize(self):
        """Initialize plugin components"""
        if self.initialized:
            print(f"[{self.PLUGIN_NAME}] Already initialized")
            return
        
        # Create data directory if it doesn't exist
        self.data_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize data monitor
        self.data_monitor = DataDirectoryMonitor(self.data_path)
        
        # Load crontab
        self.cron_manager.load_crontab()
        
        # Register keyboard shortcuts
        if hasattr(self.api, 'register_keyboard_shortcut'):
            self.api.register_keyboard_shortcut('Ctrl+Alt+C', self.show_cron_editor, 'Open Cron Editor')
        
        self.api.show_status_message("Cron Manager initialized", 2000)
        self.initialized = True
    
    def get_widget(self, parent=None):
        """Return plugin UI widget"""
        return CronManagerWidget(self, parent)
    
    def cleanup(self):
        """Cleanup plugin resources"""
        print(f"[{self.PLUGIN_NAME}] Cleaning up...")
        
        if self.api:
            self.api.unregister_all_plugin_hooks('cron_manager')
        
        self.initialized = False
        print(f"[{self.PLUGIN_NAME}] Cleaned up")
    
    def show_cron_editor(self):
        """Show cron task editor dialog"""
        dialog = CronEditorDialog(self.cron_manager, parent=self.api.ide)
        dialog.exec()
    
    def get_statistics(self) -> dict:
        """Get statistics about cron tasks and data"""
        stats = {
            'total_tasks': len(self.cron_manager.tasks),
            'enabled_tasks': sum(1 for t in self.cron_manager.tasks if t.enabled),
            'disabled_tasks': sum(1 for t in self.cron_manager.tasks if not t.enabled),
        }
        
        if self.data_monitor:
            data_stats = self.data_monitor.scan_directory()
            stats.update(data_stats)
        
        return stats


# ============================================================================
# Plugin UI Widget
# ============================================================================

class CronManagerWidget(QWidget):
    """Main plugin control panel"""
    
    def __init__(self, plugin, parent=None):
        super().__init__(parent)
        self.plugin = plugin
        self.stats_label = None
        self.data_stats_label = None
        
        self.init_ui()
        
        # Update stats every 5 seconds
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_statistics)
        self.update_timer.start(5000)
    
    def init_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout(self)
        
        # Header
        header = QLabel(f"{self.plugin.PLUGIN_ICON} {self.plugin.PLUGIN_NAME} ({self.plugin.PLUGIN_VERSION})")
        header.setStyleSheet("font-size: 18px; font-weight: bold; color: #4A9EFF; padding: 10px;")
        layout.addWidget(header)
        
        # Description
        desc = QLabel(
            "Manage cron tasks and monitor data directory.\n\n"
            "Features:\n"
            "• View and edit crontab entries\n"
            "• Add/remove cron tasks\n"
            "• Monitor ~/workspace/data\n"
            "• Quick task templates"
        )
        desc.setStyleSheet("color: #CCC; padding: 10px;")
        layout.addWidget(desc)
        
        # Cron Statistics
        self.stats_label = QLabel()
        self.stats_label.setStyleSheet("color: #AAA; padding: 10px; background: #2D2D2D; border-radius: 5px;")
        self.stats_label.setWordWrap(True)
        layout.addWidget(self.stats_label)
        
        # Data Directory Statistics
        self.data_stats_label = QLabel()
        self.data_stats_label.setStyleSheet("color: #AAA; padding: 10px; background: #2D2D2D; border-radius: 5px; margin-top: 5px;")
        self.data_stats_label.setWordWrap(True)
        layout.addWidget(self.data_stats_label)
        
        # Initial update
        self.update_statistics()
        
        # Actions
        actions_layout = QVBoxLayout()
        
        btn_editor = QPushButton("📝 Open Cron Editor")
        btn_editor.clicked.connect(self.plugin.show_cron_editor)
        btn_editor.setStyleSheet("padding: 10px;")
        actions_layout.addWidget(btn_editor)
        
        btn_reload = QPushButton("🔄 Reload Crontab")
        btn_reload.clicked.connect(self.on_reload_crontab)
        btn_reload.setStyleSheet("padding: 10px;")
        actions_layout.addWidget(btn_reload)
        
        btn_data = QPushButton("📁 Open Data Directory")
        btn_data.clicked.connect(self.on_open_data_directory)
        btn_data.setStyleSheet("padding: 10px;")
        actions_layout.addWidget(btn_data)
        
        btn_template = QPushButton("⚡ Quick Task Templates")
        btn_template.clicked.connect(self.on_show_templates)
        btn_template.setStyleSheet("padding: 10px;")
        actions_layout.addWidget(btn_template)
        
        layout.addLayout(actions_layout)
        layout.addStretch()
    
    def update_statistics(self):
        """Update statistics display"""
        stats = self.plugin.get_statistics()
        
        # Cron stats
        stats_text = (
            f"⏰ <b>Cron Tasks:</b><br>"
            f"&nbsp;&nbsp;• Total tasks: {stats['total_tasks']}<br>"
            f"&nbsp;&nbsp;• Enabled: {stats['enabled_tasks']}<br>"
            f"&nbsp;&nbsp;• Disabled: {stats['disabled_tasks']}"
        )
        self.stats_label.setText(stats_text)
        
        # Data directory stats
        if 'total_files' in stats:
            size_mb = stats['total_size'] / (1024 * 1024)
            
            file_types_text = ""
            if stats['file_types']:
                top_types = sorted(stats['file_types'].items(), key=lambda x: x[1], reverse=True)[:3]
                file_types_text = "<br>&nbsp;&nbsp;• " + ", ".join(f"{ext}: {count}" for ext, count in top_types)
            
            data_text = (
                f"📁 <b>Data Directory (~/workspace/data):</b><br>"
                f"&nbsp;&nbsp;• Total files: {stats['total_files']}<br>"
                f"&nbsp;&nbsp;• Total size: {size_mb:.2f} MB{file_types_text}"
            )
            self.data_stats_label.setText(data_text)
    
    def on_reload_crontab(self):
        """Reload crontab"""
        if self.plugin.cron_manager.load_crontab():
            self.plugin.api.show_status_message("Crontab reloaded", 2000)
            self.update_statistics()
        else:
            self.plugin.api.show_status_message("Failed to reload crontab", 3000)
    
    def on_open_data_directory(self):
        """Open data directory in file manager"""
        import platform
        import subprocess
        
        system = platform.system()
        try:
            if system == "Darwin":  # macOS
                subprocess.run(["open", str(self.plugin.data_path)])
            elif system == "Windows":
                subprocess.run(["explorer", str(self.plugin.data_path)])
            else:  # Linux
                subprocess.run(["xdg-open", str(self.plugin.data_path)])
        except Exception as e:
            print(f"Error opening directory: {e}")
    
    def on_show_templates(self):
        """Show quick task templates"""
        dialog = TaskTemplatesDialog(self.plugin.cron_manager, parent=self)
        if dialog.exec():
            self.update_statistics()


# ============================================================================
# Cron Editor Dialog
# ============================================================================

class CronEditorDialog(QDialog):
    """Dialog for editing cron tasks"""
    
    def __init__(self, cron_manager: CronManager, parent=None):
        super().__init__(parent)
        self.cron_manager = cron_manager
        self.setWindowTitle("Cron Task Editor")
        self.setMinimumSize(800, 600)
        
        self.init_ui()
        self.load_tasks()
    
    def init_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout(self)
        
        # Task table
        self.task_table = QTableWidget()
        self.task_table.setColumnCount(4)
        self.task_table.setHorizontalHeaderLabels(["Schedule", "Command", "Comment", "Enabled"])
        self.task_table.horizontalHeader().setStretchLastSection(False)
        self.task_table.setColumnWidth(0, 150)
        self.task_table.setColumnWidth(1, 350)
        self.task_table.setColumnWidth(2, 200)
        self.task_table.setColumnWidth(3, 80)
        layout.addWidget(self.task_table)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        btn_add = QPushButton("➕ Add Task")
        btn_add.clicked.connect(self.on_add_task)
        btn_layout.addWidget(btn_add)
        
        btn_edit = QPushButton("✏️ Edit Task")
        btn_edit.clicked.connect(self.on_edit_task)
        btn_layout.addWidget(btn_edit)
        
        btn_delete = QPushButton("🗑️ Delete Task")
        btn_delete.clicked.connect(self.on_delete_task)
        btn_layout.addWidget(btn_delete)
        
        btn_layout.addStretch()
        
        btn_save = QPushButton("💾 Save to Crontab")
        btn_save.clicked.connect(self.on_save)
        btn_save.setStyleSheet("background: #4A9EFF; color: white; font-weight: bold; padding: 8px;")
        btn_layout.addWidget(btn_save)
        
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.close)
        btn_layout.addWidget(btn_close)
        
        layout.addLayout(btn_layout)
    
    def load_tasks(self):
        """Load tasks into table"""
        self.task_table.setRowCount(len(self.cron_manager.tasks))
        
        for i, task in enumerate(self.cron_manager.tasks):
            self.task_table.setItem(i, 0, QTableWidgetItem(task.schedule))
            self.task_table.setItem(i, 1, QTableWidgetItem(task.command))
            self.task_table.setItem(i, 2, QTableWidgetItem(task.comment))
            
            enabled_item = QTableWidgetItem("✓" if task.enabled else "✗")
            enabled_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.task_table.setItem(i, 3, enabled_item)
    
    def on_add_task(self):
        """Add new task"""
        dialog = TaskEditDialog(parent=self)
        if dialog.exec():
            task = dialog.get_task()
            self.cron_manager.add_task(task)
            self.load_tasks()
    
    def on_edit_task(self):
        """Edit selected task"""
        current_row = self.task_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "No Selection", "Please select a task to edit")
            return
        
        task = self.cron_manager.get_task(current_row)
        dialog = TaskEditDialog(task, parent=self)
        if dialog.exec():
            updated_task = dialog.get_task()
            self.cron_manager.tasks[current_row] = updated_task
            self.load_tasks()
    
    def on_delete_task(self):
        """Delete selected task"""
        current_row = self.task_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "No Selection", "Please select a task to delete")
            return
        
        reply = QMessageBox.question(
            self, "Confirm Delete",
            "Are you sure you want to delete this task?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.cron_manager.remove_task(current_row)
            self.load_tasks()
    
    def on_save(self):
        """Save to crontab"""
        if self.cron_manager.save_crontab():
            QMessageBox.information(self, "Success", "Crontab saved successfully")
        else:
            QMessageBox.critical(self, "Error", "Failed to save crontab")


# ============================================================================
# Task Edit Dialog
# ============================================================================

class TaskEditDialog(QDialog):
    """Dialog for editing a single task"""
    
    def __init__(self, task: CronTask = None, parent=None):
        super().__init__(parent)
        self.task = task
        self.setWindowTitle("Edit Cron Task" if task else "New Cron Task")
        self.setMinimumWidth(600)
        
        self.init_ui()
        
        if task:
            self.load_task(task)
    
    def init_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout(self)
        
        # Schedule
        schedule_layout = QHBoxLayout()
        schedule_layout.addWidget(QLabel("Schedule:"))
        self.schedule_input = QLineEdit()
        self.schedule_input.setPlaceholderText("e.g., 0 * * * * (every hour)")
        schedule_layout.addWidget(self.schedule_input)
        layout.addLayout(schedule_layout)
        
        # Command
        layout.addWidget(QLabel("Command:"))
        self.command_input = QTextEdit()
        self.command_input.setMaximumHeight(100)
        layout.addWidget(self.command_input)
        
        # Comment
        comment_layout = QHBoxLayout()
        comment_layout.addWidget(QLabel("Comment:"))
        self.comment_input = QLineEdit()
        comment_layout.addWidget(self.comment_input)
        layout.addLayout(comment_layout)
        
        # Enabled
        self.enabled_checkbox = QCheckBox("Enabled")
        self.enabled_checkbox.setChecked(True)
        layout.addWidget(self.enabled_checkbox)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        btn_ok = QPushButton("OK")
        btn_ok.clicked.connect(self.accept)
        btn_layout.addWidget(btn_ok)
        
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)
        
        layout.addLayout(btn_layout)
    
    def load_task(self, task: CronTask):
        """Load task into form"""
        self.schedule_input.setText(task.schedule)
        self.command_input.setPlainText(task.command)
        self.comment_input.setText(task.comment)
        self.enabled_checkbox.setChecked(task.enabled)
    
    def get_task(self) -> CronTask:
        """Get task from form"""
        return CronTask(
            schedule=self.schedule_input.text().strip(),
            command=self.command_input.toPlainText().strip(),
            comment=self.comment_input.text().strip(),
            enabled=self.enabled_checkbox.isChecked()
        )


# ============================================================================
# Task Templates Dialog
# ============================================================================

class TaskTemplatesDialog(QDialog):
    """Dialog for selecting quick task templates"""
    
    TEMPLATES = [
        ("Every minute", "* * * * *", "*/path/to/script.sh"),
        ("Every hour", "0 * * * *", "*/path/to/script.sh"),
        ("Daily at midnight", "0 0 * * *", "*/path/to/script.sh"),
        ("Daily at 3am", "0 3 * * *", "*/path/to/script.sh"),
        ("Weekly on Sunday", "0 0 * * 0", "*/path/to/script.sh"),
        ("Monthly on 1st", "0 0 1 * *", "*/path/to/script.sh"),
        ("Every 5 minutes", "*/5 * * * *", "*/path/to/script.sh"),
        ("Every 30 minutes", "*/30 * * * *", "*/path/to/script.sh"),
        ("Weekdays at 9am", "0 9 * * 1-5", "*/path/to/script.sh"),
    ]
    
    def __init__(self, cron_manager: CronManager, parent=None):
        super().__init__(parent)
        self.cron_manager = cron_manager
        self.setWindowTitle("Quick Task Templates")
        self.setMinimumSize(500, 400)
        
        self.init_ui()
    
    def init_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout(self)
        
        layout.addWidget(QLabel("Select a template to add a new cron task:"))
        
        # Template list
        self.template_list = QTableWidget()
        self.template_list.setColumnCount(2)
        self.template_list.setHorizontalHeaderLabels(["Description", "Schedule"])
        self.template_list.setRowCount(len(self.TEMPLATES))
        
        for i, (desc, schedule, _) in enumerate(self.TEMPLATES):
            self.template_list.setItem(i, 0, QTableWidgetItem(desc))
            self.template_list.setItem(i, 1, QTableWidgetItem(schedule))
        
        self.template_list.horizontalHeader().setStretchLastSection(True)
        self.template_list.doubleClicked.connect(self.on_template_selected)
        layout.addWidget(self.template_list)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        btn_select = QPushButton("Use Template")
        btn_select.clicked.connect(self.on_template_selected)
        btn_layout.addWidget(btn_select)
        
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.reject)
        btn_layout.addWidget(btn_close)
        
        layout.addLayout(btn_layout)
    
    def on_template_selected(self):
        """Handle template selection"""
        current_row = self.template_list.currentRow()
        if current_row < 0:
            return
        
        desc, schedule, command = self.TEMPLATES[current_row]
        task = CronTask(schedule, command, desc, enabled=True)
        
        dialog = TaskEditDialog(task, parent=self)
        if dialog.exec():
            updated_task = dialog.get_task()
            self.cron_manager.add_task(updated_task)
            self.accept()