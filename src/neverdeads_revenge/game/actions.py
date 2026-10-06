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

from neverdeads_revenge.core.direction import (
    DIRECTIONS,
    Direction,
    chebyshev,
    direction_towards,
)
from neverdeads_revenge.world.items import make_coin
from neverdeads_revenge.world.map import GroundItem
from neverdeads_revenge.world.tiles import Tile

from .actors import Actor, make_enemy, pick_enemy_template
from .combat import apply_revenge, attack
from .curses import curse_by_key
from .levels import apply_gain, gains_between, level_for
from .state import GameState, LogKind, RunState

__all__ = [
    "Action",
    "ActionResult",
    "perform_action",
    "take_turn",
    "advance_world",
    "descend",
    "REVENGE_MAX_STACKS",
    "MAX_ENEMY_ACTIONS_PER_PLAYER_TURN",
]


#: What the last ember puts back on a kill.
EMBER_HEAL = 2

#: What the mirror gives back to whatever struck you. Straight, not through
#: armour -- see :meth:`~neverdeads_revenge.game.actors.Stats.reflect`.
MIRROR_REFLECTION = 2

#: Every how many kills the count's favour heals you whole.
COUNTS_FAVOUR_EVERY = 13

#: What the second mouth can hold on the first floor, plus one for every floor
#: below it.
#:
#: It was a flat four. A flat four is reached by the second draught on floor
#: three and then does nothing at all for the rest of the run -- and armour is a
#: flat subtraction, so what it is worth depends entirely on what is hitting
#: you. The cap has to move with the depth, the same way the monsters do, or the
#: amulet is a floor-three trinket wearing a strong-tier price.
SECOND_MOUTH_BASE = 3


def second_mouth_cap(depth: int) -> int:
    """The most armour the second mouth will hold on ``depth``."""
    return SECOND_MOUTH_BASE + max(0, depth)


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
    #: Open the chest underfoot. Never bound to a key: it only happens after the
    #: player has been shown the price and said yes, so the dialog is the only
    #: thing that issues it.
    OPEN_CHEST = "open_chest"
    #: Wash a curse off in the spring. Like OPEN_CHEST, never bound to a key:
    #: it only happens after the player has been shown the price and said yes.
    CLEANSE = "cleanse"
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
    #: Set when the player has to decide something before the action can happen.
    #:
    #: The domain never draws a dialog. It says one is needed, and the UI asks --
    #: which is what keeps the whole decision tree testable without a terminal.
    prompt: str | None = None
    #: Set when the thing underfoot is the spring rather than a chest. The two
    #: need different dialogs and different answers, and a string cannot say
    #: which one it is.
    spring: bool = False


# -- helpers ---------------------------------------------------------------


def _the(name: str) -> str:
    """``the`` before a name that needs one, and not before one that has it.

    Half the equipment is called "the something" -- every amulet is, and the
    strongest blades are -- and "You start with the the patient knife" is the
    sort of thing that makes a whole screen look unfinished.
    """
    return name if name.startswith("the ") else f"the {name}"


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
    _drop_coins(state, enemy)
    _learn(state)

    player = state.player

    heal = (EMBER_HEAL if state.has_passive("ember") else 0) + state.kill_heal
    if heal:
        healed = player.stats.heal(heal)
        if healed:
            state.say(f"The kill feeds you: {healed} back.", LogKind.GOOD)

    if state.has_wild("counts_favour") and state.kills % COUNTS_FAVOUR_EVERY == 0:
        player.stats.hp = player.stats.max_hp
        state.say(
            f"The count is satisfied at {state.kills}. You are whole again.",
            LogKind.GOOD,
        )

    if state.has_passive("borrowed_face"):
        # One turn of nobody being able to land on you. The world counts it down,
        # and the monsters that answer this very kill are the ones it covers.
        state.shrouded = 1

    before = state.revenge_stacks
    gain = 1 + (1 if state.has_passive("long_hunger") else 0)
    state.revenge_stacks = apply_revenge(player, before + gain)
    if state.revenge_stacks > before:
        # Say what it actually granted, not what it granted back when the game
        # had one hero. "REVENGE 3: +3 armour" is the whole point of the trait
        # belonging to the hero.
        state.say(
            f"REVENGE {state.revenge_stacks}: "
            f"{player.trait.describe(state.revenge_stacks)}.",
            LogKind.GOOD,
        )


