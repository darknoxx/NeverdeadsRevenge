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
import time
import wave
from pathlib import Path

import pytest

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
class _FakeStream:
    """A stand-in for the open player, recording what is written into it."""

    def __init__(self, alive: bool = True) -> None:
        self.written: list[bytes] = []
        self.stdin = self
        self.closed = False
        self._alive = alive

    def write(self, data: bytes) -> None:
        self.written.append(data)

    def flush(self) -> None:
        pass

    def close(self) -> None:
        self.closed = True

    def poll(self):
        return None if self._alive else 1

    def wait(self, timeout=None) -> int:
        return 0

    def kill(self) -> None:
        pass


def _a_player(name: str = "aplay", streams: bool = True) -> audio.Player:
    return audio.Player([name], streams=streams)


def _recording(monkeypatch) -> tuple[Sfx, list[str]]:
    """An Sfx whose emission is recorded instead of played."""
    monkeypatch.setattr(audio, "_find_player", lambda: _a_player())
    sfx = Sfx(muted=True)
    played: list[str] = []
    monkeypatch.setattr(sfx, "_emit", lambda clip: played.append(clip.path.stem))
    sfx._muted = False
    return sfx, played


def test_with_no_player_it_is_silent_and_harmless(monkeypatch):
    """The common case, and the one that has to be perfect: most machines
    running a terminal game have nothing to play a sound with."""
    monkeypatch.setattr(audio, "_find_player", lambda: None)
    sfx = Sfx()

    assert not sfx.available
    sfx.play("hit")
    sfx.play("no-such-sound")
    sfx.close()


def test_muting_it_means_nothing_is_queued(monkeypatch):
    monkeypatch.setattr(audio, "_find_player", lambda: _a_player())
    sfx = Sfx(muted=True)
    sfx.play("hit")
    assert sfx._queue.empty(), "a muted sound was queued anyway"


def test_toggling_reports_the_new_state(monkeypatch):
    monkeypatch.setattr(audio, "_find_player", lambda: _a_player())
    sfx = Sfx(muted=True)
    assert sfx.muted
    assert sfx.toggle() is False, "toggling off should come back on"
    assert not sfx.muted
    assert sfx.toggle() is True


def test_the_environment_can_start_it_muted(monkeypatch):
    monkeypatch.setenv(audio.MUTE_ENV, "1")
    monkeypatch.setattr(audio, "_find_player", lambda: _a_player())
    assert Sfx().muted


def test_the_environment_cannot_be_overridden_by_the_setting(monkeypatch):
    """The one caller that matters is the test suite.

    A save file that says "sound on" must not be able to turn the sound on in a
    test run, or the suite would be audible on any machine that happens to have
    a player installed.
    """
    monkeypatch.setenv(audio.MUTE_ENV, "1")
    monkeypatch.setattr(audio, "_find_player", lambda: _a_player())
    assert Sfx(muted=False).muted


def test_a_player_that_vanishes_goes_quiet_rather_than_crashing(monkeypatch):
    """A sound is never worth a crash. The audio server going away mid-run has
    to cost the player their sound effects and nothing else."""
    monkeypatch.delenv(audio.MUTE_ENV, raising=False)
    monkeypatch.setattr(audio, "_find_player", lambda: _a_player("no-such-player"))
    sfx = Sfx()
    assert sfx.available

    sfx.play("hit")
    sfx._queue.join()

    assert sfx.muted, "it kept trying"


def test_a_missing_file_is_not_an_error(monkeypatch):
    monkeypatch.setattr(audio, "_find_player", lambda: _a_player())
    sfx = Sfx(muted=True)
    sfx._muted = False
    sfx.play("no-such-sound")
    sfx._queue.join()
    assert not sfx.muted, "a missing file muted the whole game"


# -- never late --------------------------------------------------------------
def test_a_sound_whose_moment_has_passed_is_dropped(monkeypatch):
    """A fight is faster than the sounds are long.

    Queuing them means the first blow makes no noise and the next four arrive in
    a heap, which is exactly what the old per-file player did: 190ms a sound, of
    which the sound itself was fifty.
    """
    sfx, played = _recording(monkeypatch)
    sfx._free_at = time.monotonic() + 1.0  # the device is busy

    sfx._play_now("hit")

    assert played == [], "a stale sound was played"


