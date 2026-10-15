"""Go modules project template."""
from __future__ import annotations

from ...core.ProjectTemplateRegistry import (InitCommand, InitPlan, ProjectProvider,
                                             ProjectSpec, slugify)

MAIN_GO = """package main

import "fmt"

func Greet(name string) string {
	return fmt.Sprintf("Hello, %s!", name)
}

func main() {
	fmt.Println(Greet("World"))
}
"""

TEST_GO = """package main

import "testing"

func TestGreet(t *testing.T) {
	if got := Greet("World"); got != "Hello, World!" {
		t.Fatalf("unexpected greeting: %q", got)
	}
}
"""


class GoProvider(ProjectProvider):
    id = "go"
    language = "Go"
    label = "Go modules"
    marker = "go.mod"
    required_tools = ("go",)
    priority = 50
    gitignore = "bin/\n*.test\n*.out\n"

    def build_plan(self, spec: ProjectSpec) -> InitPlan:
        files = {
            "go.mod": f"module {slugify(spec.name)}\n\ngo 1.22\n",
            "main.go": MAIN_GO,
        }
        if spec.include_tests:
            files["main_test.go"] = TEST_GO
        return InitPlan(files, [InitCommand("go", ("mod", "tidy"), "Tidy module", optional=True)])


PROVIDERS = [GoProvider()]
