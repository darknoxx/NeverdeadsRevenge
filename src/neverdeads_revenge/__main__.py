"""Entry point: ``python -m neverdeads_revenge``."""

from __future__ import annotations

import sys


def main() -> int:
    """Run the game."""
    from neverdeads_revenge.ui.app import NeverdeadsRevenge

    NeverdeadsRevenge().run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
