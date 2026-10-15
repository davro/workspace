"""JavaScript / npm project template (plain ESM; TypeScript can be added as a second provider)."""
from __future__ import annotations

import json
from pathlib import Path

from ...core.ProjectTemplateRegistry import (InitCommand, InitPlan, ProjectProvider,
                                             ProjectSpec, slugify)

GREET_JS = """export function greet(name) {
  return `Hello, ${name}!`;
}
"""

INDEX_JS = """import { greet } from "./greet.js";

console.log(greet("World"));
"""

TEST_JS = """import { test } from "node:test";
import assert from "node:assert/strict";
import { greet } from "../src/greet.js";

test("greet", () => {
  assert.equal(greet("World"), "Hello, World!");
});
"""


class NpmProvider(ProjectProvider):
    id = "npm"
    language = "JavaScript / TypeScript"
    label = "npm"
    marker = "package.json"
    required_tools = ("node", "npm")
    priority = 20
    gitignore = "node_modules/\ndist/\n.env\n*.log\n"

    def build_plan(self, spec: ProjectSpec) -> InitPlan:
        scripts = {"start": "node src/index.js"}
        files = {"src/greet.js": GREET_JS, "src/index.js": INDEX_JS}
        if spec.include_tests:
            scripts["test"] = "node --test"  # built-in runner, no dependencies needed
            files["tests/greet.test.js"] = TEST_JS
        config = {
            "name": slugify(spec.name),
            "version": "0.1.0",
            "description": spec.description,
            "private": True,
            "type": "module",
            "scripts": scripts,
        }
        files["package.json"] = json.dumps(config, indent=2) + "\n"
        return InitPlan(files, [InitCommand("npm", ("install",), "Install dependencies", optional=True)])

    def validate_config(self, path: Path) -> list[str]:
        problems = super().validate_config(path)
        if problems:
            return problems
        try:
            data = json.loads((path / self.marker).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            return [f"package.json is not valid JSON: {exc}"]
        if isinstance(data, dict) and (data.get("dependencies") or data.get("devDependencies")) \
                and not (path / "node_modules").is_dir():
            problems.append("Dependencies not installed (no node_modules/ directory)")
        return problems


PROVIDERS = [NpmProvider()]
