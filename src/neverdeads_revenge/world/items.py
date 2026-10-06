"""Loot.

Items live in ``world/`` rather than ``game/`` for the same reason tiles do: the
generator has to place them, and the generator must not import the game layer.
An item is world content -- it exists on the map and can be seen, walked over and
picked up -- while what a *drink* does to your health is a game rule.

Right now everything is a healing draught. That is not a placeholder: a run has
one resource that runs out, health, and one way to get it back. Anything else
that could be found on the floor (a weapon, a scroll, a map) needs systems that
do not exist yet.
"""

from __future__ import annotations

from dataclasses import dataclass

from neverdeads_revenge.core.rng import Rng

from .map import GroundItem
from .modifiers import Modifiers

__all__ = [
    "ItemTemplate",
    "ITEMS",
    "make_item",
    "make_chest",
    "make_coin",
    "roll_item",
    "roll_chest_contents",
    "loot_count",
    "equipment_count",
    "chest_count",
    "rare_find_count",
    "RARE_FIND_CHANCE",
    "RARE_FIND_DEPTH",
    "WEAPON_GLYPH",
    "WEAPON_COLOR",
    "ARMOUR_GLYPH",
    "ARMOUR_COLOR",
    "CHEST_GLYPH",
    "CHEST_COLOR",
    "COIN_GLYPH",
    "COIN_COLOR",
]


@dataclass(frozen=True, slots=True)
class ItemTemplate:
    """A kind of item, and what it does for you."""

    key: str
    name: str
    glyph: str
    color: str
    #: ``draught``, ``weapon`` or ``armour``. The legend groups by this, because
    #: one row per kind fits in the sidebar and one row per item does not.
    kind: str
    #: Health restored when drunk.
    heal: int = 0
    #: Which equipment slot it fills. ``None`` for something you drink.
    slot: str | None = None
    #: What wearing it changes.
    modifiers: Modifiers = Modifiers()
    #: Relative chance of being rolled for a floor.
    weight: float = 1.0
    #: How much ``weight`` grows per floor descended. Better things get more
    #: common as you go down, which is what makes a deep floor's loot worth the
    #: risk of the deep floor.
    weight_growth: float = 1.0
    #: Never rolled onto a floor. Chests hand these out, and only chests.
    chest_only: bool = False
    #: Which amulet ability this grants, by key. ``None`` for everything that is
    #: not an amulet. The rule lives in :mod:`game.amulets`; this is only the
    #: name of it, the same way a chest carries a curse key.
    amulet: str | None = None


#: Glyph and colour per kind of thing. Weapons and armour follow the old
#: roguelike convention -- ``)`` for a blade, ``[`` for something you wear --
#: because it costs nothing to be legible to people who already know it.
WEAPON_GLYPH = ")"
WEAPON_COLOR = "bright_white"
ARMOUR_GLYPH = "["
ARMOUR_COLOR = "#b87333"

#: An amulet. The old roguelike convention, and the reason grass had to move off
#: this glyph: it is the one mark a player already reads as "wear this".
AMULET_GLYPH = '"'
AMULET_COLOR = "#f472b6"