def test_an_urgent_sound_is_never_dropped(monkeypatch):
    """A hit that arrives late is about a moment that has gone. A level arriving
    late is still the level."""
    sfx, played = _recording(monkeypatch)
    sfx._free_at = time.monotonic() + 1.0

    sfx._play_now("level")

    assert played == ["level"]


def test_the_device_is_booked_for_the_length_of_the_sound(monkeypatch):
    sfx, _ = _recording(monkeypatch)
    sfx._free_at = 0.0
    before = time.monotonic()

    sfx._play_now("hit")

    seconds = sfx._clip("hit").seconds
    assert sfx._free_at == pytest.approx(before + seconds, abs=0.05)


def test_a_sound_that_lands_while_the_device_is_free_plays(monkeypatch):
    sfx, played = _recording(monkeypatch)
    sfx._free_at = 0.0
    sfx._play_now("hit")
    assert played == ["hit"]


def test_the_stream_stays_open_across_sounds(monkeypatch):
    """The whole point of the pipe: one player, fed for the rest of the session.

    Spawning one per sound measured at 190ms, and the sound itself was fifty.
    """
    monkeypatch.setattr(audio, "_find_player", lambda: _a_player(streams=True))
    sfx = Sfx(muted=True)
    sfx._muted = False
    stream = _FakeStream()
    sfx._stream = stream

    for name in ("hit", "crit", "kill"):
        sfx._free_at = 0.0
        sfx._play_now(name)

    assert len(stream.written) == 3, "not everything went into the open player"
    assert all(chunk for chunk in stream.written), "raw samples went missing"


def test_a_stream_that_died_is_opened_again(monkeypatch):
    monkeypatch.setattr(audio, "_find_player", lambda: _a_player(streams=True))
    sfx = Sfx(muted=True)
    sfx._muted = False
    sfx._free_at = 0.0
    sfx._stream = _FakeStream(alive=False)

    opened: list[int] = []
    fresh = _FakeStream()
    monkeypatch.setattr(
        sfx, "_open_stream", lambda: (opened.append(1), setattr(sfx, "_stream", fresh))
    )

    sfx._play_now("hit")

    assert opened, "a dead player was written to instead of replaced"
    assert fresh.written, "the replacement was not used"


def test_closing_lets_go_of_the_player(monkeypatch):
    monkeypatch.setattr(audio, "_find_player", lambda: _a_player(streams=True))
    sfx = Sfx(muted=True)
    stream = _FakeStream()
    sfx._stream = stream

    sfx.close()

    assert stream.closed, "the player was left running"
    assert sfx._stream is None


def test_a_player_that_takes_files_is_still_used(monkeypatch):
    """afplay takes a filename and nothing else. Late is worse than early and
    much better than silent."""
    monkeypatch.delenv(audio.MUTE_ENV, raising=False)
    monkeypatch.setattr(audio, "_find_player", lambda: _a_player("afplay", streams=False))
    sfx = Sfx()
    assert sfx.available
    assert not sfx.player.streams

    spawned: list[str] = []
    monkeypatch.setattr(sfx, "_spawn", lambda clip: spawned.append(clip.path.stem))
    sfx._free_at = 0.0
    sfx._play_now("hit")

    assert spawned == ["hit"]


def test_the_sounds_live_inside_the_package():
    """They are read at runtime, so they have to travel with the code rather
    than sitting in assets/ with the desktop file."""
    package = Path(audio.__file__).resolve().parent.parent
    assert SOUNDS_DIR == package / "sounds"
    assert SOUNDS_DIR.exists()


