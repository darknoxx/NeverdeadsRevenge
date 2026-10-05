"""Hold a key to dismiss a screen.

Terminals never report a key going *up*, so "held" cannot be measured directly.
What they do report is the stream of repeat events a held key produces, and that
is enough to infer it: while the repeats keep arriving the fill keeps going, and
a moment of silence means the key was let go.

Terminals with repeat turned off would then never fill, so a few deliberate
presses count too -- and the bar shows how far along either route you are, which
is what stops a screen that will not close from being a mystery. The two routes
cannot fire at once: repeats arrive far too fast to look like deliberate
presses, and deliberate presses are far too slow to look like repeats.
"""

from __future__ import annotations

import time

__all__ = ["HoldToContinue", "BAR_CELLS", "HOLD_SECONDS"]

#: How long the key has to be held, in seconds.
#:
#: Long enough to be a decision rather than an accident, short enough that
#: somebody who is holding it does not start wondering whether it worked.
HOLD_SECONDS = 0.8

#: Silence longer than this means the key was released.
RESET_AFTER = 0.25

#: Presses that also count, for terminals with no key repeat.
FALLBACK_PRESSES = 3

#: The window those presses are counted in.
FALLBACK_WINDOW = 2.0

#: Cells in the progress bar.
BAR_CELLS = 10

#: Keys that mean "yes, go on".
HOLD_KEYS = ("enter", "return")


class HoldToContinue:
    """Watches one key and says when it has been held long enough.

    Owned by a screen, which feeds it key presses and ticks it from a timer.
    Kept apart from the screens because two of them want the same behaviour and
    the timing is the part worth testing on its own.

    The timings are parameters so a test can run the whole thing in milliseconds
    instead of sleeping through the real thing.
    """

    def __init__(
        self,
        keys: tuple[str, ...] = HOLD_KEYS,
        seconds: float = HOLD_SECONDS,
        reset_after: float = RESET_AFTER,
        fallback_presses: int = FALLBACK_PRESSES,
        fallback_window: float = FALLBACK_WINDOW,
    ) -> None:
        self.keys = keys
        self.seconds = seconds
        self.reset_after = reset_after
        self.fallback_presses = fallback_presses
        self.fallback_window = fallback_window
        self._started: float | None = None
        self._last_press = 0.0
        self._presses: list[float] = []

    # -- input --------------------------------------------------------------
    def press(self, key: str) -> bool:
        """Record a press. Returns True when the screen should go.

        True only on the fallback route -- a held key is noticed by :meth:`tick`
        once the fill completes.
        """
        if key not in self.keys:
            return False

        now = time.monotonic()
        if self._started is None:
            self._started = now
        self._last_press = now

        self._presses = [t for t in self._presses if now - t <= self.fallback_window]
        self._presses.append(now)
        return self._deliberate()

    def tick(self) -> bool:
        """Advance the clock. Returns True when the screen should go."""
        if self._started is None:
            return False

        if time.monotonic() - self._last_press > self.reset_after:
            # The hold lapsed -- the key was let go. Only the hold state is
            # cleared: the press history is the fallback route's, and wiping it
            # here would mean a slow deliberate press could never count, because
            # the timer runs between presses and would forget each one.
            self._started = None
            return False

        return self.progress >= 1.0

    def reset(self) -> None:
        """Forget the hold. The fallback's history is pruned by age, not here."""
        self._started = None

    # -- what the player sees ------------------------------------------------
    @property
    def progress(self) -> float:
        """How far through the hold, 0.0 to 1.0."""
        if self._started is None:
            return 0.0
        return min(1.0, (time.monotonic() - self._started) / self.seconds)

    def bar(self) -> str:
        """The bar as plain text; the screen decides how to colour it."""
        filled = round(self.progress * BAR_CELLS)
        return "█" * filled + "░" * (BAR_CELLS - filled)

    # -- internals -----------------------------------------------------------
    def _deliberate(self) -> bool:
        """Enough presses, spread over enough time, to mean somebody is trying.

        The spread is what distinguishes this from a repeat: a held key sends
        its events milliseconds apart, so three of them span almost no time at
        all. Three presses a third of a second apart are somebody who pressed,
        saw nothing happen, and pressed again.

        Deliberately not "every gap must be long": one quick press followed by a
        pause and then three more is still somebody trying, and requiring every
        gap would throw that away for no gain.
        """
        if len(self._presses) < self.fallback_presses:
            return False
        return self._presses[-1] - self._presses[0] > self.reset_after
