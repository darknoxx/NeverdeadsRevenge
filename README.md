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

Enemy count scales with depth, monster health and damage scale too, and wraiths
get more common the deeper you go. The legend in the sidebar quotes the current
floor's numbers, so it follows you down. The dials themselves are set out below.

No hero can heal on their own; potions and elixirs on the floor are the only way
back up. A run's health is therefore a budget you spend across ten floors, and
skipping loot to save time is a real trade.

The dungeon is built to be a wall. Measured with the bot in
`tools/balance.py` over 40 seeds a hero:

```bash
python3 tools/balance.py                 # 40 seeds a hero
python3 tools/balance.py --loadout full  # with the shop spent
```

It plays the way a competent but unimaginative player does -- kills what is
beside it, drinks when hurt, picks up what is worth walking to, washes a curse
off when it can afford to, and beelines for the exit otherwise. It is
deliberately *not* a good player: a bot that kites and plans tells you what the
game is like for somebody who has already mastered it, and the floor is what the
dials are for.

| | Noxx | Yeti | Walkyrion |
| --- | --- | --- | --- |
| nothing bought | 22% | 5% | 15% |
| every permanent upgrade, a bought blade, a bought coat and a bought amulet | 62% | 50% | 42% |

Of 120 runs with nothing bought, twenty-four reached floor 10 and fourteen never
got past floor 3. That is the shape the wall is meant to have: **floor one is a
real fight**, the run climbs a gentle curve on top of it, and the shop is the
difference between the two rows of that table.

The dials are the enemy templates (floor one is a fight, not a formality),
`POTENCY_PER_FLOOR` (14% harder per floor, capped at 2.2x on floor 9), the enemy
count (`7 + depth`) and how fast wraiths grow more common (1.25x per floor). The
slope is *shallower* than it has ever been, and that is the point: a steep curve
over a soft floor made the early game a formality and the late game a cliff. A
shallow curve over a hard floor makes every floor of the run tense.

The hero keeps up on their own, by levelling. See below.

