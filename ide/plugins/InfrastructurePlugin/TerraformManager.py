# InfrastructurePlugin/TerraformManager.py

"""
TerraformManager - builds Terraform command argv lists for a given
project directory. Like KubernetesManager, this never runs anything
itself; the widget dispatches every command through ProcessRunner.

apply/destroy always pass -auto-approve. This plugin is aimed at local,
disposable dev infrastructure - the widget itself asks for confirmation
before dispatching either command, so a second interactive prompt from
Terraform would just be redundant friction.
"""


class TerraformManager:

    @staticmethod
    def init_command():
        return ["terraform", "init", "-input=false"]

    @staticmethod
    def plan_command(var_file=None):
        cmd = ["terraform", "plan", "-input=false"]
        if var_file:
            cmd += ["-var-file", str(var_file)]
        return cmd

    @staticmethod
    def apply_command(var_file=None):
        cmd = ["terraform", "apply", "-input=false", "-auto-approve"]
        if var_file:
            cmd += ["-var-file", str(var_file)]
        return cmd

    @staticmethod
    def destroy_command(var_file=None):
        cmd = ["terraform", "destroy", "-input=false", "-auto-approve"]
        if var_file:
            cmd += ["-var-file", str(var_file)]
        return cmd

    @staticmethod
    def validate_command():
        return ["terraform", "validate"]

    @staticmethod
    def fmt_command():
        return ["terraform", "fmt", "-recursive"]

    @staticmethod
    def output_command(json=True):
        cmd = ["terraform", "output"]
        if json:
            cmd.append("-json")
        return cmd

    @staticmethod
    def state_list_command():
        return ["terraform", "state", "list"]
