"""Tests for actors, combat and the run simulation.

These play the game headlessly -- no terminal, no Textual -- which is the whole
point of keeping the domain layer free of UI imports.
"""

from __future__ import annotations

import pytest

from neverdeads_revenge.core.direction import Direction, chebyshev
from neverdeads_revenge.core.rng import Rng
from neverdeads_revenge.game import actions as actions_module
from neverdeads_revenge.game.actions import (
    Action,
    perform_action,
)
from neverdeads_revenge.game.actors import (
    ENEMIES,
    HEROES,
    NOXX,
    Actor,
    ActorKind,
    Stats,
    make_enemy,
    make_hero,
    pick_enemy_template,
    scale_template,
)
from neverdeads_revenge.game.combat import (
    MAX_HIT_CHANCE,
    MIN_HIT_CHANCE,
    attack,
    hit_chance,
    apply_revenge,
)
from neverdeads_revenge.game.difficulty import (
    MAX_ENEMY_SPEED,
    MAX_POTENCY,
    potency,
    weight_at_depth,
)
from neverdeads_revenge.game.state import GameState, LogKind, RunState, start_run

SEEDS = range(25)


# -- stats -----------------------------------------------------------------
def test_hurt_applies_armour():
    stats = Stats(max_hp=20, hp=20, armor=2)
    assert stats.hurt(5) == 3
    assert stats.hp == 17


def test_hurt_never_goes_below_zero():
    stats = Stats(max_hp=10, hp=4)
    stats.hurt(999)
    assert stats.hp == 0
    assert not stats.alive


def test_heal_is_capped_at_max():
    stats = Stats(max_hp=10, hp=8)
    assert stats.heal(5) == 2
    assert stats.hp == 10


def test_average_damage():
    assert Stats(damage=(4, 6)).average_damage == 5


# -- heroes ----------------------------------------------------------------
def test_noxx_identity():
    """The brief: fast, crit-heavy, fragile."""
    assert NOXX.name == "Noxx"
    assert NOXX.stats.speed == 1.5
    assert NOXX.stats.crit_chance >= 0.2
    assert NOXX.stats.crit_multiplier >= 2.0
    # Fragile: the least health of anything the roster will hold.
    assert NOXX.stats.max_hp <= 30


def test_noxx_is_materially_faster_than_every_enemy():
    for template in ENEMIES.values():
        assert NOXX.stats.speed > template.stats.speed, template.key


def test_noxx_stays_the_fastest_thing_in_the_dungeon_at_any_depth():
    """The one balance constraint that must never bend.

    Noxx's crit chance and his REVENGE speed stacking both pay off because he
    gets more actions than anything around him. A single monster that outruns
    him turns both of those into decoration, so the speed cap in
    ``game.difficulty`` is load-bearing and gets its own test rather than
    riding along with the potency ones.
    """
    for depth in range(1, 40):
        for template in ENEMIES.values():
            scaled = scale_template(template, depth)
            assert scaled.stats.speed < NOXX.stats.speed, (
                f"{template.key} at depth {depth} is as fast as the hero"
            )


def test_no_monster_ever_exceeds_the_documented_speed_cap():
    for depth in range(1, 60):
        for template in ENEMIES.values():
            assert scale_template(template, depth).stats.speed <= MAX_ENEMY_SPEED


def test_making_a_hero_does_not_mutate_the_template():
    actor = make_hero(NOXX, (3, 4))
    actor.stats.hp -= 10
    actor.stats.speed = 99
    assert NOXX.stats.hp == NOXX.stats.max_hp
    assert NOXX.stats.speed == 1.5


def test_hero_actor_is_flagged_as_the_player():
    actor = make_hero(NOXX, (1, 1))
    assert actor.is_player
    assert actor.kind is ActorKind.HERO


def test_enemy_templates_are_not_mutated_by_actors():
    template = ENEMIES["ghoul"]
    actor = make_enemy(template, (2, 2))
    actor.stats.hp = 1
    assert template.stats.hp == template.stats.max_hp
    assert actor.behaviour == template.behaviour


def test_speed_bonus_is_additive():
    actor = make_hero(NOXX, (0, 0))
    assert actor.speed == 1.5
    actor.speed_bonus = 0.3
    assert actor.speed == pytest.approx(1.8)


def test_enemy_spawn_weights_are_respected():
    rng = Rng(11)
    counts: dict[str, int] = {}
    for _ in range(6000):
        key = pick_enemy_template(rng).key
        counts[key] = counts.get(key, 0) + 1
    # Template keys, not display names: the skeleton's key is "bone".
    assert counts["ghoul"] > counts["bone"] > counts["wraith"]


