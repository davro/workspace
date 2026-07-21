# InfrastructurePlugin/InfrastructureWidget.py

"""
InfrastructureWidget - the plugin's UI.

Layout: a tab strip (Overview / Kubernetes / Terraform) sitting above a
single shared console. Every command, whatever tab it was launched from,
streams into that one console - so there's one place to watch, and no
risk of a long-running `terraform apply` silently keeping the UI locked
while you've clicked over to another tab.
"""

from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit,
    QGroupBox, QSpinBox, QListWidget, QTabWidget, QLineEdit, QSplitter,
    QMessageBox, QListWidgetItem, QComboBox
)
from PyQt6.QtCore import Qt

from InfrastructurePlugin.ProcessRunner import ProcessRunner, run_quick
from InfrastructurePlugin.ProjectDetector import ProjectDetector
from InfrastructurePlugin.KubernetesManager import KubernetesManager
from InfrastructurePlugin.TerraformManager import TerraformManager


def _button(text):
    btn = QPushButton(text)
    btn.setStyleSheet("""
        QPushButton { padding: 6px 14px; background: #3C3F41;
                      border: 1px solid #555; border-radius: 3px; }
        QPushButton:hover { background: #4A4A4A; }
        QPushButton:disabled { color: #777; }
    """)
    return btn


def _group(title):
    box = QGroupBox(title)
    box.setStyleSheet("""
        QGroupBox { font-weight: bold; border: 1px solid #555;
                    border-radius: 5px; margin-top: 10px; padding-top: 10px; }
        QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left;
                            padding: 0 5px; color: #4A9EFF; }
    """)
    return box


