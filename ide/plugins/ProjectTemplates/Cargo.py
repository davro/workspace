"""Rust / Cargo project template."""
from __future__ import annotations

import json

from ...core.ProjectTemplateRegistry import InitPlan, ProjectProvider, ProjectSpec, slugify

MAIN_RS = """fn greet(name: &str) -> String {
    format!("Hello, {name}!")
}

fn main() {
    println!("{}", greet("World"));
}
"""

TESTS_RS = """
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn greets() {
        assert_eq!(greet("World"), "Hello, World!");
    }
}
"""


class CargoProvider(ProjectProvider):
    id = "cargo"
    language = "Rust"
    label = "Cargo"
    marker = "Cargo.toml"
    required_tools = ("cargo",)
    priority = 40
    gitignore = "/target\n"

    def build_plan(self, spec: ProjectSpec) -> InitPlan:
        cargo_toml = (
            "[package]\n"
            f"name = {json.dumps(slugify(spec.name))}\n"
            'version = "0.1.0"\n'
            'edition = "2021"\n'
            f"description = {json.dumps(spec.description)}\n\n"
            "[dependencies]\n"
        )
        main = MAIN_RS + (TESTS_RS if spec.include_tests else "")
        return InitPlan({"Cargo.toml": cargo_toml, "src/main.rs": main})


PROVIDERS = [CargoProvider()]
