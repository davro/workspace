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