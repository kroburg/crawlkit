"""The dependency-free layers stay dependency-free.

The link checker's most useful property is that it runs anywhere a Python
interpreter runs. That property survives on luck and habit unless something
enforces it; here, adding `import requests` to probe.py fails the suite.
"""

import ast
import sys
from pathlib import Path

import pytest

PKG = Path(__file__).resolve().parents[1] / "crawlkit"

# Modules that must never grow a third-party import.
PURE = [
    "probe.py",
    "schedule.py",
    "linkstate.py",
    "ua.py",
    "exits.py",
    "contract/__init__.py",
    "cli/check_links.py",
    "qa/echo.py",
    "qa/census.py",
    "qa/agreement.py",
]

ALLOWED_THIRD_PARTY = set()


def top_level_imports(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
    return names


@pytest.mark.parametrize("relative", PURE)
def test_module_imports_only_stdlib_or_crawlkit(relative):
    path = PKG / relative
    assert path.is_file(), relative
    offenders = {
        name
        for name in top_level_imports(path)
        if name not in sys.stdlib_module_names
        and name != "crawlkit"
        and name not in ALLOWED_THIRD_PARTY
    }
    assert not offenders, f"{relative} imports {sorted(offenders)}"


def test_the_pure_layer_imports_without_any_optional_dependency(monkeypatch):
    """Simulate a bare interpreter: playwright and PIL simply absent."""
    for blocked in ("playwright", "PIL"):
        monkeypatch.setitem(sys.modules, blocked, None)
    import importlib

    for name in ("crawlkit.probe", "crawlkit.schedule", "crawlkit.linkstate"):
        importlib.reload(importlib.import_module(name))
