"""Python / pip project template (src layout, pyproject.toml)."""
from __future__ import annotations

import json
import tomllib
from pathlib import Path

from ...core.ProjectTemplateRegistry import (InitCommand, InitPlan, ProjectProvider,
                                             ProjectSpec, render, slugify)

PYPROJECT = """[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = @NAME@
version = "0.1.0"
description = @DESC@
readme = "README.md"
requires-python = ">=3.10"
dependencies = []
@DEV@
[tool.setuptools.packages.find]
where = ["src"]
@PYTEST@"""

DEV_DEPS = """
[project.optional-dependencies]
dev = ["pytest"]
"""

PYTEST = """
[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
"""

INIT_PY = '''"""@PKG@ package."""


def greet(name: str) -> str:
    return f"Hello, {name}!"
'''

TEST_PY = '''from @PKG@ import greet


def test_greet():
    assert greet("World") == "Hello, World!"
'''


class PythonProvider(ProjectProvider):
    id = "python"
    language = "Python"
    label = "pip (pyproject.toml)"
    marker = "pyproject.toml"
    required_tools = ("python3",)
    priority = 30
    gitignore = "__pycache__/\n*.pyc\n.venv/\n*.egg-info/\ndist/\nbuild/\n.pytest_cache/\n.mypy_cache/\n.ruff_cache/\n"

    def build_plan(self, spec: ProjectSpec) -> InitPlan:
        pkg = slugify(spec.name, "_")
        files = {f"src/{pkg}/__init__.py": render(INIT_PY, pkg=pkg)}
        if spec.include_tests:
            files["tests/test_basic.py"] = render(TEST_PY, pkg=pkg)
        files["pyproject.toml"] = render(
            PYPROJECT, name=json.dumps(slugify(spec.name)), desc=json.dumps(spec.description),
            dev=DEV_DEPS if spec.include_tests else "",
            pytest=PYTEST if spec.include_tests else "")
        commands = [InitCommand("python3", ("-m", "venv", ".venv"),
                                "Create virtual environment (.venv)", optional=True)]
        return InitPlan(files, commands)

    def validate_config(self, path: Path) -> list[str]:
        problems = super().validate_config(path)
        if problems:
            return problems
        try:
            tomllib.loads((path / self.marker).read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError) as exc:
            return [f"pyproject.toml is not valid TOML: {exc}"]
        return []


PROVIDERS = [PythonProvider()]
