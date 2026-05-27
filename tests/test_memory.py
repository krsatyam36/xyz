"""Tests for XYZ session memory."""
from xyz.agent.memory import SessionMemory


def test_session_creation():
    session = SessionMemory()
    assert session.id is not None
    assert session.messages == []
    assert session.file_history == {}


def test_add_message():
    session = SessionMemory()
    session.add_message("user", "hello")
    assert len(session.messages) == 1
    assert session.messages[0]["role"] == "user"
    assert session.messages[0]["content"] == "hello"


def test_get_messages():
    session = SessionMemory()
    session.add_message("user", "q1")
    session.add_message("assistant", "a1")
    msgs = session.get_messages()
    assert len(msgs) == 2


def test_track_file_write():
    session = SessionMemory()
    session.track_file_write("/tmp/test.txt", "old content")
    assert "/tmp/test.txt" in session.file_history
    assert session.file_history["/tmp/test.txt"] == ["old content"]


def test_undo_last_write():
    session = SessionMemory()
    session.track_file_write("/tmp/test.txt", "v1")
    session.track_file_write("/tmp/test.txt", "v2")
    assert session.undo_last_write("/tmp/test.txt") == "v2"
    assert session.undo_last_write("/tmp/test.txt") == "v1"
    assert session.undo_last_write("/tmp/test.txt") is None