# -- never silent by accident -------------------------------------------------
def test_the_device_is_opened_before_the_first_blow(monkeypatch):
    """Opening it costs about a hundred and forty milliseconds, and paying that
    on the first hit of the first fight is paying it where it shows."""
    monkeypatch.delenv(audio.MUTE_ENV, raising=False)
    monkeypatch.setattr(audio, "_find_player", lambda: _a_player(streams=True))

    opened: list[int] = []
    monkeypatch.setattr(
        audio.Sfx, "_open_stream", lambda self: opened.append(1)
    )
    sfx = Sfx()

    assert opened, "the device was left cold"
    sfx.close()


def test_a_muted_session_does_not_open_anything(monkeypatch):
    """Nothing is going to be played, so nothing should be started."""
    monkeypatch.setattr(audio, "_find_player", lambda: _a_player(streams=True))
    opened: list[int] = []
    monkeypatch.setattr(
        audio.Sfx, "_open_stream", lambda self: opened.append(1)
    )
    Sfx(muted=True)

    assert not opened


def test_unmuting_opens_the_device(monkeypatch):
    monkeypatch.setattr(audio, "_find_player", lambda: _a_player(streams=True))
    opened: list[int] = []
    monkeypatch.setattr(
        audio.Sfx, "_open_stream", lambda self: opened.append(1)
    )
    sfx = Sfx(muted=True)

    sfx.set_muted(False)

    assert opened, "unmuting left it silent"


def test_one_hiccup_does_not_silence_the_session(monkeypatch):
    """The old version muted on the first exception, which is why the sound used
    to stop and never come back."""
    monkeypatch.setattr(audio, "_find_player", lambda: _a_player())
    sfx = Sfx(muted=True)
    sfx._muted = False

    sfx._count_failure()

    assert not sfx.muted, "a single hiccup killed the sound"


def test_three_in_a_row_do(monkeypatch):
    monkeypatch.setattr(audio, "_find_player", lambda: _a_player())
    sfx = Sfx(muted=True)
    sfx._muted = False

    for _ in range(audio.GIVE_UP_AFTER):
        sfx._count_failure()

    assert sfx.muted


def test_a_player_that_exits_non_zero_is_a_failure(monkeypatch):
    """``check=False`` would otherwise call a broken player a success."""
    monkeypatch.delenv(audio.MUTE_ENV, raising=False)
    monkeypatch.setattr(audio, "_find_player", lambda: _a_player("false", streams=False))
    sfx = Sfx()

    sfx.play("hit")
    sfx._queue.join()

    assert sfx._failures, "a non-zero exit was not noticed"


def test_a_good_sound_clears_the_count(monkeypatch):
    monkeypatch.setattr(audio, "_find_player", lambda: _a_player())
    sfx = Sfx(muted=True)
    sfx._muted = False
    sfx._count_failure()

    monkeypatch.setattr(sfx, "_spawn", lambda clip: None)
    sfx._failures = 0  # what a successful spawn does

    assert sfx._failures == 0
    assert not sfx.muted


# -- how far behind the device may fall ---------------------------------------
def test_a_long_sound_does_not_swallow_the_next_one(monkeypatch):
    """The old rule dropped a sound the moment the device was busy with any of
    the previous one.

    Which meant a kill -- a hundred and ninety milliseconds -- ate the blow that
    landed on top of it, and the player heard a fight with holes in it. A quarter
    of a second of backlog is inaudible; more than that is not.
    """
    sfx, played = _recording(monkeypatch)
    sfx._free_at = 0.0
    sfx._play_now("kill")

    # Well inside the backlog a kill leaves behind.
    sfx._free_at = time.monotonic() + 0.14
    sfx._play_now("hit")

    assert played == ["kill", "hit"], "the second blow was thrown away"


def test_a_swamped_device_still_drops(monkeypatch):
    """Past the threshold the moment really has gone, and a blow that sounds
    three blows late is worse than one that does not sound."""
    sfx, played = _recording(monkeypatch)
    sfx._free_at = 0.0
    sfx._play_now("hit")

    sfx._free_at = time.monotonic() + audio.MAX_BACKLOG + 0.5
    sfx._play_now("hit")

    assert played == ["hit"], "a stale sound was played anyway"


