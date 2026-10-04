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
    "Trait",
    "REVENGE_MAX_STACKS",
    "REVENGE_PER_STACK",
    "Hero",
    "NOXX",
    "YETI",
    "WALKYRION",
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

    def hurt(self, amount: int, bonus_armor: int = 0) -> int:
        """Apply ``amount`` after armour. Returns damage actually taken.

        ``bonus_armor`` is the defender's temporary armour, which lives on the
        :class:`Actor` rather than here: this object is copied from a template
        and never sees a kill, so it has no business knowing about REVENGE.
        """
        amount = max(0, amount - self.armor - bonus_armor)
        self.hp = max(0, self.hp - amount)
        return amount


class ActorKind(Enum):
    """What an actor is, which decides how it is drawn and how it behaves."""

    HERO = "hero"
    ENEMY = "enemy"


#: What REVENGE grants a hero, and how much of it.
#:
#: The mechanic is the game's own name and is the same for everyone; what it
#: grants is not. Handing speed to a slow hero is handing his worst stat the
#: biggest relative boost, which is exactly backwards.
class Trait(Enum):
    """What one stack of REVENGE grants, and what to call it in the UI."""

    SPEED = "speed"
    ARMOUR = "armour"
    DAMAGE = "damage"

    @property
    def per_stack(self) -> float:
        return REVENGE_PER_STACK[self]

    @property
    def label(self) -> str:
        return self.value

    @property
    def cap(self) -> int:
        return REVENGE_MAX_STACKS[self]

    def describe(self, stacks: int) -> str:
        """A short phrase for a message log or a status line."""
        amount = self.per_stack * stacks
        if self is Trait.SPEED:
            return f"+{amount:.1f} speed"
        return f"+{int(amount)} {self.value}"


#: How much a single stack of REVENGE grants, per trait.
#:
#: Speed is the calibrated one -- 0.3 was tuned against the whole existing game
#: and left alone. The other two are chosen to be worth roughly the same: five
#: stacks of speed doubles Noxx's actions, so five stacks of armour should change
#: a deep-floor hit by about half, and five stacks of damage should cut a
#: skeleton's health in roughly half the blows.
REVENGE_PER_STACK: dict[Trait, float] = {
    Trait.SPEED: 0.3,
    Trait.ARMOUR: 1.0,
    Trait.DAMAGE: 2.0,
}

#: How many stacks each trait takes before it stops paying.
#:
#: Deliberately not one number for all three. ``+0.3 speed`` and ``+1 armour``
#: are not the same amount of game -- armour is a flat subtraction, so a point of
#: it is worth more the more of it you already have -- and a shared cap either
#: strangles one trait or lets another run away with the run. Each cap is set at
#: roughly the point the trait has doubled its own hero's speciality: Noxx's
#: actions, Yeti's armour, Walkyrion's damage.
REVENGE_MAX_STACKS: dict[Trait, int] = {
    Trait.SPEED: 5,
    Trait.ARMOUR: 3,
    Trait.DAMAGE: 4,
}


@dataclass(slots=True)
class Actor:
    """Something that occupies a cell and can act."""

    name: str
    kind: ActorKind
    stats: Stats
    position: Pos
    #: A fallback for an actor built without an identity. Heroes and monsters get
    #: theirs from their template, so this is never the player -- it used to
    #: default to ``@``, which read as "the hero" long after the hero stopped
    #: being an ``@``.
    glyph: str = "?"
    color: str = "white"
    is_player: bool = False
    alive: bool = True
    #: Cells entered since the run started. Feeds the end-of-run score.
    steps: int = 0
    #: Temporary additive bonuses granted by REVENGE. Kept on the actor rather
    #: than folded into ``stats`` so that lapsing is one assignment and cannot
    #: leave a residue behind on a template.
    speed_bonus: float = 0.0
    armor_bonus: int = 0
    damage_bonus: int = 0
    #: Which of the three REVENGE grants this actor collects. Copied from the
    #: hero so the game layer never has to look the hero up mid-fight.
    trait: Trait = Trait.SPEED
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
        """A damage value in this actor's range, plus any REVENGE bonus.

        Flat, not a multiplier: the bonus is added once to the roll, so it reads
        on screen as the same number every hit and a player can count it.
        """
        low, high = self.stats.damage
        return rng.between(low, high) + self.damage_bonus

    @property
    def armor(self) -> int:
        """Armour including any REVENGE bonus, for display and for combat."""
        return self.stats.armor + self.armor_bonus

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
    #: What REVENGE grants this hero for every kill. See :class:`Trait`.
    trait: Trait = Trait.SPEED
    #: Permanent modifiers applied when the run starts, keyed by meta upgrade.
    unlocked: bool = True

    @property
    def average_damage(self) -> float:
        return self.stats.average_damage


