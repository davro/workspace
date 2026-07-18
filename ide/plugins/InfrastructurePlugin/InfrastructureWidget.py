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
    QMessageBox, QListWidgetItem
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

        self.detector = ProjectDetector(self._project_path())
        self.detection = self.detector.detect()
        self.tools = ProjectDetector.detect_tools()

        self._build_ui()
        self.refresh_overview()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _project_path(self):
        try:
            path = self.api.get_workspace_path()
            return Path(path) if path else Path.cwd()
        except Exception:
            return Path.cwd()

    def log(self, message):
        self.console.append(message)

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
        self._runner = ProcessRunner(command, cwd=cwd, label=label)
        self._runner.line_ready.connect(self.log)

        def _done(code):
            self.log(f"[exit code {code}]\n")
            self._runner = None
            self._busy(False)
            if on_finished:
                on_finished(code)

        self._runner.finished_ok.connect(_done)
        self._runner.start()

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

        detect_box = _group("\U0001F4C1 This Project's Infra Directories")
        detect_layout = QVBoxLayout(detect_box)
        detect_hint = QLabel("Checks the open project's folders — not whether the CLI tools below are installed.")
        detect_hint.setStyleSheet("color: #888; font-style: italic; padding: 2px 8px;")
        detect_layout.addWidget(detect_hint)
        self.detect_label = QLabel()
        self.detect_label.setWordWrap(True)
        self.detect_label.setStyleSheet("color: #CCC; padding: 8px; background: #2D2D2D; border-radius: 5px;")
        detect_layout.addWidget(self.detect_label)
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
                          "the Kubernetes and Terraform tabs still work against any directory you point them at.")
        self.detect_label.setText("<br>".join(lines))

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
        if not self.cluster_name_edit.text():
            self.cluster_name_edit.setText(self.detector.default_cluster_name())

    # -- Kubernetes tab ---------------------------------------------------

    def _build_kubernetes_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        cluster_box = _group("\u2638 Disposable Cluster (k3d)")
        cluster_layout = QVBoxLayout(cluster_box)

        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Cluster name:"))
        self.cluster_name_edit = QLineEdit()
        name_row.addWidget(self.cluster_name_edit)
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
        name = self.cluster_name_edit.text().strip()
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

        self.run_command(cmd, label=f"create cluster {name}", on_finished=done)

    def delete_cluster(self):
        name = self.cluster_name_edit.text().strip()
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

        self.run_command(cmd, label=f"delete cluster {name}", on_finished=done)

    def deploy_manifests(self):
        k8s_dir = self.detection.get("k8s_dir")
        if not k8s_dir:
            self.log("[!] No k8s/ manifests directory detected in this project.")
            return
        if not self._daemon_ready():
            return
        cmd = KubernetesManager.apply_manifests_command(k8s_dir)
        self.run_command(cmd, label="deploy manifests", on_finished=lambda c: self.refresh_pods())

    def refresh_pods(self):
        if not self.tools.get("kubectl"):
            self.log("[!] kubectl is not installed.")
            return
        if not self._daemon_ready():
            self.pods_list.clear()
            self.pods_list.addItem("Container daemon not running - see console")
            return
        code, output = run_quick(KubernetesManager.get_pods_command(), timeout=8)
        self.pods_list.clear()
        if code != 0:
            self.pods_list.addItem("No cluster reachable - create one first")
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
        cmd = KubernetesManager.get_pod_logs_command(pod_name, namespace=namespace)
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