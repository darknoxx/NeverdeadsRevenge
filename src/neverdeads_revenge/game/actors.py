"""Actors: the player, the monsters, and the numbers that make them tick.

An :class:`Actor` is pure state plus a couple of queries. It holds no reference
to the map and imports nothing from the UI, so the whole simulation stays
testable without a terminal.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

from neverdeads_revenge.core.direction import Pos, chebyshev
from neverdeads_revenge.core.rng import Rng

from .difficulty import MAX_ENEMY_SPEED, potency, weight_at_depth

__all__ = [
    "Stats",
    "ActorKind",
    "Actor",
    "Hero",
    "NOXX",
    "HEROES",
    "EnemyTemplate",
    "ENEMIES",
    "make_hero",
    "make_enemy",
    "scale_template",
    "pick_enemy_template",
]


@dataclass(slots=True)
class Stats:
    """The numbers combat cares about.

    ``speed`` is the odd one out: it is not a combat stat at all but the
    interval divisor in the turn queue, which is what makes a fast hero act more
    often.
    """

    max_hp: int = 10
    hp: int = 10
    speed: float = 1.0
    damage: tuple[int, int] = (2, 4)
    crit_chance: float = 0.05
    crit_multiplier: float = 1.5
    accuracy: int = 0
    evasion: int = 0
    armor: int = 0

    @property
    def alive(self) -> bool:
        return self.hp > 0

    @property
    def average_damage(self) -> float:
        low, high = self.damage
        return (low + high) / 2

    def heal(self, amount: int) -> int:
        """Restore health, never above the maximum. Returns the amount healed."""
        before = self.hp
        self.hp = min(self.max_hp, self.hp + amount)
        return self.hp - before

    def hurt(self, amount: int) -> int:
        """Apply ``amount`` after armour. Returns damage actually taken."""
        amount = max(0, amount - self.armor)
        self.hp = max(0, self.hp - amount)
        return amount


class ActorKind(Enum):
    """What an actor is, which decides how it is drawn and how it behaves."""

    HERO = "hero"
    ENEMY = "enemy"


@dataclass(slots=True)
class Actor:
    """Something that occupies a cell and can act."""

    name: str
    kind: ActorKind
    stats: Stats
    position: Pos
    glyph: str = "@"
    color: str = "white"
    is_player: bool = False
    alive: bool = True
    #: Cells entered since the run started. Feeds the end-of-run score.
    steps: int = 0
    #: Temporary additive speed bonuses, e.g. the REVENGE reward for a kill.
    speed_bonus: float = 0.0
    #: How this actor wants to fight. Copied from the template so the AI does not
    #: have to carry the template around.
    behaviour: str = "aggressive"

    # -- combat -------------------------------------------------------------
    @property
    def hp(self) -> int:
        return self.stats.hp

    @property
    def max_hp(self) -> int:
        return self.stats.max_hp

    @property
    def speed(self) -> float:
        """Effective speed, including any active bonus.

        This is what the turn queue divides by, so a bonus granted by a kill
        immediately makes the holder act more often.
        """
        return self.stats.speed + self.speed_bonus

    def distance_from(self, other: Actor) -> int:
        """Chebyshev distance to another actor."""
        return chebyshev(self.position, other.position)

    def damage_roll(self, rng) -> int:
        """A damage value in this actor's range."""
        low, high = self.stats.damage
        return rng.between(low, high)

    def __repr__(self) -> str:
        return f"Actor({self.name!r}, hp={self.hp}/{self.max_hp}, at={self.position})"


# -- heroes ----------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Hero:
    """A playable character definition."""

    key: str
    name: str
    title: str
    blurb: str
    glyph: str
    color: str
    stats: Stats
    #: Permanent modifiers applied when the run starts, keyed by meta upgrade.
    unlocked: bool = True

    @property
    def average_damage(self) -> float:
        return self.stats.average_damage


#: Noxx -- high speed, high crit, low durability. Hits and runs.
NOXX = Hero(
    key="noxx",
    name="Noxx",
    title="the swift one",
    blurb=(
        "Quick hands, quicker feet. Noxx wins fights he should lose: strike, "
        "vanish, come back before they can swing. Fragile, but every opening "
        "is lethal."
    ),
    glyph="@",
    color="bright_white",
    stats=Stats(
        max_hp=26,
        hp=26,
        speed=1.5,
        damage=(4, 6),
        crit_chance=0.25,
        crit_multiplier=2.2,
        accuracy=1,
        evasion=4,
        armor=1,
    ),
)