ITEMS: dict[str, ItemTemplate] = {
    # -- draughts ----------------------------------------------------------
    "potion": ItemTemplate(
        key="potion",
        name="potion",
        glyph="!",
        color="bright_red",
        kind="draught",
        heal=8,
        weight=5.0,
    ),
    "elixir": ItemTemplate(
        key="elixir",
        name="elixir",
        glyph="*",
        color="bright_magenta",
        kind="draught",
        heal=20,
        weight=2.0,
        weight_growth=1.25,
    ),
    # -- weapons -----------------------------------------------------------
    "knife": ItemTemplate(
        key="knife",
        name="chipped knife",
        glyph=WEAPON_GLYPH,
        color=WEAPON_COLOR,
        kind="weapon",
        slot="weapon",
        modifiers=Modifiers(damage=1),
        weight=5.0,
    ),
    "blade": ItemTemplate(
        key="blade",
        name="serrated blade",
        glyph=WEAPON_GLYPH,
        color=WEAPON_COLOR,
        kind="weapon",
        slot="weapon",
        modifiers=Modifiers(damage=2, crit_chance=0.05),
        weight=3.0,
        weight_growth=1.10,
    ),
    "estoc": ItemTemplate(
        key="estoc",
        name="thin estoc",
        glyph=WEAPON_GLYPH,
        color=WEAPON_COLOR,
        kind="weapon",
        slot="weapon",
        modifiers=Modifiers(damage=1, crit_chance=0.10, crit_multiplier=0.2),
        weight=2.0,
        weight_growth=1.18,
    ),
    "cleaver": ItemTemplate(
        key="cleaver",
        name="rusted cleaver",
        glyph=WEAPON_GLYPH,
        color=WEAPON_COLOR,
        kind="weapon",
        slot="weapon",
        # Heavy: the most damage of the four and the only one that costs speed,
        # so "better weapon" is a decision rather than a straight upgrade.
        modifiers=Modifiers(damage=3, speed=-0.15),
        weight=2.0,
        weight_growth=1.15,
    ),
    # -- armour ------------------------------------------------------------
    "leather": ItemTemplate(
        key="leather",
        name="leather coat",
        glyph=ARMOUR_GLYPH,
        color=ARMOUR_COLOR,
        kind="armour",
        slot="armour",
        modifiers=Modifiers(armor=1),
        weight=5.0,
    ),
    "cloak": ItemTemplate(
        key="cloak",
        name="grey cloak",
        glyph=ARMOUR_GLYPH,
        color=ARMOUR_COLOR,
        kind="armour",
        slot="armour",
        # Evasion is worth ten points of enemy hit chance per point, so one is
        # already a lot. Two measured as a 30-point swing and made the floor
        # loot worth more than the fights.
        modifiers=Modifiers(evasion=1),
        weight=3.0,
        weight_growth=1.10,
    ),
    "boots": ItemTemplate(
        key="boots",
        name="swift boots",
        glyph=ARMOUR_GLYPH,
        color=ARMOUR_COLOR,
        kind="armour",
        slot="armour",
        modifiers=Modifiers(speed=0.15, evasion=1),
        weight=2.0,
        weight_growth=1.15,
    ),
    # -- amulets -----------------------------------------------------------
    #
    # A third slot, and the only one that grants an ability rather than a number.
    # The weak ones lie about and can be bought; the strong ones come out of
    # chests and from the shop. See :mod:`game.amulets` for what each one does --
    # the name here has to match the name there, which a test checks.
    "ember": ItemTemplate(
        key="ember",
        name="the last ember",
        glyph=AMULET_GLYPH,
        color=AMULET_COLOR,
        kind="amulet",
        slot="amulet",
        amulet="ember",
        # Low, so an amulet is a find rather than the usual thing on the floor.
        weight=1.0,
    ),
    "coin_hand": ItemTemplate(
        key="coin_hand",
        name="the coin hand",
        glyph=AMULET_GLYPH,
        color=AMULET_COLOR,
        kind="amulet",
        slot="amulet",
        amulet="coin_hand",
        weight=1.0,
    ),
    "marrow": ItemTemplate(
        key="marrow",
        name="the marrow",
        glyph=AMULET_GLYPH,
        color=AMULET_COLOR,
        kind="amulet",
        slot="amulet",
        amulet="marrow",
        weight=1.0,
    ),
    "wayfarer": ItemTemplate(
        key="wayfarer",
        name="the wayfarer",
        glyph=AMULET_GLYPH,
        color=AMULET_COLOR,
        kind="amulet",
        slot="amulet",
        amulet="wayfarer",
        weight=1.0,
    ),
    "rune_heart": ItemTemplate(
        key="rune_heart",
        name="the rune heart",
        glyph=AMULET_GLYPH,
        color=AMULET_COLOR,
        kind="amulet",
        slot="amulet",
        amulet="rune_heart",
        chest_only=True,
    ),
    "mirror": ItemTemplate(
        key="mirror",
        name="the mirror",
        glyph=AMULET_GLYPH,
        color=AMULET_COLOR,
        kind="amulet",
        slot="amulet",
        amulet="mirror",
        chest_only=True,
    ),
    "grave_ward": ItemTemplate(
        key="grave_ward",
        name="the grave ward",
        glyph=AMULET_GLYPH,
        color=AMULET_COLOR,
        kind="amulet",
        slot="amulet",
        amulet="grave_ward",
        chest_only=True,
    ),
    "deathwatch": ItemTemplate(
        key="deathwatch",
        name="the deathwatch",
        glyph=AMULET_GLYPH,
        color=AMULET_COLOR,
        kind="amulet",
        slot="amulet",
        amulet="deathwatch",
        chest_only=True,
    ),
    "long_hunger": ItemTemplate(
        key="long_hunger",
        name="the long hunger",
        glyph=AMULET_GLYPH,
        color=AMULET_COLOR,
        kind="amulet",
        slot="amulet",
        amulet="long_hunger",
        chest_only=True,
    ),
    "patience": ItemTemplate(
        key="patience",
        name="the revenant's patience",
        glyph=AMULET_GLYPH,
        color=AMULET_COLOR,
        kind="amulet",
        slot="amulet",
        amulet="patience",
        chest_only=True,
    ),
    "second_mouth": ItemTemplate(
        key="second_mouth",
        name="the second mouth",
        glyph=AMULET_GLYPH,
        color=AMULET_COLOR,
        kind="amulet",
        slot="amulet",
        amulet="second_mouth",
        chest_only=True,
    ),
    "dead_weight": ItemTemplate(
        key="dead_weight",
        name="the dead weight",
        glyph=AMULET_GLYPH,
        color=AMULET_COLOR,
        kind="amulet",
        slot="amulet",
        amulet="dead_weight",
        # The one amulet that costs a stat, and the reason it can afford to.
        modifiers=Modifiers(speed=-0.20),
        chest_only=True,
    ),
    "patient_knife": ItemTemplate(
        key="patient_knife",
        name="the patient knife",
        glyph=AMULET_GLYPH,
        color=AMULET_COLOR,
        kind="amulet",
        slot="amulet",
        amulet="patient_knife",
        chest_only=True,
    ),
    "borrowed_face": ItemTemplate(
        key="borrowed_face",
        name="the borrowed face",
        glyph=AMULET_GLYPH,
        color=AMULET_COLOR,
        kind="amulet",
        slot="amulet",
        amulet="borrowed_face",
        chest_only=True,
    ),
    # -- out of the chests -------------------------------------------------
    #
    # A tier of their own, never rolled onto a floor. Clearly better than
    # anything lying around, because the player paid for them with something
    # they cannot get back.
    "runed": ItemTemplate(
        key="runed",
        name="runed blade",
        glyph=WEAPON_GLYPH,
        color=WEAPON_COLOR,
        kind="weapon",
        slot="weapon",
        modifiers=Modifiers(damage=4, crit_chance=0.10),
        chest_only=True,
    ),
    "grave": ItemTemplate(
        key="grave",
        name="grave iron",
        glyph=WEAPON_GLYPH,
        color=WEAPON_COLOR,
        kind="weapon",
        slot="weapon",
        modifiers=Modifiers(damage=6, speed=-0.20),
        chest_only=True,
    ),
    "plate": ItemTemplate(
        key="plate",
        name="warden plate",
        glyph=ARMOUR_GLYPH,
        color=ARMOUR_COLOR,
        kind="armour",
        slot="armour",
        modifiers=Modifiers(armor=3),
        chest_only=True,
    ),
    "shade": ItemTemplate(
        key="shade",
        name="shade cloak",
        glyph=ARMOUR_GLYPH,
        color=ARMOUR_COLOR,
        kind="armour",
        slot="armour",
        modifiers=Modifiers(evasion=3),
        chest_only=True,
    ),
}


