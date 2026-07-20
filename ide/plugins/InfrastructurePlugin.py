# ide/plugins/InfrastructurePlugin.py

"""
Infrastructure Plugin for Workspace IDE

Lightweight local infrastructure workflows, scoped for a single laptop or
dev server with limited resources:

- Disposable Kubernetes clusters via k3d (lightest available runtime -
  Kubernetes-in-Docker, seconds to start, tens of MB of RAM per node)
- Terraform init / plan / apply / destroy / validate / fmt
- Auto-detection of terraform/, helm/, and k8s/ directories in a project
- A resource explorer for pods (list, logs)

Deliberately NOT included in this MVP: Helm release management, Ansible,
multiple Kubernetes runtimes (kind/minikube/microk8s), a local image
registry, and a combined "Develop" build-push-upgrade loop. Those were
all in the original brainstorm but add real complexity and background
resource usage (extra daemons, registries, watchers) for workflows most
projects on a constrained machine won't need day-to-day. The provider
classes (KubernetesManager, TerraformManager) are structured so any of
these can be added later without reworking the plugin.

Author: Workspace IDE Team
Version: 0.1.0
"""

import sys
from pathlib import Path

# Make the InfrastructurePlugin/ package importable, matching the pattern
# used by Codeintelligence.py and OllamaPlugin.py in this same directory.
plugin_dir = Path(__file__).parent
if str(plugin_dir) not in sys.path:
    sys.path.insert(0, str(plugin_dir))

from InfrastructurePlugin.InfrastructureWidget import InfrastructureWidget


class InfrastructurePlugin:
    """
    Infrastructure Plugin - disposable local Kubernetes (k3d) + Terraform,
    driven from a single panel in the right sidebar.
    """

    # ------------------------------------------------------------------
    # Plugin Metadata (Required)
    # ------------------------------------------------------------------

    PLUGIN_NAME = "Infrastructure"
    PLUGIN_VERSION = "0.1.0"
    PLUGIN_DESCRIPTION = "Disposable local Kubernetes (k3d) clusters and Terraform workflows"
    PLUGIN_RUN_ON_STARTUP = True
    PLUGIN_HAS_UI = True
    PLUGIN_ICON = "\u2638"  # ☸

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    def __init__(self, api):
        self.api = api
        self.initialized = False
        self.widget = None
        print(f"[{self.PLUGIN_NAME}] Instance created")

    def initialize(self):
        if self.initialized:
            print(f"[{self.PLUGIN_NAME}] Already initialized")
            return

        print(f"[{self.PLUGIN_NAME}] Initializing...")

        self.api.register_hook(
            "on_project_opened", self.on_project_opened, plugin_id="infrastructure_plugin"
        )

        self.api.register_keyboard_shortcut(
            "Ctrl+Shift+I", self.show_panel, "Show Infrastructure panel"
        )

        self.initialized = True
        self.api.show_status_message(f"{self.PLUGIN_NAME} plugin initialized", 2000)
        print(f"[{self.PLUGIN_NAME}] Initialized")

    def get_widget(self, parent=None):
        """Called by the plugin system to obtain the sidebar UI."""
        self.widget = InfrastructureWidget(self, parent)
        return self.widget

    def cleanup(self):
        print(f"[{self.PLUGIN_NAME}] Cleaning up...")
        if self.widget:
            self.widget.shutdown()
        if self.api:
            self.api.unregister_all_plugin_hooks("infrastructure_plugin")
        self.initialized = False
        print(f"[{self.PLUGIN_NAME}] Cleaned up")

    # ------------------------------------------------------------------
    # Hooks
    # ------------------------------------------------------------------

    def on_project_opened(self, project_path):
        """Re-scan for terraform/helm/k8s content whenever a project is
        activated, so the Overview tab reflects the project actually
        open - not whatever was open when the IDE started.

        This also clears any explicit Active Project dropdown selection.
        Without that, opening a different project in the IDE while the
        dropdown was pinned to some other checked project would be
        silently ignored - the dropdown selection is meant to be an
        override the user made on purpose, not something that should
        outlive an actual project switch."""
        if self.widget:
            self.widget._explicit_project_path = None
            self.widget.detector.project_path = Path(project_path)
            self.widget._populate_project_combo(keep_selection=False)
            self.widget.refresh_overview()

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def show_panel(self):
        if self.api.focus_right_sidebar_tab(self.PLUGIN_NAME):
            return
        if self.widget:
            self.api.add_to_right_sidebar(self.widget, self.PLUGIN_NAME, self.PLUGIN_ICON)
            self.api.focus_right_sidebar_tab(self.PLUGIN_NAME)