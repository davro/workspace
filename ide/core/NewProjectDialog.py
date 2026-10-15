"""Dialog for creating / initialising a project from a template provider."""
from __future__ import annotations

import shutil
from pathlib import Path

from PyQt6.QtCore import QProcess, pyqtSignal
from PyQt6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout,
                             QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPlainTextEdit,
                             QPushButton, QVBoxLayout)

from .ProjectManager import ProjectManager
from .ProjectTemplateRegistry import ProjectProvider, ProjectSpec


class NewProjectDialog(QDialog):
    """Collects options, shows a live preview, writes files, then runs commands."""

    project_created = pyqtSignal(str)  # emitted with the project directory

    def __init__(self, manager: ProjectManager, directory=None, parent=None,
                 in_place: bool = False):
        """directory: the parent folder for the new project (default: the workspace).

        in_place=True means `directory` is itself the project root (e.g. launched
        from an empty directory's context menu), so no subfolder is created and
        the name defaults to the directory's name.
        """
        super().__init__(parent)
        self._in_place = in_place
        self.manager = manager
        self.registry = manager.registry
        self.process: QProcess | None = None
        self.queue = []
        self.created_path: str | None = None
        self._busy = False
        self.setWindowTitle("New Project")
        self.resize(640, 680)
        directory = directory or manager.workspace_path
        self._build_ui(directory)
        if in_place:
            self.name_edit.setText(Path(directory).name)
        self._language_changed()

    # ---------------------------------------------------------------- UI
    def _build_ui(self, directory):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("my-project")
        self.name_edit.textChanged.connect(self._refresh_preview)
        form.addRow("Project name", self.name_edit)

        row = QHBoxLayout()
        self.dir_edit = QLineEdit(str(directory))
        self.dir_edit.textChanged.connect(self._refresh_preview)
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse)
        row.addWidget(self.dir_edit, 1)
        row.addWidget(browse)
        form.addRow("Location", row)

        self.subfolder_check = QCheckBox("Create a subfolder named after the project")
        self.subfolder_check.setChecked(not self._in_place)
        self.subfolder_check.toggled.connect(self._refresh_preview)
        form.addRow("", self.subfolder_check)

        self.description_edit = QLineEdit()
        self.description_edit.textChanged.connect(self._refresh_preview)
        form.addRow("Description", self.description_edit)

        self.language_combo = QComboBox()
        self.language_combo.addItems(self.registry.languages())
        self.language_combo.currentIndexChanged.connect(self._language_changed)
        form.addRow("Language", self.language_combo)

        self.tool_combo = QComboBox()
        self.tool_combo.currentIndexChanged.connect(self._refresh_preview)
        form.addRow("Package manager / build system", self.tool_combo)
        layout.addLayout(form)

        self.tests_check = QCheckBox("Include a basic testing setup")
        self.tests_check.setChecked(True)
        self.git_check = QCheckBox("Initialise Git repository")
        self.git_check.setChecked(True)
        self.install_check = QCheckBox("Run follow-up setup (install dependencies, create venv, …)")
        for box in (self.tests_check, self.git_check, self.install_check):
            box.toggled.connect(self._refresh_preview)
            layout.addWidget(box)

        layout.addWidget(QLabel("Planned initialisation"))
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setMaximumHeight(190)
        layout.addWidget(self.preview)

        layout.addWidget(QLabel("Output"))
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        layout.addWidget(self.output, 1)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.create_button = QPushButton("Create project")
        self.create_button.setDefault(True)
        self.create_button.clicked.connect(self._create)
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.reject)
        buttons.addWidget(self.create_button)
        buttons.addWidget(self.close_button)
        layout.addLayout(buttons)

    def _browse(self):
        chosen = QFileDialog.getExistingDirectory(self, "Select project directory", self.dir_edit.text())
        if chosen:
            self.dir_edit.setText(chosen)

    def _language_changed(self, *_):
        self.tool_combo.blockSignals(True)
        self.tool_combo.clear()
        for provider in self.registry.for_language(self.language_combo.currentText()):
            self.tool_combo.addItem(provider.label, provider.id)
        self.tool_combo.blockSignals(False)
        self._refresh_preview()

    # ---------------------------------------------------------------- state
    def _provider(self) -> ProjectProvider | None:
        return self.registry.get(self.tool_combo.currentData() or "")

    def _root(self) -> Path:
        """The project directory: <location>/<name>, or <location> when in place."""
        base = Path(self.dir_edit.text().strip() or ".").expanduser()
        name = self.name_edit.text().strip()
        if self.subfolder_check.isChecked() and name:
            return base / name
        return base

    def _spec(self) -> ProjectSpec:
        return ProjectSpec(
            name=self.name_edit.text().strip(),
            directory=self._root(),
            description=self.description_edit.text().strip(),
            include_tests=self.tests_check.isChecked(),
            init_git=self.git_check.isChecked(),
            run_install=self.install_check.isChecked(),
        )

    def _refresh_preview(self, *_):
        provider, spec = self._provider(), self._spec()
        lines, blocked = [], False
        if provider is None:
            self.preview.setPlainText("No project templates are available.")
            self.create_button.setEnabled(False)
            return

        shown = spec.directory if (spec.name or not self.subfolder_check.isChecked()) \
            else spec.directory / "<name>"
        lines.append(f"Name: {spec.name or '—'}")
        lines.append(f"Project path: {shown}")
        lines.append(f"Ecosystem: {provider.language} · {provider.label}")
        lines.append(f"Tests: {'included' if spec.include_tests else 'none'} · "
                     f"Git: {'initialised' if spec.init_git else 'not initialised'}")

        problem = (provider.validate_name(spec.name) if spec.name else "Enter a project name.") \
            or self.manager.check_directory(spec.directory) \
            or self.manager.check_location(spec.directory)
        if problem:
            lines += ["", f"⚠ {problem}"]
            blocked = True
        else:
            plan = self.manager.build_plan(provider, spec)
            conflicts = self.manager.conflicts(plan, spec.directory)
            if conflicts:
                lines += ["", "⚠ These files already exist and will not be overwritten:"]
                lines += [f"    {rel}" for rel in conflicts]
                blocked = True
            lines += ["", "Files:"] + [f"    {rel}" for rel in sorted(plan.files)]
            if plan.commands:
                lines += ["", "Commands:"] + [f"    $ {c.text}" for c in plan.commands]
            missing = provider.missing_tools()
            if missing:
                lines += ["", f"ℹ Not found on PATH: {', '.join(missing)}. "
                              "Files will still be created; commands needing them are skipped."]
        self.preview.setPlainText("\n".join(lines))
        self.create_button.setEnabled(not blocked and not self._busy)

    # ---------------------------------------------------------------- create
    def _log(self, text: str):
        self.output.appendPlainText(text)

    def _set_busy(self, busy: bool):
        self._busy = busy
        self.create_button.setEnabled(False)
        for widget in (self.name_edit, self.dir_edit, self.subfolder_check,
                       self.language_combo, self.tool_combo):
            widget.setEnabled(not busy)

    def _create(self):
        provider, spec = self._provider(), self._spec()
        if provider is None:
            return
        plan = self.manager.build_plan(provider, spec)
        try:
            written = self.manager.write_files(plan, spec.directory)
        except (OSError, ValueError) as exc:
            QMessageBox.critical(self, "New Project", f"Could not create the project:\n{exc}")
            return
        self.created_path = str(spec.directory.expanduser().resolve())
        self._log(f"Created {len(written)} files in {self.created_path}")
        self.queue = list(plan.commands)
        self._set_busy(True)
        self._run_next()

    def _run_next(self):
        if not self.queue:
            self._finish()
            return
        command = self.queue.pop(0)
        if shutil.which(command.program) is None:
            self._log(f"\n[Skipped '{command.text}': '{command.program}' not found on PATH]")
            self._run_next()
            return
        self._log(f"\n$ {command.text}")
        process = QProcess(self)
        process.setWorkingDirectory(self.created_path)
        process.setProgram(command.program)
        process.setArguments(list(command.args))
        process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        process.readyReadStandardOutput.connect(self._read_output)
        process.finished.connect(self._command_finished)
        process.errorOccurred.connect(self._command_error)
        self.process = process
        process.start()

    def _read_output(self):
        if self.process:
            text = bytes(self.process.readAllStandardOutput()).decode("utf-8", errors="replace")
            if text:
                self.output.moveCursor(self.output.textCursor().MoveOperation.End)
                self.output.insertPlainText(text)

    def _command_finished(self, code, status):
        self._read_output()
        ok = code == 0 and status == QProcess.ExitStatus.NormalExit
        self._log("[done]" if ok else f"[failed, exit code {code}]")
        if self.process:
            self.process.deleteLater()
        self.process = None
        self._run_next()

    def _command_error(self, error):
        # FailedToStart never emits finished(), so advance the queue here.
        if error == QProcess.ProcessError.FailedToStart and self.process:
            self._log(f"[Could not start: {self.process.errorString()}]")
            self.process.deleteLater()
            self.process = None
            self._run_next()

    def _finish(self):
        self._set_busy(False)
        self.create_button.setEnabled(False)  # project exists now; preview will flag conflicts
        self._log("\nProject ready.")
        if self.created_path:
            self.project_created.emit(self.created_path)

    def reject(self):
        if self.process and self.process.state() != QProcess.ProcessState.NotRunning:
            self.process.kill()
            self.process.waitForFinished(1000)
        super().reject()