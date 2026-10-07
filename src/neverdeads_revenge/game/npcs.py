"""The people down here.

Not monsters and not heroes. Something that was returned, or something that never
left: standing in a room, willing to say one true thing about the place.

They carry no mechanics at all yet -- no quest, no trade, no reward -- and that is
deliberate. A line of lore is the cheapest thing in the game to add and the most
expensive to get wrong, so the first version is one sentence and no promise. A
quest is a promise, and a promise needs a system behind it before it can be kept.

Lives in ``game/`` for the same reason the curses do: the generator places *an*
NPC and does not need to know what any of them say, so it is handed the keys.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["Npc", "NPCS", "NPC_GLYPH", "NPC_COLOR", "npc_by_key"]

#: What one looks like. One glyph and one colour for all of them, the way every
#: weapon is a ``)``: which one it is belongs in the dialog, not on the map.
#:
#: ``8`` reads as a hooded figure without being a letter, which matters -- the
#: convention here is that capitals are heroes and lowercase are monsters, and
#: neither is true of these.
NPC_GLYPH = "8"

#: Pale periwinkle. The palette is genuinely full at this point: this is one of
#: the two colours left that clear the perceptual-distance test against every
#: other mark on the map, and it clears it by four thousand six hundred.
NPC_COLOR = "#c0c0ff"


@dataclass(frozen=True, slots=True)
class Npc:
    """Somebody with nothing to sell and something to say."""

    key: str
    name: str
    #: What they say, one line per meeting. Several rather than one so that
    #: walking past the same person twice is not the same sentence twice.
    lines: tuple[str, ...]


#: Everyone who can be met. The names are people's names, because they are
#: people: the dungeon did to them what it did to the hero, or they have simply
#: been here longer.
NPCS: dict[str, Npc] = {
    "tally": Npc(
        key="tally",
        name="the Tally",
        lines=(
            "Nine came down before you. I counted them in. I did not count them out.",
            "You are the tenth. I have written it down. Do not ask me where.",
            "Numbers are the only honest thing here. Everything else lies about "
            "how long it has been.",
        ),
    ),
    "vesper": Npc(
        key="vesper",
        name="Vesper",
        lines=(
            "The dark has an hour it likes best. You will know it when your lamp "
            "stops helping.",
            "I was promised a morning. I have stopped expecting it, and I still "
            "wake at the same time.",
            "If you find the way out, do not look back at me. I would follow, and "
            "I am not fit to.",
        ),
    ),
    "ninth": Npc(
        key="ninth",
        name="the Ninth",
        lines=(
            "I was the ninth. I got as far as the stairs, and I turned around.",
            "Do not ask what is on the tenth floor. Ask what is under it.",
            "You have the axe's mark on you. I can see it from here. So can the "
            "others.",
        ),
    ),
    "cinder": Npc(
        key="cinder",
        name="Cinder",
        lines=(
            "Everything here has burned once already. That is why it is so cold.",
            "I keep a fire. It does not warm anything. I keep it because the dark "
            "hates it.",
            "Touch nothing that glows. That is not light, it is attention.",
        ),
    ),
    "lamplighter": Npc(
        key="lamplighter",
        name="the Lamplighter",
        lines=(
            "I light them on the way down. I have never lit one on the way back up.",
            "There is a floor where the lamps go out as you pass. Do not stop to "
            "relight them.",
            "A light is a promise that the room has an edge. It has never been "
            "more than that.",
        ),
    ),
    "sexton": Npc(
        key="sexton",
        name="the Sexton",
        lines=(
            "I dig. There is nobody to bury, so I dig for the digging.",
            "Every floor has a room that is smaller on the inside. You will find "
            "it. You always do.",
            "The emptiness was pleased. I heard it too. I have not slept since.",
        ),
    ),
}


def npc_by_key(key: str | None) -> Npc | None:
    """The person with this key, or ``None``."""
    return NPCS.get(key) if key else None
