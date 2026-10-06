"""How the dungeon gets harder as you go down.

Two independent dials, deliberately kept apart:

``potency``
    How hard each individual monster hits. Scales health and damage together, so
    a tougher monster is not a sponge, it is a real threat.

``weight_growth``
    Which monsters show up at all. A floor of only buffed ghouls is the same
    fight ten times; a floor that gradually fills with faster, evasier wraiths
    changes what the player has to do about it.

Both curves are pure functions of depth and hold no state, so the balance of the
whole game can be checked by calling them rather than by playing fifty runs.

Floor 1 is the baseline by construction: ``potency(1) == 1.0`` and every growth
exponent is ``depth - 1``, so the templates in :mod:`actors` describe floor 1
exactly as written. That matters for more than tidiness -- it means the numbers
in ``actors.py`` are the numbers a new player meets, and every test that builds
an enemy from a bare template is still testing floor 1.
"""

from __future__ import annotations

__all__ = [
    "POTENCY_PER_FLOOR",
    "MAX_POTENCY",
    "MAX_ENEMY_SPEED",
    "potency",
    "weight_at_depth",
]

#: Fraction added to health and damage per floor descended.
#:
#: Raised from 0.15 once the shop, the amulets and the third slot existed. The
#: floor-10 wall is the point: reaching the rift is meant to take several runs
#: and a purse spent, and at 0.15 it took one run and no purse at all. Measured,
#: not chosen -- see the escape rates in the README.
POTENCY_PER_FLOOR = 0.26

#: Ceiling on potency. Without it a floor-40 monster would be unplayable and any
#: formula mistake would silently become exponential. Three times floor 1 is
#: already a lot; past that, difficulty should come from the enemy mix and the
#: count, not from bigger numbers.
MAX_POTENCY = 3.2

#: No monster may act this fast.
#:
#: Noxx's base speed is 1.50. This is the one hard constraint in the whole
#: balance: the hero must stay strictly faster than everything in the dungeon.
#: His crit chance and his REVENGE speed stacking both pay off because he gets
#: more actions than anything else -- a single monster that outruns him turns
#: every other stat into decoration. The gap is deliberately narrow (0.05), so
#: a deep-floor wraith is genuinely faster than a floor-1 wraith without ever
#: being faster than the player.
MAX_ENEMY_SPEED = 1.45


def potency(depth: int) -> float:
    """How much harder every monster on ``depth`` hits, relative to floor 1.

    Returns exactly ``1.0`` at depth 1 and never exceeds :data:`MAX_POTENCY`.
    """
    if depth < 1:
        return 1.0
    return min(1.0 + POTENCY_PER_FLOOR * (depth - 1), MAX_POTENCY)


def weight_at_depth(base: float, growth: float, depth: int) -> float:
    """Spawn weight of one monster kind on ``depth``.

    ``growth`` is the factor applied per floor: ``1.0`` keeps a monster as
    common as it was on floor 1 forever, ``1.14`` makes it fourteen percent more
    likely on each floor down. Only relative weights matter, so two monsters
    both growing at ``1.05`` is the same mix as neither growing.
    """
    if depth < 1:
        return base
    return base * growth ** (depth - 1)