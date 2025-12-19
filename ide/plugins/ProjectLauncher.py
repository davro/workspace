"""
Retro Project Launcher Plugin - Visual Basic Style

Features:
- Auto-detects project types (Python, Node.js, PHP, Rust, Go, etc.)
- Retro VB6-inspired interface with project icons
- Quick launch projects in terminal
- Project statistics and info
- Fun nostalgic design

Save as: workspace/plugins/project_launcher.py
"""

import json
import subprocess
from pathlib import Path
from datetime import datetime
from PyQt6.QtWidgets import *
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QColor, QFont, QPalette, QIcon, QPainter, QLinearGradient

PLUGIN_NAME = "Project Launcher"
PLUGIN_VERSION = "1.0.0"

def get_widget(parent=None):
    return ProjectLauncherWidget(parent)


class ProjectLauncherWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.load_active_projects()
        self.detect_all_projects()
        self.init_ui()
    
    def load_active_projects(self):
        config_file = Path.home() / "workspace" / ".workspace_ide_config.json"
        try:
            if config_file.exists():
                with open(config_file, 'r') as f:
                    config = json.load(f)
                    self.active_projects = config.get('active_projects', [])
            else:
                self.active_projects = []
        except:
            self.active_projects = []
    
    def detect_all_projects(self):
        """Detect project types for all active projects"""
        self.projects = []
        
        for project_path in self.active_projects:
            path = Path(project_path)
            if not path.exists():
                continue
            
            project_info = {
                'name': path.name,
                'path': str(path),
                'type': self.detect_project_type(path),
                'icon': self.get_project_icon(path),
                'color': self.get_project_color(path),
                'stats': self.get_project_stats(path)
            }
            
            self.projects.append(project_info)
    
    def detect_project_type(self, path):
        """Detect project type based on files"""
        
        # Python
        if (path / "requirements.txt").exists() or (path / "setup.py").exists() or (path / "pyproject.toml").exists():
            return "Python"
        
        # Node.js / JavaScript
        if (path / "package.json").exists():
            return "Node.js"
        
        # PHP
        if (path / "composer.json").exists():
            return "PHP"
        
        # Rust
        if (path / "Cargo.toml").exists():
            return "Rust"
        
        # Go
        if (path / "go.mod").exists():
            return "Go"
        
        # Ruby
        if (path / "Gemfile").exists():
            return "Ruby"
        
        # Java / Maven
        if (path / "pom.xml").exists():
            return "Java (Maven)"
        
        # Java / Gradle
        if (path / "build.gradle").exists() or (path / "build.gradle.kts").exists():
            return "Java (Gradle)"
        
        # C/C++
        if (path / "CMakeLists.txt").exists() or (path / "Makefile").exists():
            return "C/C++"
        
        # .NET / C#
        if list(path.glob("*.csproj")) or list(path.glob("*.sln")):
            return "C# / .NET"
        
        # Docker project
        if (path / "Dockerfile").exists():
            return "Docker"
        
        # Generic web project
        if (path / "index.html").exists():
            return "Web"
        
        # Check for common file extensions
        py_files = list(path.glob("*.py"))
        js_files = list(path.glob("*.js"))
        php_files = list(path.glob("*.php"))
        
        if py_files and len(py_files) > 2:
            return "Python (Script)"
        elif js_files and len(js_files) > 2:
            return "JavaScript"
        elif php_files and len(php_files) > 2:
            return "PHP (Script)"
        
        return "Unknown"
    
    def get_project_icon(self, path):
        """Get emoji icon based on project type"""
        project_type = self.detect_project_type(path)
        
        icons = {
            "Python": "🐍",
            "Python (Script)": "🐍",
            "Node.js": "📦",
            "JavaScript": "💛",
            "PHP": "🐘",
            "PHP (Script)": "🐘",
            "Rust": "🦀",
            "Go": "🐹",
            "Ruby": "💎",
            "Java (Maven)": "☕",
            "Java (Gradle)": "☕",
            "C/C++": "⚙️",
            "C# / .NET": "🔷",
            "Docker": "🐳",
            "Web": "🌐",
            "Unknown": "📁"
        }
        
        return icons.get(project_type, "📁")
    
    def get_project_color(self, path):
        """Get color scheme based on project type"""
        project_type = self.detect_project_type(path)
        
        colors = {
            "Python": "#3776AB",
            "Python (Script)": "#3776AB",
            "Node.js": "#339933",
            "JavaScript": "#F7DF1E",
            "PHP": "#777BB4",
            "PHP (Script)": "#777BB4",
            "Rust": "#CE422B",
            "Go": "#00ADD8",
            "Ruby": "#CC342D",
            "Java (Maven)": "#007396",
            "Java (Gradle)": "#007396",
            "C/C++": "#00599C",
            "C# / .NET": "#512BD4",
            "Docker": "#2496ED",
            "Web": "#E34F26",
            "Unknown": "#666666"
        }
        
        return colors.get(project_type, "#666666")
    
    def get_project_stats(self, path):
        """Get project statistics"""
        try:
            # Count files
            file_count = sum(1 for _ in path.rglob('*') if _.is_file() and not any(p.startswith('.') for p in _.parts))
            
            # Get size
            total_size = sum(f.stat().st_size for f in path.rglob('*') if f.is_file())
            
            # Get last modified
            try:
                mtime = max(f.stat().st_mtime for f in path.rglob('*') if f.is_file())
                last_modified = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d')
            except:
                last_modified = "Unknown"
            
            return {
                'files': file_count,
                'size': self.format_size(total_size),
                'modified': last_modified
            }
        except:
            return {'files': 0, 'size': '0 B', 'modified': 'Unknown'}
    
    def format_size(self, size):
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Retro title bar
        title_bar = self.create_title_bar()
        layout.addWidget(title_bar)
        
        # Tab widget for New/Recent
        tab_widget = QTabWidget()
        tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 2px solid #000080;
                background: #A0A0A0;
            }
            QTabBar::tab {
                background: #A0A0A0;
                color: black;
                padding: 10px 24px;
                border: 2px solid #808080;
                border-bottom: none;
                margin-right: 2px;
                font-size: 13px;
                font-weight: bold;
            }
            QTabBar::tab:selected {
                background: #C0C0C0;
                border-bottom: 2px solid #C0C0C0;
            }
            QTabBar::tab:hover {
                background: #B0B0B0;
            }
        """)
        
        # New Project tab
        new_project_widget = self.create_new_project_tab()
        tab_widget.addTab(new_project_widget, "New Project")
        
        # Projects grid
        projects_widget = self.create_projects_grid()
        tab_widget.addTab(projects_widget, "Existing Projects")
        
        # Stats widget
        stats_widget = self.create_stats_widget()
        tab_widget.addTab(stats_widget, "Statistics")
        
        layout.addWidget(tab_widget)
        
        # Status bar
        status_bar = QLabel(f"Ready • {len(self.projects)} projects loaded")
        status_bar.setStyleSheet("""
            background: #C0C0C0;
            color: black;
            padding: 4px;
            border-top: 2px solid white;
            border-bottom: 2px solid #808080;
        """)
        layout.addWidget(status_bar)
        self.status_bar = status_bar
    
    def create_title_bar(self):
        """Create retro VB-style title bar"""
        title_widget = QWidget()
        title_widget.setFixedHeight(60)
        title_widget.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #000080, stop:0.5 #0000CD, stop:1 #000080);
        """)
        
        layout = QHBoxLayout(title_widget)
        layout.setContentsMargins(10, 5, 10, 5)
        
        title = QLabel("Workspace Projects")
        title.setStyleSheet("""
            color: white;
            font-size: 24px;
            font-weight: bold;
            font-family: 'Arial';
        """)
        layout.addWidget(title)
        
        layout.addStretch()
        
        # Help button
        help_btn = QPushButton("?")
        help_btn.setFixedSize(30, 30)
        help_btn.setStyleSheet("""
            QPushButton {
                background: #C0C0C0;
                border: 2px solid white;
                border-right: 2px solid #808080;
                border-bottom: 2px solid #808080;
                color: black;
                font-weight: bold;
                font-size: 16px;
            }
            QPushButton:pressed {
                border: 2px solid #808080;
                border-right: 2px solid white;
                border-bottom: 2px solid white;
            }
        """)
        help_btn.clicked.connect(self.show_help)
        layout.addWidget(help_btn)
        
        return title_widget
    
    def create_new_project_tab(self):
        """Create new project wizard tab"""
        widget = QWidget()
        widget.setStyleSheet("background: #A0A0A0;")
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(widget)
        scroll.setStyleSheet("QScrollArea { border: none; background: #A0A0A0; }")
        
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Title
        title = QLabel("Create New Project")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #000080;")
        layout.addWidget(title)
        
        subtitle = QLabel("Select a project template to get started")
        subtitle.setStyleSheet("color: #333; margin-bottom: 10px; font-size: 12px;")
        layout.addWidget(subtitle)
        
        # Project templates grid
        templates_grid = QGridLayout()
        templates_grid.setSpacing(15)
        
        # Define project templates
        templates = [
            {"name": "Python Application", "icon": "🐍", "type": "python", "color": "#3776AB", "desc": "Python project with virtual env"},
            {"name": "Node.js Application", "icon": "📦", "type": "nodejs", "color": "#339933", "desc": "Node.js with package.json"},
            {"name": "PHP Application", "icon": "🐘", "type": "php", "color": "#777BB4", "desc": "PHP project with composer"},
            {"name": "Rust Application", "icon": "🦀", "type": "rust", "color": "#CE422B", "desc": "Rust project with Cargo"},
            {"name": "Go Application", "icon": "🐹", "type": "go", "color": "#00ADD8", "desc": "Go module project"},
            {"name": "Static Website", "icon": "🌐", "type": "web", "color": "#E34F26", "desc": "HTML/CSS/JS website"},
            {"name": "Docker Project", "icon": "🐳", "type": "docker", "color": "#2496ED", "desc": "Dockerized application"},
            {"name": "Empty Project", "icon": "📁", "type": "empty", "color": "#666666", "desc": "Empty project folder"},
        ]
        
        row, col = 0, 0
        max_cols = 3
        
        for template in templates:
            tile = self.create_template_tile(template)
            templates_grid.addWidget(tile, row, col)
            
            col += 1
            if col >= max_cols:
                col = 0
                row += 1
        
        layout.addLayout(templates_grid)
        layout.addStretch()
        
        return scroll
    
    def create_template_tile(self, template):
        """Create project template tile"""
        tile = QFrame()
        tile.setFixedSize(200, 180)
        tile.setStyleSheet(f"""
            QFrame {{
                background: white;
                border: 3px solid #666;
                border-right: 3px solid #333;
                border-bottom: 3px solid #333;
                border-radius: 4px;
            }}
            QFrame:hover {{
                border: 3px solid {template['color']};
                background: #F8F8F8;
            }}
        """)
        tile.setCursor(Qt.CursorShape.PointingHandCursor)
        
        # Make clickable
        tile.mousePressEvent = lambda e: self.create_project(template)
        
        layout = QVBoxLayout(tile)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(8)
        
        # Icon
        icon_label = QLabel(template['icon'])
        icon_label.setStyleSheet("font-size: 52px; background: transparent; border: none;")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_label)
        
        # Name
        name_label = QLabel(template['name'])
        name_label.setStyleSheet(f"font-weight: bold; font-size: 14px; color: {template['color']}; background: transparent; border: none;")
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_label.setWordWrap(True)
        layout.addWidget(name_label)
        
        # Description
        desc_label = QLabel(template['desc'])
        desc_label.setStyleSheet("font-size: 11px; color: #555; background: transparent; border: none;")
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)
        
        layout.addStretch()
        
        return tile
    
    def create_project(self, template):
        """Create new project from template"""
        dialog = NewProjectDialog(template, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            project_name = dialog.project_name.text().strip()
            project_path = Path(dialog.project_location.text()) / project_name
            
            try:
                # Create project directory
                project_path.mkdir(parents=True, exist_ok=True)
                
                # Create template-specific files
                self.create_template_files(project_path, template['type'], project_name)
                
                # Add to config
                self.add_project_to_config(str(project_path))
                
                # Refresh
                self.load_active_projects()
                self.detect_all_projects()
                
                QMessageBox.information(
                    self,
                    "Success",
                    f"Project '{project_name}' created successfully!\n\nLocation: {project_path}"
                )
                
                self.status_bar.setText(f"Created project: {project_name}")
                
                # Reload UI (simple approach - recreate widgets)
                # Clear the old layout
                for i in reversed(range(self.layout().count())): 
                    widget = self.layout().itemAt(i).widget()
                    if widget:
                        widget.setParent(None)
                
                # Reinitialize
                self.detect_all_projects()
                self.init_ui()
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to create project:\n{e}")
    
    def create_template_files(self, path, template_type, project_name):
        """Create initial files based on template type"""
        
        if template_type == "python":
            # Create Python project structure
            (path / "requirements.txt").write_text("# Python dependencies\n")
            (path / "README.md").write_text(f"# {project_name}\n\nPython project\n")
            (path / "main.py").write_text('#!/usr/bin/env python3\n"""Main application file"""\n\nif __name__ == "__main__":\n    print("Hello from ' + project_name + '")\n')
            (path / ".gitignore").write_text("__pycache__/\n*.pyc\nvenv/\n.env\n")
        
        elif template_type == "nodejs":
            # Create Node.js project
            package_json = {
                "name": project_name.lower().replace(" ", "-"),
                "version": "1.0.0",
                "description": f"{project_name} - Node.js application",
                "main": "index.js",
                "scripts": {"start": "node index.js"},
                "keywords": [],
                "author": "",
                "license": "ISC"
            }
            (path / "package.json").write_text(json.dumps(package_json, indent=2))
            (path / "index.js").write_text(f'console.log("Hello from {project_name}");\n')
            (path / "README.md").write_text(f"# {project_name}\n\nNode.js project\n")
            (path / ".gitignore").write_text("node_modules/\n.env\n")
        
        elif template_type == "php":
            # Create PHP project
            composer_json = {
                "name": f"vendor/{project_name.lower().replace(' ', '-')}",
                "description": f"{project_name} - PHP application",
                "type": "project",
                "require": {"php": ">=7.4"}
            }
            (path / "composer.json").write_text(json.dumps(composer_json, indent=2))
            (path / "index.php").write_text(f'<?php\necho "Hello from {project_name}";\n')
            (path / "README.md").write_text(f"# {project_name}\n\nPHP project\n")
            (path / ".gitignore").write_text("vendor/\n.env\n")
        
        elif template_type == "rust":
            # Create Rust project
            (path / "Cargo.toml").write_text(f'[package]\nname = "{project_name.lower().replace(" ", "_")}"\nversion = "0.1.0"\nedition = "2021"\n\n[dependencies]\n')
            src_dir = path / "src"
            src_dir.mkdir(exist_ok=True)
            (src_dir / "main.rs").write_text(f'fn main() {{\n    println!("Hello from {project_name}!");\n}}\n')
            (path / "README.md").write_text(f"# {project_name}\n\nRust project\n")
            (path / ".gitignore").write_text("target/\nCargo.lock\n")
        
        elif template_type == "go":
            # Create Go project
            (path / "go.mod").write_text(f'module {project_name.lower().replace(" ", "-")}\n\ngo 1.21\n')
            (path / "main.go").write_text(f'package main\n\nimport "fmt"\n\nfunc main() {{\n    fmt.Println("Hello from {project_name}")\n}}\n')
            (path / "README.md").write_text(f"# {project_name}\n\nGo project\n")
            (path / ".gitignore").write_text("*.exe\n*.out\n")
        
        elif template_type == "web":
            # Create web project
            (path / "index.html").write_text(f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{project_name}</title>
    <link rel="stylesheet" href="style.css">
</head>
<body>
    <h1>Welcome to {project_name}</h1>
    <script src="script.js"></script>
</body>
</html>
''')
            (path / "style.css").write_text('body {\n    font-family: Arial, sans-serif;\n    margin: 0;\n    padding: 20px;\n}\n')
            (path / "script.js").write_text(f'console.log("Hello from {project_name}");\n')
            (path / "README.md").write_text(f"# {project_name}\n\nStatic website\n")
        
        elif template_type == "docker":
            # Create Docker project
            (path / "Dockerfile").write_text('FROM alpine:latest\nRUN apk add --no-cache bash\nCMD ["/bin/bash"]\n')
            (path / "docker-compose.yml").write_text(f'version: "3.8"\nservices:\n  app:\n    build: .\n    container_name: {project_name.lower().replace(" ", "_")}\n')
            (path / "README.md").write_text(f"# {project_name}\n\nDocker project\n")
            (path / ".dockerignore").write_text(".git\n.gitignore\nREADME.md\n")
        
        else:  # empty
            # Create empty project
            (path / "README.md").write_text(f"# {project_name}\n\nEmpty project\n")
    
    def add_project_to_config(self, project_path):
        """Add project to workspace config"""
        config_file = Path.home() / "workspace" / ".workspace_ide_config.json"
        
        try:
            if config_file.exists():
                with open(config_file, 'r') as f:
                    config = json.load(f)
            else:
                config = {}
            
            if 'active_projects' not in config:
                config['active_projects'] = []
            
            if project_path not in config['active_projects']:
                config['active_projects'].append(project_path)
            
            with open(config_file, 'w') as f:
                json.dump(config, f, indent=2)
        
        except Exception as e:
            raise Exception(f"Failed to update config: {e}")
    
    def create_projects_grid(self):
        """Create grid of project tiles"""
        widget = QWidget()
        widget.setStyleSheet("background: #A0A0A0;")
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(widget)
        scroll.setStyleSheet("QScrollArea { border: none; background: #A0A0A0; }")
        
        grid = QGridLayout(widget)
        grid.setSpacing(15)
        grid.setContentsMargins(15, 15, 15, 15)
        
        # Create project tiles
        row, col = 0, 0
        max_cols = 4
        
        for project in self.projects:
            tile = self.create_project_tile(project)
            grid.addWidget(tile, row, col)
            
            col += 1
            if col >= max_cols:
                col = 0
                row += 1
        
        # Add stretch to push tiles to top
        grid.setRowStretch(row + 1, 1)
        
        return scroll
    
    def create_project_tile(self, project):
        """Create individual project tile"""
        tile = QFrame()
        tile.setFixedSize(180, 200)
        tile.setStyleSheet(f"""
            QFrame {{
                background: white;
                border: 3px solid #666;
                border-right: 3px solid #333;
                border-bottom: 3px solid #333;
                border-radius: 4px;
            }}
            QFrame:hover {{
                border: 3px solid {project['color']};
                background: #F8F8F8;
            }}
        """)
        
        layout = QVBoxLayout(tile)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(5)
        
        # Icon
        icon_label = QLabel(project['icon'])
        icon_label.setStyleSheet("font-size: 52px; background: transparent; border: none;")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_label)
        
        # Project name
        name_label = QLabel(project['name'])
        name_label.setStyleSheet(f"font-weight: bold; font-size: 13px; color: {project['color']}; background: transparent; border: none;")
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_label.setWordWrap(True)
        layout.addWidget(name_label)
        
        # Project type
        type_label = QLabel(project['type'])
        type_label.setStyleSheet("font-size: 11px; color: #555; background: transparent; border: none;")
        type_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(type_label)
        
        # Stats
        stats_text = f"{project['stats']['files']} files • {project['stats']['size']}"
        stats_label = QLabel(stats_text)
        stats_label.setStyleSheet("font-size: 10px; color: #777; background: transparent; border: none;")
        stats_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(stats_label)
        
        layout.addStretch()
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        open_btn = QPushButton("Open")
        open_btn.setStyleSheet(self.get_button_style())
        open_btn.clicked.connect(lambda: self.open_project(project))
        btn_layout.addWidget(open_btn)
        
        terminal_btn = QPushButton("Terminal")
        terminal_btn.setStyleSheet(self.get_button_style())
        terminal_btn.clicked.connect(lambda: self.open_terminal(project))
        btn_layout.addWidget(terminal_btn)
        
        layout.addLayout(btn_layout)
        
        return tile
    
    def create_stats_widget(self):
        """Create statistics overview"""
        widget = QWidget()
        widget.setStyleSheet("background: #A0A0A0;")
        
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Summary
        summary_group = QGroupBox("Project Summary")
        summary_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 12px;
                border: 2px solid #666;
                margin-top: 10px;
                padding-top: 10px;
                background: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        
        summary_layout = QVBoxLayout(summary_group)
        
        # Count by type
        type_counts = {}
        for project in self.projects:
            ptype = project['type']
            type_counts[ptype] = type_counts.get(ptype, 0) + 1
        
        for ptype, count in sorted(type_counts.items(), key=lambda x: -x[1]):
            icon = self.get_project_icon(Path("dummy"))
            for p in self.projects:
                if p['type'] == ptype:
                    icon = p['icon']
                    break
            
            row = QHBoxLayout()
            row.addWidget(QLabel(f"{icon} {ptype}"))
            row.addStretch()
            
            count_label = QLabel(f"{count} project{'s' if count > 1 else ''}")
            count_label.setStyleSheet("color: #666; font-weight: normal;")
            row.addWidget(count_label)
            
            summary_layout.addLayout(row)
        
        layout.addWidget(summary_group)
        
        # Total stats
        total_group = QGroupBox("Total Statistics")
        total_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 12px;
                border: 2px solid #666;
                margin-top: 10px;
                padding-top: 10px;
                background: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        
        total_layout = QVBoxLayout(total_group)
        
        total_files = sum(p['stats']['files'] for p in self.projects)
        total_layout.addWidget(QLabel(f"📄 Total Files: {total_files:,}"))
        
        total_layout.addWidget(QLabel(f"📁 Total Projects: {len(self.projects)}"))
        
        total_layout.addWidget(QLabel(f"🗂️ Project Types: {len(type_counts)}"))
        
        layout.addWidget(total_group)
        
        layout.addStretch()
        
        return widget
    
    def get_button_style(self):
        """Get retro button style"""
        return """
            QPushButton {
                background: #C0C0C0;
                border: 2px solid white;
                border-right: 2px solid #808080;
                border-bottom: 2px solid #808080;
                padding: 4px 8px;
                color: black;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #D0D0D0;
            }
            QPushButton:pressed {
                border: 2px solid #808080;
                border-right: 2px solid white;
                border-bottom: 2px solid white;
                background: #A0A0A0;
            }
        """
    
    def open_project(self, project):
        """Open project in file explorer"""
        try:
            import platform
            system = platform.system()
            
            if system == 'Darwin':  # macOS
                subprocess.run(['open', project['path']])
            elif system == 'Windows':
                subprocess.run(['explorer', project['path']])
            else:  # Linux
                subprocess.run(['xdg-open', project['path']])
            
            self.status_bar.setText(f"Opened: {project['name']}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open project:\n{e}")
    
    def open_terminal(self, project):
        """Open terminal in project directory"""
        try:
            import platform
            system = platform.system()
            
            if system == 'Darwin':  # macOS
                script = f'tell app "Terminal" to do script "cd {project["path"]}"'
                subprocess.run(['osascript', '-e', script])
            elif system == 'Windows':
                subprocess.run(['cmd', '/k', 'cd', '/d', project['path']])
            else:  # Linux
                subprocess.Popen(['x-terminal-emulator'], cwd=project['path'])
            
            self.status_bar.setText(f"Terminal opened: {project['name']}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open terminal:\n{e}")
    
    def show_help(self):
        """Show help dialog"""
        help_text = """
<h2>🎨 Retro Project Launcher</h2>

<h3>Features:</h3>
<ul>
<li><b>Auto-Detection:</b> Automatically detects project types</li>
<li><b>Quick Launch:</b> Open projects or terminals with one click</li>
<li><b>Statistics:</b> View project summaries and stats</li>
<li><b>Retro Style:</b> Classic Visual Basic 6 inspired design</li>
</ul>

<h3>Supported Project Types:</h3>
<ul>
<li>🐍 Python (requirements.txt, setup.py, pyproject.toml)</li>
<li>📦 Node.js (package.json)</li>
<li>🐘 PHP (composer.json)</li>
<li>🦀 Rust (Cargo.toml)</li>
<li>🐹 Go (go.mod)</li>
<li>💎 Ruby (Gemfile)</li>
<li>☕ Java (pom.xml, build.gradle)</li>
<li>⚙️ C/C++ (CMakeLists.txt, Makefile)</li>
<li>🔷 C# / .NET (*.csproj, *.sln)</li>
<li>🐳 Docker (Dockerfile)</li>
<li>🌐 Web (index.html)</li>
</ul>

<h3>Tips:</h3>
<ul>
<li>Click "Open" to browse project files</li>
<li>Click "Terminal" to open command line in project</li>
<li>View "Statistics" tab for project overview</li>
<li>Enable projects in the Projects panel to see them here</li>
</ul>
"""
        
        msg = QMessageBox(self)
        msg.setWindowTitle("Help - Project Launcher")
        msg.setTextFormat(Qt.TextFormat.RichText)
        msg.setText(help_text)
        msg.setStyleSheet("""
            QMessageBox {
                background: #C0C0C0;
            }
            QLabel {
                color: black;
            }
            QPushButton {
                background: #C0C0C0;
                border: 2px solid white;
                border-right: 2px solid #808080;
                border-bottom: 2px solid #808080;
                padding: 4px 12px;
                min-width: 60px;
            }
        """)
        msg.exec()


def cleanup():
    pass


class NewProjectDialog(QDialog):
    """Dialog for creating a new project"""
    
    def __init__(self, template, parent=None):
        super().__init__(parent)
        self.template = template
        self.setWindowTitle(f"New {template['name']}")
        self.setMinimumWidth(500)
        self.setStyleSheet("""
            QDialog {
                background: #A0A0A0;
            }
            QLabel {
                color: black;
            }
            QLineEdit {
                background: white;
                color: black;
                border: 2px solid #666;
                padding: 5px;
                font-size: 12px;
            }
            QPushButton {
                background: #C0C0C0;
                color: black;
                border: 2px solid white;
                border-right: 2px solid #666;
                border-bottom: 2px solid #666;
                padding: 6px 12px;
                min-width: 70px;
                font-size: 12px;
            }
            QPushButton:pressed {
                border: 2px solid #666;
                border-right: 2px solid white;
                border-bottom: 2px solid white;
            }
        """)
        
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Header
        header = QLabel(f"{self.template['icon']} Create {self.template['name']}")
        header.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {self.template['color']};")
        layout.addWidget(header)
        
        desc = QLabel(self.template['desc'])
        desc.setStyleSheet("color: #666; margin-bottom: 15px;")
        layout.addWidget(desc)
        
        # Form
        form = QFormLayout()
        
        self.project_name = QLineEdit()
        self.project_name.setPlaceholderText("my-awesome-project")
        form.addRow("Project Name:", self.project_name)
        
        location_layout = QHBoxLayout()
        self.project_location = QLineEdit()
        self.project_location.setText(str(Path.home() / "workspace"))
        location_layout.addWidget(self.project_location)
        
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self.browse_location)
        location_layout.addWidget(browse_btn)
        
        form.addRow("Location:", location_layout)
        
        layout.addLayout(form)
        
        # Preview
        preview_group = QGroupBox("Project will be created at:")
        preview_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #808080;
                margin-top: 10px;
                padding-top: 10px;
            }
        """)
        preview_layout = QVBoxLayout(preview_group)
        
        self.preview_label = QLabel("")
        self.preview_label.setStyleSheet("color: #000080; font-family: monospace;")
        self.preview_label.setWordWrap(True)
        preview_layout.addWidget(self.preview_label)
        
        layout.addWidget(preview_group)
        
        # Update preview when name changes
        self.project_name.textChanged.connect(self.update_preview)
        self.project_location.textChanged.connect(self.update_preview)
        self.update_preview()
        
        layout.addStretch()
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        create_btn = QPushButton("Create")
        create_btn.clicked.connect(self.validate_and_accept)
        button_layout.addWidget(create_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
    
    def browse_location(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Project Location",
            self.project_location.text()
        )
        
        if folder:
            self.project_location.setText(folder)
    
    def update_preview(self):
        name = self.project_name.text().strip()
        location = self.project_location.text().strip()
        
        if name and location:
            full_path = Path(location) / name
            self.preview_label.setText(str(full_path))
        else:
            self.preview_label.setText("(enter project name)")
    
    def validate_and_accept(self):
        name = self.project_name.text().strip()
        location = self.project_location.text().strip()
        
        if not name:
            QMessageBox.warning(self, "Invalid Name", "Please enter a project name")
            return
        
        if not location:
            QMessageBox.warning(self, "Invalid Location", "Please select a location")
            return
        
        project_path = Path(location) / name
        
        if project_path.exists():
            reply = QMessageBox.question(
                self,
                "Project Exists",
                f"A folder named '{name}' already exists at this location.\n\nDo you want to use it anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply != QMessageBox.StandardButton.Yes:
                return
        
        self.accept()


def cleanup():
    pass