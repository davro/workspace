"""C / C++ project template driven by CMake."""
from __future__ import annotations

from ...core.ProjectTemplateRegistry import (InitCommand, InitPlan, ProjectProvider,
                                             ProjectSpec, render, slugify)

CMAKELISTS = """cmake_minimum_required(VERSION 3.16)
project(@NAME@ LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

add_executable(@NAME@ src/main.cpp)
target_include_directories(@NAME@ PRIVATE src)
"""

CMAKE_TESTS = """
enable_testing()
add_executable(@NAME@_tests tests/test_greeter.cpp)
target_include_directories(@NAME@_tests PRIVATE src)
add_test(NAME @NAME@_tests COMMAND @NAME@_tests)
"""

GREETER_HPP = """#pragma once
#include <string>

inline std::string greet(const std::string& name) {
    return "Hello, " + name + "!";
}
"""

MAIN_CPP = """#include <iostream>
#include "greeter.hpp"

int main() {
    std::cout << greet("World") << "\\n";
    return 0;
}
"""

TEST_CPP = """#include <cstdlib>
#include <iostream>
#include "greeter.hpp"

int main() {
    if (greet("World") != "Hello, World!") {
        std::cerr << "greet() returned an unexpected value\\n";
        return EXIT_FAILURE;
    }
    return EXIT_SUCCESS;
}
"""


class CMakeProvider(ProjectProvider):
    id = "cmake"
    language = "C / C++"
    label = "CMake"
    marker = "CMakeLists.txt"
    required_tools = ("cmake",)
    priority = 60
    gitignore = "build/\n.cache/\ncompile_commands.json\n"

    def build_plan(self, spec: ProjectSpec) -> InitPlan:
        name = slugify(spec.name, "_")
        cmake = render(CMAKELISTS, name=name)
        files = {"src/greeter.hpp": GREETER_HPP, "src/main.cpp": MAIN_CPP}
        if spec.include_tests:
            cmake += render(CMAKE_TESTS, name=name)
            files["tests/test_greeter.cpp"] = TEST_CPP
        files["CMakeLists.txt"] = cmake
        commands = [InitCommand("cmake", ("-S", ".", "-B", "build"), "Configure build", optional=True)]
        return InitPlan(files, commands)


PROVIDERS = [CMakeProvider()]
