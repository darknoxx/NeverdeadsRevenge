"""Persistent player data: what survives between runs.

Milestone 1 writes the file but does not yet fill it. The point of building it
now is that the shape is fixed: later upgrades and hero unlocks only need an
entry in :data:`META_UPGRADES`, not a change to how a run starts.

The save file lives in the XDG data directory so it follows the platform
convention rather than landing in the source tree.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

__all__ = [
    "ScoreEntry",
    "SCOREBOARD_SIZE",
    "MetaProgress",
    "MetaUpgrade",
    "META_UPGRADES",
    "data_dir",
    "save_path",
    "load_meta",
    "save_meta",
]

SAVE_VERSION = 1

#: How many runs the scoreboard keeps. Capped because the file is rewritten on
#: every ending and a list that grows forever is a file that grows forever.
SCOREBOARD_SIZE = 10


@dataclass(frozen=True, slots=True)
class MetaUpgrade:
    """A permanent, stackable upgrade bought between runs."""

    key: str
    name: str
    description: str
    #: What one stack is worth, so the UI can render "+1" without special cases.
    unit: str = ""
    #: How many stacks may be bought at most.
    max_stacks: int = 3

    def describe_stack(self, stacks: int) -> str:
        """A human-readable effect line for ``stacks`` stacks."""
        return f"{self.unit} {stacks}" if self.unit else ""


#: Registered upgrades. Empty for milestone 1 -- the mechanism is proven, the
#: content comes later.
META_UPGRADES: dict[str, MetaUpgrade] = {}


@dataclass(slots=True)
class ScoreEntry:
    """One finished run, as the scoreboard keeps it."""

    name: str
    score: int
    depth: int
    hero: str
    won: bool

    @property
    def outcome(self) -> str:
        return "escaped" if self.won else "died"


@dataclass(slots=True)
class MetaProgress:
    """Everything that outlives a single run."""

    version: int = SAVE_VERSION
    #: Hero keys that have been unlocked.
    unlocked_heroes: list[str] = field(default_factory=lambda: ["noxx"])
    #: Upgrade key -> number of stacks bought.
    upgrades: dict[str, int] = field(default_factory=dict)
    #: Coins banked across every run. Spent in the shop, so it is the one number
    #: that survives death and is worth something afterwards.
    gold: int = 0
    #: The best runs, highest first.
    scores: list[ScoreEntry] = field(default_factory=list)
    #: The name used last, so the next run costs one keypress rather than five.
    last_name: str = ""
    #: Lifetime run statistics.
    runs_started: int = 0
    runs_won: int = 0
    best_depth: int = 0
    best_score: int = 0
    total_kills: int = 0

    def stacks(self, key: str) -> int:
        return self.upgrades.get(key, 0)

    def add_stack(self, key: str) -> int:
        """Buy one stack of an upgrade, respecting its cap. Returns new count."""
        upgrade = META_UPGRADES.get(key)
        if upgrade is None:
            raise KeyError(f"unknown meta upgrade: {key}")
        current = min(self.stacks(key) + 1, upgrade.max_stacks)
        self.upgrades[key] = current
        return current

    def unlock(self, hero_key: str) -> None:
        if hero_key not in self.unlocked_heroes:
            self.unlocked_heroes.append(hero_key)

    def is_unlocked(self, hero_key: str) -> bool:
        return hero_key in self.unlocked_heroes

    def record_run(
        self,
        *,
        depth: int,
        score: int,
        kills: int,
        gold: int = 0,
        won: bool = False,
        name: str = "",
        hero: str = "",
    ) -> None:
        """Fold a finished run into the lifetime totals and the scoreboard.

        ``gold`` is added rather than kept at its best: coin is a currency, and a
        bad run that still picked up a purse is a run that moved you forward.
        The score, by contrast, is kept at its best -- a worse run does not lower
        anything.
        """
        self.runs_started += 1
        self.total_kills += kills
        self.gold += gold
        self.best_depth = max(self.best_depth, depth)
        self.best_score = max(self.best_score, score)
        if won:
            self.runs_won += 1

        if not name:
            return
        self.last_name = name
        self.scores.append(
            ScoreEntry(name=name, score=score, depth=depth, hero=hero, won=won)
        )
        self.scores.sort(key=lambda entry: entry.score, reverse=True)
        del self.scores[SCOREBOARD_SIZE:]

    def meta_upgrade_totals(self) -> dict[str, int]:
        """Upgrade stacks, as :func:`~neverdeads_revenge.game.state.start_run` wants them."""
        return dict(self.upgrades)


# -- storage ---------------------------------------------------------------


def data_dir() -> Path:
    """Return the directory the save file belongs in.

    Honours ``XDG_DATA_HOME`` and falls back to the platform default, so the
    source tree never collects save data.
    """
    override = os.environ.get("NEVERDEADS_REVENGE_HOME")
    if override:
        return Path(override).expanduser()

    base = os.environ.get("XDG_DATA_HOME")
    root = Path(base).expanduser() if base else Path.home() / ".local" / "share"
    return root / "neverdeads_revenge"


def save_path() -> Path:
    """Full path of the save file."""
    return data_dir() / "meta.json"


def load_meta(path: Path | None = None) -> MetaProgress:
    """Load saved progress, or return fresh progress if there is none.

    A corrupt or future-versioned file is not worth crashing over: a broken save
    should cost you your unlocks, not your ability to play.
    """
    target = path or save_path()
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return MetaProgress()

    if not isinstance(raw, dict) or raw.get("version") != SAVE_VERSION:
        return MetaProgress()

    # Read field by field with defaults rather than by key. A save written by an
    # older build is missing whatever was added since, and the version check
    # above would otherwise have thrown the whole file away -- losing a player's
    # high score to add a coin counter.
    try:
        return MetaProgress(
            version=raw["version"],
            unlocked_heroes=list(raw.get("unlocked_heroes", ["noxx"])),
            upgrades=dict(raw.get("upgrades", {})),
            gold=int(raw.get("gold", 0)),
            scores=[
                ScoreEntry(
                    name=str(entry.get("name", "?")),
                    score=int(entry.get("score", 0)),
                    depth=int(entry.get("depth", 1)),
                    hero=str(entry.get("hero", "noxx")),
                    won=bool(entry.get("won", False)),
                )
                for entry in raw.get("scores", [])
                if isinstance(entry, dict)
            ],
            last_name=str(raw.get("last_name", "")),
            runs_started=int(raw.get("runs_started", 0)),
            runs_won=int(raw.get("runs_won", 0)),
            best_depth=int(raw.get("best_depth", 0)),
            best_score=int(raw.get("best_score", 0)),
            total_kills=int(raw.get("total_kills", 0)),
        )
    except (KeyError, TypeError, ValueError):
        return MetaProgress()


def save_meta(progress: MetaProgress, path: Path | None = None) -> None:
    """Write progress to disk atomically.

    Writes to a temporary file in the same directory and renames it, so an
    interrupted save cannot leave a half-written file behind.
    """
    target = path or save_path()
    target.parent.mkdir(parents=True, exist_ok=True)

    payload = json.dumps(asdict(progress), indent=2)
    handle = tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=target.parent,
        prefix=".meta-",
        suffix=".tmp",
        delete=False,
    )
    try:
        with handle as stream:
            stream.write(payload)
        os.replace(handle.name, target)
    except BaseException:
        # Never leave the temp file behind on failure.
        Path(handle.name).unlink(missing_ok=True)
        raise