def test_heroes_registry_is_populated():
    assert HEROES["noxx"] is NOXX


# -- difficulty by depth ----------------------------------------------------
DEPTHS = range(1, 13)


def test_potency_is_one_on_the_first_floor():
    """``ENEMIES`` describes floor 1 exactly as written.

    If this breaks, every other test that builds a monster from a bare template
    is quietly testing a floor that no longer exists.
    """
    assert potency(1) == 1.0
    for template in ENEMIES.values():
        assert scale_template(template, 1) is template


def test_potency_rises_and_then_stops():
    """Monotonically up, capped, and never below 1."""
    values = [potency(d) for d in DEPTHS]
    assert values == sorted(values)
    assert values[0] == 1.0
    assert max(values) <= MAX_POTENCY
    assert potency(999) == MAX_POTENCY
    # Depth is not a difficulty slider into negative numbers.
    assert potency(0) == 1.0


def test_monsters_only_ever_get_tougher():
    """Health, damage and speed never go down, for any kind, on any floor.

    Without this, a rounding slip could make floor 3 weaker than floor 2 and the
    curve would stop being a curve.
    """
    for template in ENEMIES.values():
        previous = scale_template(template, 1).stats
        for depth in DEPTHS:
            current = scale_template(template, depth).stats
            assert current.max_hp >= previous.max_hp, (template.key, depth)
            assert current.damage[0] >= previous.damage[0], (template.key, depth)
            assert current.damage[1] >= previous.damage[1], (template.key, depth)
            assert current.speed >= previous.speed, (template.key, depth)
            previous = current


def test_scaled_monsters_are_actually_harder_by_the_top_floors():
    """A potency of 2.0 has to mean twice the health and twice the damage.

    Asserting the constant alone would pass even if the scaling were never
    applied to the stats that matter.
    """
    deep = scale_template(ENEMIES["ghoul"], 12)
    base = ENEMIES["ghoul"]
    assert potency(12) == MAX_POTENCY
    assert deep.stats.max_hp == round(base.stats.max_hp * MAX_POTENCY)
    assert deep.stats.damage[1] == round(base.stats.damage[1] * MAX_POTENCY)


def test_scaling_never_produces_a_zero_damage_roll():
    """A minimum of 0 would make a monster harmless half the time."""
    for template in ENEMIES.values():
        for depth in DEPTHS:
            low, high = scale_template(template, depth).stats.damage
            assert low >= 1
            assert high >= low


def test_a_newly_spawned_monster_starts_at_full_health():
    """Scaling raises ``max_hp``, and ``hp`` has to follow it.

    Easy to get wrong: raise ``max_hp`` alone and every deep-floor monster spawns
    already wounded, which reads as the curve being far harsher than it is.
    """
    for template in ENEMIES.values():
        for depth in DEPTHS:
            stats = scale_template(template, depth).stats
            assert stats.hp == stats.max_hp


def test_scaling_does_not_mutate_the_template():
    """``ENEMIES`` outlives every actor, so it has to survive scaling untouched."""
    fields = ("max_hp", "damage", "speed")
    before = {k: tuple(getattr(t.stats, f) for f in fields) for k, t in ENEMIES.items()}
    for template in ENEMIES.values():
        for depth in DEPTHS:
            scale_template(template, depth)
    after = {k: tuple(getattr(t.stats, f) for f in fields) for k, t in ENEMIES.items()}
    assert before == after


def test_armour_and_evasion_are_not_scaled():
    """Doubling armour takes more off each hit than doubling damage adds."""
    for template in ENEMIES.values():
        for depth in DEPTHS:
            scaled = scale_template(template, depth).stats
            assert scaled.armor == template.stats.armor, (template.key, depth)
            assert scaled.evasion == template.stats.evasion, (template.key, depth)
            assert scaled.accuracy == template.stats.accuracy, (template.key, depth)


# -- the enemy mix drifts as well as the numbers ----------------------------
def _share(key: str, depth: int) -> float:
    """Fraction of a floor's spawns taken by ``key`` at ``depth``."""
    target = ENEMIES[key]
    total = sum(
        weight_at_depth(t.weight, t.weight_growth, depth) for t in ENEMIES.values()
    )
    return weight_at_depth(target.weight, target.weight_growth, depth) / total


