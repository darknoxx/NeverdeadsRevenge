"""Entry point: ``python -m neverdeads_revenge``."""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    """Run the game."""
    parser = argparse.ArgumentParser(
        prog="ndr", description="Neverdead's Revenge, a terminal roguelite."
    )
    parser.add_argument(
        "--no-sound",
        action="store_true",
        help="start with the sound off, whatever the save file says",
    )
    args = parser.parse_args(argv)

    from neverdeads_revenge.ui.app import NeverdeadsRevenge

    NeverdeadsRevenge(muted=True if args.no_sound else None).run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