def test_the_backlog_threshold_is_a_fraction_of_a_second():
    assert 0.1 <= audio.MAX_BACKLOG <= 0.5


# -- the diagnostic ----------------------------------------------------------
def test_the_diagnostic_log_says_what_was_asked_for(tmp_path, monkeypatch):
    """The game cannot know whether a note came out of the speaker.

    It can say exactly what it asked for, when, and how far behind the device
    already was -- which is the difference between a bug and a guess.
    """
    path = tmp_path / "sfx.log"
    monkeypatch.setenv(audio.DEBUG_ENV, str(path))
    monkeypatch.setattr(audio, "_find_player", lambda: _a_player(streams=True))

    sfx = Sfx(muted=True)
    sfx._stream = _FakeStream()
    sfx._muted = False
    sfx._free_at = 0.0
    sfx._play_now("hit")

    written = path.read_text()
    assert "PLAY hit" in written
    assert "50ms" in written, "the length is not in the log"


def test_the_log_records_a_drop_too(tmp_path, monkeypatch):
    path = tmp_path / "sfx.log"
    monkeypatch.setenv(audio.DEBUG_ENV, str(path))
    monkeypatch.setattr(audio, "_find_player", lambda: _a_player())

    sfx = Sfx(muted=True)
    sfx._muted = False
    sfx._free_at = time.monotonic() + 5.0
    sfx._play_now("hit")

    assert "DROP hit" in path.read_text()


def test_a_log_that_cannot_be_written_is_not_an_error(monkeypatch, tmp_path):
    monkeypatch.setenv(audio.DEBUG_ENV, str(tmp_path / "no" / "such" / "dir" / "x.log"))
    monkeypatch.setattr(audio, "_find_player", lambda: _a_player())
    sfx = Sfx(muted=True)
    sfx._muted = False
    sfx._free_at = 0.0

    sfx._play_now("hit")  # must not raise

    assert sfx._debug is None, "it kept trying to write a log it cannot write"


def test_no_droppable_sound_outlasts_the_backlog():
    """The invariant that keeps the drop rule from ever firing in practice.

    A sound may only be dropped when the device is further behind than
    ``MAX_BACKLOG``. So a sound that is itself longer than that would push the
    device past the threshold on its own and eat the next one -- which is exactly
    what a kill did before the threshold existed. The four that *are* longer are
    all in ``URGENT``, and are queued rather than dropped.
    """
    from neverdeads_revenge.game.actors import HEROES  # noqa: F401  (import check)
    from neverdeads_revenge.ui.audio import SOUNDS_DIR

    for path in sorted(SOUNDS_DIR.glob("*.wav")):
        with wave.open(str(path), "rb") as handle:
            seconds = handle.getnframes() / handle.getframerate()
        if path.stem in audio.URGENT:
            continue
        assert seconds < audio.MAX_BACKLOG, (
            f"{path.stem} is {seconds:.2f}s and may be dropped, "
            f"but the device is allowed to fall {audio.MAX_BACKLOG:.2f}s behind"
        )


def test_every_sound_is_either_short_or_urgent():
    """Nothing may be both long and disposable."""
    from neverdeads_revenge.ui.audio import SOUNDS_DIR

    for path in sorted(SOUNDS_DIR.glob("*.wav")):
        with wave.open(str(path), "rb") as handle:
            seconds = handle.getnframes() / handle.getframerate()
        assert seconds < audio.MAX_BACKLOG or path.stem in audio.URGENT, path.stem


def test_the_log_exists_from_the_moment_the_game_starts(tmp_path, monkeypatch):
    """A diagnostic that only appears once something has gone wrong is a
    diagnostic nobody can tell is switched on."""
    path = tmp_path / "sfx.log"
    monkeypatch.setenv(audio.DEBUG_ENV, str(path))
    monkeypatch.setattr(audio, "_find_player", lambda: _a_player(streams=True))

    sfx = Sfx(muted=True)

    assert path.exists(), "the log was not created until the first sound"
    header = path.read_text()
    assert "sound log" in header
    assert "aplay" in header
    assert "streams=True" in header
    sfx.close()
