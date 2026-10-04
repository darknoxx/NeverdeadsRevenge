"""Tests for the things that are not the game: the installer and the icon.

Nothing here runs ``install.sh`` for real. It writes into ``$HOME`` and calls
pip, and a test suite has no business doing either -- so the installer is checked
by its syntax, its argument handling, and the files it is made of.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
INSTALL = ROOT / "install.sh"
MAKE_ICON = ROOT / "tools" / "make_icon.py"
ICON = ROOT / "assets" / "neverdeads-revenge.svg"
DESKTOP_TEMPLATE = ROOT / "assets" / "neverdeads-revenge.desktop.in"

SVG_NS = "{http://www.w3.org/2000/svg}"


# -- the installer ----------------------------------------------------------
def test_the_installer_is_valid_bash():
    """A syntax error here means the user's first command fails."""
    result = subprocess.run(
        ["bash", "-n", str(INSTALL)], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr


def test_the_installer_helps_without_doing_anything():
    result = subprocess.run(
        [str(INSTALL), "--help"], capture_output=True, text=True
    )
    assert result.returncode == 0
    for flag in ("--no-desktop", "--uninstall"):
        assert flag in result.stdout, f"{flag} is not documented"


def test_the_installer_rejects_an_unknown_option():
    """Better a loud error than a half-finished install."""
    result = subprocess.run(
        [str(INSTALL), "--not-a-real-flag"], capture_output=True, text=True
    )
    assert result.returncode != 0
    assert "unknown option" in result.stderr


def test_the_installer_does_not_need_sudo():
    """It installs per user, and that is a promise worth keeping.

    ``sudo`` is allowed inside quoted text -- telling the user which package to
    install is the whole point of the python3-venv message. What must not happen
    is the script *running* it, so the strings come out before the check.
    """
    body = INSTALL.read_text()
    without_messages = re.sub(r'"[^"]*"', '""', body)
    without_messages = re.sub(r"^#.*$", "", without_messages, flags=re.M)
    assert "sudo" not in without_messages, "install.sh runs sudo"


def test_the_installer_names_the_ubuntu_venv_package():
    """The one failure a fresh Ubuntu hits, and the fix is not guessable.

    ``python3 -m venv`` failing says something about ensurepip; the package the
    user actually needs is called python3-venv.
    """
    body = INSTALL.read_text()
    assert "python3-venv" in body


def test_the_installer_restores_the_executable_bit():
    """A zip download does not reliably keep it, and ./ndr is step one."""
    body = INSTALL.read_text()
    assert "chmod +x" in body and "ndr" in body


# -- the desktop entry ------------------------------------------------------
def test_the_desktop_entry_template_is_complete():
    body = DESKTOP_TEMPLATE.read_text()
    for key in (
        "Type=Application",
        "Name=",
        "Exec=",
        "Icon=",
        "Categories=Game",
    ):
        assert key in body, f"the desktop entry is missing {key!r}"
    for placeholder in ("@NAME@", "@EXEC@", "@SLUG@"):
        assert placeholder in body, f"{placeholder} was never substituted"


def test_the_desktop_entry_asks_for_a_terminal():
    """It is a TUI. Without this the menu item does nothing at all.

    This is the single line that decides whether clicking the icon works, so it
    is asserted rather than trusted.
    """
    assert re.search(r"^Terminal=true$", DESKTOP_TEMPLATE.read_text(), re.M)


def test_the_desktop_entry_validates_if_the_tool_is_here():
    if shutil.which("desktop-file-validate") is None:
        pytest.skip("desktop-file-validate is not installed")
    # Substitute the placeholders so the validator sees a real file.
    body = (
        DESKTOP_TEMPLATE.read_text()
        .replace("@NAME@", "Neverdead's Revenge")
        .replace("@EXEC@", "/usr/bin/true")
        .replace("@SLUG@", "neverdeads-revenge")
    )
    tmp = ROOT / ".desktop-check.desktop"
    try:
        tmp.write_text(body)
        result = subprocess.run(
            ["desktop-file-validate", str(tmp)], capture_output=True, text=True
        )
        assert result.returncode == 0, result.stdout + result.stderr
    finally:
        tmp.unlink(missing_ok=True)


# -- the icon ---------------------------------------------------------------
def _generate(tmp_path: Path, *args: str) -> Path:
    result = subprocess.run(
        [sys.executable, str(MAKE_ICON), "--out", str(tmp_path), *args],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    return tmp_path / "neverdeads-revenge.svg"


def test_the_committed_icon_is_what_the_generator_produces(tmp_path):
    """The icon is generated, so it must not be hand-edited out of sync.

    Without this, someone edits the SVG to nudge a pixel and the next
    regeneration silently undoes it.
    """
    generated = _generate(tmp_path)
    assert generated.read_text() == ICON.read_text(), (
        "assets/neverdeads-revenge.svg has drifted from tools/make_icon.py; "
        "run: python3 tools/make_icon.py"
    )


def test_the_icon_is_well_formed_svg():
    root = ET.fromstring(ICON.read_text())
    assert root.tag == f"{SVG_NS}svg"
    assert root.get("viewBox") == "0 0 256 256"


def test_the_block_motive_draws_the_hero_glyph_from_the_title_font(tmp_path):
    """Motive ``a`` is the N on the title screen, cell for cell.

    Derived rather than redrawn: a block letter duplicated by hand is a block
    letter that eventually disagrees with itself.
    """
    from neverdeads_revenge.ui.screens.title import BLOCK

    generated = _generate(tmp_path, "--motive", "a")
    root = ET.fromstring(generated.read_text())
    filled = {
        (round(float(r.get("x"))), round(float(r.get("y"))))
        for r in root.findall(f"{SVG_NS}rect")
        if r.get("fill") == "#a855f7"
    }
    assert filled, "the icon has no purple blocks at all"

    cell = 30
    origin = min(x for x, _ in filled)
    grid = {((x - origin) // cell, (y - origin) // cell) for x, y in filled}
    expected = {
        (col, row)
        for row, line in enumerate(BLOCK["N"])
        for col, char in enumerate(line)
        if char == "█"
    }
    assert grid == expected


# -- the skull --------------------------------------------------------------
def test_the_skull_sprite_is_a_rectangle():
    """Ragged rows would shear the drawing, and a sheared skull is not one."""
    from tools.make_icon import SKULL, SKULL_CELLS

    assert len(SKULL) == SKULL_CELLS
    for row, line in enumerate(SKULL):
        assert len(line) == SKULL_CELLS, f"row {row} is {len(line)} wide"


def test_the_skull_sprite_uses_only_known_characters():
    """The renderer ignores anything it does not know, so a typo is silent."""
    from tools.make_icon import SKULL

    allowed = {"#", "o", "."}
    for row, line in enumerate(SKULL):
        assert set(line) <= allowed, f"row {row} has {set(line) - allowed}"


def test_the_skull_is_left_right_symmetric():
    """A skull that is not symmetric reads as a mistake, not a style.

    Cheap to check and impossible to unsee once it is wrong, so it is checked.
    """
    from tools.make_icon import SKULL

    for row, line in enumerate(SKULL):
        assert line == line[::-1], f"row {row} is not symmetric: {line!r}"


def test_the_skull_has_two_matching_eye_sockets():
    """Two sockets, the same size, on every row that has any."""
    from tools.make_icon import SKULL

    rows = [row for row, line in enumerate(SKULL) if "o" in line]
    assert rows, "the skull has no eye sockets"
    assert rows == list(range(min(rows), max(rows) + 1)), "the sockets have gaps"

    for row in rows:
        runs = re.findall(r"o+", SKULL[row])
        assert len(runs) == 2, f"row {row} has {len(runs)} sockets"
        assert runs[0] == runs[1], f"row {row} has mismatched sockets: {runs}"


def test_the_committed_icon_is_the_skull(tmp_path):
    """The shipped icon uses bone and glowing sockets, not the block N."""
    from tools.make_icon import BONE, PURPLE

    root = ET.fromstring(ICON.read_text())
    colours = {r.get("fill") for r in root.findall(f"{SVG_NS}rect")}
    assert BONE in colours, "the icon has no bone in it"
    assert PURPLE in colours, "the eye sockets are not lit"

    generated = _generate(tmp_path)  # default motive
    assert generated.read_text() == ICON.read_text()


@pytest.mark.parametrize("motive", ["skull", "a", "b", "c"])
def test_every_motive_generates_a_usable_icon(tmp_path, motive):
    generated = _generate(tmp_path, "--motive", motive)
    root = ET.fromstring(generated.read_text())
    assert root.tag == f"{SVG_NS}svg"
    assert root.findall(f"{SVG_NS}rect"), "the icon has no background"


def test_the_icon_ships_no_stray_characters():
    """The title art's lesson, applied here: blocks or nothing."""
    body = ICON.read_text()
    assert "█" not in body, "the SVG should use rects, not block characters"
