# Neverdead's Revenge

A terminal roguelite. You are **Noxx** — fast, fragile, and lethal in the right hands.

Built with [Textual](https://textual.textualize.io/).

## Status

Milestone 1 — vertical slice. Playable from the title screen down to the death screen.

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
| `>` or walk onto stairs | Descend |
| `i` | Inventory |
| `?` | Help |
| `Esc` | Menu / quit |

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
