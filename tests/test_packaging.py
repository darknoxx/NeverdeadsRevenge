"""Tests for the things that are not the game: the installer and the icon.

Nothing here runs ``install.sh`` for real. It writes into ``$HOME`` and calls
pip, and a test suite has no business doing either -- so the installer is checked
by its syntax, its argument handling, and the files it is made of.
"""

from __future__ import annotations

import os
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


# -- running on other systems -----------------------------------------------
def _as_macos(tmp_path: Path) -> dict[str, str]:
    """A PATH whose ``uname`` claims to be Darwin."""
    fake_bin = tmp_path / "fakebin"
    fake_bin.mkdir(exist_ok=True)
    uname = fake_bin / "uname"
    uname.write_text("#!/bin/sh\necho Darwin\n")
    uname.chmod(0o755)
    return {**os.environ, "PATH": f"{fake_bin}:{os.environ['PATH']}"}


def _plan(*args: str, env: dict[str, str] | None = None) -> str:
    """Run the installer in dry-run mode and return what it said it would do."""
    result = subprocess.run(
        [str(INSTALL), "--dry-run", *args],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


def test_the_dry_run_changes_nothing():
    """The whole point of it. Checked by looking for the files afterwards."""
    before = sorted(p.name for p in Path.home().glob(".local/share/applications/*"))
    _plan()
    after = sorted(p.name for p in Path.home().glob(".local/share/applications/*"))
    assert before == after


def test_the_plan_offers_the_menu_entry_on_linux():
    assert "menu entry  yes" in _plan()


def test_the_plan_skips_the_menu_entry_on_macos(tmp_path):
    """macOS has no applications menu for .desktop files.

    Writing one there does not fail, it just produces a file nothing opens --
    which is worse than not writing it, because it looks like it worked.
    """
    plan = _plan(env=_as_macos(tmp_path))
    assert "Darwin (macOS)" in plan
    assert "menu entry  no" in plan
    assert ".desktop" not in plan


def test_macos_can_still_be_told_to_write_the_entry(tmp_path):
    """--desktop is an escape hatch, not a mistake waiting to happen."""
    plan = _plan("--desktop", env=_as_macos(tmp_path))
    assert "menu entry  yes" in plan


def test_no_desktop_wins_on_linux_too():
    assert "menu entry  no" in _plan("--no-desktop")


def test_the_installer_knows_a_mac_python_stub_when_it_sees_one():
    """`command -v python3` passes on a Mac with no command line tools.

    /usr/bin/python3 is a shim there: it exists, and running it prints "no
    developer tools were found". Checking that the interpreter *runs* is the
    difference between a useful message and one about a version nobody can see.
    """
    body = INSTALL.read_text()
    assert "xcode-select --install" in body
    assert "import sys' >/dev/null" in body, "python3 is never actually run"
    assert "brew install python" in body


def test_the_too_old_message_on_a_mac_says_what_to_do(tmp_path):
    """The failure every Mac user hits first, and it must not just state a number.

    macOS ships Python 3.9 and never replaces it. The first version of this
    message said only "3.9.6 is what is installed" and left the user to work out
    the rest -- which cost five minutes on a real Mac.
    """
    fake_bin = tmp_path / "fakebin"
    fake_bin.mkdir()
    (fake_bin / "uname").write_text("#!/bin/sh\necho Darwin\n")
    (fake_bin / "python3").write_text(
        "#!/bin/sh\n"
        'case "$1" in\n'
        '  -V) echo "Python 3.9.6" ;;\n'
        '  -c) case "$2" in *version_info*) exit 1 ;; *) exit 0 ;; esac ;;\n'
        "  *) exit 0 ;;\n"
        "esac\n"
    )
    for script in fake_bin.iterdir():
        script.chmod(0o755)

    env = {**os.environ, "PATH": f"{fake_bin}:{os.environ['PATH']}"}
    result = subprocess.run(
        [str(INSTALL), "--dry-run"], capture_output=True, text=True, env=env
    )

    assert result.returncode != 0
    message = result.stderr
    assert "3.9.6" in message, "the message does not say what it found"
    assert "3.12" in message, "the message does not say what it needs"
    assert "brew install python" in message, "no way out given"
    assert "python.org" in message, "no alternative given"
    assert "--python" in message, "no way to point at another interpreter"


# -- choosing an interpreter ------------------------------------------------
def test_the_interpreter_can_be_chosen():
    """A Mac can have four Pythons and no reliable answer to which is python3."""
    default = _plan()
    chosen = _plan("--python", sys.executable)

    assert "(python3)" in default, "the default is not python3"
    assert sys.executable in chosen, "the chosen interpreter was not used"
    assert sys.executable not in default, "the plan ignored --python"


def test_choosing_an_interpreter_that_is_not_there_fails_loudly():
    result = subprocess.run(
        [str(INSTALL), "--dry-run", "--python", "/nope/python3"],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "/nope/python3" in result.stderr


def test_the_python_flag_insists_on_a_value():
    """`--python` with nothing after it would otherwise silently use python3."""
    result = subprocess.run(
        [str(INSTALL), "--python"], capture_output=True, text=True
    )
    assert result.returncode != 0
    assert "--python" in result.stderr


def test_the_help_documents_the_python_flag():
    result = subprocess.run(
        [str(INSTALL), "--help"], capture_output=True, text=True
    )
    assert "--python" in result.stdout


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


# -- the licence ------------------------------------------------------------
def test_the_licence_says_the_same_thing_everywhere():
    """README, LICENSE and the package metadata have to agree.

    They did not before: pyproject declared MIT and there was no LICENSE file at
    all, so the repository contradicted itself about the one thing a reader is
    entitled to take at face value.
    """
    import tomllib

    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    declared = project["license"]["text"]
    assert "GPL" in declared, f"pyproject still says {declared!r}"

    licence = (ROOT / "LICENSE").read_text(encoding="utf-8")
    assert "GNU GENERAL PUBLIC LICENSE" in licence
    assert "Version 3" in licence

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "General Public License" in readme, "the README does not name the licence"
    assert "LICENSE" in readme, "the README does not point at the file"


def test_the_licence_file_is_shipped_with_the_package():
    """A licence nobody receives is not a licence."""
    import tomllib

    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    files = project.get("license-files", [])
    assert files, "license-files is not set, so LICENSE will not be shipped"
    for name in files:
        assert (ROOT / name).exists(), f"license-files names {name}, which is not there"


def test_the_licence_file_is_the_real_thing():
    """Not a stub, not a summary -- the text the FSF publishes."""
    licence = (ROOT / "LICENSE").read_text(encoding="utf-8")
    assert len(licence) > 30_000, "the LICENSE file looks like a summary, not the text"
    assert "Copyright (C) 2007 Free Software Foundation" in licence
    assert "TERMS AND CONDITIONS" in licence