#: Noxx -- high speed, high crit, low durability. Hits and runs.
#:
#: ``N`` rather than the usual ``@``: this hero has a name, and the map is where
#: the player spends the whole run looking at him. Purple is his own -- the
#: wraith is plain magenta and the elixir is bright magenta, so no two things on
#: the map share both a glyph and a colour.
NOXX = Hero(
    key="noxx",
    name="Noxx",
    title="the swift one",
    blurb=(
        "Quick hands, quicker feet. Noxx wins fights he should lose: strike, "
        "vanish, come back before they can swing. Fragile, but every opening "
        "is lethal."
    ),
    glyph="N",
    # A hex rather than the name "purple": named colours get snapped to the
    # terminal's nearest palette entry, and "purple" lands on the same magenta
    # the wraith already uses. Hex renders exactly and stays his own.
    color="#a855f7",
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
    # REVENGE makes him faster still, which is the same joke his whole kit tells:
    # the fight is over before it started.
    trait=Trait.SPEED,
)

#: Yeti -- the opposite answer to the same question. Where Noxx avoids the blow,
#: Yeti absorbs it: armour is a flat subtraction, so it eats the small hits that
#: early floors are made of, and it is the only hero who can stand in a corridor
#: and let three things hit him.
#:
#: His speed is below everything that matters and below the average of the
#: dungeon, deliberately. He does not get to choose the fight, and a player who
#: picks him is trading tempo for the right to never be the one who dies first.
#: Damage is what makes that survivable: the sweep said raising his health
#: changed nothing while raising his damage moved his escape rate threefold,
#: because a slow hero does not lose by being fragile, he loses by needing four
#: turns to kill something that hits him every one of them.
YETI = Hero(
    key="yeti",
    name="Yeti",
    title="the unmoved",
    blurb=(
        "Slow as a glacier and about as easy to move. Yeti does not dodge and "
        "does not rush; everything that reaches him has to get through the "
        "armour first, and most things do not."
    ),
    glyph="Y",
    color="#7fd4ff",
    stats=Stats(
        max_hp=52,
        hp=52,
        speed=0.75,
        # Damage is what makes a slow hero work, and the sweep said so: raising
        # his health changed nothing (54 hp measured the same as 46) while
        # raising his damage moved the escape rate threefold. A slow hero does
        # not lose by being fragile, he loses by taking four turns to kill
        # something that hits him every one of them.
        damage=(9, 13),
        crit_chance=0.05,
        crit_multiplier=1.5,
        accuracy=1,
        evasion=0,
        armor=3,
    ),
    # Every kill hardens him. This is the one the roster was missing: REVENGE
    # used to hand a *slow* hero a speed bonus, which meant the hero built to
    # absorb hits was the one who most wanted to stop taking them, and the trait
    # worked hardest on the hero whose identity least wanted it.
    trait=Trait.ARMOUR,
)

#: Walkyrion -- the middle road, taken on purpose. Fast enough to leave a fight
#: he does not want, armoured enough to survive the one he misjudged, and with no
#: single glaring hole for a deep floor to find.
#:
#: Every hero needs one number they are bad at or they are not a choice. His is
#: that none of his numbers is the best, so nothing he does wins the run by
#: itself.
WALKYRION = Hero(
    key="walkyrion",
    name="Walkyrion",
    title="the even blade",
    blurb=(
        "No weakness worth naming and no trick worth relying on. Walkyrion "
        "strikes on time, takes the hit he has to, and is still standing when "
        "the screaming stops."
    ),
    glyph="W",
    color="#ffb000",
    stats=Stats(
        # Every number here sits between Noxx's and Yeti's, which is the whole
        # point, and the accuracy of 2 is the one thing that is nobody else's.
        # "Balanced" measured as the worst hero in the game until that edge
        # existed: a middle of two specialists is below both of them unless it
        # gets a small speciality of its own, and never missing is a quiet one.
        max_hp=36,
        hp=36,
        speed=1.15,
        damage=(6, 9),
        crit_chance=0.20,
        crit_multiplier=1.8,
        accuracy=2,
        evasion=2,
        armor=2,
    ),
    # Every kill sharpens him. He is the hero with the least to gain from
    # becoming more of one thing, so he becomes more dangerous instead -- which
    # is what "balanced" should compound into rather than turning him into a
    # slightly worse version of whoever he is standing next to.
    trait=Trait.DAMAGE,
)

#: Registry. Later heroes drop in here and the select screen picks them up for
#: free -- that is the whole reason heroes are data and not a hardcoded branch.
#:
#: Heroes take the capital of their name and monsters stay lowercase, so a letter
#: on the map tells you which side of the fight it is on before you have read the
#: legend. The wraith had the ``W`` until Walkyrion needed it.
HEROES: dict[str, Hero] = {hero.key: hero for hero in (NOXX, YETI, WALKYRION)}


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
        trait=hero.trait,
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
        glyph="w",
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
