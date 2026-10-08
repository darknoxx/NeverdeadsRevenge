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
    parser.add_argument(
        "--sound-log",
        nargs="?",
        const="/tmp/ndr-sound.log",
        metavar="PATH",
        help=(
            "write every sound decision to PATH (default /tmp/ndr-sound.log): "
            "what played, what was dropped, and how far behind the device was"
        ),
    )
    parser.add_argument(
        "--testrun",
        action="store_true",
        help=(
            "start with every page of the chronicle and 9999 coin, for testing. "
            "The save file is copied to meta.json.bak first, once"
        ),
    )
    args = parser.parse_args(argv)

    if args.testrun:
        from neverdeads_revenge.game.lore import PAGE_COUNT
        from neverdeads_revenge.persistence import TEST_GOLD, grant_test_save

        path, backup = grant_test_save()
        print(f"test save: {PAGE_COUNT} pages and {TEST_GOLD} coin -> {path}")
        if backup is not None:
            print(f"the save from before is kept at {backup}")
        else:
            print("there was no save to keep")

    if args.sound_log:
        # The audio layer reads this itself, so the flag is only a friendlier
        # way of setting it. One variable, two ways in.
        import os

        from neverdeads_revenge.ui.audio import DEBUG_ENV

        os.environ[DEBUG_ENV] = args.sound_log

    from neverdeads_revenge.ui.app import NeverdeadsRevenge

    NeverdeadsRevenge(muted=True if args.no_sound else None).run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
