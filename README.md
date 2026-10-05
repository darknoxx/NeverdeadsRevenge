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

Measured with two bots over 24 seeds each, because the choice of bot turned out
to matter more than the hero:

* **trade** — attack whatever is adjacent, always.
* **kite** — break contact and drink when badly hurt.

| hero | trade | kite |
| --- | --- | --- |
| Noxx | 4/24 | **11/24** |
| Yeti | **8/24** | 4/24 |
| Walkyrion | **8/24** | 3/24 |

Each hero played to its own strength — Noxx kites, the armoured two trade — Noxx
is the strongest, which is what a speed-and-crit hero should be. The single
trade-only bot used to report the opposite, and it was the instrument: it cannot
express disengaging, so it flattered the heroes who survive by standing still.
The numbers above are a rough read, not a verdict; 24 runs is a small sample.

Measured stage by stage, on the same seeds:

| | escapes |
| --- | --- |
| no equipment at all | 17–33% |
| equipment, no chests | 38–46% |
| equipment and chests | 17–33% |

Loot doubles your chances and then the curses take it back. That is the bargain
working: a chest is worth opening and worth thinking about.

## Install

```bash
./install.sh
```

That creates a virtualenv, installs the game and its dependencies, and adds
**Neverdead's Revenge** to your applications menu with an icon. Everything goes
under `$HOME` — no `sudo`, nothing system-wide.

| | |
| --- | --- |
| `./install.sh --no-desktop` | set up without the menu entry |
| `./install.sh --uninstall` | remove the menu entry and the icon |

Safe to re-run: it reuses the virtualenv if there is one.

On a fresh Ubuntu the virtualenv step needs `python3-venv`. If it is missing the
installer says so and tells you the one line to run.

### macOS

The game runs on macOS. The installer just does less there, because macOS has no
applications menu that reads `.desktop` files — so it sets up the virtualenv and
skips the menu entry rather than writing a file nothing will ever open.

macOS ships an old Python and never updates it, so the first run will normally
stop there. Install a current one and try again:

```bash
brew install python        # or https://www.python.org/downloads/
./install.sh
./ndr
```

If `python3` is still the old one afterwards — Homebrew keeps versioned formulae
out of the way — point the installer at the right interpreter:

```bash
./install.sh --python "$(brew --prefix)/bin/python3"
```

`--desktop` writes the menu entry anyway, if you have a reason to want it. And if
`python3` does not run at all, the installer says which of the two problems it is:
on a Mac without the Xcode command line tools, `/usr/bin/python3` exists but only
prints an error.

Doing it by hand is still fine:

```bash
python3 -m venv .venv
./.venv/bin/pip install -e ".[dev]"
```

## Run

```bash
./ndr
```

Or pick it from the applications menu. The game is a terminal program, so the
menu entry opens a terminal — size it to roughly 100×34 if you can, because the
sidebar gets cramped below about 30 rows.

## Scoring

A run is scored on three things, and walking is not one of them:

```
kills x 100  +  floors cleared x 250        what you did
+ speed bonus                               how quickly you did it
+ 5000 if you got out alive                 the only ending that really counts
```

The speed bonus is `(80 x floors cleared) - turns`, times ten, and never below
zero. Eighty turns a floor is the budget; across 144 bot runs the median floor
cost 63 and the quickest 34, so most runs score something and only a genuinely
slow one scores nothing. Slower than the budget costs you the bonus rather than
going negative, so a slow run is worth less, not worth less than nothing.

## Test

```bash
./.venv/bin/pytest
```

## The icon

A pixel skull: bone `#e8e4dc`, sockets lit purple `#a855f7`, on the game's own
`#121212`. Drawn on a 16×16 grid because everything else in the project is
blocks — the title screen is a block font and the map is one character per cell,
so a smooth vector skull would be the only soft edge in it.

It is generated, not drawn by hand:

```bash
python3 tools/make_icon.py                  # the skull
python3 tools/make_icon.py --motive a       # the block N from the title screen
python3 tools/make_icon.py --motive b       # the N with a rift crack
python3 tools/make_icon.py --motive c       # the rift alone
python3 tools/make_icon.py --png 256 48     # also rasterise, for looking at
```

The generator writes the SVG with run-length-merged rectangles, so a
sixteen-by-sixteen drawing is 44 lines rather than two hundred. A test
regenerates the icon and fails if the committed file disagrees, and another
checks the skull is left-right symmetric — a skull that is not reads as a
mistake rather than a style.

## Controls

| Key | Action |
| --- | --- |
| `w` `a` `s` `d` / `h` `j` `k` `l` / arrows | Move (walk into an enemy to attack) |
| `.` or `space` | Wait a turn |
| `enter` | Interact: pick up what you are standing on, or take the stairs |
| `>` | Descend, when you already know that is what you want |
| `q` | Drink a potion |
| `c` | Character sheet: every stat, and what each piece is contributing |
| `i` | Show what you are carrying |
| `?` | Controls and the terrain reference |
| `Esc` | Menu, `q` there to quit to title |

The prologue and the run summary close on a **held enter**, not a single press.
They are the only prose in the game and the only place a run is added up, and a
stray key should not throw either away. The arrows scroll the prologue, and the
bar under the hint fills as you hold. Terminals that do not repeat a held key
are covered too: three presses do the same thing.

The repeats a held key keeps sending are ignored by whatever screen comes next,
so holding enter to start does not walk you around the first room printing
"There is nothing here" — the next screen only acts on a new press.

## High score

The best score is kept in `~/.local/share/neverdeads_revenge/meta.json` (or
`$XDG_DATA_HOME`) and shown on the title screen and the run summary. That is
everything that is saved — no run survives being closed, and there are no
unlocks yet.

## Loot and equipment

Two kinds of thing lie on the floor.

**Draughts** — `!` a potion, `*` an elixir — go in the pack and heal when drunk
with `q`. Health is the run's real currency, so these are the supply that decides
how far you get.

**Equipment** is worn the moment you step on it and press `enter`: a weapon (`)`)
or a coat (`[`). Whatever it replaces is set down on the floor *beside* you, so
nothing is ever lost and walking back onto it puts it on again. Weapons raise
damage and crit; armour raises armour, evasion and speed.

**Chests** (`&`) are not loot, they are a question. Standing on one and pressing
`enter` stops the game and shows you the price — and only the price. Whatever is
inside is better than anything lying around, and it is not free. Say yes and you
get both: the strong tier of weapons and armour, and a curse that lasts the rest
of the run.

| curse | what it takes |
| --- | --- |
| WITHER | a quarter of your health, taken now and for good |
| BLEED | a drop of blood every third step |
| FRAIL | two points of armour, gone |
| HEAVY | a quarter of your speed |
| DIM | your sight, cut to five paces |
| FAMINE | half of what every draught is worth |

`c` opens the full sheet: every stat, what each piece is contributing, and what
has been done to you.

## Not implemented yet

A talent tree, equipment slots beyond the two, sound, saving mid-run, and the
meta-progression the persistence layer is shaped for (`META_UPGRADES` is still an
empty dict, and `state._apply_upgrades` is a no-op). Two roster slots are shown
locked and are not playable yet. There is no way to lift a curse: it is a
decision made once and lived with.

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

## License

**MIT.** The full text is in [LICENSE](LICENSE).

In short: do what you like with this — use it, change it, share it, sell it —
as long as the copyright notice stays with it. There is no warranty.
