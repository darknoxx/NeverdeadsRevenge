# Neverdead's Revenge

A terminal roguelite. You are **Noxx** — fast, fragile, and lethal in the right hands.

Built with [Textual](https://textual.textualize.io/).

## Status

Milestone 1 — vertical slice. Playable from the title screen down to the death
screen, with a prologue, a legend and a message log.

Enemy count scales with depth (`6 + depth`). Monster health and damage scale
too — 15% per floor, capped at twice floor 1 from floor 8 — and wraiths get more
common the deeper you go. Nothing in the dungeon ever acts faster than Noxx. The
legend in the sidebar quotes the current floor's numbers, so it follows you down.

There is no win condition yet.

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
| `g` | Pick up item |
| `>` | Descend, from anywhere on the floor |
| `enter` / `return` | Descend, while standing on the stairs |
| `?` | Controls |
| `Esc` | Menu, `q` there to quit to title |

## Not implemented yet

Loot, inventory, a talent tree, sound, saving mid-run. The game also has no win
condition yet: there is no victory state, and `RunState.ESCAPED` is never set,
so the only way a run ends is death.

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
