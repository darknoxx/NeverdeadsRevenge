# Neverdead's Revenge

A terminal roguelite. Three heroes, ten floors, and one way out.

Built with [Textual](https://textual.textualize.io/).

## The heroes

| | | | REVENGE grants |
| --- | --- | --- | --- |
| **N** | Noxx | Fast, fragile, lethal. Dodges what it cannot survive, and acts more often than anything in the dungeon. | +0.3 speed per kill |
| **Y** | Yeti | Slow and armoured. The only hero who does not get to pick his fights, and the only one who can stand in a corridor and let three things hit him. | +1 armour per kill |
| **W** | Walkyrion | The middle of the other two, with accuracy as his one edge: he misses least. | +2 damage per kill |

Heroes take the capital of their name; monsters stay lowercase. A letter on the
map tells you which side of the fight it is on before you have read the legend.

**REVENGE** is the game's own name and is the same mechanic for everyone: every
kill makes you more of what you already are. What it *grants* is the hero's.
Each trait caps where it has roughly doubled that hero's speciality — five
stacks of speed, three of armour, four of damage — because `+0.3 speed` and
`+1 armour` are not the same amount of game, and a single shared cap either
strangles one trait or lets another run away with the run.

## Status

Milestone 1 — vertical slice. Playable from the title screen to either ending: a
death, or an escape.

**The goal is to get out.** The dungeon is ten floors deep, and the tenth holds a
rift instead of stairs. Step into it and the run is won; die before that and the
run is over. Both endings show the same summary screen.

Enemy count scales with depth (`6 + depth`). Monster health and damage scale too
— 15% per floor, capped at twice floor 1 from floor 8 — and wraiths get more
common the deeper you go. The legend in the sidebar quotes the current floor's
numbers, so it follows you down.

No hero can heal on their own; potions and elixirs on the floor are the only way
back up. A run's health is therefore a budget you spend across ten floors, and
skipping loot to save time is a real trade.

Measured with a greedy bot over 30 seeds each (attack what is adjacent, drink
when hurt, detour for nearby loot, otherwise beeline for the exit):

| hero | escapes | mean depth |
| --- | --- | --- |
| Noxx | 3/30 | 7.0 |
| Yeti | 7/30 | 8.7 |
| Walkyrion | 8/30 | 7.9 |

The bot plays "always trade" and cannot kite, so it underrates Noxx and flatters
the armoured heroes. It is a rough instrument, not a verdict.

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
| `enter` | Interact: pick up what you are standing on, or take the stairs |
| `>` | Descend, when you already know that is what you want |
| `q` | Drink a potion |
| `i` | Show what you are carrying |
| `?` | Controls and the terrain reference |
| `Esc` | Menu, `q` there to quit to title |

## Not implemented yet

A talent tree, equipment, sound, saving mid-run, and the meta-progression the
persistence layer is shaped for (`META_UPGRADES` is still an empty dict, and
`state._apply_upgrades` is a no-op). Two roster slots are shown locked and are
not playable yet.

The prologue is the only prose in the game, and it is shown once per session
rather than once per run — told every run it stops being a premise and becomes a
toll.

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
