"""Combat resolution.

Deliberately small and legible. One function decides an attack, and it returns a
result object rather than mutating the world silently, so the caller can report
exactly what happened and tests can assert on it.

The hit chance is a flat base nudged by the accuracy/evasion difference. Noxx's
evasion 4 against a ghoul's accuracy 0 puts him at roughly 45% -- being hard to
pin down is half of what makes him work, and the other half is that he gets to
attack more often.
"""

from __future__ import annotations

from dataclasses import dataclass

from neverdeads_revenge.core.rng import Rng

from .actors import Actor, Trait
from .actors import REVENGE_MAX_STACKS as REVENGE_MAX_STACKS

__all__ = [
    "AttackOutcome",
    "BASE_HIT_CHANCE",
    "MIN_HIT_CHANCE",
    "MAX_HIT_CHANCE",
    "REVENGE_MAX_STACKS",
    "hit_chance",
    "attack",
    "apply_revenge",
]

BASE_HIT_CHANCE = 0.85
MIN_HIT_CHANCE = 0.30
MAX_HIT_CHANCE = 0.97


@dataclass(frozen=True, slots=True)
class AttackOutcome:
    """What happened when ``attacker`` swung at ``defender``."""

    hit: bool
    crit: bool
    damage: int
    killed: bool
    dodged: bool = False

    @property
    def is_success(self) -> bool:
        return self.hit

    @property
    def verb(self) -> str:
        """Third person singular, for when a monster is the subject.

            f"The ghoul {outcome.verb} you for {outcome.damage}."
        """
        return _VERBS[self._outcome_key][0]

    @property
    def verb_second_person(self) -> str:
        """Second person singular, for when the player is the subject.

            f"You {outcome.verb_second_person} the ghoul for {outcome.damage}."
        """
        return _VERBS[self._outcome_key][1]

    @property
    def _outcome_key(self) -> tuple[bool, bool, bool]:
        return (self.dodged or not self.hit, self.crit, self.killed)


#: outcome key -> (third person, second person)
_VERBS: dict[tuple[bool, bool, bool], tuple[str, str]] = {
    (True, False, False): ("misses", "miss"),
    (True, True, False): ("misses", "miss"),
    (True, False, True): ("misses", "miss"),
    (True, True, True): ("misses", "miss"),
    (False, False, False): ("hits", "hit"),
    (False, True, False): ("crits", "crit"),
    (False, False, True): ("kills", "kill"),
    (False, True, True): ("obliterates", "obliterate"),
}


def hit_chance(attacker: Actor, defender: Actor) -> float:
    """Probability that ``attacker`` lands a blow on ``defender``."""
    edge = attacker.stats.accuracy - defender.stats.evasion
    chance = BASE_HIT_CHANCE + 0.1 * edge
    return max(MIN_HIT_CHANCE, min(MAX_HIT_CHANCE, chance))


def attack(attacker: Actor, defender: Actor, rng: Rng) -> AttackOutcome:
    """Resolve one attack from ``attacker`` against adjacent ``defender``.

    Mutates ``defender``'s health and the ``alive`` flag when it lands a killing
    blow. The caller is responsible for cleaning up the body.
    """
    if not rng.chance(hit_chance(attacker, defender)):
        return AttackOutcome(hit=False, crit=False, damage=0, killed=False, dodged=True)

    base = attacker.damage_roll(rng)
    crit = rng.chance(attacker.stats.crit_chance)
    damage = int(round(base * attacker.stats.crit_multiplier)) if crit else base

    dealt = defender.stats.hurt(damage, defender.armor_bonus)
    killed = not defender.stats.alive
    if killed:
        defender.alive = False

    return AttackOutcome(hit=True, crit=crit, damage=dealt, killed=killed)


def apply_revenge(actor: Actor, stacks: int) -> int:
    """Set ``actor``'s REVENGE to ``stacks`` and fold the grant into its bonuses.

    Returns the stack count actually held, clamped so a long chain cannot let the
    holder run away with the run. The grant follows the actor's own
    :class:`~neverdeads_revenge.game.actors.Trait`: speed for one hero, armour for
    another, raw damage for a third.

    Set rather than increment, deliberately. Gaining a stack and losing them all
    on a new floor are then the same operation, so lapsing cannot leave a residue
    behind on an actor -- and every bonus is written on every call rather than
    only the relevant one, for the same reason.
    """
    stacks = max(0, min(stacks, actor.trait.cap))
    amount = actor.trait.per_stack * stacks

    actor.speed_bonus = amount if actor.trait is Trait.SPEED else 0.0
    actor.armor_bonus = int(amount) if actor.trait is Trait.ARMOUR else 0
    actor.damage_bonus = int(amount) if actor.trait is Trait.DAMAGE else 0
    return stacks