def _learn(state: GameState) -> None:
    """Fold whatever the last kill taught into the hero.

    Asked after every kill and almost always a no-op. The level is derived from
    the kill count rather than counted up, so this is a comparison and not a
    counter that could drift out of step with the thing it counts.
    """
    reached = level_for(state.kills)
    if reached <= state.level:
        return

    gain = gains_between(state.level, reached)
    state.level = reached
    apply_gain(state.player, gain)
    state.say(f"Level {reached}: {gain.describe()}.", LogKind.GOOD)


def _drop_coins(state: GameState, enemy: Actor) -> None:
    """Leave what the monster was carrying where it fell.

    A pile rather than a number added straight to the purse: gold you have to
    walk over is gold you can decide to leave, and deciding is the point. It
    also puts the two clocks in the game against each other -- the score wants
    you gone quickly, the coins want you to take one more step.
    """
    low, high = enemy.gold
    if high <= 0:
        return

    value = max(1, round(state.rng.between(low, high) * state.coin_factor))
    existing = state.dungeon_map.item_at(enemy.position)
    if existing is not None and existing.kind == "coin":
        # Two kills in the same corner should be one bigger pile, not one pile
        # and a silently overwritten one.
        existing.gold += value
        return
    if existing is not None:
        return  # something else is lying there; the coins are lost to it

    state.dungeon_map.add_item(enemy.position, make_coin(value))


def _player_takes_damage(state: GameState, enemy: Actor, outcome) -> None:
    if outcome.hit:
        state.say(
            f"The {enemy.name} {outcome.verb} you for {outcome.damage}.",
            LogKind.BAD if outcome.killed else LogKind.DAMAGE,
        )
    else:
        state.say(f"The {enemy.name} attacks and misses you.", LogKind.PLAIN)
    if outcome.killed:
        state.die(f"You are slain by the {enemy.name}.")

    # The deathwatch turns on the moment the wound lands, so it is recomputed
    # before the next thing in the queue swings.
    state.refresh_passives()


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

    state.refresh_passives()

    match action:
        case Action.INTERACT:
            return _interact(state)
        case Action.PICK_UP:
            return _pick_up(state)
        case Action.OPEN_CHEST:
            return _open_chest(state)
        case Action.CLEANSE:
            return _cleanse(state)
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
    _bleed(state)
    return True


def _bleed(state: GameState) -> None:
    """Lose a point of blood every so many steps, if cursed to.

    Cadenced on the run's step count rather than a counter of its own, so the
    drip is even across floors and a descent does not reset it.

    It can kill. A curse the player chose should be able to finish them, or it
    is not a price -- and the message says plainly what happened.
    """
    every = state.bleed_every
    if not every or state.player.steps % every:
        return
    if not state.player.alive:
        return

    state.player.stats.hp = max(0, state.player.stats.hp - 1)
    if state.player.hp <= 0:
        state.die("You bleed out between one step and the next.")
        return
    state.say("You are bleeding.", LogKind.DAMAGE)


def _resolve_player_attack(state: GameState, target: Actor) -> None:
    # The patient knife only makes the *first* blow count double, so something
    # has to remember whether there has been one. The flag is cleared on every
    # descent, with the monsters it belonged to.
    first = not target.struck
    outcome = attack(
        state.player,
        target,
        state.rng,
        force_crit=first and state.has_passive("patient_knife"),
    )
    target.struck = True

    if not outcome.hit:
        state.say(f"You swing at the {target.name} and miss.", LogKind.PLAIN)
        return

    if outcome.crit and state.has_passive("patient_knife") and first:
        state.say("It has been waiting for this one.", LogKind.GOOD)

    _enemy_takes_damage(state, target, outcome)
    if outcome.killed:
        _remove_corpse(state, target)
        return

    if state.has_passive("dead_weight"):
        _knock_back(state, target)