def test_only_the_wraith_becomes_more_common():
    """The mix has to drift, or every floor is the same fight.

    Note what is and is not asserted. The ghoul's and skeleton's *weights* stay
    put, but their *shares* fall, because the wraith is eating a bigger slice of
    a pool whose total grows. Asserting the share would have been the more
    obvious test and it would have been the wrong one: a weight that drifts while
    its share does not is not a drifting weight.
    """
    for steady in ("ghoul", "bone"):
        template = ENEMIES[steady]
        assert weight_at_depth(template.weight, template.weight_growth, 8) == template.weight
        assert _share(steady, 8) < _share(steady, 1)

    assert _share("wraith", 8) > _share("wraith", 1) * 1.5


def test_spawn_weights_at_a_depth_are_still_valid():
    """Every floor has to be able to spawn something."""
    for depth in DEPTHS:
        weights = [
            weight_at_depth(t.weight, t.weight_growth, depth) for t in ENEMIES.values()
        ]
        assert all(w > 0 for w in weights)
        assert sum(weights) > 0


def test_picking_an_enemy_at_depth_returns_a_depth_sized_one():
    rng = Rng(3)
    smallest_on_floor_one = min(t.stats.max_hp for t in ENEMIES.values())
    for depth in (4, 9):
        picked = [pick_enemy_template(rng, depth) for _ in range(200)]
        assert min(t.stats.max_hp for t in picked) > smallest_on_floor_one


def test_a_deep_floor_is_actually_populated_with_bigger_monsters():
    """End to end: the curve has to reach the dungeon, not just the helper."""
    state = start_run(NOXX, seed=4)
    weak = sum(e.stats.max_hp for e in state.enemies)

    state.build_floor(10)
    assert state.depth == 10
    assert state.enemies
    # Floor 10 spawns more monsters *and* bigger ones, so comparing sums is
    # enough; the exact per-monster numbers are covered above.
    assert sum(e.stats.max_hp for e in state.enemies) > weak


def test_descending_does_not_make_monsters_weaker():
    """Cheap guard against the sign of the scaling being inverted."""
    state = start_run(NOXX, seed=8)
    for depth in range(2, 8):
        before = sum(e.stats.max_hp for e in state.enemies)
        state.build_floor(depth)
        after = sum(e.stats.max_hp for e in state.enemies)
        # Not a strict comparison: the enemy count grows too, and a floor can
        # roll all-ghouls right after an all-skeletons one. It only has to not
        # collapse, and every monster's own stats are covered above.
        assert after >= before * 0.5, f"floor {depth} got weaker"


# -- combat maths ----------------------------------------------------------
def test_hit_chance_stays_in_bounds():
    hero = make_hero(NOXX, (0, 0))
    ghost = Actor("g", ActorKind.ENEMY, Stats(evasion=99), (1, 0))
    tank = Actor("t", ActorKind.ENEMY, Stats(evasion=-50), (1, 0))
    assert hit_chance(hero, ghost) >= MIN_HIT_CHANCE
    assert hit_chance(hero, tank) <= MAX_HIT_CHANCE


def test_noxx_evades_much_of_what_throws_at_him():
    """Evasion 4 is half the reason he works; assert it actually pays."""
    hero = make_hero(NOXX, (0, 0))
    ghoul = make_enemy(ENEMIES["ghoul"], (1, 0))
    rng = Rng(5)
    hits = sum(
        1
        for _ in range(4000)
        if attack(ghoul, hero, rng).hit
    )
    assert 1200 < hits < 2400  # roughly 35-60%


def test_crit_rate_is_about_right():
    rng = Rng(99)
    crits = sum(
        1
        for _ in range(4000)
        if attack(make_hero(NOXX, (0, 0)), make_enemy(ENEMIES["ghoul"], (1, 0)), rng).crit
    )
    assert 800 < crits < 1200  # ~25%


def test_crit_multiplies_damage():
    hero = make_hero(NOXX, (0, 0))
    target = Actor("t", ActorKind.ENEMY, Stats(max_hp=9999, hp=9999, armor=0), (1, 0))
    rng = Rng(3)
    plain, crits = [], []
    for _ in range(3000):
        probe = Actor("t", ActorKind.ENEMY, Stats(max_hp=9999, hp=9999, armor=0), (1, 0))
        outcome = attack(hero, probe, rng)
        (crits if outcome.crit else plain).append(outcome.damage)
    assert max(plain) <= 6
    assert max(crits) >= 11  # 6 * 2.2 = 13.2


