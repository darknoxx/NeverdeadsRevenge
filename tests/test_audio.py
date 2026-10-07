"""Tests for the sounds.

Two halves. The files themselves are generated, so they are checked the way the
icon is -- regenerate and compare -- and the player is checked for the thing
that actually matters about it: that it is *safe*. A machine with no audio must
get silence and no delay, never an error, because a sound effect is not worth a
crash and most machines running a terminal game have no business making noise.
"""

from __future__ import annotations

import subprocess
import sys
import wave
from pathlib import Path

from neverdeads_revenge.game.state import LogKind
from neverdeads_revenge.ui import audio
from neverdeads_revenge.ui.audio import SOUNDS_DIR, Sfx, loudest_kind, sound_for_kind

ROOT = Path(__file__).resolve().parent.parent
MAKE_SOUNDS = ROOT / "tools" / "make_sounds.py"


# -- the files ---------------------------------------------------------------
def test_every_sound_the_game_can_ask_for_exists():
    """The recipes are the list. A sound named in the code and not generated is
    a sound that plays nothing, silently, forever."""
    for name in audio.BY_KIND.values():
        assert (SOUNDS_DIR / f"{name}.wav").exists(), name
    for name in ("level", "stairs", "death", "victory", "chest"):
        assert (SOUNDS_DIR / f"{name}.wav").exists(), name


def test_every_committed_sound_is_a_playable_wav():
    files = sorted(SOUNDS_DIR.glob("*.wav"))
    assert len(files) >= 10, "the sound set shrank"
    for path in files:
        with wave.open(str(path), "rb") as handle:
            assert handle.getnchannels() == 1, path.name
            assert handle.getsampwidth() == 2, path.name
            assert handle.getframerate() == 11025, path.name
            assert handle.getnframes() > 0, path.name


def test_no_sound_outlives_the_thing_it_announces():
    """A sound effect in a turn-based game is punctuation. Anything long enough
    to be waited for is a sound the player learns to dread."""
    for path in SOUNDS_DIR.glob("*.wav"):
        with wave.open(str(path), "rb") as handle:
            seconds = handle.getnframes() / handle.getframerate()
        assert seconds <= 0.8, f"{path.name} is {seconds:.2f}s"


def test_the_sounds_are_small_enough_to_ship():
    total = sum(path.stat().st_size for path in SOUNDS_DIR.glob("*.wav"))
    assert total < 200_000, f"the sound set is {total / 1024:.0f} kB"


def test_the_committed_sounds_are_what_the_generator_produces(tmp_path):
    """They are generated, so they must not be hand-edited out of sync.

    Without this, someone nudges a WAV and the next regeneration silently undoes
    it -- which is the same trap the icon has a test for, and for the same
    reason.
    """
    result = subprocess.run(
        [sys.executable, str(MAKE_SOUNDS), "--out", str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr

    generated = {path.name: path.read_bytes() for path in tmp_path.glob("*.wav")}
    committed = {path.name: path.read_bytes() for path in SOUNDS_DIR.glob("*.wav")}

    assert generated.keys() == committed.keys(), "the set of sounds has drifted"
    for name, data in generated.items():
        assert data == committed[name], (
            f"src/neverdeads_revenge/sounds/{name} has drifted from "
            f"tools/make_sounds.py; run: python3 tools/make_sounds.py"
        )


def test_the_generator_is_deterministic(tmp_path):
    """The noise channel is seeded, not drawn from the system -- otherwise the
    comparison above would fail at random."""
    from tools.make_sounds import render, SOUNDS

    for name, notes in SOUNDS.items():
        assert render(notes) == render(notes), name


# -- which sound a message gets ----------------------------------------------
def test_the_combat_kinds_all_make_a_noise():
    for kind in (LogKind.CRIT, LogKind.COMBAT, LogKind.DAMAGE):
        assert sound_for_kind(kind), kind


def test_the_quiet_kinds_stay_quiet():
    """A sound for every line is a sound for none of them."""
    for kind in (LogKind.PLAIN, LogKind.SYSTEM):
        assert sound_for_kind(kind) is None, kind


def test_a_turn_sounds_like_the_worst_thing_that_happened_in_it():
    """Not like all three at once, and not like the first one either."""
    assert loudest_kind([LogKind.COMBAT, LogKind.DAMAGE]) is LogKind.DAMAGE
    assert loudest_kind([LogKind.GOOD, LogKind.CRIT, LogKind.COMBAT]) is LogKind.CRIT
    assert loudest_kind([LogKind.COIN]) is LogKind.COIN
    assert loudest_kind([]) is None
    assert loudest_kind([LogKind.PLAIN, LogKind.SYSTEM]) is None


def test_a_crit_is_louder_than_a_hit():
    assert audio.LOUDNESS[LogKind.CRIT] > audio.LOUDNESS[LogKind.COMBAT]


# -- the player --------------------------------------------------------------
def test_with_no_player_it_is_silent_and_harmless(monkeypatch):
    """The common case, and the one that has to be perfect: most machines
    running a terminal game have nothing to play a sound with."""
    monkeypatch.setattr(audio, "_find_player", lambda: None)
    sfx = Sfx(enabled=True)

    assert not sfx.available
    sfx.play("hit")
    sfx.play("no-such-sound")
    sfx.close()


def test_muting_it_means_nothing_is_queued(monkeypatch):
    monkeypatch.setattr(audio, "_find_player", lambda: ["aplay"])
    sfx = Sfx(enabled=True)
    sfx.set_muted(True)
    sfx.play("hit")
    assert sfx._queue.empty(), "a muted sound was queued anyway"


def test_toggling_reports_the_new_state(monkeypatch):
    monkeypatch.setattr(audio, "_find_player", lambda: ["aplay"])
    sfx = Sfx(enabled=False)
    assert sfx.muted
    assert sfx.toggle() is False, "toggling off should come back on"
    assert not sfx.muted
    assert sfx.toggle() is True


def test_the_environment_can_start_it_muted(monkeypatch):
    monkeypatch.setenv(audio.MUTE_ENV, "1")
    monkeypatch.setattr(audio, "_find_player", lambda: ["aplay"])
    assert Sfx().muted


def test_a_player_that_vanishes_goes_quiet_rather_than_crashing(monkeypatch):
    """A sound is never worth a crash. The audio server going away mid-run has
    to cost the player their sound effects and nothing else."""
    monkeypatch.setattr(audio, "_find_player", lambda: ["no-such-player-at-all"])
    sfx = Sfx(enabled=True)
    assert sfx.available

    sfx.play("hit")
    sfx._queue.join()

    assert sfx.muted, "it kept trying"


def test_a_missing_file_is_not_an_error(monkeypatch):
    monkeypatch.setattr(audio, "_find_player", lambda: ["aplay"])
    sfx = Sfx(enabled=True)
    sfx.play("no-such-sound")
    sfx._queue.join()
    assert not sfx.muted, "a missing file muted the whole game"


def test_the_sounds_live_inside_the_package():
    """They are read at runtime, so they have to travel with the code rather
    than sitting in assets/ with the desktop file."""
    package = Path(audio.__file__).resolve().parent.parent
    assert SOUNDS_DIR == package / "sounds"
    assert SOUNDS_DIR.exists()
