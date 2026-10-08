"""What the dungeon gives back.

A curse is the price. This is the other half of the bargain, and it is *not* the
blade behind the lid -- it is a rule, and it lasts the rest of the run.

The difference matters. A better sword is a bigger number and the player already
has three slots of those. A gift changes what the player can *do*: strike from
two squares away, walk through the wall, take an action back. Which is the same
thing the amulets do, and for the same reason -- the decisions worth stopping
for are the ones that change the shape of a fight rather than its arithmetic.

A gift is meant to be about as good as the curse is bad. Not better: a chest that
is worth opening for free would make the price decoration. And not worse: nobody
would take the bargain twice. The pair is meant to be a *trade of shape*, and the
run afterwards is played differently rather than harder.

They are held in a set on the run, exactly like the wild offers, and the rules
live where they act -- ``game/actions.py`` for the two that change what a step
does, ``game/state.py`` for the one that changes a descent.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["Gift", "GIFTS", "gift_by_key"]


@dataclass(frozen=True, slots=True)
class Gift:
    """One rule the dungeon hands over."""

    key: str
    name: str
    #: The sentence the character sheet shows. Written to be read once, next to
    #: a curse's price, by somebody working out what they traded.
    blurb: str


GIFTS: dict[str, Gift] = {
    "long_reach": Gift(
        key="long_reach",
        name="THE LONG REACH",
        blurb="your blow reaches two squares, and nothing solid in between",
    ),
    "step_behind": Gift(
        key="step_behind",
        name="THE STEP BEHIND",
        blurb="every fifth step costs you no time at all",
    ),
    "kind_dark": Gift(
        key="kind_dark",
        name="THE KIND DARK",
        blurb="every floor you descend lifts one curse",
    ),
    "hollow_road": Gift(
        key="hollow_road",
        name="THE HOLLOW ROAD",
        blurb="walk into stone, at two health a square",
    ),
    "borrowed_hour": Gift(
        key="borrowed_hour",
        name="THE BORROWED HOUR",
        blurb="once a floor, take back the last thing you did",
    ),
}


def gift_by_key(key: str | None) -> Gift | None:
    """The gift with this key, or ``None``."""
    return GIFTS.get(key) if key else None
