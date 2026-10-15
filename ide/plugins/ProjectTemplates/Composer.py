"""PHP / Composer project template (reference implementation for other providers)."""
from __future__ import annotations

import json
from pathlib import Path

from ...core.ProjectTemplateRegistry import (InitCommand, InitPlan, ProjectProvider,
                                             ProjectSpec, slugify)

GREETER = """<?php

declare(strict_types=1);

namespace App;

final class Greeter
{
    public function greet(string $name): string
    {
        return "Hello, {$name}!";
    }
}
"""

GREETER_TEST = """<?php

declare(strict_types=1);

namespace App\\Tests;

use App\\Greeter;
use PHPUnit\\Framework\\TestCase;

final class GreeterTest extends TestCase
{
    public function testGreet(): void
    {
        $this->assertSame('Hello, World!', (new Greeter())->greet('World'));
    }
}
"""

PHPUNIT_XML = """<?xml version="1.0" encoding="UTF-8"?>
<phpunit xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:noNamespaceSchemaLocation="vendor/phpunit/phpunit/phpunit.xsd"
         bootstrap="vendor/autoload.php"
         colors="true">
    <testsuites>
        <testsuite name="default">
            <directory>tests</directory>
        </testsuite>
    </testsuites>
    <source>
        <include>
            <directory>src</directory>
        </include>
    </source>
</phpunit>
"""


class ComposerProvider(ProjectProvider):
    id = "composer"
    language = "PHP"
    label = "Composer"
    marker = "composer.json"
    required_tools = ("php", "composer")
    priority = 10
    gitignore = "/vendor/\n.phpunit.cache/\n.phpunit.result.cache\ncomposer.phar\n"

    def build_plan(self, spec: ProjectSpec) -> InitPlan:
        config: dict = {
            "name": f"local/{slugify(spec.name)}",
            "description": spec.description,
            "type": "project",
            "require": {"php": "^8.2"},
            "autoload": {"psr-4": {"App\\": "src/"}},
            "config": {"sort-packages": True},
        }
        files = {"src/Greeter.php": GREETER}
        if spec.include_tests:
            config["require-dev"] = {"phpunit/phpunit": "^11.0"}
            config["autoload-dev"] = {"psr-4": {"App\\Tests\\": "tests/"}}
            config["scripts"] = {"test": "phpunit"}
            files["tests/GreeterTest.php"] = GREETER_TEST
            files["phpunit.xml.dist"] = PHPUNIT_XML
        files["composer.json"] = json.dumps(config, indent=4) + "\n"
        commands = [InitCommand("composer", ("install", "--no-interaction", "--no-ansi"),
                                "Install dependencies", optional=True)]
        return InitPlan(files, commands)

    def validate_config(self, path: Path) -> list[str]:
        problems = super().validate_config(path)
        if problems:
            return problems
        try:
            data = json.loads((path / self.marker).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            return [f"composer.json is not valid JSON: {exc}"]
        if not isinstance(data, dict):
            return ["composer.json must contain a JSON object"]
        if "name" not in data:
            problems.append("composer.json has no 'name'")
        if not (path / "vendor").is_dir():
            problems.append("Dependencies not installed (no vendor/ directory)")
        return problems


PROVIDERS = [ComposerProvider()]
