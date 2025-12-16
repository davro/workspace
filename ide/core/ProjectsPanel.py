from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QStyledItemDelegate,
)
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtCore import Qt, pyqtSignal

from ide import WORKSPACE_PATH



class ProjectHighlightDelegate(QStyledItemDelegate):
    """Custom delegate to highlight active projects in tree view"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.active_projects = set()

    def set_active_projects(self, projects):
        """Update list of active projects"""
        self.active_projects = set(str(Path(p).name) for p in projects)

    def paint(self, painter, option, index):
        """Custom paint to highlight active projects"""
        model = index.model()
        file_path = model.filePath(index)
        path = Path(file_path)

        parent_path = path.parent
        workspace_path = Path.home() / WORKSPACE_PATH

        is_project = (parent_path == workspace_path and
                     path.is_dir() and
                     path.name in self.active_projects)

        if is_project:
            painter.save()
            bg_color = QColor("#2D5A2D")
            painter.fillRect(option.rect, bg_color)
            painter.setPen(QColor("#7FFF7F"))
            text = index.data(Qt.ItemDataRole.DisplayRole)
            font = option.font
            font.setBold(True)
            painter.setFont(font)
            text_rect = option.rect.adjusted(5, 0, 0, 0)
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter, text)
            painter.restore()
        else:
            super().paint(painter, option, index)


# ---------------------- Projects Panel ----------------------
class ProjectsPanel(QWidget):
    """Panel showing workspace projects that can be activated"""

    project_selected = pyqtSignal(str)
    projects_changed = pyqtSignal()

    def __init__(self, workspace_path, parent=None):
        super().__init__(parent)
        self.workspace_path = workspace_path
        self.active_projects = set()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        header = QHBoxLayout()
        title = QLabel("Active Projects")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        header.addWidget(title)

        refresh_btn = QPushButton("↻")
        refresh_btn.setFixedWidth(30)
        refresh_btn.setToolTip("Refresh project list")
        refresh_btn.clicked.connect(self.scan_projects)
        header.addWidget(refresh_btn)

        layout.addLayout(header)

        self.info_label = QLabel("Check projects to include in Quick Open (Ctrl+P)")
        self.info_label.setStyleSheet("color: #999; font-size: 10px;")
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)

        self.projects_list = QListWidget()
        self.projects_list.itemChanged.connect(self.on_project_toggled)
        layout.addWidget(self.projects_list)

        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet("color: #666; font-size: 10px;")
        layout.addWidget(self.stats_label)

        self.scan_projects()

    def scan_projects(self):
        """Scan workspace for project directories"""
        self.projects_list.clear()

        if not self.workspace_path.exists():
            return

        projects = []
        for item in self.workspace_path.iterdir():
            if item.is_dir() and not item.name.startswith('.'):
                projects.append(item)

        projects.sort(key=lambda p: p.name.lower())

        for project_path in projects:
            item = QListWidgetItem(project_path.name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)

            if str(project_path) in self.active_projects:
                item.setCheckState(Qt.CheckState.Checked)
            else:
                item.setCheckState(Qt.CheckState.Unchecked)

            item.setData(Qt.ItemDataRole.UserRole, str(project_path))

            try:
                file_count = sum(1 for _ in project_path.rglob('*') if _.is_file())
                item.setToolTip(f"{project_path}\n~{file_count} files")
            except:
                item.setToolTip(str(project_path))

            self.projects_list.addItem(item)

        self.update_stats()

    def on_project_toggled(self, item):
        """Handle project checkbox toggle"""
        project_path = item.data(Qt.ItemDataRole.UserRole)

        if item.checkState() == Qt.CheckState.Checked:
            self.active_projects.add(project_path)
        else:
            self.active_projects.discard(project_path)

        self.update_stats()
        self.project_selected.emit(project_path)
        self.projects_changed.emit()

    def update_stats(self):
        """Update statistics label"""
        total = self.projects_list.count()
        active = len(self.active_projects)
        self.stats_label.setText(f"{active} of {total} projects active")

    def get_active_projects(self):
        """Get list of active project paths"""
        return list(self.active_projects)

    def set_active_projects(self, projects):
        """Set which projects are active"""
        self.active_projects = set(projects)
        for i in range(self.projects_list.count()):
            item = self.projects_list.item(i)
            project_path = item.data(Qt.ItemDataRole.UserRole)
            if project_path in self.active_projects:
                item.setCheckState(Qt.CheckState.Checked)
            else:
                item.setCheckState(Qt.CheckState.Unchecked)
        self.update_stats()
        self.projects_changed.emit()