def _knock_back(state: GameState, target: Actor) -> None:
    """Throw ``target`` one square further away, if there is anywhere to go.

    The one amulet that trades a stat for a rule, and the rule has to be worth the
    trade. It is not free damage -- it is a turn the monster spends walking back,
    which is the thing a slow hero needs more than anything.
    """
    away = direction_towards(state.player.position, target.position)
    landing = away.step(target.position)
    if not state.dungeon_map.is_walkable(landing):
        return
    if state.actor_at(landing) is not None:
        return
    target.position = landing
    state.say(f"The weight of it throws the {target.name} back.", LogKind.GOOD)


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
        item = state.dungeon_map.item_at(state.player.position)
        assert item is not None
        if item.kind == "chest":
            # Not a refusal and not an action: the player has been asked to
            # decide, and the domain does not decide for them.
            return ActionResult(consumed_turn=False, acted=False, prompt=chest_prompt(item))
        return _pick_up(state)

    if state.at_the_spring:
        return _spring(state)

    if state.on_exit:
        return _try_descend(state)

    state.say("There is nothing here.", LogKind.PLAIN)
    return ActionResult(consumed_turn=False, acted=False)


def chest_prompt(chest: GroundItem) -> str:
    """What the dialog says about a chest: the price, and nothing else.

    The reward stays hidden until the lid is up. Showing both would turn daring
    into arithmetic -- and the player is meant to be weighing a cost against a
    hope, not comparing two numbers.
    """
    curse = curse_by_key(chest.curse)
    if curse is None:
        return "Whatever is inside is not free."
    return f"The price: {curse.price}."


def spring_prompt(state: GameState) -> str:
    """What the spring says before it costs anything.

    Which curse comes off is the water's decision, not the player's, so the
    dialog says so -- and when there is only one curse there is nothing random
    about it, so it names it.
    """
    if len(state.curses) == 1:
        return (
            f"The water will take {state.curses[0].name} off you, "
            f"for {state.cleanse_cost} coins."
        )
    return (
        "The water will take one of your curses, whichever it chooses, "
        f"for {state.cleanse_cost} coins."
    )


def _spring(state: GameState) -> ActionResult:
    """Standing in the spring. Ask before it costs anything.

    Three answers and all three are said plainly: nothing to wash off, not
    enough coin, or the question. The middle one is stated rather than offered
    and then refused, because a dialog that ends in "you cannot afford this" is
    a dialog that wasted the player's time.
    """
    if not state.curses:
        state.say(
            "The water is clear and cold. There is nothing on you to wash off.",
            LogKind.PLAIN,
        )
        return ActionResult(consumed_turn=False, acted=False)

    if state.gold < state.cleanse_cost:
        state.say(
            f"The water would take a curse off you, for {state.cleanse_cost} "
            f"coins, and you have {state.gold}.",
            LogKind.PLAIN,
        )
        return ActionResult(consumed_turn=False, acted=False)

    return ActionResult(
        consumed_turn=False,
        acted=False,
        prompt=spring_prompt(state),
        spring=True,
    )


def _cleanse(state: GameState) -> ActionResult:
    """Wash one curse off, chosen by the water.

    Only ever reached from the dialog, so there is no key that spends forty
    coins by accident. Costs no turn: being clean should not be something the
    monsters get to answer.
    """
    if not state.at_the_spring or not state.curses:
        return ActionResult(consumed_turn=False, acted=False)
    if state.gold < state.cleanse_cost:
        return ActionResult(consumed_turn=False, acted=False)

    curse = state.rng.pick(state.curses)
    state.gold -= state.cleanse_cost
    state.remove_curse(curse)

    # Spent. One wash per spring, so a curse becomes a decision about which
    # spring to spend rather than a standing offer you can walk back to -- and
    # the tile goes back to plain floor, which is what the map should show and
    # what makes ``enter`` on it say "there is nothing here" like anywhere else.
    state.dungeon_map.set_tile(state.player.position, Tile.FLOOR)

    state.say(
        f"The water closes over {curse.name} and takes it with it.",
        LogKind.GOOD,
    )
    state.say("The spring is spent, and the water goes still.", LogKind.PLAIN)
    return ActionResult(consumed_turn=False, acted=False)


