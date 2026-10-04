"""Tests for the entry point.

``python -m neverdeads_revenge`` and the ``ndr`` launcher both go through
:mod:`neverdeads_revenge.__main__`. That module had an import pointing at a
module path that does not exist, so the game could not start at all while every
other test passed -- the UI tests import the app directly and never touch the
entry point. These tests exist to keep that gap closed.

The import is deliberately inside :func:`main` (so that importing this module
does not pull in Textual), which means the failure only shows up when the game
is actually launched. Hence the subprocess check as well as the source scan.
"""

from __future__ import annotations

import ast
import importlib.util
import pathlib
import subprocess
import sys

PACKAGE_ROOT = pathlib.Path(__file__).parent.parent / "src" / "neverdeads_revenge"


def imported_modules() -> set[str]:
    """Every module ``__main__`` imports, read from its source."""
    source = (PACKAGE_ROOT / "__main__.py").read_text()
    names: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_entrypoint_imports_only_modules_that_exist():
    """Every name ``__main__`` imports must resolve.

    This is the check that would have caught the broken entry point.
    """
    for name in imported_modules():
        assert importlib.util.find_spec(name) is not None, (
            f"__main__ imports {name!r}, which does not exist"
        )


def test_entrypoint_uses_the_same_app_class_as_the_ui_tests():
    from neverdeads_revenge.ui.app import NeverdeadsRevenge

    app_module = next(
        name for name in imported_modules() if name.endswith("app")
    )
    module = __import__(app_module, fromlist=["NeverdeadsRevenge"])
    assert module.NeverdeadsRevenge is NeverdeadsRevenge


def test_main_is_callable():
    from neverdeads_revenge import __main__

    assert callable(__main__.main)


def test_no_top_level_app_module():
    """The application lives under ``ui``; there is no top-level ``app``.

    Guards against an alias being added back, which would leave two import
    paths for one class.
    """
    assert importlib.util.find_spec("neverdeads_revenge.app") is None


def test_launcher_reaches_the_app_in_a_subprocess():
    """Start the app the way the launcher does, then stop it.

    ``run_test`` cannot cover this: it drives an app instance directly and never
    executes ``__main__``, which is how a broken entry point survived a fully
    green suite.

    The app does not exit on its own -- it waits for keys -- so this starts it,
    gives it a moment to paint the title screen, and kills it. Reaching the
    screen is the assertion; the exit status of a killed process is not.
    """
    process = subprocess.Popen(
        [sys.executable, "-c", "import neverdeads_revenge.__main__ as m; m.main()"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
    )
    try:
        try:
            _, stderr = process.communicate(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill()
            _, stderr = process.communicate()
    finally:
        if process.poll() is None:  # pragma: no cover - defensive
            process.kill()

    combined = (stderr or b"").decode(errors="replace")
    assert "ModuleNotFoundError" not in combined, combined
    assert "ImportError" not in combined, combined
    assert "Traceback" not in combined, combined