# InfrastructurePlugin/KubernetesManager.py

"""
KubernetesManager - thin wrapper around k3d + kubectl.

k3d is the only cluster runtime wired up for now: it runs Kubernetes-in-
Docker with a footprint of tens of MB of RAM per node, starts in a few
seconds, and needs nothing but a Docker (or Podman) daemon already
running on the laptop/dev server. That matches this plugin's brief -
lightweight, disposable, no extra VM overhead.

kind and minikube are heavier (kind needs more memory per node, minikube
spins up a full VM/driver stack) so they're deliberately left out of the
MVP. Adding one later just means adding another *_command() method here
and a runtime switch in the widget - nothing else has to change.

This module only *builds command argv lists* and does light parsing of
their output. It never calls subprocess directly - the widget runs
everything through ProcessRunner so the UI thread never blocks.
"""

from pathlib import Path

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


class KubernetesManager:
    RUNTIME = "k3d"

    # ------------------------------------------------------------------
    # Cluster lifecycle (k3d)
    # ------------------------------------------------------------------

    @staticmethod
    def create_cluster_command(name, agents=0, port_mappings=None):
        """
        Build a `k3d cluster create` command.

        Args:
            name: cluster name
            agents: number of extra worker nodes (0 = single-node, lightest)
            port_mappings: list of "hostPort:containerPort" strings, e.g.
                ["8080:80@loadbalancer"]
        """
        cmd = ["k3d", "cluster", "create", name]
        if agents:
            cmd += ["--agents", str(agents)]
        for mapping in port_mappings or []:
            cmd += ["--port", mapping]
        return cmd

    @staticmethod
    def delete_cluster_command(name):
        return ["k3d", "cluster", "delete", name]

    @staticmethod
    def list_clusters_command():
        return ["k3d", "cluster", "list", "--no-headers"]

    @staticmethod
    def parse_cluster_list(output):
        """
        Parses `k3d cluster list --no-headers` output into a list of dicts:
        [{'name': ..., 'servers': ..., 'agents': ..., 'loadbalancer': ...}]
        """
        clusters = []
        for line in output.splitlines():
            parts = line.split()
            if not parts:
                continue
            clusters.append({
                "name": parts[0],
                "servers": parts[1] if len(parts) > 1 else "",
                "agents": parts[2] if len(parts) > 2 else "",
                "loadbalancer": parts[3] if len(parts) > 3 else "",
            })
        return clusters

    # ------------------------------------------------------------------
    # kubectl - context, deploy, resource explorer
    # ------------------------------------------------------------------

    @staticmethod
    def kube_context_name(cluster_name):
        """k3d names the kubectl context 'k3d-<cluster-name>' and switches
        to it automatically on create, so this is mostly for display."""
        return f"k3d-{cluster_name}"

    @staticmethod
    def apply_manifests_command(path, context=None):
        cmd = ["kubectl"]
        if context:
            cmd += ["--context", context]
        cmd += ["apply", "-f", str(path)]
        return cmd

    @staticmethod
    def get_pods_command(namespace=None, context=None):
        cmd = ["kubectl"]
        if context:
            cmd += ["--context", context]
        cmd += ["get", "pods", "-o", "wide"]
        cmd += ["--all-namespaces"] if not namespace else ["-n", namespace]
        return cmd

    @staticmethod
    def get_pod_logs_command(pod_name, namespace="default", tail=200, context=None):
        cmd = ["kubectl"]
        if context:
            cmd += ["--context", context]
        cmd += ["logs", pod_name, "-n", namespace, f"--tail={tail}"]
        return cmd

    @staticmethod
    def describe_pod_command(pod_name, namespace="default", context=None):
        cmd = ["kubectl"]
        if context:
            cmd += ["--context", context]
        cmd += ["describe", "pod", pod_name, "-n", namespace]
        return cmd

    @staticmethod
    def current_context_command():
        return ["kubectl", "config", "current-context"]

    # ------------------------------------------------------------------
    # Port forwarding
    # ------------------------------------------------------------------

    @staticmethod
    def port_forward_command(target, local_port, remote_port, namespace="default", context=None):
        """
        Build a `kubectl port-forward` command. `target` should already
        be prefixed, e.g. 'svc/infra-plugin-example' or 'pod/some-pod'.

        Unlike every other command this module builds, this one never
        exits on its own under normal use - it runs until killed. The
        widget dispatches it through its own dedicated ProcessRunner
        slot rather than the shared single-command one for exactly that
        reason (see InfrastructureWidget's port-forward handlers).
        """
        cmd = ["kubectl"]
        if context:
            cmd += ["--context", context]
        cmd += ["port-forward", target, f"{local_port}:{remote_port}", "-n", namespace]
        return cmd

    @staticmethod
    def find_service_in_manifests(k8s_dir):
        """
        Scans the .yaml/.yml files directly under k8s_dir (same
        non-recursive scope as ProjectDetector.has_k8s_manifests /
        `kubectl apply -f <dir>`'s own default) for the first Service
        resource, and returns (name, port) from its first port entry -
        e.g. ('infra-plugin-example', 80) for the scaffolded starter
        manifest, or ('infra-plugin-test', 80) for the original
        test-infra-project fixture.

        This is a best-effort UI convenience (auto-filling the port-
        forward target field), not something anything else depends on -
        returns (None, None) on anything that doesn't cleanly resolve
        to a single answer: no PyYAML installed, no k8s_dir, no Service
        found, or a file that doesn't parse. Callers should treat that
        the same as "nothing to suggest, let the user type it in".
        """
        if not HAS_YAML or not k8s_dir:
            return None, None
        k8s_dir = Path(k8s_dir)
        if not k8s_dir.is_dir():
            return None, None
        for file in sorted(list(k8s_dir.glob("*.yaml")) + list(k8s_dir.glob("*.yml"))):
            try:
                with open(file, "r", encoding="utf-8") as f:
                    docs = yaml.safe_load_all(f)
                    for doc in docs:
                        if not doc or doc.get("kind") != "Service":
                            continue
                        name = doc.get("metadata", {}).get("name")
                        ports = doc.get("spec", {}).get("ports") or []
                        port = ports[0].get("port") if ports else None
                        if name and port:
                            return name, port
            except Exception:
                continue
        return None, None