"""The scoreboard.

The best runs, highest first. Read-only, and the one screen in the game that is
about runs that are over rather than the one in progress.

Takes the progress it draws from rather than reading the app, so it can be
handed a fixed board in a test.
"""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Static

from ...persistence import MetaProgress

__all__ = ["ScoreboardScreen"]


class ScoreboardScreen(ModalScreen[None]):
    """Every run worth remembering. Any key closes."""

    BINDINGS = [Binding("escape", "dismiss", "Close")]

    DEFAULT_CSS = """
    ScoreboardScreen {
        align: center middle;
        background: $background 70%;
    }
    """

    def __init__(self, progress: MetaProgress) -> None:
        super().__init__()
        self.progress = progress

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="scoreboard"):
            yield Static("SCOREBOARD", id="scoreboard-title")
            yield Static(self._table(), id="scoreboard-body")
            yield Static("press any key", id="scoreboard-hint")

    def on_key(self, event) -> None:
        # A key still repeating from the title must not close the board on the
        # way in. See App.note_key.
        if self.app.note_key(event.key):
            event.stop()
            return
        event.stop()
        self.dismiss()

    def _table(self) -> str:
        if not self.progress.scores:
            return "[dim]No runs yet. Go and die a few times.[/]"

        lines = [
            "[dim]    name   score   depth  hero        ending[/]",
        ]
        for rank, entry in enumerate(self.progress.scores, start=1):
            hero = entry.hero
            lines.append(
                f"[bold]{rank:>2}.[/] [bold]{entry.name:<5}[/] "
                f"{entry.score:>6}   {entry.depth:>4}   {hero:<10}  "
                f"[dim]{entry.outcome}[/]"
            )
        lines.append("")
        lines.append(f"[dim]coins banked  {self.progress.gold}[/]")
        return "\n".join(lines)
