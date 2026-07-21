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

# Starter content written by scaffold() when the Overview tab's "+ Create"
# buttons make a missing directory. Both are real, runnable examples -
# safe and fully disposable - so a brand-new project can go straight to
# Init -> Plan -> Apply or Deploy -> Refresh Pods without first having to
# hand-write a file just to satisfy has_terraform_files()/has_k8s_manifests().
# No cloud credentials, no external images beyond nginx:alpine.
TERRAFORM_STARTER = '''# Starter Terraform configuration created by the Infrastructure plugin.
# Safe to run immediately - this is a local-only example (no cloud
# credentials needed) so you can try Init -> Plan -> Apply -> Destroy
# right away. Replace it with your own resources when you're ready.

resource "local_file" "example" {
  filename = "${path.module}/example-output.txt"
  content  = "Hello from the Infrastructure plugin!\\n"
}
'''

K8S_STARTER = '''# Starter manifest created by the Infrastructure plugin.
# Deploys a single disposable nginx pod + service so you can try
# Deploy k8s/ Manifests -> Refresh Pods -> View Logs right away.
# Replace it with your own manifests when you're ready.
apiVersion: apps/v1
kind: Deployment
metadata:
  name: infra-plugin-example
spec:
  replicas: 1
  selector:
    matchLabels:
      app: infra-plugin-example
  template:
    metadata:
      labels:
        app: infra-plugin-example
    spec:
      containers:
        - name: nginx
          image: nginx:alpine
          ports:
            - containerPort: 80
---
apiVersion: v1
kind: Service
metadata:
  name: infra-plugin-example
spec:
  selector:
    app: infra-plugin-example
  ports:
    - port: 80
      targetPort: 80
'''


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
        name = self.project_path.name.lower().replace("_", "-")
        # Avoid "workspace-workspace" when the project folder is itself
        # named "workspace" (or already starts with it) - the prefix
        # exists to scope the name, not to repeat it.
        if name.startswith("workspace"):
            return name
        return f"workspace-{name}"

    # ------------------------------------------------------------------
    # Tool detection
    # ------------------------------------------------------------------

    def scaffold(self, kind):
        """
        Creates the standard directory for `kind` in {'terraform', 'helm',
        'k8s'} under this instance's project_path, if none of that kind's
        hint-names already exists. terraform/k8s also get a real, runnable
        starter file (see TERRAFORM_STARTER/K8S_STARTER above); helm/ is
        left empty since there's no HelmManager yet to do anything with a
        scaffolded chart.

        This is filesystem-only (mkdir + write) - same cost class as the
        rest of this module, no subprocess spawned - and it never
        overwrites: if the directory (or the starter file inside it)
        already exists, it's left completely untouched.

        Returns the created directory Path, or None if there was nothing
        to do (no project_path set, unknown `kind`, or that kind's
        directory is already present under one of its hint names).
        """
        if not self.project_path:
            return None
        hints = {"terraform": TERRAFORM_HINTS, "helm": HELM_HINTS, "k8s": K8S_HINTS}.get(kind)
        if hints is None:
            return None
        if self._find_dir(hints):
            return None  # already present under some hint name - don't touch it

        target = self.project_path / hints[0]
        target.mkdir(parents=True, exist_ok=True)

        starter = {
            "terraform": ("main.tf", TERRAFORM_STARTER),
            "k8s": ("nginx-example.yaml", K8S_STARTER),
        }.get(kind)
        if starter:
            filename, content = starter
            starter_path = target / filename
            if not starter_path.exists():
                starter_path.write_text(content, encoding="utf-8")

        return target

    @staticmethod
    def has_terraform_files(directory):
        """
        True if `directory` contains at least one `.tf` file directly in
        it. Non-recursive on purpose - `terraform init/plan/apply` only
        read the working directory itself, not subfolders, so checking
        deeper would give a false sense of "there's something here" for
        a layout Terraform wouldn't actually pick up.

        Note this is informational, not a hard gate: an empty Terraform
        directory isn't actually an error - init/plan/apply all complete
        fine against zero resources ("Plan: 0 to add"). Callers should
        warn, not block.
        """
        if not directory:
            return False
        directory = Path(directory)
        if not directory.is_dir():
            return False
        return any(directory.glob("*.tf"))

    @staticmethod
    def has_k8s_manifests(directory):
        """
        True if `directory` contains at least one `.yaml`/`.yml` file
        directly in it. Non-recursive to match `kubectl apply -f <dir>`'s
        own default behavior (no `-R`), so this reflects exactly what
        kubectl would actually pick up, not just "some content exists
        somewhere under here."

        Unlike has_terraform_files, an empty result here IS a real
        problem: `kubectl apply -f` on a directory with no manifests
        fails outright ("error: no objects passed to apply"), it doesn't
        gracefully no-op. Callers should block, not just warn.
        """
        if not directory:
            return False
        directory = Path(directory)
        if not directory.is_dir():
            return False
        return any(directory.glob("*.yaml")) or any(directory.glob("*.yml"))

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