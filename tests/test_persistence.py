"""Tests for what outlives a run.

The save file is the one thing in the project that can lose a player's work, so
it gets its own file rather than a corner of ``test_game``.
"""

from __future__ import annotations

import json
from pathlib import Path

from neverdeads_revenge.persistence import (
    SCOREBOARD_SIZE,
    MetaProgress,
    ScoreEntry,
    load_meta,
    save_meta,
)


# -- the scoreboard ---------------------------------------------------------
def test_the_board_keeps_the_best_first():
    progress = MetaProgress()
    for name, score in (("AAA", 100), ("BBB", 900), ("CCC", 500)):
        progress.record_run(depth=1, score=score, kills=0, name=name)

    assert [entry.name for entry in progress.scores] == ["BBB", "CCC", "AAA"]


def test_the_board_is_capped():
    """The file is rewritten on every ending; a list that grows forever is a
    file that grows forever."""
    progress = MetaProgress()
    for score in range(SCOREBOARD_SIZE + 8):
        progress.record_run(depth=1, score=score, kills=0, name="AAA")

    assert len(progress.scores) == SCOREBOARD_SIZE
    assert progress.scores[0].score == SCOREBOARD_SIZE + 7


def test_a_worse_run_does_not_lower_the_best():
    progress = MetaProgress()
    progress.record_run(depth=1, score=900, kills=0, name="AAA")
    progress.record_run(depth=1, score=10, kills=0, name="BBB")

    assert progress.best_score == 900
    assert len(progress.scores) == 2, "a bad run is still a run worth listing"


def test_gold_is_added_and_the_score_is_kept_at_its_best():
    """Coin is a currency; a score is a record. They behave differently."""
    progress = MetaProgress()
    progress.record_run(depth=1, score=100, kills=0, gold=40, name="AAA")
    progress.record_run(depth=1, score=50, kills=0, gold=25, name="BBB")

    assert progress.gold == 65
    assert progress.best_score == 100


def test_a_run_without_a_name_is_not_listed():
    """The totals still count it -- a run that was abandoned is still a run."""
    progress = MetaProgress()
    progress.record_run(depth=3, score=200, kills=2)

    assert progress.scores == []
    assert progress.runs_started == 1
    assert progress.best_score == 200


def test_the_last_name_is_remembered():
    """So the next run costs one keypress rather than five."""
    progress = MetaProgress()
    progress.record_run(depth=1, score=1, kills=0, name="NXX")

    assert progress.last_name == "NXX"


def test_an_entry_says_how_the_run_ended():
    won = ScoreEntry(name="AAA", score=1, depth=10, hero="noxx", won=True)
    lost = ScoreEntry(name="BBB", score=1, depth=4, hero="yeti", won=False)
    assert won.outcome == "escaped"
    assert lost.outcome == "died"


# -- the file ---------------------------------------------------------------
def test_progress_round_trips_through_the_file(tmp_path: Path):
    path = tmp_path / "meta.json"
    progress = MetaProgress(gold=250)
    progress.record_run(
        depth=10, score=4200, kills=17, gold=80, won=True, name="NOXX", hero="yeti"
    )

    save_meta(progress, path)
    loaded = load_meta(path)

    assert loaded.gold == 250 + 80
    assert loaded.best_score == 4200
    assert loaded.last_name == "NOXX"
    assert len(loaded.scores) == 1
    assert loaded.scores[0].name == "NOXX"
    assert loaded.scores[0].hero == "yeti"
    assert loaded.scores[0].won is True


def test_a_save_from_an_older_build_is_kept_not_discarded(tmp_path: Path):
    """The version check used to throw the file away for a missing key.

    Which would have cost a player their high score in exchange for adding a
    coin counter -- the sort of thing that makes somebody stop trusting saves.
    """
    path = tmp_path / "meta.json"
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "unlocked_heroes": ["noxx"],
                "upgrades": {},
                "runs_started": 4,
                "runs_won": 1,
                "best_depth": 9,
                "best_score": 12345,
                "total_kills": 40,
            }
        )
    )

    loaded = load_meta(path)

    assert loaded.best_score == 12345, "the high score was thrown away"
    assert loaded.runs_started == 4
    assert loaded.gold == 0, "a field the old file never had"
    assert loaded.scores == []
    assert loaded.last_name == ""


def test_a_corrupt_file_costs_progress_and_not_the_game(tmp_path: Path):
    path = tmp_path / "meta.json"
    path.write_text("{ this is not json")

    loaded = load_meta(path)

    assert loaded.best_score == 0
    assert loaded.gold == 0


def test_a_future_version_is_not_guessed_at(tmp_path: Path):
    """A file from a newer build is not ours to interpret."""
    path = tmp_path / "meta.json"
    path.write_text(json.dumps({"version": 99, "best_score": 99999}))

    assert load_meta(path).best_score == 0


def test_a_missing_file_is_just_a_fresh_start(tmp_path: Path):
    assert load_meta(tmp_path / "nothing-here.json").best_score == 0