def _open_chest(state: GameState) -> ActionResult:
    """Prise open the chest underfoot: the reward, and the bill.

    Only ever reached from the dialog, so there is no key that opens a chest by
    accident -- walking onto one and pressing enter asks first.
    """
    chest = state.dungeon_map.item_at(state.player.position)
    if chest is None or chest.kind != "chest":
        return ActionResult(consumed_turn=False, acted=False)

    state.dungeon_map.remove_item(state.player.position)
    state.say("The lid gives, and something in the dark takes note.", LogKind.SYSTEM)

    curse = curse_by_key(chest.curse)
    if curse is not None:
        state.add_curse(curse)

    if chest.contents is not None:
        _equip(state, chest.contents)

    return ActionResult(consumed_turn=False, acted=False)


def _pick_up(state: GameState) -> ActionResult:
    item = state.dungeon_map.item_at(state.player.position)
    if item is None:
        state.say("There is nothing here to take.", LogKind.PLAIN)
        return ActionResult(consumed_turn=False, acted=False)

    if item.kind == "chest":
        # It is furniture, not loot. Without this the whole chest -- contents
        # and all -- went into the pack, and the curse went with it unread.
        state.say("It is not going anywhere. It has to be opened.", LogKind.PLAIN)
        return ActionResult(consumed_turn=False, acted=False)

    state.dungeon_map.remove_item(state.player.position)

    if item.kind == "coin":
        state.gold += item.gold
        state.say(f"You pocket {item.gold} coins.", LogKind.GOOD)
        return ActionResult(consumed_turn=False, acted=False)

    if item.slot:
        _equip(state, item)
    else:
        state.inventory.append(item)
        state.say(f"You pick up {_the(item.name)}.", LogKind.GOOD)
    return ActionResult(consumed_turn=False, acted=False)


def _set_down(state: GameState, item: GroundItem) -> bool:
    """Lay ``item`` on a free tile beside the player. Returns whether it fitted.

    Beside, not under. An item beneath your feet is one you pick up again the
    next time you press enter, which turns swapping equipment into a loop that
    never lets ``enter`` reach the stairs -- and it is also the square the
    player has to stand on to leave. Swapping stays reversible, it just costs a
    step: walk onto what you set down and take it back.
    """
    for direction in DIRECTIONS:
        pos = direction.step(state.player.position)
        if not state.dungeon_map.is_walkable(pos):
            continue
        if state.actor_at(pos) is not None:
            continue
        if state.dungeon_map.item_at(pos) is not None:
            continue
        state.dungeon_map.add_item(pos, item)
        return True
    return False


def _equip(state: GameState, item: GroundItem) -> None:
    """Wear ``item``, setting whatever it replaces down beside the player.

    Setting down rather than discarding is what makes trying something on free:
    what you took off is still on the floor, so nothing a player finds can be
    lost by picking it up. That is the only reason auto-equipping is safe --
    there is no comparison dialog, so there has to be an undo.
    """
    player = state.player
    previous = player.equipment.get(item.slot)
    player.equipment[item.slot] = item

    changes = ", ".join(item.modifiers.describe())
    detail = f" ({changes})" if changes else ""

    if previous is None:
        state.say(f"You take up {_the(item.name)}{detail}.", LogKind.GOOD)
        return

    if _set_down(state, previous):
        state.say(
            f"You take up {_the(item.name)}{detail} and set down "
            f"{_the(previous.name)}.",
            LogKind.GOOD,
        )
        return

    # Boxed in on every side. Rare, and the item is not thrown away for it.
    state.dungeon_map.add_item(player.position, previous)
    state.say(
        f"You take up {_the(item.name)}{detail}; {_the(previous.name)} falls at "
        f"your feet.",
        LogKind.GOOD,
    )


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
    if state.draughts_forbidden:
        state.say(
            "Your mouth is closed to it. Nothing you drink stays down.",
            LogKind.BAD,
        )
        return ActionResult(consumed_turn=False, acted=False)

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
    amount = max(1, round(item.heal * state.heal_scale))
    healed = player.stats.heal(amount)
    state.say(f"You drink the {item.name} and recover {healed}.", LogKind.GOOD)
    if amount < item.heal:
        state.say(
            f"It should have been more. The curse takes its share.",
            LogKind.BAD,
        )
    elif healed < amount:
        spare = amount - healed
        if state.has_passive("second_mouth"):
            # Armour for this floor only. Carrying it down would make one drink
            # on floor two worth something on floor nine.
            cap = second_mouth_cap(state.depth)
            kept = min(cap, player.stored_armor + spare) - player.stored_armor
            player.stored_armor += kept
            if kept:
                state.say(
                    f"The second mouth keeps what spills: {kept} armour.",
                    LogKind.GOOD,
                )
        else:
            state.say(
                f"Its power spills past the wound; {spare} is lost.",
                LogKind.PLAIN,
            )

    if state.has_wild("mirror_of_hunger"):
        _wake_something(state)

    # Drinking takes a turn, so it is not a free action in the middle of a fight
    # and monsters get their answer.
    state.turn += 1
    state.total_turns += 1
    advance_world(state)
    state.refresh_vision()
    return _outcome(state, consumed_turn=True, acted=True)


