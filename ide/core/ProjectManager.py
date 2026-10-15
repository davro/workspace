"""Project lifecycle orchestration: plan, create and check projects (Qt-free)."""
from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .ProjectTemplateRegistry import (InitCommand, InitPlan, ProjectProvider,
                                      ProjectSpec, ProjectTemplateRegistry)


@dataclass(frozen=True)
class HealthIssue:
    level: str  # "info" | "warning" | "error"
    message: str


class ProjectManager:
    def __init__(self, workspace_path, registry: ProjectTemplateRegistry | None = None):
        self.workspace_path = Path(workspace_path).expanduser().resolve()
        self.registry = registry or ProjectTemplateRegistry().discover()

    # ------------------------------------------------------------------ create
    def check_directory(self, directory) -> str | None:
        path = Path(directory).expanduser()
        if path.exists() and not path.is_dir():
            return "The selected path is not a directory."
        return None

    def check_location(self, directory) -> str | None:
        """Projects must be direct children of the workspace.

        The Projects tab only lists direct subfolders of the workspace, so a
        project anywhere else would become active but could never be unticked.
        """
        try:
            root = Path(directory).expanduser().resolve()
        except (OSError, RuntimeError):
            return "The selected path is not valid."
        if root == self.workspace_path:
            return ("This would create the project in the workspace root itself. "
                    "Tick 'Create a subfolder' or choose a different location.")
        if root.parent != self.workspace_path:
            return (f"Projects must be a direct subfolder of the workspace "
                    f"({self.workspace_path}) to appear in the Projects tab.")
        return None

    def build_plan(self, provider: ProjectProvider, spec: ProjectSpec) -> InitPlan:
        """Provider plan plus the common extras (README, .gitignore, git init)."""
        plan = provider.build_plan(spec)
        files = dict(plan.files)
        files.setdefault("README.md", f"# {spec.name}\n\n{spec.description}\n".rstrip() + "\n")
        commands: list[InitCommand] = []
        if spec.init_git:
            if provider.gitignore:
                files.setdefault(".gitignore", provider.gitignore)
            commands.append(InitCommand("git", ("init",), "Initialise Git repository"))
        commands += [c for c in plan.commands if spec.run_install or not c.optional]
        return InitPlan(files, commands, list(plan.notes))

    def conflicts(self, plan: InitPlan, directory) -> list[str]:
        root = Path(directory).expanduser()
        return sorted(rel for rel in plan.files if (root / rel).exists())

    def write_files(self, plan: InitPlan, directory) -> list[Path]:
        """Write the plan's files. Never overwrites: raises FileExistsError instead."""
        root = Path(directory).expanduser().resolve()
        existing = self.conflicts(plan, root)
        if existing:
            raise FileExistsError("Would overwrite: " + ", ".join(existing))
        root.mkdir(parents=True, exist_ok=True)
        written: list[Path] = []
        for rel, content in plan.files.items():
            target = (root / rel).resolve()
            if root not in target.parents:
                raise ValueError(f"Refusing to write outside the project: {rel}")
            target.parent.mkdir(parents=True, exist_ok=True)
            with open(target, "x", encoding="utf-8", newline="\n") as handle:  # "x" = fail if exists
                handle.write(content)
            written.append(target)
        return written

    # ------------------------------------------------------------------ health
    def check_health(self, path) -> list[HealthIssue]:
        """First cut of Project Health: config validity, tools, Git state."""
        root = Path(path).expanduser().resolve()
        provider = self.registry.detect(root)
        if provider is None:
            return [HealthIssue("warning", "No supported project configuration found.")]
        issues = [HealthIssue("info", f"{provider.language} · {provider.label}")]
        issues += [HealthIssue("error", problem) for problem in provider.validate_config(root)]
        missing = provider.missing_tools()
        if missing:
            issues.append(HealthIssue("warning", "Missing tools: " + ", ".join(missing)))
        if not (root / ".git").exists():
            issues.append(HealthIssue("info", "Not a Git repository."))
        elif shutil.which("git"):
            try:
                result = subprocess.run(["git", "status", "--porcelain"], cwd=root,
                                        capture_output=True, text=True, timeout=5)
            except (OSError, subprocess.SubprocessError):
                pass
            else:
                changed = len(result.stdout.splitlines())
                issues.append(HealthIssue("info", f"Git: {changed} changed file(s)" if changed
                                          else "Git: working tree clean"))
        return issues