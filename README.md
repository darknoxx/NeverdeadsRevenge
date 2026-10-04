# Neverdead's Revenge

A terminal roguelite. You are **Noxx** — fast, fragile, and lethal in the right hands.

Built with [Textual](https://textual.textualize.io/).

## Status

Milestone 1 — vertical slice. Playable from the title screen to either ending: a
death, or an escape.

**The goal is to get out.** The dungeon is ten floors deep, and the tenth holds a
rift instead of stairs. Step into it and the run is won; die before that and the
run is over. Both endings show the same summary screen.

Enemy count scales with depth (`6 + depth`). Monster health and damage scale too
— 15% per floor, capped at twice floor 1 from floor 8 — and wraiths get more
common the deeper you go. Nothing in the dungeon ever acts faster than Noxx, so
his crit chance and his REVENGE speed stacking keep paying off all the way down.
The legend in the sidebar quotes the current floor's numbers, so it follows you
down.

Noxx cannot heal on his own; potions and elixirs on the floor are the only way
back up. A run's health is therefore a budget you spend across ten floors, and
skipping loot to save time is a real trade.

Measured with a greedy bot over 30 seeds (attack what is adjacent, drink when
hurt, detour for nearby loot, otherwise beeline for the exit): mean depth 7.0,
and it escapes 3 times in 30.

## Install

```bash
python3 -m venv .venv
./.venv/bin/pip install -e ".[dev]"
```

## Run

```bash
./ndr
```

or, without the launcher:

```bash
./.venv/bin/python -m neverdeads_revenge
```

## Test

```bash
./.venv/bin/pytest
```

## Controls

| Key | Action |
| --- | --- |
| `w` `a` `s` `d` / `h` `j` `k` `l` / arrows | Move (walk into an enemy to attack) |
| `.` or `space` | Wait a turn |
| `g` | Pick up what is under you |
| `q` | Drink a potion |
| `i` | Show what you are carrying |
| `>` | Take the stairs / step into the rift, from anywhere on the floor |
| `enter` / `return` | Same, while standing on them |
| `?` | Controls and the terrain reference |
| `Esc` | Menu, `q` there to quit to title |

## Not implemented yet

A talent tree, equipment, sound, saving mid-run, and the meta-progression the
persistence layer is shaped for (`META_UPGRADES` is still an empty dict, and
`state._apply_upgrades` is a no-op). There is no second hero yet.

The prologue text is German while the rest of the game's text is English. That is
a genuine inconsistency and needs a decision.

## Layout

```
src/neverdeads_revenge/
├── core/     seeded rng, directions, energy-based turn queue
├── world/    tiles, dungeon map, generator, field of view
├── game/     actors, combat, game state, actions
└── ui/       Textual app, screens, widgets
```

The one rule: `core/`, `world/` and `game/` never import `textual`.
Game logic is headless and deterministic; the UI only renders it. That keeps the
logic testable without a terminal and makes a headless simulator possible later.