def _wake_something(state: GameState) -> None:
    """Put a monster beside the player, if there is anywhere to put one.

    The mirror of hunger. It does not appear on the far side of the floor and
    walk over -- it is already there, and it was waiting for you to be thirsty.
    """
    spots = [
        direction.step(state.player.position)
        for direction in DIRECTIONS
    ]
    free = [
        pos
        for pos in spots
        if state.dungeon_map.is_walkable(pos) and state.actor_at(pos) is None
    ]
    if not free:
        return

    enemy = make_enemy(
        pick_enemy_template(state.rng, state.depth), state.rng.pick(free)
    )
    state.enemies.append(enemy)
    state.turn_queue.add(enemy)
    state.say("Something drinks with you, and it was already here.", LogKind.BAD)


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

    if state.toll_per_floor:
        # After the descent, so it reads as the price of the floor rather than
        # as something that happened on the last one. It can empty the purse but
        # not go below it: a debt the run cannot pay is not a toll.
        paid = min(state.toll_per_floor, state.gold)
        state.gold -= paid
        state.say(f"The dark takes its toll: {paid} coins.", LogKind.BAD)

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
    if state.shrouded and state.has_passive("borrowed_face"):
        state.say(
            f"The {attacker.name} strikes at where you were, and finds nothing.",
            LogKind.PLAIN,
        )
        return

    warded = state.ward_ready and state.has_passive("grave_ward")
    outcome = attack(attacker, player, state.rng, damage_scale=0.5 if warded else 1.0)

    _player_takes_damage(state, attacker, outcome)

    if warded and outcome.hit:
        # Spent by a blow that landed, not by a swing. "The first blow of each
        # floor" is what the amulet says, and a swing that missed was not one.
        state.ward_ready = False
        state.say("The ward takes half of it, and is spent.", LogKind.GOOD)

    if outcome.hit and state.has_passive("mirror"):
        # Whatever struck you wears it. Two points is small against a deep-floor
        # monster and is not meant to be the answer -- it is meant to make a
        # crowd of small things into a decision.
        back = attacker.stats.reflect(MIRROR_REFLECTION)
        if back:
            state.say(f"The mirror gives {back} of it back.", LogKind.GOOD)
        if not attacker.stats.alive:
            state.say(f"The {attacker.name} comes apart on its own blow.", LogKind.GOOD)
            _remove_corpse(state, attacker)


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
    state.refresh_passives()
    for _ in range(MAX_ENEMY_ACTIONS_PER_PLAYER_TURN):
        if state.over:
            break
        actor = state.turn_queue.pop()
        if actor is None:
            break
        if actor.is_player:
            break  # back to the player
        if actor.alive:
            take_turn(state, actor)

    # Counted down here rather than once per turn, so the borrowed face covers
    # exactly the monsters that answer the kill and not the ones after them.
    if state.shrouded:
        state.shrouded -= 1
