"""What a chest takes from you.

A chest is a deal: something worth having, and something owed for it. This is the
owed half. The reward stays hidden until the lid is up -- that is what makes it
daring rather than arithmetic -- so the price has to be stated plainly, and
:attr:`Curse.price` is the sentence the player decides on.

A wide record rather than one class per curse. There are six of these, each uses
one or two of the fields, and one table you can take in at a glance beats six
small classes with one method each. The alternative would be a hierarchy built to
express five different kinds of nothing.

Lives in ``game/`` because a curse changes how a run plays. The chest itself
carries only the curse's *key*, so ``world/`` never has to import this.
"""

from __future__ import annotations

from dataclasses import dataclass

from neverdeads_revenge.world.modifiers import Modifiers

__all__ = ["Curse", "CURSES", "curse_by_key"]


@dataclass(frozen=True, slots=True)
class Curse:
    """One thing a chest can take."""

    key: str
    name: str
    #: The price, in words, as the dialog puts it to the player.
    price: str
    #: Ongoing changes to the hero's stats.
    modifiers: Modifiers = Modifiers()
    #: Fraction of maximum health taken the moment the curse lands, for good.
    wither: float = 0.0
    #: What the wither above actually took, in points, filled in when it lands.
    #: The fraction is of the maximum *at that moment*, so recomputing it later
    #: would hand back a different number -- and a spring that gives back the
    #: wrong amount is a spring nobody trusts twice.
    wither_taken: int = 0
    #: Health lost per this many steps, or 0 for none.
    bleed_every: int = 0
    #: What the sight radius becomes, or ``None`` to leave it alone.
    sight: int | None = None
    #: Multiplier on what a draught restores.
    heal_scale: float = 1.0


#: Every curse a chest can hold.
#:
#: Prices are written to be read once, in a modal, by somebody who is about to
#: lose something. Short, concrete, no adjectives.
CURSES: dict[str, Curse] = {
    "wither": Curse(
        key="wither",
        name="WITHER",
        price="a quarter of your health, taken now and for good",
        wither=0.25,
    ),
    "bleed": Curse(
        key="bleed",
        name="BLEED",
        price="a drop of blood every third step",
        bleed_every=3,
    ),
    "frail": Curse(
        key="frail",
        name="FRAIL",
        price="two points of armour, gone",
        modifiers=Modifiers(armor=-2),
    ),
    "heavy": Curse(
        key="heavy",
        name="HEAVY",
        price="a quarter of your speed",
        modifiers=Modifiers(speed=-0.25),
    ),
    "dim": Curse(
        key="dim",
        name="DIM",
        price="your sight, cut to five paces",
        sight=5,
    ),
    "famine": Curse(
        key="famine",
        name="FAMINE",
        price="half of what every draught is worth",
        heal_scale=0.5,
    ),
}


def curse_by_key(key: str | None) -> Curse | None:
    """The curse with this key, or ``None``."""
    return CURSES.get(key) if key else None
