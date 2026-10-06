"""The scrolling combat log.

Colours come from :class:`~neverdeads_revenge.game.state.LogKind` rather than from
parsing message text, so wording can change freely without breaking the styling.
"""

from __future__ import annotations

from rich.text import Text
from textual.widgets import RichLog

from neverdeads_revenge.game.state import GameState, LogKind

__all__ = ["MessageLog"]

#: LogKind -> Rich style.
KIND_STYLES: dict[LogKind, str] = {
    LogKind.PLAIN: "white",
    LogKind.COMBAT: "bright_white",
    LogKind.CRIT: "bold yellow",
    LogKind.DAMAGE: "orange1",
    LogKind.GOOD: "bold green",
    LogKind.BAD: "bold red",
    LogKind.SYSTEM: "bold cyan",
    # The same gold the coins are on the map, so the line and the pile match.
    LogKind.COIN: "bold yellow",
}


class MessageLog(RichLog):
    """Shows the most recent messages, newest at the bottom.

    The height comes from the stylesheet (``#message-log`` in ``app.tcss``) rather
    than from here, so the surrounding layout can decide the split between this
    panel and the legend beside it.
    """

    DEFAULT_CSS = """
    MessageLog {
        background: $surface;
    }
    """

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("wrap", True)
        kwargs.setdefault("markup", False)
        kwargs.setdefault("highlight", False)
        super().__init__(**kwargs)
        self.can_focus = False
        self._seen = 0

    def show_new(self, state: GameState) -> None:
        """Write any messages added since the last call.

        Only new lines are written, so the log does not fill with duplicates.
        """
        entries = state.log[self._seen :]
        self._seen = len(state.log)
        for entry in entries:
            self.write(Text(entry.text, style=KIND_STYLES.get(entry.kind, "white")))

    def reset(self) -> None:
        """Forget what has been shown, e.g. when a new run starts."""
        self.clear()
        self._seen = 0