#: Registry. Later heroes drop in here and the select screen picks them up for
#: free -- that is the whole reason heroes are data and not a hardcoded branch.
HEROES: dict[str, Hero] = {NOXX.key: NOXX}


def make_hero(hero: Hero, position: Pos) -> Actor:
    """Create a fresh actor from a hero definition."""
    return Actor(
        name=hero.name,
        kind=ActorKind.HERO,
        # Copy the stats: templates are shared and must never be mutated.
        # replace(), not vars() -- Stats uses __slots__, so it has no __dict__.
        stats=replace(hero.stats),
        position=position,
        glyph=hero.glyph,
        color=hero.color,
        is_player=True,
    )


# -- enemies ---------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class EnemyTemplate:
    """A monster definition, plus how it wants to fight."""

    key: str
    name: str
    glyph: str
    color: str
    stats: Stats
    #: How this monster behaves. See game.ai.
    behaviour: str = "aggressive"
    #: Relative chance of being picked when populating a floor.
    weight: float = 1.0
    #: How much ``weight`` grows per floor descended. ``1.0`` keeps the monster
    #: as common as on floor 1; higher values make it steadily more likely, and
    #: that is how the enemy *mix* shifts rather than just the enemy *numbers*.
    #: See :mod:`game.difficulty`.
    weight_growth: float = 1.0


ENEMIES: dict[str, EnemyTemplate] = {
    "ghoul": EnemyTemplate(
        key="ghoul",
        name="ghoul",
        glyph="g",
        color="green",
        behaviour="aggressive",
        stats=Stats(max_hp=9, hp=9, speed=0.7, damage=(2, 4), evasion=0, armor=0),
        weight=4.0,
    ),
    "bone": EnemyTemplate(
        key="bone",
        name="skeleton",
        glyph="s",
        color="grey70",
        behaviour="cautious",
        stats=Stats(max_hp=14, hp=14, speed=1.0, damage=(3, 6), accuracy=1, armor=1),
        weight=3.0,
    ),
    "wraith": EnemyTemplate(
        key="wraith",
        name="wraith",
        glyph="W",
        color="magenta",
        behaviour="hunter",
        stats=Stats(max_hp=7, hp=7, speed=1.3, damage=(2, 5), evasion=3),
        weight=1.5,
        # The only monster that gets more common as you descend. It is fast and
        # evasive, which is exactly the thing that makes a floor feel unfair if
        # the player cannot simply out-trade it -- so the deeper floors are
        # floors where out-trading is no longer the whole answer.
        weight_growth=1.14,
    ),
}


def make_enemy(template: EnemyTemplate, position: Pos) -> Actor:
    """Create a fresh actor from an enemy template."""
    return Actor(
        name=template.name,
        kind=ActorKind.ENEMY,
        # Copy for the same reason as make_hero: templates outlive every actor.
        stats=replace(template.stats),
        position=position,
        glyph=template.glyph,
        color=template.color,
        behaviour=template.behaviour,
    )


def scale_template(template: EnemyTemplate, depth: int) -> EnemyTemplate:
    """Return ``template`` as it appears on ``depth``.

    Health and damage scale with :func:`~game.difficulty.potency`; speed scales
    too but is clamped to :data:`~game.difficulty.MAX_ENEMY_SPEED` so nothing in
    the dungeon ever acts more often than the hero does. Armour, evasion and
    accuracy stay put: they are small integers, and doubling an armour value
    would subtract more from every hit than doubling damage adds.

    At ``depth == 1`` the template comes back unchanged, which is what lets
    ``ENEMIES`` double as the floor-1 reference.
    """
    factor = potency(depth)
    if factor == 1.0:
        return template

    low, high = template.stats.damage
    stats = replace(
        template.stats,
        max_hp=round(template.stats.max_hp * factor),
        hp=round(template.stats.max_hp * factor),
        damage=(
            max(1, round(low * factor)),
            max(1, round(high * factor)),
        ),
        # The clamp is the point: potency alone would hand a deep-floor wraith
        # speed 2.6, faster than Noxx, and the hero would stop being the fast one.
        speed=min(template.stats.speed * factor, MAX_ENEMY_SPEED),
    )
    return replace(template, stats=stats)


def pick_enemy_template(rng: Rng, depth: int = 1) -> EnemyTemplate:
    """Choose an enemy for a floor at ``depth``, honouring spawn weights.

    Both the weights (via ``weight_growth``) and the returned stats are depth
    dependent, so this is the only place a floor's population is decided.
    """
    weights = [
        (t, weight_at_depth(t.weight, t.weight_growth, depth))
        for t in ENEMIES.values()
    ]
    return scale_template(rng.choice_weighted(weights), depth)
