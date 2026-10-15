"""Provider interface and registry for project templates.

This module is deliberately Qt-free so it can be unit tested without a GUI.
Each ecosystem (Composer, npm, Cargo, ...) is a ProjectProvider living in
ide/plugins/ProjectTemplates/<name>.py and exposing a module-level
``PROVIDERS`` list. ``ProjectTemplateRegistry.discover()`` finds them.
"""
from __future__ import annotations

import importlib
import pkgutil
import re
import shutil
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9._-]{0,63}$")


def slugify(name: str, sep: str = "-") -> str:
    """'My Project!' -> 'my-project' (or 'my_project' with sep='_')."""
    slug = re.sub(r"[^a-z0-9]+", sep, name.lower()).strip(sep)
    return slug or "project"


def render(template: str, **values: str) -> str:
    """Replace @KEY@ tokens. Used instead of str.format so code braces are safe."""
    for key, value in values.items():
        template = template.replace(f"@{key.upper()}@", value)
    return template


@dataclass(frozen=True)
class ProjectSpec:
    name: str
    directory: Path
    description: str = ""
    include_tests: bool = True
    init_git: bool = True
    run_install: bool = False  # run the provider's optional follow-up commands


@dataclass(frozen=True)
class InitCommand:
    program: str
    args: tuple[str, ...] = ()
    description: str = ""
    optional: bool = False  # only run when ProjectSpec.run_install is set

    @property
    def text(self) -> str:
        return " ".join((self.program, *self.args))


@dataclass
class InitPlan:
    files: dict[str, str] = field(default_factory=dict)  # relative path -> content
    commands: list[InitCommand] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


class ProjectProvider(ABC):
    """One language / package manager / build system."""

    id: str = ""
    language: str = ""          # shown in the Language combo
    label: str = ""             # shown in the Package manager combo
    marker: str = ""            # config file that identifies the project
    required_tools: tuple[str, ...] = ()
    gitignore: str = ""
    priority: int = 100         # ordering in the UI (lower first)

    def validate_name(self, name: str) -> str | None:
        if not NAME_RE.match(name):
            return "Use letters, digits, '.', '-' or '_' (start with a letter, max 64 characters)."
        return None

    def missing_tools(self) -> list[str]:
        return [tool for tool in self.required_tools if shutil.which(tool) is None]

    @abstractmethod
    def build_plan(self, spec: ProjectSpec) -> InitPlan:
        """Return files and commands. Must not touch the filesystem."""

    def validate_config(self, path: Path) -> list[str]:
        """Return a list of problems with an existing project's configuration."""
        if not (path / self.marker).is_file():
            return [f"{self.marker} not found"]
        return []


class ProjectTemplateRegistry:
    def __init__(self):
        self._providers: dict[str, ProjectProvider] = {}

    def register(self, provider: ProjectProvider) -> None:
        self._providers[provider.id] = provider

    def get(self, provider_id: str) -> ProjectProvider | None:
        return self._providers.get(provider_id)

    def all(self) -> list[ProjectProvider]:
        return sorted(self._providers.values(), key=lambda p: (p.priority, p.label))

    def languages(self) -> list[str]:
        seen: list[str] = []
        for provider in self.all():
            if provider.language not in seen:
                seen.append(provider.language)
        return seen

    def for_language(self, language: str) -> list[ProjectProvider]:
        return [p for p in self.all() if p.language == language]

    def detect(self, path) -> ProjectProvider | None:
        path = Path(path)
        return next((p for p in self.all() if (path / p.marker).is_file()), None)

    def discover(self, package: str | None = None) -> "ProjectTemplateRegistry":
        """Import every module in the ProjectTemplates package and register PROVIDERS."""
        if package is None:
            root = (__package__ or "").rpartition(".")[0]  # 'ide.core' -> 'ide'
            package = f"{root}.plugins.ProjectTemplates"
        pkg = importlib.import_module(package)
        for info in pkgutil.iter_modules(pkg.__path__):
            module = importlib.import_module(f"{package}.{info.name}")
            for provider in getattr(module, "PROVIDERS", ()):
                self.register(provider)
        return self