#: What a chest looks like. Gold, because a chest is treasure before it is a
#: trap, and the dialog is where the trap gets said out loud.
CHEST_GLYPH = "&"
CHEST_COLOR = "bright_yellow"

#: Coins left by a dead monster.
COIN_GLYPH = "$"
COIN_COLOR = "#ffd700"


def make_coin(value: int) -> GroundItem:
    """A pile of coins on the floor."""
    return GroundItem(
        item_id="coin",
        name="coins",
        glyph=COIN_GLYPH,
        color=COIN_COLOR,
        kind="coin",
        gold=value,
    )


def make_chest(curse_key: str, contents: ItemTemplate) -> GroundItem:
    """A locked chest holding ``contents`` and owing ``curse_key``.

    Rolled when the floor is built rather than when the lid opens, so a seed
    still determines a whole run: what is in the chest is decided before the
    player has done anything to change the dice.
    """
    return GroundItem(
        item_id="chest",
        name="ominous chest",
        glyph=CHEST_GLYPH,
        color=CHEST_COLOR,
        kind="chest",
        curse=curse_key,
        contents=make_item(contents),
    )


def make_item(template: ItemTemplate) -> GroundItem:
    """Create a floor item from a template."""
    return GroundItem(
        item_id=template.key,
        name=template.name,
        glyph=template.glyph,
        color=template.color,
        heal=template.heal,
        kind=template.kind,
        slot=template.slot,
        modifiers=template.modifiers,
        amulet=template.amulet,
    )


