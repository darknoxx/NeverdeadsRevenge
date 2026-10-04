"""Player actions and the AI that answers them.

Everything the player can do goes through :func:`perform_action`, and everything
a monster does goes through :func:`take_turn`. Both mutate :class:`GameState` and
return nothing; the messages they emit are what the UI renders. Keeping the
decision-making here and the drawing in ``ui/`` means a test can play ten turns of
the game without a terminal.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from neverdeads_revenge.core.direction import Direction, chebyshev, direction_towards
from neverdeads_revenge.world.tiles import Tile

from .actors import Actor
from .combat import REVENGE_SPEED_BONUS, apply_revenge, attack
from .state import GameState, LogKind, RunState

__all__ = [
    "Action",
    "ActionResult",
    "perform_action",
    "take_turn",
    "advance_world",
    "descend",
    "REVENGE_SPEED_BONUS",
    "MAX_ENEMY_ACTIONS_PER_PLAYER_TURN",
]


class Action(Enum):
    """Everything the player can do."""

    MOVE_NORTH = "north"
    MOVE_SOUTH = "south"
    MOVE_EAST = "east"
    MOVE_WEST = "west"
    MOVE_NE = "ne"
    MOVE_NW = "nw"
    MOVE_SE = "se"
    MOVE_SW = "sw"
    WAIT = "wait"
    #: Do whatever is under the player: take it, or take the stairs. This is the
    #: verb a key is bound to. The two specific actions below stay because they
    #: are meaningful on their own -- ``>`` is the classic "go down" and does not
    #: need to guess, and a test that wants to pick something up should not have
    #: to arrange a floor first.
    INTERACT = "interact"
    PICK_UP = "pickup"
    DESCEND = "descend"
    QUAFF = "quaff"
    INVENTORY = "inventory"

    @property
    def direction(self) -> Direction:
        """The movement direction, or ``NONE`` for non-movement actions."""
        return _ACTION_DIRECTIONS.get(self, Direction.NONE)


_ACTION_DIRECTIONS: dict[Action, Direction] = {
    Action.MOVE_NORTH: Direction.NORTH,
    Action.MOVE_SOUTH: Direction.SOUTH,
    Action.MOVE_EAST: Direction.EAST,
    Action.MOVE_WEST: Direction.WEST,
    Action.MOVE_NE: Direction.NORTH_EAST,
    Action.MOVE_NW: Direction.NORTH_WEST,
    Action.MOVE_SE: Direction.SOUTH_EAST,
    Action.MOVE_SW: Direction.SOUTH_WEST,
}


@dataclass(frozen=True, slots=True)
class ActionResult:
    """Outcome of a player action."""

    consumed_turn: bool
    acted: bool
    died: bool = False
    escaped: bool = False


# -- helpers ---------------------------------------------------------------


def _remove_corpse(state: GameState, enemy: Actor) -> None:
    enemy.alive = False
    state.enemies.remove(enemy)
    state.turn_queue.remove(enemy)


def _kill_message(state: GameState, enemy: Actor, outcome) -> None:
    """Report a kill and grant REVENGE when the player did it."""
    state.say(
        f"You {outcome.verb_second_person} the {enemy.name} for {outcome.damage}!",
        LogKind.CRIT if outcome.crit else LogKind.COMBAT,
    )
    state.kills += 1

    stacks = apply_revenge(state.player, state.revenge_stacks)
    gained = stacks > state.revenge_stacks
    state.revenge_stacks = stacks
    if gained:
        state.say(
            f"REVENGE {stacks}: +{REVENGE_SPEED_BONUS:.1f} speed.",
            LogKind.GOOD,
        )


def _player_takes_damage(state: GameState, enemy: Actor, outcome) -> None:
    if outcome.hit:
        state.say(
            f"The {enemy.name} {outcome.verb} you for {outcome.damage}.",
            LogKind.BAD if outcome.killed else LogKind.DAMAGE,
        )
    else:
        state.say(f"The {enemy.name} attacks and misses you.", LogKind.PLAIN)
    if outcome.killed:
        state.player.alive = False
        state.run_state = RunState.DEAD
        state.say(f"You are slain by the {enemy.name}.", LogKind.BAD)


def _enemy_takes_damage(state: GameState, enemy: Actor, outcome) -> None:
    if outcome.killed:
        _kill_message(state, enemy, outcome)
        return
    state.say(
        f"You {outcome.verb_second_person} the {enemy.name} for {outcome.damage}.",
        LogKind.CRIT if outcome.crit else LogKind.COMBAT,
    )


# -- player actions --------------------------------------------------------


def _outcome(state: GameState, consumed_turn: bool, acted: bool) -> ActionResult:
    """Wrap a result, reading the ending off the state rather than assuming it.

    Worth the two lines: ``died=state.over`` was true after an escape too, and
    the game over screen would have announced a death to a player who had just
    won.
    """
    return ActionResult(
        consumed_turn=consumed_turn,
        acted=acted,
        died=state.run_state is RunState.DEAD,
        escaped=state.run_state is RunState.ESCAPED,
    )


def perform_action(state: GameState, action: Action) -> ActionResult:
    """Apply a player action, then let the world answer.

    Returns whether the action consumed a turn, so the UI knows whether to run
    enemy turns.
    """
    if state.over:
        return _outcome(state, consumed_turn=False, acted=False)

    match action:
        case Action.INTERACT:
            return _interact(state)
        case Action.PICK_UP:
            return _pick_up(state)
        case Action.QUAFF:
            return _quaff(state)
        case Action.INVENTORY:
            return _inventory(state)
        case Action.DESCEND:
            return _try_descend(state)
        case _:
            pass

    if action is Action.WAIT:
        state.say("You wait.", LogKind.PLAIN)
        acted = True
    else:
        acted = _try_move(state, action.direction)

    if state.over:
        return _outcome(state, consumed_turn=acted, acted=acted)

    # Only a real action advances the clock. Bumping a wall must not tick the
    # turn counter, or the displayed turn number drifts away from the world.
    if acted:
        state.turn += 1
        state.total_turns += 1
        advance_world(state)
    state.refresh_vision()
    return _outcome(state, consumed_turn=acted, acted=acted)


def _try_move(state: GameState, direction: Direction) -> bool:
    """Move or attack in ``direction``. Returns True if a turn was spent."""
    target = direction.step(state.player.position)
    if not state.dungeon_map.in_bounds(target):
        return False

    blocker = state.actor_at(target)
    if blocker is not None:
        if blocker.is_player:  # cannot happen, but be explicit
            return False
        _resolve_player_attack(state, blocker)
        return True

    if not state.dungeon_map.is_walkable(target):
        return False

    state.player.position = target
    state.player.steps += 1
    return True


def _resolve_player_attack(state: GameState, target: Actor) -> None:
    outcome = attack(state.player, target, state.rng)
    if not outcome.hit:
        state.say(f"You swing at the {target.name} and miss.", LogKind.PLAIN)
        return
    _enemy_takes_damage(state, target, outcome)
    if outcome.killed:
        _remove_corpse(state, target)


def _interact(state: GameState) -> ActionResult:
    """Do the one useful thing where the player is standing.

    Items are taken before the exit is used, and the order is the whole design:
    the generator never puts loot on the stairs, but if it ever did, walking onto
    the staircase and leaving the floor without the potion would be the game
    silently throwing something away on the player's behalf. Taking it first
    means ``enter`` is always safe to press.

    Costs no turn. Picking something up and going downstairs are not things the
    monsters should get to answer.
    """
    if state.dungeon_map.item_at(state.player.position) is not None:
        return _pick_up(state)

    if state.on_exit:
        return _try_descend(state)

    state.say("There is nothing here.", LogKind.PLAIN)
    return ActionResult(consumed_turn=False, acted=False)


def _pick_up(state: GameState) -> ActionResult:
    item = state.dungeon_map.item_at(state.player.position)
    if item is None:
        state.say("There is nothing here to take.", LogKind.PLAIN)
        return ActionResult(consumed_turn=False, acted=False)
    state.dungeon_map.remove_item(state.player.position)
    state.inventory.append(item)
    state.say(f"You pick up the {item.name}.", LogKind.GOOD)
    return ActionResult(consumed_turn=False, acted=False)


def _inventory(state: GameState) -> ActionResult:
    """Report what is being carried. Costs nothing -- it is only a look."""
    if not state.inventory:
        state.say("You carry nothing.", LogKind.PLAIN)
        return ActionResult(consumed_turn=False, acted=False)

    counts: dict[str, int] = {}
    for item in state.inventory:
        counts[item.name] = counts.get(item.name, 0) + 1
    carried = ", ".join(f"{count}x {name}" for name, count in sorted(counts.items()))
    state.say(f"You carry {carried}.", LogKind.PLAIN)
    return ActionResult(consumed_turn=False, acted=False)


def _quaff(state: GameState) -> ActionResult:
    """Drink the cheapest draught that covers the wound.

    Picking the smallest one that still heals in full is the choice a careful
    player would make anyway: drinking the elixir at 24/26 health throws away
    sixteen points of it. Handing that decision to the player is a real decision,
    but it is also one a new player gets wrong once and then never again, so the
    game makes the obvious play and charges a turn for it.
    """
    if not state.inventory:
        state.say("You have nothing to drink.", LogKind.PLAIN)
        return ActionResult(consumed_turn=False, acted=False)

    player = state.player
    missing = player.max_hp - player.stats.hp
    if missing <= 0:
        state.say("You are unhurt.", LogKind.PLAIN)
        return ActionResult(consumed_turn=False, acted=False)

    # Spend the smallest draught that does the job without overflowing; if none
    # can, spend the smallest one anyway and accept the spill. Either way the
    # good draught is saved for a wound that needs it.
    affordable = [item for item in state.inventory if item.heal <= missing]
    item = (
        max(affordable, key=lambda i: i.heal)
        if affordable
        else min(state.inventory, key=lambda i: i.heal)
    )

    state.inventory.remove(item)
    healed = player.stats.heal(item.heal)
    state.say(f"You drink the {item.name} and recover {healed}.", LogKind.GOOD)
    if healed < item.heal:
        state.say(
            f"Its power spills past the wound; {item.heal - healed} is lost.",
            LogKind.PLAIN,
        )

    # Drinking takes a turn, so it is not a free action in the middle of a fight
    # and monsters get their answer.
    state.turn += 1
    state.total_turns += 1
    advance_world(state)
    state.refresh_vision()
    return _outcome(state, consumed_turn=True, acted=True)


def _try_descend(state: GameState) -> ActionResult:
    if not state.on_exit:
        # On the last floor there are no stairs at all, and "no stairs here"
        # next to a glowing rift would read as a bug.
        if state.dungeon_map.find_tile(Tile.RIFT):
            state.say("There is nothing here to take you out.", LogKind.PLAIN)
        else:
            state.say("There are no stairs here.", LogKind.PLAIN)
        return ActionResult(consumed_turn=False, acted=False)

    if state.at_the_rift:
        state.escape()
        return _outcome(state, consumed_turn=False, acted=False)

    state.floors_cleared += 1
    state.build_floor(state.depth + 1)
    return _outcome(state, consumed_turn=False, acted=False)


#: Public wrapper so the UI can trigger a descent without importing internals.
def descend(state: GameState) -> ActionResult:
    """Try to go down a level from wherever the player stands."""
    return _try_descend(state)


# -- enemy turns -----------------------------------------------------------


def take_turn(state: GameState, actor: Actor) -> bool:
    """Let one enemy act. Returns whether it actually spent a turn."""
    if not actor.alive or state.over:
        return False
    if not state.dungeon_map.is_visible(actor.position):
        return False  # only act when the player can see you; keeps the game fair

    player = state.player
    distance = chebyshev(actor.position, player.position)

    if distance <= 1:
        _resolve_enemy_attack(state, actor, player)
        return True

    if _move_towards_player(state, actor, player, distance):
        return True
    return False


def _resolve_enemy_attack(state: GameState, attacker: Actor, player: Actor) -> None:
    outcome = attack(attacker, player, state.rng)
    _player_takes_damage(state, attacker, outcome)


def _move_towards_player(
    state: GameState, actor: Actor, player: Actor, distance: int
) -> bool:
    """Step one cell closer, or drift if there is no way through.

    Candidate steps are tried in preference order, straight ahead first, so
    monsters close in rather than jitter. Sideways options let them slide around
    a blocked approach instead of pressing uselessly into a wall.
    """
    forward = direction_towards(actor.position, player.position)

    if actor.behaviour == "cautious" and distance > 5:
        # Keep their distance until the player comes to them.
        options = [forward.rotate(2), forward.rotate(-2)]
    else:
        options = [forward]
        if distance <= 6:
            options = [forward, forward.rotate(1), forward.rotate(-1)]

    for direction in dict.fromkeys(options):  # de-duplicate, keep order
        target = direction.step(actor.position)
        if not state.dungeon_map.is_walkable(target):
            continue
        if state.actor_at(target) is not None:
            continue
        if chebyshev(target, player.position) >= distance:
            continue
        actor.position = target
        return True
    return False


#: Safety net so a pathological queue can never hang the game loop.
MAX_ENEMY_ACTIONS_PER_PLAYER_TURN = 64


def advance_world(state: GameState) -> None:
    """Run the scheduler until it is the player's turn again.

    This is where the speed stat actually pays off: Noxx acts, then one or two
    monsters get an action in before the queue hands control back. A speed-0.7
    ghoul only gets to move about every second player turn.
    """
    for _ in range(MAX_ENEMY_ACTIONS_PER_PLAYER_TURN):
        if state.over:
            return
        actor = state.turn_queue.pop()
        if actor is None:
            return
        if actor.is_player:
            return  # back to the player
        if actor.alive:
            take_turn(state, actor)
