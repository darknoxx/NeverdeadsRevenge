# Roadmap

The list from the 9th of October, broken into steps that can each be finished,
tested and pushed on their own. Everything lands on `experimental`; `main` is
released deliberately and not touched by any of this.

Each step is done when its tests are green and the whole suite still passes.
The order is the order they are worked, and it is a dependency order rather than
a preference: the status effects come before the weapons that use them, and the
balance pass comes after everything that moves a number.


## Step 1 — The marks panel, as columns

`| ...log... | curses | gifts |`, names only. The descriptions move out of the
panel and stay on the character sheet (`c`), which is where a player goes when
they want to read rather than to glance.

* Two narrow panels beside the log, sharing the bottom row with it.
* No descriptions, no headings over an empty column, no keypress.
* The sidebar keeps running the full height of the screen, so the legend keeps
  its room -- the panel must not cost it a row.
* Truncation stays: a column that cannot show everything says `+N`.


## Step 2 — Status effects, and the weapons that inflict them

The foundation for bleed and poison, and for anything else that acts after the
blow rather than with it.

* A status lives on an actor: `bleed`, `poison`, `burn`, each with a stack count
  and a rule for what a stack does at the start of the actor's turn.
* They tick in the turn queue, so a monster can bleed to death between its own
  turns -- and so can the player.
* The character sheet and the marks panel show what is running on the hero.
* Weapons carry them: a blade that opens a wound, a blade that poisons, a coat
  that leaves thorns in whatever touches it.


## Step 3 — More weapons, more armour

Hyperbole in the item table, where the game has the most room for it. The brief
is *character*: an item whose stats make you play differently, not an item with a
bigger number. The lore is the source -- the Ancient Lords, the machine, the ash,
the thing with no depth.

* Several new weapons across the existing tiers, including the status ones from
  step 2.
* Several new coats, including one or two that punish being hit.
* Every one of them reachable through the chest ladder the game already has, so
  nothing new has to be invented to hand them out.


## Step 4 — More monsters, and monsters that scale

Two problems in one: too few kinds of thing to meet, and a run that gets *easier*
as it goes because a good weapon outgrows the floor.

* New templates, including genuinely tanky ones -- high health, low damage, slow
  -- which the current roster has no example of.
* A second scaling dial for health, separate from damage, so a floor can be
  longer without being more lethal.
* Re-measure with `tools/balance.py` and put the numbers in the README.


## Step 5 — The hunter

One floor in ten, something that is looking for you.

* `X` on the map, if the glyph is free.
* Lots of health, faster than most things, and it hunts: it walks toward the
  player from anywhere on the floor rather than waiting to be walked into.
* It is a decision, not a wall: it can be outrun, and it can be left behind on
  the stairs. Killing it should be worth something.


## Step 6 — More gifts

The chest's other half. A gift is a *rule*, so the bar is that it changes what
the player can do rather than what they hit for.

* A handful of new ones, drawn from the same well as the curses: the hour, the
  road, the reach.
* Each one has to be as good as the curse beside it is bad.


## Step 7 — The balance pass

After all of the above, the dials are wrong somewhere.

* `tools/balance.py` over the full loadout and over nothing, before and after.
* The README table re-measured, and the honest note about what is still noisy.
* The one question this step answers: *does a good weapon still trivialise the
  floor it was found on?*


## Not in this list

The five meta curses (FORGOTTEN RUN, SECOND SELF, TAB, UNNAMED, NEXT ONE) are
still planned and still need the meta/persistence plumbing. They are deliberately
not mixed into this list -- they are a different kind of work and would make the
balance pass meaningless.
