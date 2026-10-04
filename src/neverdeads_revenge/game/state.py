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

__all__ = ["LogEntry", "LogKind", "RunState", "GameState", "VIEW_RADIUS", "ESCAPE_BONUS"]

VIEW_RADIUS = 9
"""How far the player can see, in cells."""

ESCAPE_BONUS = 5000
"""Score awarded for leaving the dungeon alive instead of dying in it."""


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
            VIEW_RADIUS,
            self.dungeon_map.is_opaque,
            self.dungeon_map.in_bounds,
        )
        self.dungeon_map.visible = visible
        self.dungeon_map.explored |= explored

    # -- floors -------------------------------------------------------------
    def build_floor(self, depth: int) -> GeneratedFloor:
        """Generate the next floor and move everyone onto it."""
        self.depth = depth
        floor = generate_floor(self.rng, depth=depth)
        self.dungeon_map = floor.map

        if self.player is None:
            self.player = make_hero(self.hero, floor.player_start)
        else:
            self.player.position = floor.player_start
            self.player.steps = 0

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
    def score(self) -> int:
        """A rough run score, for the summary screen.

        The escape bonus is larger than any plausible death score at the same
        depth, so a screen full of numbers can never rank an escape below a run
        that died on floor 10 one step from the rift.
        """
        base = self.kills * 100 + self.floors_cleared * 250 + self.player.steps
        return base + (ESCAPE_BONUS if self.run_state is RunState.ESCAPED else 0)


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