Two things were measured and left alone. The rare finds and the springs move the
escape rate by less than the noise on a thirty-run sample. And the fastest hero
still strictly outruns everything in the dungeon, which is the one hard
constraint in the whole balance: a single monster that outran Noxx would turn
every other stat he has into decoration.

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
floors cleared x 250                        how far you got
+ speed bonus                               how quickly you got there
+ 5000 if you got out alive                 the only ending that really counts
```

Killing things is not in there. It pays in coin instead, and the two are kept
apart on purpose: the score is a record of the run, the purse is what the run was
worth to you afterwards. Running them together made every fight worth points
whether or not it was worth fighting.

The two currencies are also set against each other on purpose. The nameless run
halves the score and doubles the coin, and the pilgrim's toll charges for every
floor down while paying better for what you find there. A run is allowed to be
about one or the other.

The speed bonus is `(80 x floors cleared) - turns`, times ten, and never below
zero. Eighty turns a floor is the budget; across 144 bot runs the median floor
cost 63 and the quickest 34, so most runs score something and only a genuinely
slow one scores nothing. Slower than the budget costs you the bonus rather than
going negative, so a slow run is worth less, not worth less than nothing.

## Levels

A run is ten floors long and the monsters get 14% harder on each of them, so
something has to keep up with that, and it should be the hero rather than the
shop. So kills teach: **every four kills is a level**, and a level is a small
package of stats.

| | |
| --- | --- |
| every level | +2 max health |
| every third | +1 damage |
| every fourth | +1 armour |
| every fifth | +0.05 speed |

Health every level, because health is the resource a run spends and the one you
watch. Then a rotation, with coprime lengths on purpose: if two of them shared a
period the run would feel like a staircase instead of a curve. A run that dies on
floor three has had none of the rotation; a run that reaches floor nine has had
all of it a few times. The cap is level 20.

It is automatic rather than a choice. A talent pick needs a screen and a key, and
the point of this is that you notice yourself getting stronger without stopping
to think about it. The decisions worth stopping for are in the shop, between
runs, where they belong -- and levels are *run-only*: they go into the hero's own
stats, so unlike REVENGE they do not lapse when you take the stairs.

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
| `enter` | Interact: pick up what you are standing on, take the stairs, or use the spring |
| `c` | Character sheet: every stat, all three slots, and what has been done to you |
| `>` | Descend, when you already know that is what you want |
| `q` | Drink a potion |
| `c` | Character sheet: every stat, and what each piece is contributing |
| `i` | What you are carrying and wearing, and what each of them does |
| `i` | Show what you are carrying |
| `?` | Controls and the terrain reference |
| `Esc` | Menu: `r` resume, `s` save and quit, `m` sound on/off, `q` quit to title |

On the **title screen**: any key starts a run, `s` opens the shop and `h` opens
the scoreboard. In the **shop**: up/down choose, `enter` buys, `s` or `Esc`
leaves.

**Holding a direction walks, and fights, at six steps a second** -- and it scales
with the hero's speed, so Noxx rattles along at eight and Yeti plods at four and a
half. A terminal repeats a held key about thirty-three times a second, which is a
rate nobody chose: it made a fight an unreadable blur and it dropped two sounds in
three.

The scaling changes nothing about the balance. The turn queue decides who acts how
often, and a *tap* is never throttled, so this is purely how a hero feels under
the finger -- which is the one place speed is felt rather than read. The cap of
eight belongs to the sound: a note has to finish before the next one starts or the
device is permanently behind.

Only *movement* is capped. Every other key is a deliberate press a player may well
make twice in quick succession, and there is no way to tell a repeat from a fast
press anyway -- Textual's key event carries only ``key`` and ``character``.

**A blow that lands flashes.** The cell it landed on is drawn inverted until your
next action -- the monster you hit, and your own cell when you take one. It is
the useful half of a hit you cannot see coming: the log scrolls and the map is
where you are looking. No timer, because there are none in this project and for a
good reason; the flash ends because the next action clears it, which is what the
throttle above makes long enough to see.

The prologue and the run summary close on a **held enter**, not a single press.
They are the only prose in the game and the only place a run is added up, and a
stray key should not throw either away. The arrows scroll the prologue, and the
bar under the hint fills as you hold. Terminals that do not repeat a held key
are covered too: three presses do the same thing.

The repeats a held key keeps sending are ignored by whatever screen comes next,
so holding enter to start does not walk you around the first room printing
"There is nothing here" — the next screen only acts on a new press.

## Sound

Chiptune, generated rather than recorded, and shipped with the package:

```bash
python3 tools/make_sounds.py            # regenerate them all
python3 tools/make_sounds.py --list     # what there is, and how long
```

A Gameboy's two pulse channels are square waves with a duty cycle and its noise
channel is noise, which between them is `math` and `struct` from the standard
library -- so the sounds are synthesised exactly, with no samples, no
dependencies and nothing to license. Twelve of them, sixty kilobytes, none
longer than two thirds of a second. A test regenerates every file and fails if
the committed one disagrees, the same way the icon is checked.

The sounds are read off the message log, which already sorts itself into combat,
crit, damage and the rest, so the rules are not written down a second time. A
turn that produces three lines sounds like the worst thing that happened in it
rather than like all three at once. Levels, descents, chests and the two endings
are named events and get their own.

**It is never late.** Spawning a player per sound measured at 190ms on the
machine this was written on, of which the sound itself was fifty: a fight is
faster than that, so the first blow made no noise and the next four arrived in a
heap. The fix is to keep one player open and write raw samples into its standard
input -- ten microseconds a sound instead of a hundred and ninety milliseconds --
and to drop a sound whose moment has passed rather than queueing it behind the
one playing. Levels, descents, chests and the two endings are never dropped:
a hit that arrives late is about a moment that has gone, and a level arriving
late is still the level.

**And it is silent when it has to be.** A terminal game has no business assuming
it can make a noise, so the player looks for `aplay` or `ffplay` (which can be
kept open) and falls back to `pw-play`, `paplay` or `afplay` (which take a
filename), or the standard library on Windows -- and does nothing at all if it
finds none. No error, no delay, no missing feature. If the audio server goes away
mid-run the game goes quiet and carries on.

**And a sound is not thrown away for being a fifth of a second late.** The old
rule dropped one the moment the device was busy with any of the previous one,
which meant a kill -- a hundred and ninety milliseconds -- ate the blow that
landed on top of it, and a fight came out with holes in it. The device may now
fall a quarter of a second behind before anything is dropped; a sound shorter than
that can never push it past the threshold on its own, and a test holds every sound
to it.

**And it does not go quiet by accident.** The device is opened before the first
blow rather than on it -- opening it costs about a hundred and forty milliseconds,
and paying that on the first hit of the first fight is paying it where it shows.
And a failure is counted rather than obeyed: one hiccup used to silence the rest
of the session, which is why the sound used to stop and never come back. Three in
a row and it gives up; one, and it tries again.

`m` in the pause menu turns it off, `--no-sound` starts it off, and
`NEVERDEADS_REVENGE_MUTE=1` starts it off and cannot be overridden -- the one
caller that matters is the test suite. The pause menu's choice is written to the
save file, because a player who turns the sound off in a library means it for the
next time too.

If the sound is ever wrong in a way that cannot be heard from where the code was
written, there is a log:

```bash
./ndr --sound-log                 # writes /tmp/ndr-sound.log
./ndr --sound-log /tmp/mine.log   # or wherever you like
```

Every decision lands there -- what played, what was dropped, how long the sound
was, and how far behind the device already was. The file exists from the moment
the game starts, with a header saying which player was found, so it is obvious
whether the log is on. The game cannot know whether a note came out of the
speaker, but it can say exactly what it asked for.

`NEVERDEADS_REVENGE_SOUND_LOG=/tmp/sfx.log` does the same thing if you would
rather set it in the environment than pass a flag.

## Gold and the shop

Monsters leave a pile of coins (`$`) where they fall. Walk over it and it goes in
the purse; leave it and it does not. A deep floor pays better — coin scales with
depth the same way damage does — so there is a reason to keep going down rather
than farm the first three.

Gold is banked when the run ends, and it is the first thing in the game that
death does not take away. It is spent in the shop, which `s` opens from the title.

| shelf | what it is |
| --- | --- |
| **Supplies** | draughts, used up next run |
| **Gear** | a weapon or a coat, worn from the first step of the next run |
| **Amulets** | all fourteen, and the only shelf where the thing you buy changes how a fight is fought |
| **Upgrades** | permanent, bought in stacks, and the only thing here a bad run cannot take back |
| **Wild offers** | two at a time, re-rolled after every run |

The wild offers are the reason to look at the shop even when the sensible things
are bought. Each is a bargain with a catch, and both halves are on the screen:

| offer | what it gives | what it takes |
| --- | --- | --- |
| the blind box | something from the deep, unseen | you do not get to look first |
| the wager | a coin, thrown into the dark | one face a blade, the other a curse |
| greed | coins are worth double | everything below is a fifth tougher |
| the pact | coins are worth half again as much | you start cursed, and the dark picks |
| the pilgrim's toll | coins are worth half again as much | the dark takes five for each floor |
| the nameless run | coins are worth double | and the score is worth half |
| grave goods | grave iron in hand from the start | it is heavy, and it slows you down |
| the hollow tooth | every kill feeds you three | and no draught will ever stay down |
| the mirror of hunger | a draught heals half again as much | and something drinks beside you |
| second wind | the first killing blow does not land | once a run, and no more |
| the count's favour | every thirteenth kill heals you whole | you do not want to know who counts |
| blood bargain | +0.15 speed, for good | -4 max health, for good |

Prices are tuned around one number: **a run banks 50 to 115 coin, and the full
permanent set costs 1040.** That is twelve to eighteen runs -- cheap enough that
every run buys something, expensive enough that the wall is what you are buying
your way through. A single-run wild offer always costs less than the cheapest
permanent upgrade, because it is one run's worth of change and the upgrade is
not.

A bought parcel is taken off the books the moment the next run starts, so a
draught bought for a run is drunk in that run. Upgrades and the permanent wild
offer are not.

## The people

`8` is somebody. Not a monster and not a hero -- something that was returned, or
something that never left, standing in a room and willing to say one true thing
about the place. About one floor in four from the second one down, and never on
the first, because floor one is where you learn what a monster looks like.

They are solid: walking into one says so rather than silently refusing to move,
and `enter` beside one is a conversation. They never take a turn, they cannot be
attacked, and they never stand on the way out -- a conversation on the exit is a
conversation you have to walk past twice.

| | |
| --- | --- |
| **the Tally** | counts things in and does not count them out |
| **Vesper** | was promised a morning |
| **the Ninth** | got as far as the stairs and turned around |
| **Cinder** | keeps a fire that does not warm anything |
| **the Lamplighter** | has never lit one on the way back up |
| **the Sexton** | digs, because there is nobody to bury |

Each of them has several lines and says one per meeting, at random: hearing the
same sentence twice from the same person is the moment a person becomes
furniture. **They carry no mechanics at all** -- no quest, no trade, no reward --
and that is deliberate. A line of lore is the cheapest thing in the game to add
and the most expensive to get wrong, so the first version is one sentence and no
promise. A quest is a promise, and a promise needs a system behind it.

## Saving a run

`Esc` then `s` writes the run down and quits to the title. The title then offers
to pick it up, with `c`, and the save is **deleted the moment it is read**.

That is the whole design. One slot, overwritten, consumed on load -- so quitting
in front of a monster you do not like the look of and coming back to a fresh roll
of the dice is not a thing you can do twice. What it is for is the terminal being
closed and the laptop running out of battery, and the twenty minutes already
spent.

It is a real save, not a snapshot: the floor is the floor you left, tile for tile,
the map remembers what you had explored, the generator comes back exactly where it
left off, and the turn order is the order it was. It is about forty kilobytes of
JSON, in its own file beside the progress file, because one being corrupt should
not take the other with it.

The codec is generic -- it walks dataclasses by reflection rather than listing
fields -- because a list of fields is a list somebody has to remember to add to.
What makes that safe is the round-trip test: it builds a run with every field the
game can put in one, saves it, reads it back and compares the two field by field,
recursively. A field added to the game and forgotten by the codec fails *there*
instead of in somebody's saved run.

## High score

Every run ends by asking for a name — five slots, on a death and on an escape
alike, because both collected points. The best ten runs are kept and `h` opens
the scoreboard from the title.

Everything is saved in `~/.local/share/neverdeads_revenge/meta.json` (or
`$XDG_DATA_HOME`): the scoreboard, the best score, the coin, the upgrades and the
shelf. No run survives being closed. Saves from older builds are read field by
field, so adding a field never costs you a high score.

## Loot and equipment

Two kinds of thing lie on the floor.

**Draughts** — `!` a potion, `*` an elixir — go in the pack and heal when drunk
with `q`. Health is the run's real currency, so these are the supply that decides
how far you get.

**Equipment** is worn the moment you step on it and press `enter`: a weapon (`)`)
or a coat (`[`). Whatever it replaces is set down on the floor *beside* you, so
nothing is ever lost and walking back onto it puts it on again. Weapons raise
damage and crit; armour raises armour, evasion and speed.

The name grows with the thing, and the ladder is ordered by how rare it is:

| | weapon | coat |
| --- | --- | --- |
| common | the rusted tooth, +1 damage | the thin hide, +1 armour |
| | the grey bite, +2 damage, +5% crit | the grey shroud, +1 evasion |
| | the long hunger, +2 damage, +10% crit | the swift step, +0.15 speed, +1 evasion |
| rare | the heavy sorrow, +3 damage, -0.15 speed | the rune plate, +2 armour |
| chest | the runed edge, +4 damage, +10% crit | warden plate, +3 armour |
| chest | the last argument, +5 damage, +1 armour | shade cloak, +3 evasion |
| chest | grave iron, +6 damage, -0.20 speed | the burial shroud, +2 armour, +2 evasion, -0.10 speed |

**Amulets** (`"`) are the third slot and the only one that grants an ability
rather than a number. There are fourteen, four of them lying about and the rest
out of chests or the shop, and the strange half is the point:

| amulet | what it does |
| --- | --- |
| the last ember | every kill puts two health back |
| the coin hand | every coin is worth a quarter more |
| the marrow | draughts heal half again as much |
| the wayfarer | you know the way out when you arrive |
| the rune heart | +1 max health for every floor down |
| the mirror | whatever strikes you takes two back, straight through armour |
| the grave ward | the first blow of each floor is halved |
| the deathwatch | three armour under a third health |
| the deep hunger | kills feed REVENGE one more stack |
| the revenant's patience | you hit harder the longer you linger, up to four |
| the second mouth | overhealing a draught becomes armour, up to 3 + the floor |
| the dead weight | slower; your blows throw them back a square |
| the patient knife | your first blow on each thing crits |
| the borrowed face | the turn after a kill, nothing lands |

A chest looks at what you are already wearing and prefers a slot you have not
filled, so the second chest is not a second coat. It also gets better with depth:
a chest on floor nine hands out the top of its tier, which is the only thing that
keeps it worth the curse once every slot is full.

**Chests** (`&`) are not loot, they are a question. Standing on one and pressing
`enter` stops the game and shows you the price — and only the price. Whatever is
inside is better than anything lying around, and it is not free. Say yes and you
get both: the strong tier of weapons and armour, and a curse.

**Springs** (`{`) are the only tile that undoes something instead of doing it.
Standing in one and pressing `enter` offers to take one curse off you, for coin.
*Which* curse is the water's decision, not yours — and the water says so when you
are carrying more than one. The price is stated plainly rather than offered and
then refused, and walking away costs nothing at all.

**Rare finds.** The strong tier usually costs a curse. From floor 4 down it very
occasionally does not: one of those blades or coats turns up lying on the floor
with nothing owed for it. Rare enough to be a surprise, common enough to be worth
the detour.

**Wraiths leave something behind.** One blow in twenty, the wraith's touch sticks:
the dark closes in, or your guard goes slack, or the weight, or the slow leak.
Rare enough that a run can pass without it, often enough that a wraith is
something you would rather not be touched by -- which is the point of the only
monster here that is already fast, evasive and hard to out-trade.

It is never WITHER. A quarter of your health taken by a random blow in a corridor
is not a price, it is a mugging; that one belongs on a chest, where you read it
and said yes. Every other curse in the game is something you agreed to, and this
is the one that simply happens to you.

| curse | what it takes |
| --- | --- |
| WITHER | a quarter of your health, taken now |
| BLEED | a drop of blood every tenth step |
| FRAIL | two points of armour, gone |
| HEAVY | a quarter of your speed |
| DIM | your sight, cut to five paces |
| FAMINE | half of what every draught is worth |

Every curse can be lifted at a spring, and lifting one gives back *exactly* what
it took. WITHER is why that is worth saying: "a quarter of your health" is a
quarter of whatever the maximum was the moment it landed, so the amount is
written down when it lands rather than recomputed on the way out.

`c` opens the full sheet: every stat, what each piece is contributing, and what
has been done to you.

## Not implemented yet

A talent tree (levels are automatic for now, not a choice), a fourth equipment
slot, music as opposed to sound effects, and hero unlocks. Two roster slots are
shown locked and are not playable yet. The people have nothing to trade and
nothing to ask of you yet: quests are the next thing they need.

The prologue is the only prose in the game, and it is shown once per session
rather than once per run — told every run it stops being a premise and becomes a
toll.

## Layout

```
src/neverdeads_revenge/
├── core/     seeded rng, directions, energy-based turn queue
├── world/    tiles, dungeon map, generator, items, field of view
├── game/     actors, combat, game state, actions, curses, amulets, the shop
└── ui/       Textual app, screens, widgets
```

The one rule: `core/`, `world/` and `game/` never import `textual`.
Game logic is headless and deterministic; the UI only renders it. That keeps the
logic testable without a terminal and makes a headless simulator possible later.

## License

**MIT.** The full text is in [LICENSE](LICENSE).

In short: do what you like with this — use it, change it, share it, sell it —
as long as the copyright notice stays with it. There is no warranty.