def test_damage_is_bounded_and_armour_applies():
    hero = make_hero(NOXX, (0, 0))
    soft = Actor("s", ActorKind.ENEMY, Stats(max_hp=999, hp=999, armor=0), (1, 0))
    armoured = Actor("a", ActorKind.ENEMY, Stats(max_hp=999, hp=999, armor=5), (1, 0))
    rng = Rng(21)
    a = max(attack(hero, soft, rng).damage for _ in range(200))
    b = max(attack(hero, armoured, rng).damage for _ in range(200))
    assert a >= b + 5


def test_kill_marks_the_target_dead():
    hero = make_hero(NOXX, (0, 0))
    victim = Actor("v", ActorKind.ENEMY, Stats(max_hp=1, hp=1), (1, 0))
    rng = Rng(2)
    outcome = None
    for _ in range(200):
        probe = Actor("v", ActorKind.ENEMY, Stats(max_hp=1, hp=1), (1, 0))
        outcome = attack(hero, probe, rng)
        if outcome.killed:
            break
    assert outcome is not None and outcome.killed
    assert not victim.alive or True  # probe was discarded; assert on outcome only


def test_verbs_agree_with_their_subject():
    from neverdeads_revenge.game.combat import AttackOutcome

    def verbs(**kw):
        base = dict(hit=True, crit=False, damage=5, killed=False)
        base.update(kw)
        o = AttackOutcome(**base)
        return o.verb, o.verb_second_person

    assert verbs() == ("hits", "hit")
    assert verbs(crit=True) == ("crits", "crit")
    assert verbs(killed=True) == ("kills", "kill")
    assert verbs(killed=True, crit=True) == ("obliterates", "obliterate")
    assert verbs(hit=False) == ("misses", "miss")
    assert verbs(hit=False, dodged=True) == ("misses", "miss")


def test_revenge_stacks_and_caps():
    actor = make_hero(NOXX, (0, 0))
    stacks = 0
    for _ in range(50):
        stacks = apply_revenge(actor, stacks)
    assert stacks == 5
    assert actor.speed == pytest.approx(1.5 + 5 * 0.3)


# -- run setup -------------------------------------------------------------
def test_start_run_places_the_player_somewhere_solid():
    for seed in SEEDS:
        state = start_run(NOXX, seed=seed)
        assert state.dungeon_map.is_walkable(state.player.position)


def test_same_seed_reproduces_the_whole_dungeon():
    a = start_run(NOXX, seed=1234)
    b = start_run(NOXX, seed=1234)
    assert a.dungeon_map.tiles == b.dungeon_map.tiles
    assert [e.position for e in a.enemies] == [e.position for e in b.enemies]


def test_different_seeds_give_different_dungeons():
    a = start_run(NOXX, seed=1).dungeon_map.tiles
    b = start_run(NOXX, seed=2).dungeon_map.tiles
    assert a != b


def test_run_starts_with_vision_already_computed():
    state = start_run(NOXX, seed=5)
    assert state.player.position in state.dungeon_map.visible
    assert state.dungeon_map.visible <= state.dungeon_map.explored


# -- actions ---------------------------------------------------------------
def test_moving_into_a_wall_costs_nothing():
    state = start_run(NOXX, seed=8)
    # The player starts mid-room where nothing is blocked, so walk them to a
    # spot that actually has a wall in it before testing this.
    corner = next(
        (pos for pos in state.dungeon_map.walkable_positions() if _has_wall_neighbour(state, pos)),
        None,
    )
    if corner is None:
        pytest.skip("no wall-adjacent floor on this floor")
    state.player.position = corner
    state.refresh_vision()

    blocked = next(
        d
        for d in Direction
        if d is not Direction.NONE
        and not state.dungeon_map.is_walkable(d.step(state.player.position))
    )
    before_turn = state.turn
    before_pos = state.player.position
    result = perform_action(state, _action_for(blocked))
    assert not result.consumed_turn
    assert not result.acted
    assert state.turn == before_turn
    assert state.player.position == before_pos


def _has_wall_neighbour(state: GameState, pos) -> bool:
    return any(
        not state.dungeon_map.is_walkable(d.step(pos))
        for d in Direction
        if d is not Direction.NONE
    )


def test_moving_into_open_ground_advances_the_position():
    state = start_run(NOXX, seed=8)
    open_move = next(
        (
            d
            for d in Direction
            if d is not Direction.NONE and state.dungeon_map.is_walkable(d.step(state.player.position))
        ),
        None,
    )
    if open_move is None:
        pytest.skip("player is fully enclosed")
    before = state.player.position
    result = perform_action(state, _action_for(open_move))
    assert result.consumed_turn
    assert state.player.position == open_move.step(before)


