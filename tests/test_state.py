import json
import os
from datetime import UTC, datetime

import pytest

from project_kit import fsutil
from project_kit.state import State, StateError, load_state, parse_state, save_state, state_path


def test_missing_state_gives_fresh_one(tmp_path):
    assert load_state(tmp_path) == State()


def test_roundtrip_with_ids_and_approvals(tmp_path):
    state = State(phase="plan")
    state.set_id("milestones", "m1", "7")
    state.set_id("issues", "epic-1", "42")
    state.approve("plan", datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC))
    save_state(tmp_path, state)

    loaded = load_state(tmp_path)
    assert loaded == state
    assert loaded.get_id("issues", "epic-1") == "42"
    assert loaded.get_id("issues", "missing") is None
    assert loaded.get_id("nokind", "x") is None
    assert loaded.approvals["plan"] == "2026-01-02T03:04:05+00:00"
    assert loaded.is_approved("plan") and not loaded.is_approved("handoff")


def test_file_is_stable_and_readable(tmp_path):
    state = State()
    state.set_id("b", "2", "y")
    state.set_id("a", "1", "x")
    save_state(tmp_path, state)
    text = state_path(tmp_path).read_text(encoding="utf-8")
    assert text.endswith("\n")
    assert text.index('"a"') < text.index('"b"')
    assert json.loads(text)["version"] == 1


@pytest.mark.parametrize(
    ("data", "message"),
    [
        ("not json", "not valid JSON"),
        ("[]", "must contain an object"),
        ('{"phase": "init"}', "Unsupported state.json version"),
        ('{"version": 99}', "Upgrade project-kit"),
        ('{"version": 1, "phase": "party"}', "phase must be one of"),
        ('{"version": 1, "approvals": {"party": "x"}}', "unknown phase"),
        ('{"version": 1, "provider_ids": {"issues": {"a": 1}}}', "provider_ids.issues"),
        ('{"version": 1, "provider_ids": {"issues": []}}', "provider_ids.issues"),
    ],
)
def test_invalid_state_is_rejected(data, message):
    with pytest.raises(StateError, match=message):
        parse_state(data)


def test_unknown_phase_cannot_be_approved():
    with pytest.raises(StateError):
        State().approve("party")


def test_save_refuses_invalid_state(tmp_path):
    with pytest.raises(StateError):
        save_state(tmp_path, State(phase="party"))
    assert not state_path(tmp_path).exists()


def test_interrupted_write_keeps_previous_state(tmp_path, monkeypatch):
    first = State()
    first.set_id("issues", "a", "1")
    save_state(tmp_path, first)
    before = state_path(tmp_path).read_text(encoding="utf-8")

    def boom(src, dst):
        raise OSError("killed before rename")

    monkeypatch.setattr(os, "replace", boom)
    second = State()
    second.set_id("issues", "a", "2")
    with pytest.raises(OSError, match="killed"):
        save_state(tmp_path, second)
    monkeypatch.undo()

    assert state_path(tmp_path).read_text(encoding="utf-8") == before
    assert load_state(tmp_path) == first
    assert list(state_path(tmp_path).parent.glob("*.tmp")) == []


def test_atomic_write_creates_parent_directories(tmp_path):
    target = tmp_path / "a" / "b" / "f.txt"
    fsutil.atomic_write_text(target, "hi")
    assert target.read_text(encoding="utf-8") == "hi"
