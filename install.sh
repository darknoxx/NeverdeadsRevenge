#!/usr/bin/env bash
#
# Install Neverdead's Revenge for the current user.
#
# Everything goes under $HOME -- no sudo, nothing system-wide, and the game stays
# in this directory. Run it again any time; it reuses what is already there.
#
#   ./install.sh                 set up and add the menu entry
#   ./install.sh --no-desktop    set up only
#   ./install.sh --uninstall     remove the menu entry and the icon
#
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
slug="neverdeads-revenge"
name="Neverdead's Revenge"

data_home="${XDG_DATA_HOME:-$HOME/.local/share}"
launcher_dir="$data_home/$slug"
desktop_dir="$data_home/applications"
icon_dir="$data_home/icons/hicolor/scalable/apps"

want_desktop=1
want_uninstall=0

say() { printf '\033[1m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m warning:\033[0m %s\n' "$*" >&2; }
die() { printf '\033[1;31m error:\033[0m %s\n' "$*" >&2; exit 1; }

usage() {
    sed -n '3,11p' "$0" | sed 's/^# \{0,1\}//'
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --no-desktop) want_desktop=0 ;;
        --uninstall) want_uninstall=1 ;;
        -h|--help) usage; exit 0 ;;
        *) die "unknown option '$1' (try --help)" ;;
    esac
    shift
done

# -- uninstall --------------------------------------------------------------

if [[ $want_uninstall -eq 1 ]]; then
    say "Removing the menu entry"
    rm -f "$desktop_dir/$slug.desktop"
    rm -f "$icon_dir/$slug.svg"
    rm -rf "$launcher_dir"
    command -v update-desktop-database >/dev/null && update-desktop-database "$desktop_dir" 2>/dev/null || true
    say "Done. The game itself is untouched -- delete this directory to remove it,"
    say "and .venv inside it if you want the virtualenv gone too."
    exit 0
fi

# -- python -----------------------------------------------------------------

command -v python3 >/dev/null || die "python3 not found. Install it with: sudo apt install python3"

if ! python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)'; then
    die "Python 3.12 or newer is required, but $(python3 -V 2>&1) is what is installed."
fi

python=""
if [[ -x "$here/.venv/bin/python" ]]; then
    python="$here/.venv/bin/python"
    say "Reusing the virtualenv in .venv"
else
    say "Creating a virtualenv in .venv"
    # The one Ubuntu trap worth catching by hand: python3-venv is a separate
    # package, and without it this fails with a message about ensurepip that
    # does not name the package you actually need.
    if ! err="$(python3 -m venv "$here/.venv" 2>&1)"; then
        printf '%s\n' "$err" >&2
        die "could not create a virtualenv. On Ubuntu this is usually fixed by:
       sudo apt install python3-venv"
    fi
    python="$here/.venv/bin/python"
fi

say "Installing $name and its dependencies"
"$python" -m pip install --quiet --upgrade pip
"$python" -m pip install --quiet --editable "$here"

# A zip download does not reliably keep the executable bit, and ./ndr is the
# first thing the README tells you to run.
chmod +x "$here/ndr"

say "Checking the install"
"$python" -c "import neverdeads_revenge, textual" \
    || die "the game was installed but cannot be imported -- please report this."

# -- menu entry -------------------------------------------------------------

if [[ $want_desktop -eq 1 ]]; then
    say "Adding $name to your applications menu"
    mkdir -p "$launcher_dir" "$desktop_dir" "$icon_dir"

    # The game is a TUI, so the desktop entry has to ask for a terminal. This
    # wrapper is what it launches: on a normal quit the window closes, but if
    # the game dies on start-up the message stays on screen instead of flashing
    # past in a window that immediately vanishes.
    cat > "$launcher_dir/launch.sh" <<WRAPPER
#!/usr/bin/env bash
"$here/ndr" || {
    printf '\n%s failed to start. Press Enter to close.\n' "$name"
    read -r _
}
WRAPPER
    chmod +x "$launcher_dir/launch.sh"

    # The entry lives in assets/ rather than in a heredoc here, so it can be
    # read, diffed and validated like any other file.
    template="$here/assets/$slug.desktop.in"
    if [[ -f "$template" ]]; then
        sed -e "s|@NAME@|$name|g" \
            -e "s|@EXEC@|$launcher_dir/launch.sh|g" \
            -e "s|@SLUG@|$slug|g" \
            "$template" > "$desktop_dir/$slug.desktop"
    else
        warn "no desktop entry template at $template; skipping the menu entry"
    fi

    if [[ -f "$here/assets/$slug.svg" ]]; then
        cp "$here/assets/$slug.svg" "$icon_dir/$slug.svg"
    else
        warn "no icon found at assets/$slug.svg; the menu entry will use a default"
    fi

    command -v update-desktop-database >/dev/null && update-desktop-database "$desktop_dir" 2>/dev/null || true
    command -v gtk-update-icon-cache >/dev/null && gtk-update-icon-cache -qtf "$data_home/icons/hicolor" 2>/dev/null || true
fi

say "Done."
printf '\n  Play it now:      %s/ndr\n' "$here"
if [[ $want_desktop -eq 1 ]]; then
    printf '  Or from the menu: look for "%s" (it may take a moment to appear)\n' "$name"
fi
printf '  To remove it:     %s/install.sh --uninstall\n\n' "$here"
