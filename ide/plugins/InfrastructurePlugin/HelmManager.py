# InfrastructurePlugin/HelmManager.py

"""
HelmManager - builds Helm command argv lists. Like TerraformManager and
KubernetesManager, this only builds commands and does light parsing of
their output; the widget dispatches everything through ProcessRunner (or
run_quick for the cheap `helm list` call) so the UI thread never blocks.

install_command() uses `helm upgrade --install` rather than a plain
`helm install`, so clicking it a second time - after editing values, or
just by mistake - upgrades the existing release in place instead of
crashing with "cannot re-use a name that is still in use". Same
reasoning as TerraformManager's apply/destroy always passing
-auto-approve: this plugin is aimed at local, disposable dev work, so
the idempotent form is the right default rather than the strict one.

Every action here targets whatever kube-context the Kubernetes tab's
cluster combo currently shows (--kube-context), for the same reason
KubernetesManager's kubectl commands take a `context` argument - without
it, Helm would silently act on kubectl's ambient current-context instead
of "the cluster for the currently selected project" (see
InfrastructureWidget._current_cluster_context's docstring for the full
story - that's gotcha #12's fix, and Helm needs the same treatment).
"""

import json


class HelmManager:

    @staticmethod
    def create_chart_command(name):
        """`helm create <name>` - Helm's own scaffold generator. Run with
        cwd set to the project's helm/ directory so it lands at
        helm/<name>/ with a real Chart.yaml, values.yaml, and templates/,
        rather than trying to hand-roll a starter chart."""
        return ["helm", "create", name]

    @staticmethod
    def install_command(release, chart, context=None, namespace=None, values_file=None):
        """
        Build a `helm upgrade --install` command. `chart` is a local path
        (a project's helm/<name>/ directory) - this plugin doesn't wire up
        remote chart repos.
        """
        cmd = ["helm", "upgrade", "--install", release, str(chart)]
        if context:
            cmd += ["--kube-context", context]
        if namespace:
            cmd += ["--namespace", namespace, "--create-namespace"]
        if values_file:
            cmd += ["--values", str(values_file)]
        return cmd

    @staticmethod
    def uninstall_command(release, context=None, namespace=None):
        cmd = ["helm", "uninstall", release]
        if context:
            cmd += ["--kube-context", context]
        if namespace:
            cmd += ["--namespace", namespace]
        return cmd

    @staticmethod
    def list_releases_command(context=None):
        """--all-namespaces, since this plugin doesn't have a namespace
        picker anywhere yet - showing everything is the honest option,
        same call as KubernetesManager.get_pods_command's default."""
        cmd = ["helm", "list", "-o", "json", "--all-namespaces"]
        if context:
            cmd += ["--kube-context", context]
        return cmd

    @staticmethod
    def parse_release_list(output):
        """
        Parses `helm list -o json` output into a list of dicts, using
        Helm's own JSON schema as-is (name/namespace/revision/status/
        chart/app_version/...). Returns [] on anything unparsable rather
        than raising - callers treat that the same as "no releases".
        """
        try:
            data = json.loads(output)
        except (json.JSONDecodeError, TypeError):
            return []
        return data if isinstance(data, list) else []

    @staticmethod
    def lint_command(chart_path):
        return ["helm", "lint", str(chart_path)]

    @staticmethod
    def template_command(release, chart_path):
        """Renders the chart locally without touching a cluster at all -
        a fast, cluster-free sanity check to run before Install."""
        return ["helm", "template", release, str(chart_path)]