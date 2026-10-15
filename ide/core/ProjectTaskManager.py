"""Project discovery and task definitions for Workspace."""
from __future__ import annotations
import json
import re
import shlex
import tomllib
from dataclasses import dataclass
from pathlib import Path

IGNORED = {".git", ".hg", ".svn", ".idea", ".vscode", "__pycache__", ".venv",
           "venv", "env", "node_modules", "vendor", "target", "build", "dist",
           "out", ".pytest_cache", ".mypy_cache"}

@dataclass(frozen=True)
class ProjectTask:
    project_path: Path
    name: str
    category: str
    program: str
    args: tuple[str, ...]
    description: str = ""
    @property
    def command_text(self):
        return shlex.join((self.program, *self.args))

@dataclass(frozen=True)
class ProjectInfo:
    path: Path
    name: str
    project_types: tuple[str, ...]
    tasks: tuple[ProjectTask, ...]
    @property
    def type_label(self):
        return " · ".join(self.project_types) or "Project"

class ProjectTaskManager:
    MARKERS = ("package.json", "pyproject.toml", "requirements.txt", "setup.py",
               "setup.cfg", "composer.json", "Cargo.toml", "go.mod", "Makefile",
               "makefile", "CMakeLists.txt")

    def __init__(self, workspace_path):
        self.workspace_path = Path(workspace_path).expanduser().resolve()

    def _add(self, tasks, path, name, category, program, args, description=""):
        tasks.append(ProjectTask(path, name, category, program, tuple(args), description))

    def _has_marker(self, path):
        return any((path / name).is_file() for name in self.MARKERS)

    def discover_projects(self):
        root = self.workspace_path
        candidates = []
        if root.is_dir() and self._has_marker(root):
            candidates.append(root)
        if root.is_dir():
            try:
                candidates += [p for p in sorted(root.iterdir(), key=lambda x: x.name.lower())
                               if p.is_dir() and p.name not in IGNORED and
                               not p.name.startswith(".") and self._has_marker(p)]
            except OSError:
                pass
        found, seen = [], set()
        for path in candidates:
            path = path.resolve()
            if path in seen:
                continue
            seen.add(path)
            info = self.inspect_project(path)
            if info.project_types:
                found.append(info)
        return found

    def inspect_project(self, path):
        path = Path(path).expanduser().resolve()
        types, tasks = [], []

        # Node.js: discover scripts without executing them.
        package = path / "package.json"
        if package.is_file():
            types.append("Node.js")
            try:
                scripts = json.loads(package.read_text(encoding="utf-8")).get("scripts", {})
            except (OSError, ValueError):
                scripts = {}
            if isinstance(scripts, dict):
                categories = {"start": "Run", "dev": "Run", "serve": "Run",
                              "test": "Test", "lint": "Lint", "check": "Check",
                              "typecheck": "Check", "build": "Build"}
                for name, command in scripts.items():
                    if not isinstance(name, str):
                        continue
                    category = categories.get(name.lower(), "Script")
                    self._add(tasks, path, f"{category}: {name}", category, "npm",
                              ("run", name), f"package.json script: {command}")

        ##############################################################################
        # Python projects.
        ##############################################################################
        pyproject, requirements = path / "pyproject.toml", path / "requirements.txt"
        if any((path / x).is_file() for x in ("pyproject.toml", "requirements.txt", "setup.py", "setup.cfg")):
            types.append("Python")
            config = {}
            if pyproject.is_file():
                try:
                    config = tomllib.loads(pyproject.read_text(encoding="utf-8"))
                except (OSError, tomllib.TOMLDecodeError):
                    pass
            has_tests = ((path / "tests").is_dir() or any(path.glob("test_*.py"))
                         or "pytest" in config.get("tool", {}))
            if has_tests:
                self._add(tasks, path, "Test: pytest", "Test", "python3", ("-m", "pytest"),
                          "Runs the project's pytest suite.")
            if config.get("build-system"):
                self._add(tasks, path, "Build: Python package", "Build", "python3", ("-m", "build"),
                          "Requires the 'build' package in the active Python environment.")
            tool = config.get("tool", {})
            if isinstance(tool, dict) and "ruff" in tool:
                self._add(tasks, path, "Lint: Ruff", "Lint", "ruff", ("check", "."))
            if isinstance(tool, dict) and "mypy" in tool:
                self._add(tasks, path, "Check: mypy", "Check", "mypy", (".",))

        ##############################################################################
        # Composer / PHP.
        ##############################################################################
        composer = path / "composer.json"
        if composer.is_file():
            types.append("PHP / Composer")
        
            try:
                scripts = json.loads(
                    composer.read_text(encoding="utf-8")
                ).get("scripts", {})
            except (OSError, ValueError):
                scripts = {}
        
            if isinstance(scripts, dict):
                categories = {
                    "test": "Test",
                    "lint": "Lint",
                    "build": "Build",
                    "start": "Run",
                }
                for name, value in scripts.items():
                    if isinstance(name, str) and not name.startswith("@"):
                        category = categories.get(name.lower(), "Script")
                        self._add(
                            tasks,
                            path,
                            f"{category}: {name}",
                            category,
                            "composer",
                            ("run-script", name),
                            f"composer.json script: {value}",
                        )
        
            if any(
                (path / x).exists()
                for x in ("phpunit.xml", "phpunit.xml.dist")
            ):
                self._add(
                    tasks,
                    path,
                    "Test: PHPUnit",
                    "Test",
                    "vendor/bin/phpunit",
                    (),
                )
        
            # Add the built-in Composer commands here.
            tasks.extend(self._composer_tasks(path))

        ##############################################################################
        # Rust.
        ##############################################################################
        if (path / "Cargo.toml").is_file():
            types.append("Rust / Cargo")
            for name, category, args in (("Run: cargo run", "Run", ("run",)),
                                         ("Test: cargo test", "Test", ("test",)),
                                         ("Build: cargo build", "Build", ("build",))):
                self._add(tasks, path, name, category, "cargo", args)

        ##############################################################################
        # Go.
        ##############################################################################
        if (path / "go.mod").is_file():
            types.append("Go")
            for name, category, args in (("Run: go run .", "Run", ("run", ".")),
                                         ("Test: go test ./...", "Test", ("test", "./...")),
                                         ("Build: go build ./...", "Build", ("build", "./..."))):
                self._add(tasks, path, name, category, "go", args)

        # Make: parse simple explicit target declarations only.
        makefile = next((path / x for x in ("Makefile", "makefile") if (path / x).is_file()), None)
        if makefile:
            types.append("Make")
            try:
                lines = makefile.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                lines = []
            targets = []
            for line in lines:
                if line.startswith(("\t", " ", "#")) or any(x in line for x in (":=", "?=", "+=")):
                    continue
                match = re.match(r"^([A-Za-z0-9_.-]+)\s*:(?![=])", line)
                if match:
                    target = match.group(1)
                    if target not in {".PHONY", ".DEFAULT", ".SUFFIXES"} and not target.startswith(".") and "%" not in target and target not in targets:
                        targets.append(target)
            for target in targets:
                category = {"test": "Test", "lint": "Lint", "check": "Check",
                            "build": "Build", "run": "Run", "clean": "Clean"}.get(target.lower(), "Make")
                self._add(tasks, path, f"{category}: make {target}", category, "make", (target,))

        # CMake is deliberately split into configure then build.
        if (path / "CMakeLists.txt").is_file():
            types.append("CMake")
            self._add(tasks, path, "Configure: CMake", "Configure", "cmake", ("-S", ".", "-B", "build"))
            self._add(tasks, path, "Build: CMake", "Build", "cmake", ("--build", "build"))

        return ProjectInfo(path, path.name or str(path), tuple(types), tuple(tasks))

    def tasks_for_directory(self, path):
        return list(self.inspect_project(path).tasks)


    def _composer_tasks(self, project_path: Path) -> list[ProjectTask]:
        """Return common Composer commands for a PHP project."""
    
        composer_json = project_path / "composer.json"
    
        if not composer_json.is_file():
            return []
    
        commands = [
            ProjectTask(
                project_path=project_path,
                name="Install dependencies",
                category="Composer",
                program="composer",
                args=("install",),
                description="Install dependencies from composer.lock.",
            ),
            ProjectTask(
                project_path=project_path,
                name="Update dependencies",
                category="Composer",
                program="composer",
                args=("update",),
                description="Update dependencies and rewrite composer.lock.",
            ),
            ProjectTask(
                project_path=project_path,
                name="Validate configuration",
                category="Composer",
                program="composer",
                args=("validate",),
                description="Validate composer.json and composer.lock.",
            ),
            ProjectTask(
                project_path=project_path,
                name="Dump autoload",
                category="Composer",
                program="composer",
                args=("dump-autoload",),
                description="Regenerate Composer autoload files.",
            ),
            ProjectTask(
                project_path=project_path,
                name="Check outdated dependencies",
                category="Composer",
                program="composer",
                args=("outdated",),
                description="List dependencies with newer available versions.",
            ),
            ProjectTask(
                project_path=project_path,
                name="Diagnose Composer",
                category="Composer",
                program="composer",
                args=("diagnose",),
                description="Check Composer configuration and environment.",
            ),
        ]
    
        return commands