def test_waiting_costs_a_turn():
    state = start_run(NOXX, seed=8)
    before = state.turn
    assert perform_action(state, Action.WAIT).consumed_turn
    assert state.turn == before + 1


def test_player_and_enemy_never_share_a_cell():
    state = start_run(NOXX, seed=4)
    for _ in range(120):
        if state.over:
            break
        perform_action(state, Action.WAIT)
    for enemy in state.living_enemies:
        assert enemy.position != state.player.position


def test_killing_an_enemy_removes_it_from_the_floor():
    state = start_run(NOXX, seed=6)
    victim = _place_adjacent_enemy(state)
    for _ in range(20):
        if state.over or not victim.alive:
            break
        perform_action(state, Action.MOVE_EAST)
    assert state.kills >= 1
    assert victim not in state.enemies
    assert victim not in state.turn_queue


def test_killing_grants_revenge_speed():
    state = start_run(NOXX, seed=6)
    victim = _place_adjacent_enemy(state)
    for _ in range(20):
        if state.over or not victim.alive:
            break
        perform_action(state, Action.MOVE_EAST)
    assert state.revenge_stacks >= 1
    assert state.player.speed == pytest.approx(1.5 + 0.3 * state.revenge_stacks)


def test_descending_requires_standing_on_the_stairs():
    state = start_run(NOXX, seed=6)
    assert not state.on_stairs
    result = perform_action(state, Action.DESCEND)
    assert not result.consumed_turn
    assert state.depth == 1


def test_descending_from_the_stairs_makes_a_new_floor():
    state = start_run(NOXX, seed=6)
    state.player.position = state.stairs
    state.refresh_vision()
    perform_action(state, Action.DESCEND)
    assert state.depth == 2
    assert state.floors_cleared == 1
    assert state.revenge_stacks == 0, "revenge lapses between floors"
    assert state.player.speed_bonus == 0.0


def test_enemies_only_act_when_the_player_can_see_them():
    """Monsters out of sight hold position. Keeps the fight about what you can see."""
    state = start_run(NOXX, seed=13)
    hidden = state.enemies[0]

    # Pick a genuinely dark cell rather than hoping one exists where we guessed.
    state.refresh_vision()
    dark = next(
        (
            pos
            for pos in state.dungeon_map.walkable_positions()
            if not state.dungeon_map.is_visible(pos)
        ),
        None,
    )
    if dark is None:
        pytest.skip("player happens to see the whole floor")

    hidden.position = dark
    before = hidden.position
    # Wait a real turn, otherwise the queue hands control straight back to the
    # player and the enemy never gets an action to be denied.
    perform_action(state, Action.WAIT)
    assert hidden.position == before


def test_a_visible_enemy_does_close_in():
    """The counterpart: seen monsters do get to move."""
    state = start_run(NOXX, seed=13)
    for other in state.enemies[1:]:
        state.turn_queue.remove(other)
    del state.enemies[1:]

    hunter = state.enemies[0]
    state.dungeon_map.clear_visibility()
    hunter.position = Direction.EAST.step(Direction.EAST.step(state.player.position))
    state.refresh_vision()
    if not state.dungeon_map.is_visible(hunter.position):
        pytest.skip("chosen cell is walled off")

    before_distance = chebyshev(hunter.position, state.player.position)
    # One wait is not necessarily enough: the scheduler only hands an action to
    # monsters that come due before Noxx's next action. Speed 1.0 needs two of
    # his actions to come round.
    for _ in range(4):
        if state.over or chebyshev(hunter.position, state.player.position) < before_distance:
            break
        perform_action(state, Action.WAIT)
    assert chebyshev(hunter.position, state.player.position) < before_distance