class InfrastructureWidget(QWidget):

    def __init__(self, plugin, parent=None):
        super().__init__(parent)
        self.plugin = plugin
        self.api = plugin.api
        self._runner = None  # currently active ProcessRunner, if any
        # None = follow whatever the IDE considers the "open" project
        # (via get_workspace_path()). Set once the user picks something
        # from the Active Project dropdown, and from then on that
        # explicit choice wins over the IDE's own notion of "current".
        self._explicit_project_path = None

        self.detector = ProjectDetector(self._project_path())
        self.detection = self.detector.detect()
        self.tools = ProjectDetector.detect_tools()

        self._build_ui()
        self._connect_projects_panel()
        self._populate_project_combo()
        self.refresh_overview()
        self.refresh_pods()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _project_path(self):
        try:
            path = self.api.get_workspace_path()
            raw = Path(path) if path else Path.cwd()
        except Exception:
            raw = Path.cwd()
        # get_workspace_path() can return a path with an un-resolved ".."
        # segment (seen in practice). is_dir()/exists() checks handle that
        # fine since the OS resolves it, but leaving it in place makes the
        # Scanning Path debug label misleading - resolve() collapses it to
        # a clean absolute path instead.
        try:
            return raw.resolve()
        except Exception:
            return raw

    def _get_projects_panel(self):
        """
        Returns the IDE's ProjectsPanel instance if one exists, else None.
        Defensive on purpose - get_main_window()/projects_panel aren't
        part of the formal plugin API contract, just an implementation
        detail of the current Workspace class, so this degrades to the
        old single-project behavior rather than crashing if either is
        ever renamed or missing.
        """
        try:
            main_window = self.api.get_main_window()
            return getattr(main_window, "projects_panel", None)
        except Exception:
            return None

    def _connect_projects_panel(self):
        panel = self._get_projects_panel()
        if panel is None:
            return
        try:
            panel.projects_changed.connect(lambda: self._populate_project_combo(keep_selection=True))
        except Exception:
            pass

    def _populate_project_combo(self, keep_selection=False):
        """
        Fills the Active Project dropdown from ProjectsPanel's checked
        projects. Falls back to a single entry for the IDE's current
        workspace if the panel isn't available or nothing's checked -
        that keeps this plugin working exactly as before for anyone not
        using the Projects panel feature.
        """
        panel = self._get_projects_panel()
        active = []
        if panel:
            try:
                active = panel.get_active_projects()
            except Exception:
                active = []

        previous_path = self.project_combo.currentData() if keep_selection else None

        self.project_combo.blockSignals(True)
        self.project_combo.clear()

        if not active:
            fallback = self._project_path()
            self.project_combo.addItem(f"{fallback.name}  (current workspace)", str(fallback))
        else:
            current_workspace = str(self._project_path())
            for p in sorted(active, key=lambda x: Path(x).name.lower()):
                self.project_combo.addItem(Path(p).name, p)
            # Prefer keeping whatever was already selected (e.g. the
            # Projects panel just added/removed an unrelated project),
            # else the IDE's current workspace if it happens to be
            # checked, else just the first one alphabetically.
            target = previous_path if previous_path in active else (
                current_workspace if current_workspace in active else active[0]
            )
            idx = self.project_combo.findData(target)
            if idx >= 0:
                self.project_combo.setCurrentIndex(idx)

        self.project_combo.blockSignals(False)
        # Sync the detector to whatever ended up selected - refresh_overview
        # is called separately by whoever triggered this (init, or the
        # dropdown's own change handler), so don't double-refresh here.
        self._apply_selected_project(refresh=False)

    def _apply_selected_project(self, refresh=True):
        data = self.project_combo.currentData()
        if not data:
            return
        self._explicit_project_path = Path(data)
        # Switching projects should re-autofill the cluster name and
        # Terraform directory for the NEW project, not keep whatever was
        # typed/selected for the previous one. clearEditText() (not
        # clear()!) - clear() on a QComboBox wipes its whole item list,
        # which would blow away the cluster dropdown's contents instead
        # of just resetting the current selection/typed text.
        self.cluster_name_edit.clearEditText()
        self.tf_dir_edit.clear()
        self._populate_cluster_list()
        if refresh:
            self.refresh_overview()

    def log(self, message):
        self.console.append(message)

    def _on_tab_changed(self, index):
        """
        Keep each tab's data current without requiring a manual refresh
        click first - most noticeably, the pod list previously stayed
        empty until Refresh Pods was clicked, even right after switching
        onto the Kubernetes tab. Indices match the fixed addTab() order
        in _build_ui(): 0=Overview, 1=Kubernetes, 2=Terraform.
        """
        if index == 0:
            self.refresh_overview()
        elif index == 1:
            self.refresh_pods()
            self._populate_cluster_list()

    def _populate_cluster_list(self):
        """
        Populates the cluster name combo from `k3d cluster list`. This is
        a GLOBAL list of every k3d cluster on the machine, not scoped to
        the currently selected project - the plugin has no reliable way
        to know which cluster "belongs" to which project beyond the
        `workspace-<project>` naming convention it suggests but doesn't
        enforce (nothing stops someone naming a cluster anything they
        like). Showing everything and letting the user pick an existing
        one, or type a brand new name to create one, is the honest option
        rather than guessing at a filter that could hide a cluster they
        actually want.

        Cheap enough to call on tab switch / project switch / after
        create-delete - `k3d cluster list` normally returns in well under
        a second, same class of call as the daemon check.
        """
        current_text = self.cluster_name_edit.currentText()
        self.cluster_name_edit.blockSignals(True)
        self.cluster_name_edit.clear()

        if self.tools.get("k3d"):
            code, output = run_quick(KubernetesManager.list_clusters_command(), timeout=5)
            if code == 0:
                for c in KubernetesManager.parse_cluster_list(output):
                    self.cluster_name_edit.addItem(c["name"])

        # Restore whatever was typed/selected before repopulating - this
        # is what lets a user keep typing a brand-new cluster name across
        # a background refresh instead of having it wiped out from under them.
        self.cluster_name_edit.setEditText(current_text)
        self.cluster_name_edit.blockSignals(False)

    def _busy(self, is_busy):
        """Disable action buttons while a command is running so two
        infra commands can't collide (e.g. two `terraform apply`s)."""
        for btn in self._action_buttons:
            btn.setEnabled(not is_busy)

    def run_command(self, command, cwd=None, on_finished=None, label=None):
        """Dispatch a command through ProcessRunner and stream it to the
        shared console. Refuses to start a second command concurrently."""
        if self._runner is not None:
            self.log("[!] A command is already running - wait for it to finish.")
            return

        self.log(f"$ {' '.join(command)}")
        self._busy(True)
        self._runner = ProcessRunner(command, cwd=cwd, label=label, parent=self)
        self._runner.line_ready.connect(self.log)

        def _done(code):
            self.log(f"[exit code {code}]\n")
            self._runner = None
            self._busy(False)
            if on_finished:
                on_finished(code)

        self._runner.finished_ok.connect(_done)
        self._runner.start()

    def shutdown(self):
        """
        Must be called before this widget is destroyed (the plugin's
        cleanup() does this). Blocks briefly to guarantee no QThread is
        still running when Qt tears the widget down - destroying a
        running QThread is a hard, unrecoverable Qt-level abort
        ("QThread: Destroyed while thread is still running"), not
        something a try/except can catch afterward. Cluster-create can
        legitimately take 30-50+ seconds, so this can genuinely have
        something to wait for, not just a formality.
        """
        if self._runner is None:
            return
        self.log("[!] Stopping in-flight command before shutdown...")
        self._runner.cancel()
        if not self._runner.wait(5000):
            # cancel() already tried terminate() then kill() on the
            # subprocess itself - if the QThread STILL hasn't exited
            # after 5s, something is stuck reading a pipe that will
            # never close. Give it one more grace period; if that also
            # fails there's nothing safe left to do but proceed, since
            # blocking the whole IDE shutdown indefinitely is worse.
            self._runner.wait(3000)
        self._runner = None

    def closeEvent(self, event):
        # Defense in depth: if the IDE ever tears this widget down through
        # a path that doesn't go through the plugin's cleanup() hook (e.g.
        # closing the sidebar tab directly rather than a full plugin
        # unload), this still catches it before Qt destroys the widget.
        self.shutdown()
        super().closeEvent(event)

    def _confirm(self, title, message):
        reply = QMessageBox.question(
            self, title, message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return reply == QMessageBox.StandardButton.Yes

    def _daemon_ready(self):
        """
        Pre-flight check before any k3d/docker-dependent action. k3d's own
        error output when the daemon is down is a multi-line stack of
        "Failed Cluster Preparation" / "FAILED to rollback" noise - this
        catches the same condition in ~1 command and gives one clear line
        with the actual fix instead.
        """
        status = ProjectDetector.container_runtime_status()
        if not status["installed"]:
            self.log("[!] No container runtime (Docker or Podman) found on PATH. "
                      "k3d needs one to run.")
            return False
        if not status["daemon_running"]:
            hint = ProjectDetector.daemon_start_hint(status["runtime"], status["permission_denied"])
            self.log(f"[!] {status['runtime']} is installed but its daemon isn't reachable. {hint}")
            return False
        return True

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        layout = QVBoxLayout(self)

        header = QLabel(f"{self.plugin.PLUGIN_ICON} {self.plugin.PLUGIN_NAME}")
        header.setStyleSheet("font-size: 18px; font-weight: bold; color: #4A9EFF; padding: 6px;")
        layout.addWidget(header)

        splitter = QSplitter(Qt.Orientation.Vertical)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_overview_tab(), "\U0001F4CB Overview")
        self.tabs.addTab(self._build_kubernetes_tab(), "\u2638 Kubernetes")
        self.tabs.addTab(self._build_terraform_tab(), "\U0001F5FA Terraform")
        self.tabs.currentChanged.connect(self._on_tab_changed)
        splitter.addWidget(self.tabs)

        console_box = _group("Console")
        console_layout = QVBoxLayout(console_box)
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setStyleSheet("""
            background: #1E1E1E; color: #CCC; border: 1px solid #555;
            font-family: 'Courier New', monospace; font-size: 11px;
        """)
        console_layout.addWidget(self.console)
        clear_btn = _button("\U0001F5D1 Clear Console")
        clear_btn.clicked.connect(self.console.clear)
        console_layout.addWidget(clear_btn)
        splitter.addWidget(console_box)

        splitter.setSizes([420, 220])
        layout.addWidget(splitter)

        # Buttons that should be disabled while a command is in flight.
        self._action_buttons = [
            self.create_cluster_btn, self.delete_cluster_btn, self.deploy_btn,
            self.refresh_pods_btn, self.pod_logs_btn,
            self.tf_init_btn, self.tf_plan_btn, self.tf_apply_btn,
            self.tf_destroy_btn, self.tf_validate_btn, self.tf_fmt_btn,
        ]

    # -- Overview tab ---------------------------------------------------

    def _build_overview_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        project_box = _group("\U0001F5C2 Active Project")
        project_layout = QVBoxLayout(project_box)
        project_hint = QLabel(
            "Populated from the Projects panel's checked projects. Falls back to "
            "the IDE's current workspace if none are checked."
        )
        project_hint.setStyleSheet("color: #888; font-style: italic; padding: 2px 8px;")
        project_hint.setWordWrap(True)
        project_layout.addWidget(project_hint)

        project_row = QHBoxLayout()
        self.project_combo = QComboBox()
        self.project_combo.currentIndexChanged.connect(lambda _: self._apply_selected_project(refresh=True))
        project_row.addWidget(self.project_combo, stretch=1)
        project_refresh_btn = _button("\U0001F504")
        project_refresh_btn.setToolTip("Reload the list from the Projects panel")
        project_refresh_btn.setFixedWidth(40)
        project_refresh_btn.clicked.connect(lambda: self._populate_project_combo(keep_selection=True))
        project_row.addWidget(project_refresh_btn)
        project_layout.addLayout(project_row)
        layout.addWidget(project_box)

        path_box = _group("\U0001F4CD Scanning Path")
        path_layout = QVBoxLayout(path_box)
        self.scan_path_label = QLabel()
        self.scan_path_label.setWordWrap(True)
        self.scan_path_label.setStyleSheet(
            "color: #4A9EFF; padding: 8px; background: #2D2D2D; border-radius: 5px; "
            "font-family: 'Courier New', monospace;"
        )
        path_layout.addWidget(self.scan_path_label)
        layout.addWidget(path_box)

        detect_box = _group("\U0001F4C1 This Project's Infra Directories")
        detect_layout = QVBoxLayout(detect_box)
        detect_hint = QLabel("Checks the open project's folders — not whether the CLI tools below are installed.")
        detect_hint.setStyleSheet("color: #888; font-style: italic; padding: 2px 8px;")
        detect_layout.addWidget(detect_hint)
        self.detect_label = QLabel()
        self.detect_label.setWordWrap(True)
        self.detect_label.setStyleSheet("color: #CCC; padding: 8px; background: #2D2D2D; border-radius: 5px;")
        detect_layout.addWidget(self.detect_label)

        # "+ Create" buttons scaffold whichever directories aren't present
        # yet (terraform/, helm/, k8s/ each get their own button, plus a
        # catch-all). Each is disabled once its directory is detected -
        # refresh_overview() below toggles these on every (re-)scan, so
        # there's no "create it again" trap.
        scaffold_row = QHBoxLayout()
        self.scaffold_tf_btn = _button("+ terraform/")
        self.scaffold_tf_btn.setToolTip("Create terraform/ with a runnable, local-only starter example")
        self.scaffold_tf_btn.clicked.connect(lambda: self.scaffold_dir("terraform"))
        scaffold_row.addWidget(self.scaffold_tf_btn)

        self.scaffold_helm_btn = _button("+ helm/")
        self.scaffold_helm_btn.setToolTip("Create an empty helm/ directory (no Helm tab wired up yet to scaffold a chart)")
        self.scaffold_helm_btn.clicked.connect(lambda: self.scaffold_dir("helm"))
        scaffold_row.addWidget(self.scaffold_helm_btn)

        self.scaffold_k8s_btn = _button("+ k8s/")
        self.scaffold_k8s_btn.setToolTip("Create k8s/ with a runnable, disposable nginx example")
        self.scaffold_k8s_btn.clicked.connect(lambda: self.scaffold_dir("k8s"))
        scaffold_row.addWidget(self.scaffold_k8s_btn)

        scaffold_row.addStretch()

        self.scaffold_all_btn = _button("\u2795 Create All Missing")
        self.scaffold_all_btn.clicked.connect(self.scaffold_all_missing)
        scaffold_row.addWidget(self.scaffold_all_btn)

        detect_layout.addLayout(scaffold_row)
        layout.addWidget(detect_box)

        tools_box = _group("\U0001F527 Installed CLI Tools")
        tools_layout = QVBoxLayout(tools_box)
        self.tools_label = QLabel()
        self.tools_label.setWordWrap(True)
        self.tools_label.setStyleSheet("color: #CCC; padding: 8px; background: #2D2D2D; border-radius: 5px;")
        tools_layout.addWidget(self.tools_label)
        layout.addWidget(tools_box)

        refresh_btn = _button("\U0001F504 Re-scan Project")
        refresh_btn.clicked.connect(self.refresh_overview)
        layout.addWidget(refresh_btn)

        layout.addStretch()
        return widget

    def refresh_overview(self):
        # An explicit dropdown selection always wins over the IDE's own
        # notion of "current" workspace - otherwise every re-scan would
        # silently snap back to whatever get_workspace_path() reports,
        # undoing the user's choice.
        current_path = self._explicit_project_path or self._project_path()
        self.detector.project_path = current_path
        self.scan_path_label.setText(str(current_path))

        self.detection = self.detector.detect()
        self.tools = ProjectDetector.detect_tools()

        d = self.detection
        lines = []
        lines.append(f"terraform/ directory: {'\u2705 ' + str(d['terraform_dir']) if d['terraform_dir'] else '\u2014 not present in this project'}")
        lines.append(f"helm/ directory: {'\u2705 ' + str(d['helm_dir']) if d['helm_dir'] else '\u2014 not present in this project'}")
        lines.append(f"k8s/ manifests directory: {'\u2705 ' + str(d['k8s_dir']) if d['k8s_dir'] else '\u2014 not present in this project'}")
        if not d["has_any"]:
            lines.append("")
            lines.append("This project has no terraform/, helm/, or k8s/ folder yet - "
                          "the Kubernetes and Terraform tabs still work against any directory you point them "
                          "at, or use the buttons below to scaffold one with a runnable starter example.")
        self.detect_label.setText("<br>".join(lines))

        # Each button is only useful when its directory doesn't exist yet -
        # disable it otherwise so there's no "create it again" trap, and
        # no risk of it looking like it would overwrite something real.
        self.scaffold_tf_btn.setEnabled(not d["terraform_dir"])
        self.scaffold_helm_btn.setEnabled(not d["helm_dir"])
        self.scaffold_k8s_btn.setEnabled(not d["k8s_dir"])
        self.scaffold_all_btn.setEnabled(not (d["terraform_dir"] and d["helm_dir"] and d["k8s_dir"]))

        tool_lines = []
        for name, found in self.tools.items():
            mark = "\u2705" if found else "\u2014"
            tool_lines.append(f"{mark} {name}")
        # Real NBSP characters, not the "&nbsp;" entity - QLabel only parses
        # HTML entities once it detects rich text (e.g. via a <br> tag), so
        # a plain string full of "&nbsp;" prints literally instead of as a gap.
        self.tools_label.setText("\u00A0\u00A0\u00A0\u00A0".join(tool_lines))

        preferred = ProjectDetector.preferred_runtime(self.tools)
        if not preferred:
            self.tools_label.setText(
                self.tools_label.text() +
                "<br><br><i>No supported Kubernetes runtime found. Install k3d for the lightest option.</i>"
            )

        runtime_status = ProjectDetector.container_runtime_status()
        if runtime_status["installed"]:
            if runtime_status["daemon_running"]:
                status_line = f"\u2705 {runtime_status['runtime']} daemon is running"
            else:
                hint = ProjectDetector.daemon_start_hint(runtime_status["runtime"], runtime_status["permission_denied"])
                status_line = f"\u26A0\uFE0F {runtime_status['runtime']} is installed but its daemon isn't reachable. {hint}"
        else:
            status_line = "\u2014 no container runtime (Docker/Podman) found"
        self.tools_label.setText(self.tools_label.text() + f"<br><br>{status_line}")

        # Pre-fill terraform directory and cluster name if not already edited
        if d["terraform_dir"] and not self.tf_dir_edit.text():
            self.tf_dir_edit.setText(str(d["terraform_dir"]))
        if not self.cluster_name_edit.currentText():
            self.cluster_name_edit.setCurrentText(self.detector.default_cluster_name())

    def scaffold_dir(self, kind):
        """
        Creates the missing terraform/helm/k8s directory (+ a runnable
        starter file for terraform/k8s) for whichever project is
        currently selected, then re-scans so the Overview tab and any
        auto-filled fields (e.g. the Terraform directory box) pick it up
        immediately. Filesystem-only, so there's no need to route this
        through ProcessRunner or block on _busy - it's effectively
        instant even on a slow disk.
        """
        self.detector.project_path = self._explicit_project_path or self._project_path()
        created = self.detector.scaffold(kind)
        if created:
            self.log(f"[+] Created {created}")
        else:
            self.log(f"[!] {kind}/ already exists for this project (or nothing to scaffold) - not touching it.")
        self.refresh_overview()

    def scaffold_all_missing(self):
        """Runs scaffold_dir() for every kind that isn't already present,
        one re-scan at the end rather than one per directory."""
        self.detector.project_path = self._explicit_project_path or self._project_path()
        any_created = False
        for kind in ("terraform", "helm", "k8s"):
            created = self.detector.scaffold(kind)
            if created:
                self.log(f"[+] Created {created}")
                any_created = True
        if not any_created:
            self.log("[!] Nothing to scaffold - terraform/, helm/, and k8s/ all already exist for this project.")
        self.refresh_overview()

    # -- Kubernetes tab ---------------------------------------------------

    def _build_kubernetes_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        cluster_box = _group("\u2638 Disposable Cluster (k3d)")
        cluster_layout = QVBoxLayout(cluster_box)

        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Cluster name:"))
        self.cluster_name_edit = QComboBox()
        self.cluster_name_edit.setEditable(True)
        self.cluster_name_edit.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.cluster_name_edit.setToolTip(
            "Pick an existing k3d cluster, or type a new name to create one."
        )
        name_row.addWidget(self.cluster_name_edit, stretch=1)
        cluster_refresh_btn = _button("\U0001F504")
        cluster_refresh_btn.setToolTip("Reload the list of existing k3d clusters")
        cluster_refresh_btn.setFixedWidth(40)
        cluster_refresh_btn.clicked.connect(self._populate_cluster_list)
        name_row.addWidget(cluster_refresh_btn)
        name_row.addWidget(QLabel("Extra agents:"))
        self.agents_spin = QSpinBox()
        self.agents_spin.setRange(0, 5)
        name_row.addWidget(self.agents_spin)
        cluster_layout.addLayout(name_row)

        btn_row = QHBoxLayout()
        self.create_cluster_btn = _button("\u2795 Create Cluster")
        self.create_cluster_btn.clicked.connect(self.create_cluster)
        btn_row.addWidget(self.create_cluster_btn)

        self.delete_cluster_btn = _button("\U0001F5D1 Delete Cluster")
        self.delete_cluster_btn.clicked.connect(self.delete_cluster)
        btn_row.addWidget(self.delete_cluster_btn)

        self.deploy_btn = _button("\U0001F680 Deploy k8s/ Manifests")
        self.deploy_btn.clicked.connect(self.deploy_manifests)
        btn_row.addWidget(self.deploy_btn)
        btn_row.addStretch()
        cluster_layout.addLayout(btn_row)
        layout.addWidget(cluster_box)

        explorer_box = _group("\U0001F4E6 Resource Explorer")
        explorer_layout = QVBoxLayout(explorer_box)

        explorer_btn_row = QHBoxLayout()
        self.refresh_pods_btn = _button("\U0001F504 Refresh Pods")
        self.refresh_pods_btn.clicked.connect(self.refresh_pods)
        explorer_btn_row.addWidget(self.refresh_pods_btn)

        self.pod_logs_btn = _button("\U0001F4C4 View Logs")
        self.pod_logs_btn.clicked.connect(self.view_pod_logs)
        explorer_btn_row.addWidget(self.pod_logs_btn)
        explorer_btn_row.addStretch()
        explorer_layout.addLayout(explorer_btn_row)

        self.pods_list = QListWidget()
        self.pods_list.setStyleSheet("""
            QListWidget { background: #2D2D2D; color: #CCC; border: 1px solid #555; }
        """)
        explorer_layout.addWidget(self.pods_list)
        layout.addWidget(explorer_box)

        return widget

    def create_cluster(self):
        name = self.cluster_name_edit.currentText().strip()
        if not name:
            self.log("[!] Enter a cluster name first.")
            return
        if not self.tools.get("k3d"):
            self.log("[!] k3d is not installed. Install it to create disposable clusters.")
            return
        if not self._daemon_ready():
            return

        cmd = KubernetesManager.create_cluster_command(name, agents=self.agents_spin.value())

        def done(code):
            if code == 0:
                self.api.show_status_message(f"Cluster '{name}' created", 3000)
                self.log(f"kubectl context switched to k3d-{name} automatically.")
                self._populate_cluster_list()

        self.run_command(cmd, label=f"create cluster {name}", on_finished=done)

    def delete_cluster(self):
        name = self.cluster_name_edit.currentText().strip()
        if not name:
            self.log("[!] Enter a cluster name first.")
            return
        if not self._daemon_ready():
            return
        if not self._confirm("Delete Cluster", f"Delete k3d cluster '{name}'? This cannot be undone."):
            return

        cmd = KubernetesManager.delete_cluster_command(name)

        def done(code):
            if code == 0:
                self.api.show_status_message(f"Cluster '{name}' deleted", 3000)
                self._populate_cluster_list()

        self.run_command(cmd, label=f"delete cluster {name}", on_finished=done)

    def _current_cluster_context(self):
        """
        Returns the kubectl context matching whatever cluster name is
        currently shown in the Kubernetes tab's combo box, or None if
        it's empty.

        Without this, every kubectl call below would hit whatever
        context happened to be ambient (kubectl's own "current-context"),
        which is NOT the same thing as "the cluster for the currently
        selected project." k3d switches the ambient context on Create,
        but nothing switches it back when you just change the Active
        Project dropdown - so refreshing pods after switching to a
        different (or not-yet-created) project's cluster would silently
        keep showing the PREVIOUS project's pods instead of erroring or
        showing nothing. Scoping every call with --context ties each
        action to the cluster name actually on screen, not whatever was
        left over from the last Create Cluster click.
        """
        name = self.cluster_name_edit.currentText().strip()
        if not name:
            return None
        return KubernetesManager.kube_context_name(name)

    def deploy_manifests(self):
        k8s_dir = self.detection.get("k8s_dir")
        if not k8s_dir:
            self.log("[!] No k8s/ manifests directory detected in this project.")
            return
        if not ProjectDetector.has_k8s_manifests(k8s_dir):
            self.log(f"[!] {k8s_dir} has no .yaml/.yml files in it - nothing to deploy. "
                     f"Add a manifest there first, then try again.")
            return
        if not self._daemon_ready():
            return
        cmd = KubernetesManager.apply_manifests_command(k8s_dir, context=self._current_cluster_context())
        self.run_command(cmd, label="deploy manifests", on_finished=lambda c: self.refresh_pods())

    def refresh_pods(self):
        if not self.tools.get("kubectl"):
            self.log("[!] kubectl is not installed.")
            return
        if not self._daemon_ready():
            self.pods_list.clear()
            self.pods_list.addItem("Container daemon not running - see console")
            return
        context = self._current_cluster_context()
        code, output = run_quick(KubernetesManager.get_pods_command(context=context), timeout=8)
        self.pods_list.clear()
        if code != 0:
            label = f"No cluster named '{context}' reachable" if context else "No cluster reachable"
            self.pods_list.addItem(f"{label} - create one first")
            return
        lines = output.splitlines()
        if len(lines) <= 1:
            self.pods_list.addItem("No pods found")
            return
        for line in lines[1:]:
            self.pods_list.addItem(line)

    def view_pod_logs(self):
        item = self.pods_list.currentItem()
        if not item:
            self.log("[!] Select a pod from the list first.")
            return
        parts = item.text().split()
        if len(parts) < 2:
            return
        namespace, pod_name = parts[0], parts[1]
        cmd = KubernetesManager.get_pod_logs_command(
            pod_name, namespace=namespace, context=self._current_cluster_context()
        )
        self.run_command(cmd, label=f"logs {pod_name}")

    # -- Terraform tab ---------------------------------------------------

    def _build_terraform_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        dir_box = _group("\U0001F5FA Terraform Directory")
        dir_layout = QHBoxLayout(dir_box)
        self.tf_dir_edit = QLineEdit()
        dir_layout.addWidget(self.tf_dir_edit)
        layout.addWidget(dir_box)

        actions_box = _group("Actions")
        actions_layout = QVBoxLayout(actions_box)

        row1 = QHBoxLayout()
        self.tf_init_btn = _button("Init")
        self.tf_init_btn.clicked.connect(self.tf_init)
        row1.addWidget(self.tf_init_btn)

        self.tf_validate_btn = _button("Validate")
        self.tf_validate_btn.clicked.connect(self.tf_validate)
        row1.addWidget(self.tf_validate_btn)

        self.tf_fmt_btn = _button("Format")
        self.tf_fmt_btn.clicked.connect(self.tf_fmt)
        row1.addWidget(self.tf_fmt_btn)
        row1.addStretch()
        actions_layout.addLayout(row1)

        row2 = QHBoxLayout()
        self.tf_plan_btn = _button("\U0001F4CB Plan")
        self.tf_plan_btn.clicked.connect(self.tf_plan)
        row2.addWidget(self.tf_plan_btn)

        self.tf_apply_btn = _button("\u2705 Apply")
        self.tf_apply_btn.clicked.connect(self.tf_apply)
        row2.addWidget(self.tf_apply_btn)

        self.tf_destroy_btn = _button("\u274C Destroy")
        self.tf_destroy_btn.clicked.connect(self.tf_destroy)
        row2.addWidget(self.tf_destroy_btn)
        row2.addStretch()
        actions_layout.addLayout(row2)

        layout.addWidget(actions_box)
        layout.addStretch()
        return widget

    def _tf_dir(self):
        text = self.tf_dir_edit.text().strip()
        if not text:
            self.log("[!] Set the Terraform directory first.")
            return None
        path = Path(text)
        if not path.is_dir():
            self.log(f"[!] Not a directory: {path}")
            return None
        if not ProjectDetector.has_terraform_files(path):
            self.log(f"[!] {path} has no .tf files in it - this will run against an "
                     f"empty configuration (e.g. 'Plan: 0 to add'), not an error.")
        return path

    def tf_init(self):
        d = self._tf_dir()
        if d:
            self.run_command(TerraformManager.init_command(), cwd=d, label="terraform init")

    def tf_validate(self):
        d = self._tf_dir()
        if d:
            self.run_command(TerraformManager.validate_command(), cwd=d, label="terraform validate")

    def tf_fmt(self):
        d = self._tf_dir()
        if d:
            self.run_command(TerraformManager.fmt_command(), cwd=d, label="terraform fmt")

    def tf_plan(self):
        d = self._tf_dir()
        if d:
            self.run_command(TerraformManager.plan_command(), cwd=d, label="terraform plan")

    def tf_apply(self):
        d = self._tf_dir()
        if not d:
            return
        if not self._confirm("Apply Terraform", f"Run terraform apply in:\n{d}\n\nThis will provision real resources."):
            return
        self.run_command(TerraformManager.apply_command(), cwd=d, label="terraform apply")

    def tf_destroy(self):
        d = self._tf_dir()
        if not d:
            return
        if not self._confirm("Destroy Terraform", f"Run terraform destroy in:\n{d}\n\nThis will tear down all managed resources."):
            return
        self.run_command(TerraformManager.destroy_command(), cwd=d, label="terraform destroy")