"""Tests for XYZ Playbook system."""
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from xyz.agent.playbook import (
    Playbook, PlaybookStep,
    save_playbook, load_playbook,
    list_playbooks, delete_playbook,
    init_builtin_playbooks, BUILTIN_PLAYBOOKS,
)
from xyz.config import PLAYBOOKS_DIR


def test_playbook_model():
    pb = Playbook(
        name="test-pb",
        description="A test playbook",
        steps=[
            PlaybookStep(instruction="Step one", mode="explore"),
            PlaybookStep(instruction="Step two", mode="build"),
        ],
    )
    assert pb.name == "test-pb"
    assert len(pb.steps) == 2
    assert pb.steps[0].mode == "explore"
    assert pb.steps[1].mode == "build"


def test_save_and_load_playbook():
    pb = Playbook(
        name="test-save-load",
        description="Testing save and load",
        author="test",
        steps=[
            PlaybookStep(instruction="Do something", mode="build"),
        ],
    )
    path = save_playbook(pb)
    assert path.exists()
    assert path.suffix == ".yml"

    loaded = load_playbook("test-save-load")
    assert loaded is not None
    assert loaded.name == "test-save-load"
    assert loaded.description == "Testing save and load"
    assert len(loaded.steps) == 1
    assert loaded.steps[0].instruction == "Do something"
    assert loaded.steps[0].mode == "build"

    path.unlink(missing_ok=True)


def test_list_playbooks():
    pb1 = Playbook(name="pb-one", description="First", steps=[PlaybookStep(instruction="Step", mode="build")])
    pb2 = Playbook(name="pb-two", description="Second", steps=[PlaybookStep(instruction="Step", mode="explore")])
    save_playbook(pb1)
    save_playbook(pb2)

    pbs = list_playbooks()
    names = [p["name"] for p in pbs]
    assert "pb-one" in names
    assert "pb-two" in names

    delete_playbook("pb-one")
    delete_playbook("pb-two")


def test_delete_playbook():
    pb = Playbook(name="delete-me", description="To delete", steps=[PlaybookStep(instruction="Step", mode="build")])
    save_playbook(pb)
    assert load_playbook("delete-me") is not None
    assert delete_playbook("delete-me") is True
    assert load_playbook("delete-me") is None
    assert delete_playbook("nonexistent") is False


def test_load_nonexistent_playbook():
    pb = load_playbook("does-not-exist")
    assert pb is None


def test_playbook_step_defaults():
    step = PlaybookStep(instruction="Default mode")
    assert step.mode == "build"
    assert step.confirm is False


def test_playbook_tags():
    pb = Playbook(
        name="tagged-pb",
        description="Has tags",
        tags=["testing", "quality", "ci"],
        steps=[PlaybookStep(instruction="Run tests", mode="build")],
    )
    assert "testing" in pb.tags
    assert len(pb.tags) == 3


def test_init_builtin_playbooks():
    # Clean up any existing builtin playbooks
    for pb in BUILTIN_PLAYBOOKS:
        delete_playbook(pb.name)

    count = init_builtin_playbooks()
    assert count == len(BUILTIN_PLAYBOOKS)

    # Second call should not create duplicates
    count2 = init_builtin_playbooks()
    assert count2 == 0

    # Verify all builtin playbooks are loadable
    for pb in BUILTIN_PLAYBOOKS:
        loaded = load_playbook(pb.name)
        assert loaded is not None
        assert loaded.name == pb.name
        assert len(loaded.steps) == len(pb.steps)

    # Cleanup
    for pb in BUILTIN_PLAYBOOKS:
        delete_playbook(pb.name)


def test_playbook_serialization_roundtrip():
    pb = Playbook(
        name="roundtrip-test",
        description="Round trip test",
        author="test-author",
        version="2.0.0",
        tags=["tag1", "tag2"],
        steps=[
            PlaybookStep(instruction="Step A", mode="explore"),
            PlaybookStep(instruction="Step B", mode="plan"),
            PlaybookStep(instruction="Step C", mode="build", confirm=True),
        ],
    )
    save_playbook(pb)
    loaded = load_playbook("roundtrip-test")
    assert loaded.name == "roundtrip-test"
    assert loaded.author == "test-author"
    assert loaded.version == "2.0.0"
    assert loaded.tags == ["tag1", "tag2"]
    assert len(loaded.steps) == 3
    assert loaded.steps[2].confirm is True
    delete_playbook("roundtrip-test")