def _weight_at(template: ItemTemplate, depth: int) -> float:
    if depth < 1:
        return template.weight
    return template.weight * template.weight_growth ** (depth - 1)


def roll_item(
    rng: Rng, depth: int = 1, kinds: tuple[str, ...] | None = None
) -> ItemTemplate:
    """Pick an item kind for a floor at ``depth``.

    ``kinds`` restricts the pool. Draughts and equipment are rolled separately
    rather than from one table, and that is not a detail: a single table cut the
    supply of healing to a quarter the moment equipment was added, and the game
    became far harder without anything obviously having changed.

    Chest-only things are never in the pool. They are not rarer, they are
    elsewhere.
    """
    pool = [
        t
        for t in ITEMS.values()
        if not t.chest_only and (kinds is None or t.kind in kinds)
    ]
    return rng.choice_weighted([(t, _weight_at(t, depth)) for t in pool])


#: How much likelier a chest is to hold a blade or a coat than an amulet.
#:
#: Evenly was right when the strong tier was four blades and coats. Now that it
#: holds fourteen things, an even split makes the blade the rare find and hands
#: out amulets three chests running -- which is the thing the third slot was
#: meant to fix. The chest is still not a second lottery: the player cannot
#: influence it either way, and that is what "not a lottery" has always meant
#: here. The mix is a design choice, not a dice roll.
CHEST_GEAR_BIAS = 4.0


def roll_chest_contents(rng: Rng) -> ItemTemplate:
    """What is inside a chest: one of the strong things."""
    strong = [t for t in ITEMS.values() if t.chest_only]
    return rng.choice_weighted(
        [
            (t, CHEST_GEAR_BIAS if t.kind in ("weapon", "armour") else 1.0)
            for t in strong
        ]
    )


def loot_count(depth: int) -> int:
    """How many draughts a floor holds.

    Deliberately stingy, and it grows slowly. Health is a run-long resource, so
    the supply of it is the difficulty dial that matters most: a floor that
    hands out four draughts is a floor where the monsters stop being scary.
    """
    return min(1 + depth // 3, 4)


def equipment_count(depth: int) -> int:
    """How many weapons and coats a floor holds, on top of the draughts.

    Its own budget, not a share of the draughts'. Kept small and grown slowly:
    equipment is never used up, so every piece is a permanent upgrade, and a
    floor that scatters three of them is handing out three of those across a run
    that only has ten floors. The strong tier is meant to be the chests.
    """
    return min(1 + depth // 5, 2)


#: How often a floor holds one of the chest-only things lying in the open.
RARE_FIND_CHANCE = 0.22

#: The floor a rare find can first appear on.
RARE_FIND_DEPTH = 4


def rare_find_count(rng: Rng, depth: int) -> int:
    """Whether this floor holds a strong thing lying around, uncursed.

    Never on the shallow floors. The strong tier is what a chest pays for with a
    curse, and handing one out free on floor two would make the chest the fool's
    bargain. Deeper down it starts to turn up, which is one more reason the deep
    floors are worth the risk of being deep.

    Takes the generator rather than being a plain probability so that it is
    decided by the run's seed like everything else: a floor has to be the same
    floor when it is regenerated.
    """
    if depth < RARE_FIND_DEPTH:
        return 0
    return 1 if rng.chance(RARE_FIND_CHANCE) else 0


def chest_count(depth: int) -> int:
    """How many chests a floor holds.

    Stingier than the equipment, and flatter: a chest is worth several floor
    finds and costs something permanent, so two on one floor is already a lot of
    deciding.
    """
    return min(1 + depth // 6, 2)