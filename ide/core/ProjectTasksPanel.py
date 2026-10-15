"""Sidebar panel for discovering and running project tasks asynchronously."""
from __future__ import annotations
import shlex
import re
from pathlib import Path
from PyQt6.QtCore import QProcess, QTimer, Qt
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QListWidget, QListWidgetItem, QPlainTextEdit, QMessageBox, QSplitter, QGroupBox)
from .ProjectTaskManager import ProjectTaskManager, ProjectTask
from .ProjectManager import ProjectManager
from .NewProjectDialog import NewProjectDialog


class ProjectTasksPanel(QWidget):

    def __init__(self, workspace_path, parent=None, projects_panel=None):

        super().__init__(parent)

        self.workspace_path = Path(workspace_path).expanduser().resolve()
        self.manager = ProjectTaskManager(self.workspace_path)
        self.project_manager = ProjectManager(self.workspace_path)

        # Reference to the Projects tab.
        self.projects_panel = projects_panel
        self.projects = []
        self.process = None
        self.active_task = None
        self.stop_timer = None
        self._build_ui()

        # Refresh when activated projects change.
        if self.projects_panel is not None:
            self.projects_panel.projects_changed.connect(
                self._projects_changed
            )

        self.refresh_projects()

    def _projects_changed(self, *args):
        """Refresh tasks when the activated project list changes."""
        self.refresh_projects()

    def new_project(self, directory=None, in_place=None):
        """Open the New Project wizard.

        With no directory the project is created as <workspace>/<name>. When a
        directory is given (e.g. from the file explorer's context menu) it is
        initialised in place, unless in_place=False asks for a subfolder of it.
        """
        if in_place is None:
            in_place = directory is not None
        dialog = NewProjectDialog(
            self.project_manager, directory or self.workspace_path, self,
            in_place=in_place,
        )
        dialog.project_created.connect(self._project_created)
        dialog.exec()

    def _project_created(self, path):
        """Activate a freshly created project so its tasks appear here."""
        activate = getattr(self.projects_panel, "activate_project", None)
        if callable(activate):
            # activate_project() emits projects_changed, which refreshes us.
            activate(path)
        else:
            self.refresh_projects()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        header = QHBoxLayout()
        header.addWidget(QLabel("Project tasks"))
        header.addStretch(1)
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh_projects)
        header.addWidget(self.refresh_button)
        self.new_button = QPushButton("New…")
        self.new_button.setToolTip("Create or initialise a project")
        self.new_button.clicked.connect(lambda: self.new_project())
        header.addWidget(self.new_button)
        layout.addLayout(header)
        self.project_combo = QComboBox()
        self.project_combo.currentIndexChanged.connect(self._project_changed)
        layout.addWidget(self.project_combo)
        self.type_label = QLabel("Detecting projects…")
        self.type_label.setWordWrap(True)
        layout.addWidget(self.type_label)
        split = QSplitter(Qt.Orientation.Vertical)
        self.task_list = QListWidget()
        self.task_list.itemDoubleClicked.connect(lambda _item: self.run_selected_task())
        self.task_list.currentRowChanged.connect(lambda _row: self._update_controls())
        split.addWidget(self.task_list)
        group = QGroupBox("Output")
        output_layout = QVBoxLayout(group)
        status_row = QHBoxLayout()
        self.status_label = QLabel("Idle")
        status_row.addWidget(self.status_label, 1)
        clear = QPushButton("Clear")
        clear.clicked.connect(lambda: self.output.clear())
        status_row.addWidget(clear)
        output_layout.addLayout(status_row)
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        output_layout.addWidget(self.output)
        split.addWidget(group)
        split.setSizes([180, 240])
        layout.addWidget(split, 1)
        buttons = QHBoxLayout()
        self.run_button = QPushButton("Run")
        self.run_button.clicked.connect(self.run_selected_task)
        buttons.addWidget(self.run_button)
        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(self.stop_task)
        self.stop_button.setEnabled(False)
        buttons.addWidget(self.stop_button)
        layout.addLayout(buttons)

    def refresh_projects(self):
        """Display tasks only for projects activated in the Projects tab."""
    
        previous = self.project_combo.currentData()
    
        self.projects = []
    
        # Use the Projects tab as the source of truth.
        if self.projects_panel is not None:
            active_projects = self.projects_panel.get_active_projects()
    
            for item in active_projects:
                # Support project paths returned as strings or Path objects.
                if isinstance(item, (str, Path)):
                    project_path = Path(item)
                else:
                    # Support project objects with a path attribute.
                    project_path = getattr(item, "path", None)
    
                    if project_path is None:
                        continue
    
                    project_path = Path(project_path)
    
                # Resolve relative paths against the workspace root.
                if not project_path.is_absolute():
                    project_path = self.workspace_path / project_path
    
                project_path = project_path.expanduser().resolve()
    
                # Only include existing directories.
                if not project_path.is_dir():
                    continue
    
                # Inspect the activated project for supported tasks.
                project = self.manager.inspect_project(project_path)
    
                if project is not None:
                    self.projects.append(project)
    
        self.project_combo.blockSignals(True)
        self.project_combo.clear()
    
        for project in self.projects:
            try:
                relative = project.path.relative_to(self.workspace_path)
                label = f"{project.name} — {relative}"
            except ValueError:
                label = str(project.path)
    
            self.project_combo.addItem(label, str(project.path))
    
        # Restore the previously selected project if it remains active.
        if previous:
            idx = self.project_combo.findData(previous)
            if idx >= 0:
                self.project_combo.setCurrentIndex(idx)
    
        self.project_combo.blockSignals(False)
    
        if self.projects:
            self._project_changed(self.project_combo.currentIndex())
        else:
            self.task_list.clear()
            self.type_label.setText(
                "No active projects with supported task configurations."
            )
    
        self._update_controls()

    def _project_changed(self, index):
        self.task_list.clear()
        if index < 0 or index >= len(self.projects):
            self.type_label.setText("No project selected")
            self._update_controls()
            return
        project = self.projects[index]
        self.type_label.setText(project.type_label)
        for task in project.tasks:
            item = QListWidgetItem(f"[{task.category}] {task.name}")
            item.setData(Qt.ItemDataRole.UserRole, task)
            item.setToolTip(f"{task.description}\n{task.command_text}\nWorking directory: {task.project_path}")
            self.task_list.addItem(item)
        if not project.tasks:
            self.task_list.addItem("No runnable tasks detected")
        self._update_controls()

    def get_tasks_for_directory(self, path):
        return self.manager.tasks_for_directory(path)

    def run_task_for_directory(self, path, task_name=None):
        tasks = self.manager.tasks_for_directory(path)
        task = next((x for x in tasks if x.name == task_name), None) if task_name else None
        if task:
            self._start_task(task)
            return
        if not tasks:
            QMessageBox.information(self, "Project Tasks", "No runnable tasks were found in this directory.")
            return
        resolved = str(Path(path).resolve())
        index = self.project_combo.findData(resolved)
        if index < 0:
            self.refresh_projects()
            index = self.project_combo.findData(resolved)
        if index >= 0:
            self.project_combo.setCurrentIndex(index)
        self.show()
        for row in range(self.task_list.count()):
            if self.task_list.item(row).data(Qt.ItemDataRole.UserRole):
                self.task_list.setCurrentRow(row)
                break
        self.run_selected_task()

    def run_selected_task(self):
        item = self.task_list.currentItem()
        task = item.data(Qt.ItemDataRole.UserRole) if item else None
        if isinstance(task, ProjectTask):
            self._start_task(task)
        else:
            QMessageBox.information(self, "Project Tasks", "Select a runnable task first.")

    def _start_task(self, task):
        if self.process and self.process.state() != QProcess.ProcessState.NotRunning:
            QMessageBox.warning(self, "Task already running", "Stop the active task before starting another.")
            return
        program = task.program
        if "/" in program:
            candidate = task.project_path / program
            if candidate.exists():
                program = str(candidate)
            elif program.startswith("vendor/"):
                QMessageBox.warning(self, "Executable not found", f"Local executable not found:\n{candidate}")
                return
        command = shlex.join((program, *task.args))
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Run project task?")
        box.setText(f"Run '{task.name}'?")
        box.setInformativeText(f"Command:\n{command}\n\nWorking directory:\n{task.project_path}\n\nProject tasks may execute arbitrary code.")
        box.setStandardButtons(QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Yes)
        box.setDefaultButton(QMessageBox.StandardButton.Cancel)
        if box.exec() != QMessageBox.StandardButton.Yes:
            return
        self.output.appendPlainText(f"\n$ {command}\n[Working directory: {task.project_path}]\n")
        self.status_label.setText(f"Running: {task.name}")
        self.active_task = task
        self.process = QProcess(self)
        self.process.setWorkingDirectory(str(task.project_path))
        self.process.setProgram(program)
        self.process.setArguments(list(task.args))
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
        self.process.readyReadStandardOutput.connect(self._read_stdout)
        self.process.readyReadStandardError.connect(self._read_stderr)
        self.process.finished.connect(self._finished)
        self.process.errorOccurred.connect(self._error)
        self._update_controls()
        self.process.start()

    # def _append(self, data):
        # if data:
            # self.output.moveCursor(self.output.textCursor().MoveOperation.End)
            # self.output.insertPlainText(bytes(data).decode("utf-8", errors="replace"))
            # self.output.ensureCursorVisible()


    def _append(self, data):
        """Append process output after removing ANSI terminal formatting."""
    
        if not data:
            return
    
        # Decode process output.
        text = bytes(data).decode("utf-8", errors="replace")
    
        # Remove ANSI colour and formatting escape sequences.
        text = self._strip_ansi_codes(text)
    
        if text:
            self.output.moveCursor(
                self.output.textCursor().MoveOperation.End
            )
            self.output.insertPlainText(text)
            self.output.ensureCursorVisible()

    def _read_stdout(self):
        if self.process:
            self._append(self.process.readAllStandardOutput())

    def _read_stderr(self):
        if self.process:
            self._append(self.process.readAllStandardError())

    def _finished(self, code, status):
        self._read_stdout()
        self._read_stderr()
        result = f"finished (exit code {code})" if code == 0 and status == QProcess.ExitStatus.NormalExit else f"failed/stopped (exit code {code})"
        name = self.active_task.name if self.active_task else "Task"
        self.output.appendPlainText(f"\n[Task {result}]\n")
        self.status_label.setText(f"{name}: {result}")
        self.process = None
        self.active_task = None
        if self.stop_timer:
            self.stop_timer.stop()
        self._update_controls()

    def _error(self, error):
        if error == QProcess.ProcessError.FailedToStart and self.process:
            self.output.appendPlainText(f"\n[Could not start: {self.process.errorString()}]\n")
            self.status_label.setText("Failed to start")
            self.process = None
            self.active_task = None
            self._update_controls()

    def stop_task(self):
        if not self.process or self.process.state() == QProcess.ProcessState.NotRunning:
            return
        self.status_label.setText("Stopping…")
        self.process.terminate()
        self.stop_timer = QTimer(self)
        self.stop_timer.setSingleShot(True)
        self.stop_timer.timeout.connect(self._kill_if_running)
        self.stop_timer.start(2000)

    def _kill_if_running(self):
        if self.process and self.process.state() != QProcess.ProcessState.NotRunning:
            self.process.kill()

    def _update_controls(self):
        running = bool(self.process and self.process.state() != QProcess.ProcessState.NotRunning)
        item = self.task_list.currentItem()
        selected = bool(item and isinstance(item.data(Qt.ItemDataRole.UserRole), ProjectTask))
        self.run_button.setEnabled(not running and selected)
        self.stop_button.setEnabled(running)
        self.refresh_button.setEnabled(not running)
        self.new_button.setEnabled(not running)
        self.project_combo.setEnabled(not running)

    def close_running_task(self):
        if self.process and self.process.state() != QProcess.ProcessState.NotRunning:
            self.process.kill()
            self.process.waitForFinished(1000)
            self.process = None
            self.active_task = None

    def _strip_ansi_codes(self, text):
        """Remove ANSI terminal colour and formatting sequences."""
        ansi_pattern = re.compile(
            r'\x1B(?:'
            r'\[[0-?]*[ -/]*[@-~]'
            r'|[@-_]'
            r')'
        )
        return ansi_pattern.sub('', text)