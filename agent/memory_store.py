"""Architectural Memory for XYZ - persistent knowledge across sessions."""

import os
import json
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Optional

from xyz.config import XYZ_DIR


MEMORY_DB = XYZ_DIR / "memory.db"
MEMORY_MD = XYZ_DIR / "memory.md"


def _get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(MEMORY_DB))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL DEFAULT 'general',
            rule TEXT NOT NULL UNIQUE,
            source TEXT DEFAULT '',
            created TEXT NOT NULL,
            updated TEXT NOT NULL,
            weight INTEGER DEFAULT 1
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS preferences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT NOT NULL UNIQUE,
            value TEXT NOT NULL,
            created TEXT NOT NULL,
            updated TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn


def remember_rule(rule: str, category: str = "general", source: str = "") -> dict:
    """Store a learned rule about the codebase."""
    conn = _get_db()
    now = datetime.now().isoformat()
    try:
        conn.execute(
            "INSERT INTO rules (category, rule, source, created, updated) VALUES (?, ?, ?, ?, ?)",
            (category, rule, source, now, now),
        )
        conn.commit()
        return {"status": "remembered", "rule": rule[:80]}
    except sqlite3.IntegrityError:
        conn.execute(
            "UPDATE rules SET updated = ?, weight = weight + 1 WHERE rule = ?",
            (now, rule),
        )
        conn.commit()
        return {"status": "reinforced", "rule": rule[:80]}
    finally:
        conn.close()


def forget_rule(rule: str) -> dict:
    """Remove a learned rule."""
    conn = _get_db()
    try:
        cur = conn.execute("DELETE FROM rules WHERE rule = ?", (rule,))
        conn.commit()
        deleted = cur.rowcount > 0
        return {"status": "forgotten" if deleted else "not_found"}
    finally:
        conn.close()


def list_rules(category: Optional[str] = None) -> list[dict]:
    """List all learned rules, optionally filtered by category."""
    conn = _get_db()
    try:
        if category:
            cur = conn.execute(
                "SELECT category, rule, source, created, weight FROM rules WHERE category = ? ORDER BY weight DESC",
                (category,),
            )
        else:
            cur = conn.execute(
                "SELECT category, rule, source, created, weight FROM rules ORDER BY weight DESC"
            )
        return [
            {"category": row[0], "rule": row[1], "source": row[2], "created": row[3], "weight": row[4]}
            for row in cur.fetchall()
        ]
    finally:
        conn.close()


def get_memory_context(max_rules: int = 20) -> str:
    """Get a formatted string of learned rules for the system prompt."""
    rules = list_rules()
    if not rules:
        return ""

    lines = ["[Architectural Memory]", "Learned rules about this codebase:"]
    for r in rules[:max_rules]:
        lines.append(f"- [{r['category']}] {r['rule']}")
    return "\n".join(lines)


def set_preference(key: str, value: str) -> dict:
    """Store a user preference."""
    conn = _get_db()
    now = datetime.now().isoformat()
    try:
        conn.execute(
            "INSERT INTO preferences (key, value, created, updated) VALUES (?, ?, ?, ?)",
            (key, value, now, now),
        )
        conn.commit()
        return {"status": "set", "key": key, "value": value}
    except sqlite3.IntegrityError:
        conn.execute(
            "UPDATE preferences SET value = ?, updated = ? WHERE key = ?",
            (value, now, key),
        )
        conn.commit()
        return {"status": "updated", "key": key, "value": value}
    finally:
        conn.close()


def get_preference(key: str) -> Optional[str]:
    """Get a stored preference."""
    conn = _get_db()
    try:
        cur = conn.execute("SELECT value FROM preferences WHERE key = ?", (key,))
        row = cur.fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def export_memory_to_md() -> str:
    """Export architectural memory to markdown file."""
    rules = list_rules()
    conn = _get_db()
    try:
        cur = conn.execute("SELECT key, value, created, updated FROM preferences")
        prefs = cur.fetchall()
    finally:
        conn.close()

    lines = ["# XYZ Architectural Memory", f"# Generated: {datetime.now().isoformat()[:19]}", ""]

    if rules:
        lines.append("## Learned Rules")
        for r in rules:
            lines.append(f"- **[{r['category']}]** {r['rule']} *({r['source']})*")
        lines.append("")

    if prefs:
        lines.append("## Preferences")
        for p in prefs:
            lines.append(f"- **{p[0]}**: {p[1]}")
        lines.append("")

    content = "\n".join(lines)
    MEMORY_MD.write_text(content)
    return content
