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
from neverdeads_revenge.world.map import DungeonMap
from neverdeads_revenge.world.tiles import Tile

from .actors import Actor, Hero, make_enemy, make_hero, pick_enemy_template

__all__ = ["LogEntry", "LogKind", "RunState", "GameState", "VIEW_RADIUS"]

VIEW_RADIUS = 9
"""How far the player can see, in cells."""


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
    run_state: RunState = RunState.PLAYING
    kills: int = 0
    revenge_stacks: int = 0
    floors_cleared: int = 0

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
            make_enemy(pick_enemy_template(self.rng), pos)
            for pos in floor.spawn_points
        ]
        self.turn_queue = TurnQueue([self.player, *self.enemies])
        self.refresh_vision()
        self.turn = 0

        # Revenge is a per-floor reward, so it lapses on the way down.
        self.revenge_stacks = 0
        self.player.speed_bonus = 0.0

        self.say(f"You descend to floor {depth}.", LogKind.SYSTEM)
        if self.enemies:
            self.say(f"{len(self.enemies)} shapes move in the dark.", LogKind.PLAIN)
        return floor

    @property
    def stairs(self) -> Pos:
        """Where the stairs down currently are."""
        found = self.dungeon_map.find_tile(Tile.STAIRS_DOWN)
        return found[0] if found else self.player.position

    @property
    def on_stairs(self) -> bool:
        return self.player.position == self.stairs

    # -- scoring ------------------------------------------------------------
    @property
    def score(self) -> int:
        """A rough run score, for the summary screen."""
        return self.kills * 100 + self.floors_cleared * 250 + self.player.steps


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
