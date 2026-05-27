"""Tests for XYZ Architectural Memory."""
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from xyz.agent.memory_store import (
    remember_rule, forget_rule, list_rules,
    get_memory_context, set_preference, get_preference,
    export_memory_to_md, MEMORY_DB, MEMORY_MD,
)


def test_remember_and_list_rules():
    # Clean slate
    if MEMORY_DB.exists():
        MEMORY_DB.unlink()

    result = remember_rule("Use Pydantic v2 for validation", category="style", source="user")
    assert result["status"] == "remembered"

    result2 = remember_rule("Always use absolute imports", category="style")
    assert result2["status"] == "remembered"

    rules = list_rules()
    assert len(rules) >= 2
    categories = [r["category"] for r in rules]
    assert "style" in categories


def test_remember_duplicate_reinforces():
    if MEMORY_DB.exists():
        MEMORY_DB.unlink()

    remember_rule("Test rule", category="test")
    result = remember_rule("Test rule", category="test")
    assert result["status"] == "reinforced"


def test_forget_rule():
    if MEMORY_DB.exists():
        MEMORY_DB.unlink()

    remember_rule("Rule to forget", category="test")
    result = forget_rule("Rule to forget")
    assert result["status"] == "forgotten"

    result = forget_rule("Nonexistent rule")
    assert result["status"] == "not_found"


def test_list_rules_by_category():
    if MEMORY_DB.exists():
        MEMORY_DB.unlink()

    remember_rule("Style rule", category="style")
    remember_rule("Security rule", category="security")

    style_rules = list_rules(category="style")
    assert len(style_rules) >= 1
    assert style_rules[0]["category"] == "style"

    security_rules = list_rules(category="security")
    assert len(security_rules) >= 1


def test_get_memory_context():
    if MEMORY_DB.exists():
        MEMORY_DB.unlink()

    ctx = get_memory_context()
    assert ctx == "" or ctx is None

    remember_rule("Test memory context", category="general")
    ctx = get_memory_context()
    assert "Architectural Memory" in ctx
    assert "Test memory context" in ctx


def test_set_and_get_preference():
    if MEMORY_DB.exists():
        MEMORY_DB.unlink()

    result = set_preference("theme", "dark")
    assert result["status"] == "set"
    assert result["key"] == "theme"

    result = set_preference("theme", "light")
    assert result["status"] == "updated"

    value = get_preference("theme")
    assert value == "light"

    value = get_preference("nonexistent")
    assert value is None


def test_export_memory_to_md():
    if MEMORY_DB.exists():
        MEMORY_DB.unlink()

    remember_rule("Export test rule", category="test", source="user")
    set_preference("editor", "vim")

    content = export_memory_to_md()
    assert "XYZ Architectural Memory" in content
    assert "Export test rule" in content
    assert "editor" in content
    assert MEMORY_MD.exists()
