"""Tests for the template registry, providers and ProjectManager (no Qt needed)."""
import json
import tomllib

import pytest

from ide.core.ProjectManager import ProjectManager
from ide.core.ProjectTemplateRegistry import ProjectSpec, ProjectTemplateRegistry

EXPECTED = {"composer", "npm", "python", "cargo", "go", "cmake"}


@pytest.fixture
def manager(tmp_path):
    return ProjectManager(tmp_path)


def spec_for(tmp_path, **kw):
    return ProjectSpec(name="my-project", directory=tmp_path / "proj", **kw)


def test_discovery_finds_all_providers():
    registry = ProjectTemplateRegistry().discover()
    assert {p.id for p in registry.all()} == EXPECTED
    assert registry.languages()[0] == "PHP"


@pytest.mark.parametrize("provider_id", sorted(EXPECTED))
@pytest.mark.parametrize("tests", [True, False])
def test_every_provider_creates_its_marker(manager, tmp_path, provider_id, tests):
    provider = manager.registry.get(provider_id)
    spec = spec_for(tmp_path, include_tests=tests)
    plan = manager.build_plan(provider, spec)
    manager.write_files(plan, spec.directory)
    assert (spec.directory / provider.marker).is_file()
    assert (spec.directory / "README.md").is_file()
    assert (spec.directory / ".gitignore").is_file()
    assert any(c.program == "git" for c in plan.commands)
    # Created projects are recognised again and pass config validation
    assert manager.registry.detect(spec.directory) is provider
    assert not [p for p in provider.validate_config(spec.directory) if "not installed" not in p]


def test_optional_commands_only_with_run_install(manager, tmp_path):
    provider = manager.registry.get("composer")
    off = manager.build_plan(provider, spec_for(tmp_path))
    on = manager.build_plan(provider, spec_for(tmp_path, run_install=True))
    assert "composer" not in [c.program for c in off.commands]
    assert "composer" in [c.program for c in on.commands]


def test_composer_json_content(manager, tmp_path):
    spec = spec_for(tmp_path)
    plan = manager.build_plan(manager.registry.get("composer"), spec)
    data = json.loads(plan.files["composer.json"])
    assert data["name"] == "local/my-project"
    assert data["scripts"] == {"test": "phpunit"}
    assert "phpunit.xml.dist" in plan.files
    no_tests = json.loads(manager.build_plan(manager.registry.get("composer"),
                                             spec_for(tmp_path, include_tests=False)).files["composer.json"])
    assert "require-dev" not in no_tests


def test_pyproject_is_valid_toml(manager, tmp_path):
    plan = manager.build_plan(manager.registry.get("python"), spec_for(tmp_path, description='say "hi"'))
    data = tomllib.loads(plan.files["pyproject.toml"])
    assert data["project"]["name"] == "my-project"
    assert "src/my_project/__init__.py" in plan.files


def test_existing_files_are_never_overwritten(manager, tmp_path):
    spec = spec_for(tmp_path)
    spec.directory.mkdir()
    (spec.directory / "composer.json").write_text("{}")
    plan = manager.build_plan(manager.registry.get("composer"), spec)
    assert manager.conflicts(plan, spec.directory) == ["composer.json"]
    with pytest.raises(FileExistsError):
        manager.write_files(plan, spec.directory)
    assert (spec.directory / "composer.json").read_text() == "{}"
    assert not (spec.directory / "src").exists()  # nothing written at all


def test_path_traversal_is_rejected(manager, tmp_path):
    from ide.core.ProjectTemplateRegistry import InitPlan
    with pytest.raises(ValueError):
        manager.write_files(InitPlan(files={"../evil.txt": "x"}), tmp_path / "proj")


def test_name_validation(manager):
    provider = manager.registry.get("npm")
    assert provider.validate_name("good-name_1") is None
    for bad in ("1abc", "../x", "a b", "", "x" * 80):
        assert provider.validate_name(bad)


def test_health_reports_invalid_config(manager, tmp_path):
    (tmp_path / "composer.json").write_text("{not json")
    issues = manager.check_health(tmp_path)
    assert any(i.level == "error" for i in issues)
    assert manager.check_health(tmp_path / "empty-nonexistent")[0].level == "warning"


def test_location_must_be_direct_child_of_workspace(manager, tmp_path):
    assert manager.check_location(tmp_path / "demo") is None
    assert "workspace root" in manager.check_location(tmp_path)
    assert "direct subfolder" in manager.check_location(tmp_path / "a" / "b")
    assert "direct subfolder" in manager.check_location(tmp_path.parent / "elsewhere")
