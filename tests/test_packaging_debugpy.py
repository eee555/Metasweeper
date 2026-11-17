"""Protect release builds from accidentally bundling the optional debugger."""

import ast
import re
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def read(relative):
    return (ROOT / relative).read_text(encoding="utf-8-sig")


@pytest.mark.parametrize("spec", [
    "package_tool/macos/metasweeper_mac.spec",
    "package_tool/macos/plugin_manager_mac.spec",
])
def test_pyinstaller_specs_exclude_debugpy(spec):
    tree = ast.parse(read(spec))
    analysis = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "Analysis"
    )
    options = {item.arg: item.value for item in analysis.keywords}
    assert "debugpy" in ast.literal_eval(options["excludes"])
    assert not any("debugpy" in hook for hook in ast.literal_eval(options["runtime_hooks"]))


def test_windows_batch_excludes_debugpy_from_both_executables():
    text = read("build.bat")
    excludes = re.search(r"(?im)^set EXCLUDES=(.*)$", text).group(1)
    assert "--exclude-module debugpy" in excludes
    commands = re.findall(r"(?ims)^pyinstaller\s+.*?(?=\nif errorlevel)", text)
    assert len(commands) == 2
    assert all("%EXCLUDES%" in command for command in commands)
    assert "hook-debugpy" not in text.lower()
    assert not re.search(r"(?im)^\s*(?:xcopy|copy)\s+.*debugpy", text)


def test_ci_excludes_debugpy_from_both_executables():
    text = read(".github/workflows/python-app.yml")
    commands = re.findall(r"(?ms)^\s+pyinstaller `\s*\n.*?(?=\n\s+- name:)", text)
    assert len(commands) == 2
    assert all("--exclude-module debugpy" in command for command in commands)
    assert "hook-debugpy" not in text.lower()
    assert not re.search(r"for pkg in \[[^\]]*['\"]debugpy['\"]", text)


def test_nuitka_excludes_debugpy_from_both_executables():
    text = read("package_tool/build_nuitka_main.bat")
    options = re.search(r'(?im)^set "EXCLUDE_OPTIONS=([^"]+)"', text).group(1)
    excluded = re.search(r"--nofollow-import-to=([^\s]+)", options).group(1).split(",")
    assert "debugpy" in excluded
    commands = re.findall(r"(?ims)^\"%PYTHON%\" -m nuitka\s+.*?(?=\nif errorlevel)", text)
    assert len(commands) == 2
    assert all("%EXCLUDE_OPTIONS%" in command for command in commands)
    assert "--include-package=debugpy" not in text.lower()
    assert "NUITKA_INCLUDE_DEBUGPY" not in text
    assert not re.search(r"(?im)^\s*(?:xcopy|copy)\s+.*(?:debugpy|pydevd)", text)
