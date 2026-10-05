"""Shared test setup.

The one thing that has to happen before anything else: point the save file at a
throwaway directory. ``persistence`` reads ``NEVERDEADS_REVENGE_HOME`` first, and
without this every UI test would read and *write* the real
``~/.local/share/neverdeads_revenge/meta.json`` -- so running the suite would
quietly rewrite the player's high score.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _isolated_save_file(tmp_path_factory, monkeypatch):
    home = tmp_path_factory.mktemp("neverdeads-home")
    monkeypatch.setenv("NEVERDEADS_REVENGE_HOME", str(home))
    yield home
