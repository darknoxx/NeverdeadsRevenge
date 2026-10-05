"""Run state: everything one attempt at the dungeon consists of.

:class:`GameState` owns the map, the actors, the turn queue and the message log.
It is pure data plus queries -- no Textual, no I/O -- which is what lets the
whole game be simulated in a unit test.

A "run" is one life: pick a hero, descend until you die, see the summary.
Permanent progress between runs lives in :mod:`neverdeads_revenge.persistence`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from neverdeads_revenge.core.direction import Pos
from neverdeads_revenge.core.rng import Rng
from neverdeads_revenge.core.turn_queue import TurnQueue
from neverdeads_revenge.world.fov import compute_fov_full
from neverdeads_revenge.world.generator import GeneratedFloor, generate_floor
from neverdeads_revenge.world.map import DungeonMap, GroundItem
from neverdeads_revenge.world.tiles import Tile

from .actors import Actor, Hero, make_enemy, make_hero, pick_enemy_template
from .combat import apply_revenge
from .curses import CURSES, Curse

__all__ = [
    "LogEntry",
    "LogKind",
    "RunState",
    "GameState",
    "VIEW_RADIUS",
    "ESCAPE_BONUS",
    "TURN_BUDGET_PER_FLOOR",
    "SPEED_BONUS_PER_TURN",
]

VIEW_RADIUS = 9
"""How far the player can see, in cells."""

ESCAPE_BONUS = 5000
"""Score awarded for leaving the dungeon alive instead of dying in it."""

#: Turns a floor is "allowed" before speed stops paying.
#:
#: Measured, not chosen: across 144 bot runs the median floor cost 63 turns and
#: the quickest cost 34, so a budget of 80 leaves most runs scoring something
#: while still going to zero for a slow one. A budget nobody beats is
#: decoration; one everybody beats is noise.
TURN_BUDGET_PER_FLOOR = 80

#: Points per turn saved against that budget.
#:
#: Ten makes the difference between a brisk run and a median one worth roughly a
#: sixth of the total, which is enough to play for and not enough to drown out
#: killing things and getting out alive.
SPEED_BONUS_PER_TURN = 10


class LogKind(Enum):
    """Message categories, so the UI can colour them without parsing text."""

    PLAIN = "plain"
    COMBAT = "combat"
    CRIT = "crit"
    DAMAGE = "damage"
    GOOD = "good"
    BAD = "bad"
    SYSTEM = "system"


@dataclass(frozen=True, slots=True)
class LogEntry:
    """One line in the message log."""

    text: str
    kind: LogKind = LogKind.PLAIN
    turn: int = 0


class RunState(Enum):
    """Where the run currently stands."""

    PLAYING = "playing"
    DEAD = "dead"
    ESCAPED = "escaped"


@dataclass(slots=True)
class GameState:
    """A run in progress."""

    hero: Hero
    rng: Rng
    seed: int
    depth: int = 1
    dungeon_map: DungeonMap = field(default_factory=lambda: DungeonMap(width=1, height=1))
    player: Actor = None  # type: ignore[assignment]
    enemies: list[Actor] = field(default_factory=list)
    turn_queue: TurnQueue = field(default_factory=TurnQueue)
    log: list[LogEntry] = field(default_factory=list)
    turn: int = 0
    total_turns: int = 0
    run_state: RunState = RunState.PLAYING
    kills: int = 0
    revenge_stacks: int = 0
    floors_cleared: int = 0
    #: Draughts carried, not drunk. Survives a descent: it is the run's health
    #: reserve, and a floor that stripped it would make every descent a fresh
    #: start rather than a cost.
    inventory: list[GroundItem] = field(default_factory=list)
    #: What chests have taken. Run-long: there is no cure, so a curse is a
    #: decision made once and lived with.
    curses: list[Curse] = field(default_factory=list)
    #: Coins picked up this run. Banked when the run ends and spent in the shop,
    #: which is why it is kept apart from the score: one is a record of the run,
    #: the other is what the run was worth to you afterwards.
    gold: int = 0

    # -- curses -------------------------------------------------------------
    def add_curse(self, curse: Curse) -> None:
        """Take on ``curse``, for good.

        The stat changes are folded into the player's ``curse_modifiers`` here
        rather than derived on every read, because the effective stats are asked
        for constantly -- every attack, every turn of the queue -- and a list of
        curses walked each time is a cost paid in the hot path for a value that
        changes at most twice a run.

        Wither is the exception: it is not a modifier but a subtraction, taken
        once, from the health the hero will never get back.
        """
        self.curses.append(curse)
        player = self.player
        player.curse_modifiers = player.curse_modifiers + curse.modifiers

        if curse.wither:
            lost = max(1, round(player.max_hp * curse.wither))
            player.stats.max_hp = max(1, player.stats.max_hp - lost)
            player.stats.hp = min(player.stats.hp, player.stats.max_hp)

        self.say(f"{curse.name}: {curse.price}.", LogKind.BAD)

    @property
    def sight_radius(self) -> int:
        """How far the player can see, after anything that narrows it.

        The tightest curse wins rather than the last one applied: two things
        closing the dark in should not open it back up.
        """
        radius = VIEW_RADIUS
        for curse in self.curses:
            if curse.sight is not None:
                radius = min(radius, curse.sight)
        return radius

    @property
    def bleed_every(self) -> int:
        """Steps between losing a point of blood, or 0 for none."""
        return min(
            (curse.bleed_every for curse in self.curses if curse.bleed_every),
            default=0,
        )

    @property
    def heal_scale(self) -> float:
        """What a draught is worth, as a fraction of what it says on the tin."""
        scale = 1.0
        for curse in self.curses:
            scale *= curse.heal_scale
        return scale

    # -- logging ------------------------------------------------------------
    def say(self, text: str, kind: LogKind = LogKind.PLAIN) -> None:
        """Append a message to the log."""
        self.log.append(LogEntry(text=text, kind=kind, turn=self.turn))

    def recent_log(self, count: int = 8) -> list[LogEntry]:
        """The last ``count`` messages, oldest first."""
        return self.log[-count:]

    # -- queries ------------------------------------------------------------
    @property
    def over(self) -> bool:
        return self.run_state is not RunState.PLAYING

    @property
    def living_enemies(self) -> list[Actor]:
        return [enemy for enemy in self.enemies if enemy.alive]

    def actor_at(self, pos: Pos) -> Actor | None:
        """The actor standing on ``pos``, if any."""
        if self.player.alive and self.player.position == pos:
            return self.player
        for enemy in self.enemies:
            if enemy.alive and enemy.position == pos:
                return enemy
        return None

    def visible_enemies(self) -> list[Actor]:
        """Living enemies currently in the player's line of sight."""
        return [
            enemy for enemy in self.living_enemies if self.dungeon_map.is_visible(enemy.position)
        ]

    def enemy_beside_player(self) -> Actor | None:
        """An adjacent living enemy, if there is one."""
        from neverdeads_revenge.core.direction import DIRECTIONS

        for direction in DIRECTIONS:
            neighbour = direction.step(self.player.position)
            found = self.actor_at(neighbour)
            if found is not None and not found.is_player:
                return found
        return None

    # -- perception ---------------------------------------------------------
    def refresh_vision(self) -> None:
        """Recompute what the player can see. Call after every move."""
        self.dungeon_map.clear_visibility()
        visible, explored = compute_fov_full(
            self.player.position,
            self.sight_radius,
            self.dungeon_map.is_opaque,
            self.dungeon_map.in_bounds,
        )
        self.dungeon_map.visible = visible
        self.dungeon_map.explored |= explored

    # -- floors -------------------------------------------------------------
    def build_floor(self, depth: int) -> GeneratedFloor:
        """Generate the next floor and move everyone onto it."""
        self.depth = depth
        floor = generate_floor(self.rng, depth=depth, curse_keys=tuple(CURSES))
        self.dungeon_map = floor.map

        if self.player is None:
            self.player = make_hero(self.hero, floor.player_start)
        else:
            self.player.position = floor.player_start
            # ``steps`` is deliberately not reset here. It is a run total, like
            # ``total_turns``. It used to reset per floor, which made the
            # summary's "Cells walked" report only the last floor while reading
            # like a run total -- and the old score, which counted steps, was
            # quietly counting only that one floor too.

        self.enemies = [
            make_enemy(pick_enemy_template(self.rng, depth), pos)
            for pos in floor.spawn_points
        ]
        self.turn_queue = TurnQueue([self.player, *self.enemies])
        self.refresh_vision()
        # The per-floor clock restarts; total_turns keeps counting so the run
        # summary reports the whole run, not the room the hero died in.
        self.turn = 0

        # Revenge is a per-floor reward, so it lapses on the way down. Setting it
        # to zero clears whichever bonus this hero collects, without the caller
        # needing to know which that is.
        self.revenge_stacks = 0
        apply_revenge(self.player, 0)

        self.say(f"You descend to floor {depth}.", LogKind.SYSTEM)
        if floor.is_final:
            self.say("A rift tears the dark open, and beyond it: air.", LogKind.GOOD)
        if self.enemies:
            self.say(f"{len(self.enemies)} shapes move in the dark.", LogKind.PLAIN)
        return floor

    @property
    def exit_pos(self) -> Pos | None:
        """Where the way onward is, or ``None`` on a floor that has none.

        Deliberately optional. The old version fell back to the player's own
        position, which quietly turned ``on_stairs`` into "always true" on any
        floor without a staircase -- and the final floor is exactly that floor.
        """
        for tile in (Tile.STAIRS_DOWN, Tile.RIFT):
            found = self.dungeon_map.find_tile(tile)
            if found:
                return found[0]
        return None

    @property
    def on_exit(self) -> bool:
        """Standing on whatever takes you onward, stairs or rift alike."""
        return self.exit_pos is not None and self.player.position == self.exit_pos

    @property
    def at_the_rift(self) -> bool:
        """Standing on the rift, which ends the run rather than descends."""
        return self.dungeon_map.tile_at(self.player.position) is Tile.RIFT

    @property
    def stairs(self) -> Pos | None:
        """Where the stairs down are, if this floor has any."""
        found = self.dungeon_map.find_tile(Tile.STAIRS_DOWN)
        return found[0] if found else None

    @property
    def on_stairs(self) -> bool:
        return self.stairs is not None and self.player.position == self.stairs

    # -- endings ------------------------------------------------------------
    def escape(self) -> None:
        """Step through the rift and out of the dungeon.

        The one ending that is not a death, and the answer to the question the
        prologue asks. Kept here beside ``build_floor`` so both endings of a run
        are set in one file.
        """
        self.run_state = RunState.ESCAPED
        self.say("You step into the rift. The emptiness lets you go.", LogKind.GOOD)

    # -- scoring ------------------------------------------------------------
    @property
    def base_score(self) -> int:
        """Depth, before speed and before getting out.

        Killing things pays in coin rather than in points. The score is about
        how far and how fast; the purse is about what you can afford next time,
        and running them together made every fight worth points whether or not
        it was worth fighting.
        """
        return self.floors_cleared * 250

    @property
    def speed_bonus(self) -> int:
        """Points for getting through the floors quickly.

        A budget rather than a penalty. Going over it scores nothing here instead
        of going negative, so a slow run is worth less, not worth less than
        nothing -- a screen with a minus sign on it reads as a punishment rather
        than a comparison.

        Scaled by the floors actually cleared, so standing still on floor one
        cannot bank a bonus for the turns it did not spend descending.
        """
        budget = TURN_BUDGET_PER_FLOOR * self.floors_cleared
        return max(0, budget - self.total_turns) * SPEED_BONUS_PER_TURN

    @property
    def score(self) -> int:
        """The run's score, for the summary screen.

        Time is in here and walking is not: steps measure how much of the floor
        you saw, and a run should be rewarded for leaving sooner rather than for
        wandering further. The escape bonus is larger than any plausible death
        score at the same depth, so a screen full of numbers can never rank an
        escape below a run that died on floor ten one step from the rift.
        """
        escape = ESCAPE_BONUS if self.run_state is RunState.ESCAPED else 0
        return self.base_score + self.speed_bonus + escape


def start_run(hero: Hero, seed: int, upgrades: dict[str, int] | None = None) -> GameState:
    """Begin a fresh run with ``hero``.

    Args:
        hero: The chosen character.
        seed: The run seed. The same seed always yields the same dungeon.
        upgrades: Permanent meta upgrades, as ``{key: stacks}``.
    """
    state = GameState(hero=hero, rng=Rng(seed), seed=seed)
    _apply_upgrades(state, upgrades or {})
    state.build_floor(1)
    return state


def _apply_upgrades(state: GameState, upgrades: dict[str, int]) -> None:
    """Fold permanent meta upgrades into the hero's starting stats.

    Stubbed for milestone 1: the data path exists so later upgrades only need an
    entry here, not a change to the run setup.
    """
    del upgrades  # nothing to apply yet