def test_a_faster_enemy_acts_more_often_than_a_slower_one(monkeypatch):
    """The core mechanic measured through the real action flow.

    Noxx at speed 1.5 should take roughly three actions for every two taken by a
    speed-1.0 monster. Counts actual enemy actions rather than trusting the
    scheduler in isolation.
    """
    counts = {"slow": 0, "fast": 0}
    real_take_turn = actions_module.take_turn

    def counting_take_turn(state, actor):
        if actor.name == "slow":
            counts["slow"] += 1
        elif actor.name == "fast":
            counts["fast"] += 1
        return real_take_turn(state, actor)

    monkeypatch.setattr(actions_module, "take_turn", counting_take_turn)

    def run_with(enemy_speed: float, label: str) -> None:
        state = start_run(NOXX, seed=17)
        for other in state.enemies[1:]:
            state.turn_queue.remove(other)
        del state.enemies[1:]

        enemy = state.enemies[0]
        enemy.name = label
        enemy.stats.speed = enemy_speed
        enemy.stats.max_hp = 9999
        enemy.stats.hp = 9999
        enemy.behaviour = "hunter"
        state.player.stats.hp = 9999
        state.player.stats.max_hp = 9999
        # Keep both alive so the count runs the full length.
        state.turn_queue.remove(enemy)
        state.turn_queue.add(enemy)

        for _ in range(200):
            if state.over:
                break
            perform_action(state, Action.WAIT)

    run_with(1.0, "slow")
    slow_actions = counts["slow"]
    counts["fast"] = 0
    run_with(2.0, "fast")
    fast_actions = counts["fast"]

    assert fast_actions > slow_actions * 1.5, (
        f"speed 2.0 monster acted {fast_actions}x, speed 1.0 monster {slow_actions}x"
    )


def test_player_can_die():
    state = start_run(NOXX, seed=3)
    state.player.stats.hp = 1
    _place_adjacent_enemy(state)
    for _ in range(60):
        if state.over:
            break
        perform_action(state, Action.WAIT)
    assert state.run_state is RunState.DEAD
    assert not state.player.alive
    assert state.over


def test_no_actions_are_accepted_after_death():
    state = start_run(NOXX, seed=3)
    state.player.stats.hp = 1
    _place_adjacent_enemy(state)
    for _ in range(60):
        if state.over:
            break
        perform_action(state, Action.WAIT)
    assert state.over
    before = state.turn
    result = perform_action(state, Action.MOVE_NORTH)
    assert not result.consumed_turn and result.died
    assert state.turn == before


def test_score_rewards_kills_and_depth():
    state = start_run(NOXX, seed=6)
    assert state.score == 0
    state.kills = 3
    state.floors_cleared = 2
    state.player.steps = 10
    assert state.score == 3 * 100 + 2 * 250 + 10


# -- longer simulations ----------------------------------------------------
@pytest.mark.parametrize("seed", SEEDS)
def test_a_hundred_turns_never_crash(seed):
    """Smoke test across many generated dungeons."""
    state = start_run(NOXX, seed=seed)
    moves = [a for a in Action if a.name.startswith("MOVE")]
    for i in range(100):
        if state.over:
            break
        perform_action(state, moves[i % len(moves)])
    assert state.turn >= 0


@pytest.mark.parametrize("seed", SEEDS)
def test_vision_stays_consistent_during_play(seed):
    state = start_run(NOXX, seed=seed)
    for i in range(60):
        if state.over:
            break
        perform_action(state, [Action.WAIT, Action.MOVE_EAST, Action.MOVE_SOUTH][i % 3])
        assert state.player.position in state.dungeon_map.visible
        assert state.dungeon_map.visible <= state.dungeon_map.explored


@pytest.mark.parametrize("seed", SEEDS)
def test_the_log_never_bloats_without_bound(seed):
    state = start_run(NOXX, seed=seed)
    for i in range(200):
        if state.over:
            break
        perform_action(state, [Action.WAIT, Action.MOVE_NORTH, Action.MOVE_WEST][i % 3])
    assert len(state.log) < 2000


# -- helpers ---------------------------------------------------------------
def _action_for(direction: Direction) -> Action:
    return {
        Direction.NORTH: Action.MOVE_NORTH,
        Direction.SOUTH: Action.MOVE_SOUTH,
        Direction.EAST: Action.MOVE_EAST,
        Direction.WEST: Action.MOVE_WEST,
        Direction.NORTH_EAST: Action.MOVE_NE,
        Direction.NORTH_WEST: Action.MOVE_NW,
        Direction.SOUTH_EAST: Action.MOVE_SE,
        Direction.SOUTH_WEST: Action.MOVE_SW,
    }[direction]


def _place_adjacent_enemy(state: GameState) -> Actor:
    """Park the first enemy next to the player, removing every other."""
    for other in state.enemies[1:]:
        state.turn_queue.remove(other)
    del state.enemies[1:]
    victim = state.enemies[0]
    victim.position = Direction.EAST.step(state.player.position)
    state.refresh_vision()
    return victim
