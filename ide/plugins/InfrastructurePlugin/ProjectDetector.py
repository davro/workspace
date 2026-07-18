# InfrastructurePlugin/ProjectDetector.py

"""
ProjectDetector - figures out what a project needs, without provisioning
anything itself. Pure filesystem checks + `which` lookups, so this stays
instant even on a slow disk. Everything here is cheap by design: no
subprocess calls that hit the network or a daemon.
"""

import shutil
from pathlib import Path

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


# Candidate directory/file names we look for, in priority order.
TERRAFORM_HINTS = ["terraform", "infra/terraform", "infrastructure"]
HELM_HINTS = ["helm", "chart", "charts"]
K8S_HINTS = ["k8s", "kubernetes", "manifests"]

# Binaries the plugin knows how to work with. k3d is listed first because
# it's the lightest-weight option and the one this plugin prefers.
KUBERNETES_RUNTIMES = ["k3d", "kind", "minikube", "microk8s"]
OTHER_TOOLS = ["kubectl", "terraform", "helm", "docker", "podman"]


class ProjectDetector:
    """Detects Terraform/Helm/Kubernetes content in a project and which
    local tools are available to work with them."""

    def __init__(self, project_path):
        self.project_path = Path(project_path) if project_path else None

    # ------------------------------------------------------------------
    # Project content detection
    # ------------------------------------------------------------------

    def _find_dir(self, hints):
        if not self.project_path:
            return None
        for hint in hints:
            candidate = self.project_path / hint
            if candidate.is_dir():
                return candidate
        return None

    def detect(self):
        """
        Returns a dict describing what infra-related content the current
        project has, plus its workspace.yml config (if any):

        {
            'terraform_dir': Path | None,
            'helm_dir': Path | None,
            'k8s_dir': Path | None,
            'has_any': bool,
            'config': dict,   # parsed workspace.yml 'plugins' section, or {}
        }
        """
        result = {
            "terraform_dir": self._find_dir(TERRAFORM_HINTS),
            "helm_dir": self._find_dir(HELM_HINTS),
            "k8s_dir": self._find_dir(K8S_HINTS),
            "config": self._load_workspace_config(),
        }
        result["has_any"] = any(
            [result["terraform_dir"], result["helm_dir"], result["k8s_dir"]]
        )
        return result

    def _load_workspace_config(self):
        if not self.project_path:
            return {}
        config_file = self.project_path / "workspace.yml"
        if not config_file.exists() or not HAS_YAML:
            return {}
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            return data.get("plugins", {}) or {}
        except Exception:
            return {}

    def default_cluster_name(self):
        """A stable, project-scoped cluster name, e.g. 'workspace-myproject'."""
        if not self.project_path:
            return "workspace-default"
        return f"workspace-{self.project_path.name}".lower().replace("_", "-")

    # ------------------------------------------------------------------
    # Tool detection
    # ------------------------------------------------------------------

    @staticmethod
    def detect_tools():
        """
        Returns {tool_name: bool} for every runtime/tool this plugin knows
        about. Cheap `shutil.which` calls only - no subprocess spawned.
        """
        return {
            name: shutil.which(name) is not None
            for name in KUBERNETES_RUNTIMES + OTHER_TOOLS
        }

    @staticmethod
    def preferred_runtime(available_tools):
        """Pick the lightest available Kubernetes runtime. k3d first -
        it's a handful of MB and starts in seconds, which matters most
        when running on a resource-constrained laptop or dev server."""
        for name in KUBERNETES_RUNTIMES:
            if available_tools.get(name):
                return name
        return None

    @staticmethod
    def container_runtime_status():
        """
        Checks whether a container daemon is actually reachable, not just
        installed. `docker`/`podman info` fails almost instantly if the
        daemon is down, so this is safe to call before every cluster
        operation - unlike the rest of this module, it does hit a daemon,
        which is why it's a separate call rather than part of detect_tools().

        Returns:
            {'runtime': 'docker' | 'podman' | None,
             'installed': bool,
             'daemon_running': bool,
             'permission_denied': bool}   # group membership not active yet
        """
        # Imported lazily to keep this module's own import list daemon-free.
        from InfrastructurePlugin.ProcessRunner import run_quick

        for runtime in ("docker", "podman"):
            if shutil.which(runtime):
                code, output = run_quick([runtime, "info"], timeout=5)
                return {
                    "runtime": runtime,
                    "installed": True,
                    "daemon_running": code == 0,
                    "permission_denied": "permission denied" in output.lower(),
                }
        return {"runtime": None, "installed": False, "daemon_running": False, "permission_denied": False}

    @staticmethod
    def daemon_start_hint(runtime, permission_denied=False):
        """Best-effort, platform-aware instructions for fixing the daemon."""
        import platform

        if permission_denied:
            return (f"Your user was added to the {runtime} group, but that only takes "
                     f"effect in a new session - log out and back in, or run "
                     f"`newgrp {runtime}`, then try again.")
        system = platform.system()
        if runtime == "podman":
            return "Start Podman, e.g. `systemctl --user start podman.socket`."
        if system == "Linux":
            return "Start Docker: `sudo systemctl start docker`."
        if system == "Darwin":
            return "Start Docker Desktop from Applications / the menu bar."
        return "Start Docker Desktop, or your platform's Docker service."