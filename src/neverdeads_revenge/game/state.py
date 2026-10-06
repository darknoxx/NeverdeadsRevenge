"""Run state: everything one attempt at the dungeon consists of.

:class:`GameState` owns the map, the actors, the turn queue and the message log.
It is pure data plus queries -- no Textual, no I/O -- which is what lets the
whole game be simulated in a unit test.

A "run" is one life: pick a hero, descend until you die, see the summary.
Permanent progress between runs lives in :mod:`neverdeads_revenge.persistence`.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum

from neverdeads_revenge.core.direction import Pos
from neverdeads_revenge.core.rng import Rng
from neverdeads_revenge.core.turn_queue import TurnQueue
from neverdeads_revenge.world.fov import compute_fov_full
from neverdeads_revenge.world.generator import GeneratedFloor, generate_floor
from neverdeads_revenge.world.items import ITEMS, make_item
from neverdeads_revenge.world.map import DungeonMap, GroundItem
from neverdeads_revenge.world.modifiers import Modifiers
from neverdeads_revenge.world.tiles import Tile

from .actors import Actor, Hero, make_enemy, make_hero, pick_enemy_template
from .combat import apply_revenge
from .curses import CURSES, Curse
from .shop import META_UPGRADES, Loadout

__all__ = [
    "LogEntry",
    "LogKind",
    "RunState",
    "GameState",
    "VIEW_RADIUS",
    "ESCAPE_BONUS",
    "TURN_BUDGET_PER_FLOOR",
    "SPEED_BONUS_PER_TURN",
    "CLEANSE_COST",
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

#: What the spring charges to take one curse off.
#:
#: A flat price, and deliberately a real one: coin is the only thing in the game
#: that outlives the run, so spending it on the run in progress is a genuine
#: trade rather than a formality. Placeholder, like every other price.
CLEANSE_COST = 40


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

    # -- what the shop sent with you ----------------------------------------
    #
    # Bought before the run and carried into it. Kept as plain numbers rather
    # than as a reference to the purchase, so nothing in the hot path has to ask
    # the save file what a wild offer does.
    #: Extra sight on top of the base radius, from the lantern upgrade.
    sight_bonus: int = 0
    #: What a dropped coin is multiplied by: the pact and greed both touch it.
    coin_multiplier: float = 1.0
    #: What every monster's health is multiplied by. Greed's catch.
    enemy_hp_multiplier: float = 1.0
    #: Killing blows left before one of them lands. Second wind.
    extra_lives: int = 0
    #: Player turns during which nothing can land a blow on you. The borrowed
    #: face, set to one by a kill and counted down by the world.
    shrouded: int = 0
    #: Whether the grave ward is still unspent on this floor. Armed when the
    #: floor is built, spent by the first blow that reaches you.
    ward_ready: bool = False
    #: Which wild offers are in force this run, by key.
    #:
    #: The two that multiply -- greed and the pact -- are numbers rather than
    #: flags, because two of them have to stack. Everything else is a rule that
    #: is either on or off, and a set says that once instead of six booleans.
    wilds: set[str] = field(default_factory=set)

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
            # Written down, because the fraction is of the maximum at this
            # moment and recomputing it later would give a different number.
            self.curses[-1] = replace(curse, wither_taken=lost)

        self.say(f"{curse.name}: {curse.price}.", LogKind.BAD)

    def remove_curse(self, curse: Curse) -> None:
        """Lift a curse, and give back exactly what it took.

        Exactly, because "a quarter of your health" is a quarter of whatever the
        maximum was the moment it landed. Recomputed later it is a quarter of a
        different number, and a spring that hands back the wrong amount is a
        spring nobody trusts twice.
        """
        if curse not in self.curses:
            return
        self.curses.remove(curse)

        player = self.player
        # Rebuilt rather than subtracted. Floats do not subtract back to where
        # they started, and a residue of 0.0000001 on the speed would be
        # invisible right up until it was not.
        player.curse_modifiers = Modifiers()
        for remaining in self.curses:
            player.curse_modifiers = player.curse_modifiers + remaining.modifiers

        if curse.wither_taken:
            player.stats.max_hp += curse.wither_taken
            player.stats.hp = min(
                player.stats.max_hp, player.stats.hp + curse.wither_taken
            )

    @property
    def sight_radius(self) -> int:
        """How far the player can see, after anything that narrows it.

        The tightest curse wins rather than the last one applied: two things
        closing the dark in should not open it back up.
        """
        radius = VIEW_RADIUS + self.sight_bonus
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
        """What a draught is worth, as a fraction of what it says on the tin.

        Curses take their share and the marrow adds to it, and the two are meant
        to be able to meet: FAMINE halves a draught and the marrow makes it half
        again as much, which is the whole reason the marrow is worded that way.
        """
        scale = 1.0
        for curse in self.curses:
            scale *= curse.heal_scale
        if self.has_passive("marrow"):
            scale *= 1.5
        return scale

    # -- amulets ------------------------------------------------------------
    @property
    def amulet(self) -> str | None:
        """The ability the worn amulet grants, or ``None``.

        One slot, so one ability. A second amulet would be a second rule to hold
        in your head at the same time, and the three slots already ask for two.
        """
        worn = self.player.equipment.get("amulet")
        return worn.amulet if worn is not None else None

    def has_passive(self, key: str) -> bool:
        """Whether the worn amulet is this one."""
        return self.amulet == key

    # -- what a wild offer did to the run -----------------------------------
    def has_wild(self, key: str) -> bool:
        """Whether this wild offer is in force."""
        return key in self.wilds

    @property
    def draughts_forbidden(self) -> bool:
        """Whether drinking has been taken away. The hollow tooth."""
        return self.has_wild("hollow_tooth")

    @property
    def kill_heal(self) -> int:
        """Health a kill puts back from the run's bargains.

        The last ember is an amulet and is asked separately; this is the one a
        wild offer pays, and the two are added rather than compared because a
        player who bought both bought both.
        """
        return 3 if self.has_wild("hollow_tooth") else 0

    @property
    def toll_per_floor(self) -> int:
        """What the dark charges for the next floor down. The pilgrim's toll."""
        return 5 if self.has_wild("pilgrims_toll") else 0

    @property
    def score_multiplier(self) -> float:
        """What the run is worth on the board.

        The nameless run halves it and pays in coin instead, which is the two
        currencies of this game set against each other on purpose.
        """
        return 0.5 if self.has_wild("nameless_run") else 1.0

    @property
    def coin_factor(self) -> float:
        """What a dropped coin is multiplied by, from every source.

        The wilds set ``coin_multiplier``; the coin hand multiplies it on top.
        Kept apart so a wild can be re-applied or replaced without having to know
        what the amulet is doing.
        """
        factor = self.coin_multiplier
        if self.has_passive("coin_hand"):
            factor *= 1.25
        return factor

    def refresh_passives(self) -> None:
        """Recompute the two amulets whose effect depends on the moment.

        Written on every call rather than only when something changed, for the
        same reason REVENGE is: a bonus that is written rather than nudged cannot
        leave a residue behind when its condition stops being true.
        """
        player = self.player
        player.passive_armor = 0
        player.passive_damage = 0

        amulet = self.amulet
        if amulet == "deathwatch" and player.hp * 3 <= player.max_hp:
            player.passive_armor += 3
        if amulet == "patience":
            # Four at turn forty, which is about the point a careful floor stops
            # being careful and starts being a fight. The score wants you gone
            # quickly and this amulet wants you to stay; that argument is the
            # whole reason it exists.
            player.passive_damage += min(4, self.turn // 10)

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
        # What the player is already carrying goes into the floor's own dice.
        # A chest that hands out a third coat is a chest nobody opens twice, and
        # the floor is the only place that can decide not to.
        floor = generate_floor(
            self.rng,
            depth=depth,
            curse_keys=tuple(CURSES),
            filled_slots=tuple(self.player.equipment) if self.player else (),
        )
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
        self.toughen_enemies()
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

        self.arm_amulets()

        self.say(f"You descend to floor {depth}.", LogKind.SYSTEM)
        if floor.is_final:
            self.say("A rift tears the dark open, and beyond it: air.", LogKind.GOOD)
        if self.enemies:
            self.say(f"{len(self.enemies)} shapes move in the dark.", LogKind.PLAIN)
        return floor

    def arm_amulets(self) -> None:
        """Whatever the worn amulet does at the start of a floor.

        Called from ``build_floor`` and again from :func:`start_run`, because the
        first floor is built before the shop's parcel is opened. Without the
        second call an amulet bought or found for this run would sit out the floor
        it was bought for -- the same trap the wild offers fell into.

        Every step has to survive being run twice on the same floor, which is why
        the rune heart is guarded by depth and the rest are plain assignments.
        """
        self.player.stored_armor = 0
        self.shrouded = 0
        for enemy in self.enemies:
            enemy.struck = False

        if self.depth > 1 and self.has_passive("rune_heart"):
            # Only on the way down. Paying out on floor one as well would make
            # "every floor you descend" one floor more than it says.
            self.player.stats.max_hp += 1
            self.player.stats.hp += 1

        if self.has_passive("wayfarer") and self.exit_pos is not None:
            # Dimly, the way anywhere else you have walked past is drawn. The map
            # already knows how to show a place you have been and cannot see; this
            # only tells it that you have been there.
            self.dungeon_map.explored.add(self.exit_pos)

        self.ward_ready = self.has_passive("grave_ward")
        self.refresh_passives()

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
    def spring_pos(self) -> Pos | None:
        """Where the cleansing spring is, if this floor has one."""
        found = self.dungeon_map.find_tile(Tile.SPRING)
        return found[0] if found else None

    @property
    def at_the_spring(self) -> bool:
        """Standing in the spring, which is the only way to use it."""
        return self.dungeon_map.tile_at(self.player.position) is Tile.SPRING

    @property
    def cleanse_cost(self) -> int:
        """What one curse costs to wash off, right now."""
        return CLEANSE_COST

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

    def toughen_enemies(self) -> None:
        """Apply the enemy-health multiplier to whatever is on this floor.

        Called from ``build_floor``, and again from :func:`start_run` after the
        wild offers land -- greed is bought for a run that has already had its
        first floor built, and a bargain that skips floor one is a bargain that
        is quietly mis-sold.
        """
        if self.enemy_hp_multiplier == 1.0:
            return
        for enemy in self.enemies:
            enemy.stats.max_hp = max(
                1, round(enemy.stats.max_hp * self.enemy_hp_multiplier)
            )
            enemy.stats.hp = enemy.stats.max_hp

    # -- endings ------------------------------------------------------------
    def die(self, cause: str) -> bool:
        """Kill the hero, unless something bought keeps them alive.

        Returns whether the hero actually died. One place rather than at every
        way a run can end, because bleeding out is a death like any other and a
        bargain that only worked against monsters would be a bargain with a
        footnote.
        """
        if self.extra_lives > 0:
            self.extra_lives -= 1
            self.player.stats.hp = 1
            self.player.alive = True
            self.say(
                "Something hauls you back from the edge. Not this time.",
                LogKind.GOOD,
            )
            return False

        self.player.alive = False
        self.run_state = RunState.DEAD
        self.say(cause, LogKind.BAD)
        return True

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
        return round(
            (self.base_score + self.speed_bonus + escape) * self.score_multiplier
        )


def start_run(
    hero: Hero,
    seed: int,
    loadout: Loadout | None = None,
    upgrades: dict[str, int] | None = None,
) -> GameState:
    """Begin a fresh run with ``hero``.

    Args:
        hero: The chosen character.
        seed: The run seed. The same seed always yields the same dungeon.
        loadout: What the shop sold for this run.
        upgrades: Permanent meta upgrades, as ``{key: stacks}``. Kept as a
            shorthand for callers that have no loadout; ``loadout.upgrades``
            wins when both are given.
    """
    loadout = loadout or Loadout()
    state = GameState(hero=hero, rng=Rng(seed), seed=seed)

    # The floor first, because the hero does not exist until it is built and
    # everything below changes the hero.
    state.build_floor(1)

    permanent = loadout.upgrades or (upgrades or {})
    _apply_upgrades(state, permanent)
    _apply_pending(state, loadout.pending)
    _apply_wilds(state, loadout.wilds)
    # The floor is already built, so anything the loadout changed about the
    # monsters or the amulet has to be applied to it now.
    state.toughen_enemies()
    state.arm_amulets()
    return state


def _apply_upgrades(state: GameState, upgrades: dict[str, int]) -> None:
    """Fold permanent upgrades into the hero's starting stats.

    Every upgrade is a delta, including the negative one the blood bargain
    sells, which is why this is a sum and not a set of special cases.
    """
    player = state.player
    for key, stacks in upgrades.items():
        upgrade = META_UPGRADES.get(key)
        if upgrade is None or stacks <= 0:
            continue
        if upgrade.max_hp:
            player.stats.max_hp = max(1, player.stats.max_hp + upgrade.max_hp * stacks)
        if upgrade.speed:
            player.stats.speed += upgrade.speed * stacks
        if upgrade.sight:
            state.sight_bonus += upgrade.sight * stacks

    # A run starts whole. Bought health you do not have is not bought health,
    # and the blood bargain's whole point is that the missing part is gone.
    player.stats.hp = player.stats.max_hp


def _the(name: str) -> str:
    """``the`` before a name that needs one, and not before one that has it."""
    return name if name.startswith("the ") else f"the {name}"


def _receive(state: GameState, template) -> None:
    """Put an item where it belongs: draughts in the pack, the rest worn."""
    item = make_item(template)
    if template.kind == "draught":
        state.inventory.append(item)
    else:
        state.player.equipment[template.slot] = item


def _apply_pending(state: GameState, keys) -> None:
    """Open the shop's parcel: everything bought for this run."""
    for key in keys:
        template = ITEMS.get(key)
        if template is None:
            continue
        _receive(state, template)
        state.say(
            f"You start with {_the(template.name)}.",
            LogKind.SYSTEM,
        )


def _apply_wilds(state: GameState, keys) -> None:
    """Apply the bargains. Each one is its own small rule, on purpose.

    A table of effects would be shorter and would also be a table of lambdas,
    which is not shorter to read. There are six of these and each does something
    the others do not.
    """
    for key in keys:
        state.wilds.add(key)

        if key == "blind_box":
            template = state.rng.choice_weighted(
                [(t, t.weight) for t in ITEMS.values()]
            )
            _receive(state, template)
            state.say(f"The blind box holds a {template.name}.", LogKind.GOOD)
        elif key == "pact":
            state.coin_multiplier *= 1.5
            state.add_curse(state.rng.pick(list(CURSES.values())))
            state.say("The pact settles over you, and will not lift.", LogKind.BAD)
        elif key == "greed":
            state.coin_multiplier *= 2.0
            state.enemy_hp_multiplier *= 1.2
            state.say("You want all of it, and the dark can tell.", LogKind.BAD)
        elif key == "grave_goods":
            _receive(state, ITEMS["grave"])
            state.say("Grave iron, cold and heavier than it looks.", LogKind.SYSTEM)
        elif key == "second_wind":
            state.extra_lives += 1
            state.say("Something down here is keeping count of your deaths.", LogKind.SYSTEM)
        elif key == "wager":
            # A coin, and it is not a metaphor. Half the runs it is the best
            # blade in the game and half the runs it is a curse, and the player
            # who buys it has decided they do not mind which.
            strong_blades = [
                t.key
                for t in ITEMS.values()
                if t.chest_only and t.kind == "weapon"
            ]
            if state.rng.chance(0.5):
                blade = ITEMS[state.rng.pick(strong_blades)]
                _receive(state, blade)
                state.say(
                    f"The coin comes up clean. {blade.name} is in your hands.",
                    LogKind.GOOD,
                )
            else:
                state.add_curse(state.rng.pick(list(CURSES.values())))
                state.say("The coin comes up dark.", LogKind.BAD)
        elif key == "hollow_tooth":
            state.say(
                "Your teeth are gone and nothing will stay down. "
                "Everything you kill feeds you instead.",
                LogKind.SYSTEM,
            )
        elif key == "pilgrims_toll":
            state.coin_multiplier *= 1.5
            state.say("Every floor down will be paid for.", LogKind.BAD)
        elif key == "counts_favour":
            state.say("Something is counting your kills. It has a number in mind.", LogKind.SYSTEM)
        elif key == "mirror_of_hunger":
            state.say("Something will drink whenever you do.", LogKind.BAD)
        elif key == "nameless_run":
            state.coin_multiplier *= 2.0
            state.say(
                "Your name is not on this run, and the coin does not care.",
                LogKind.SYSTEM,
            )
