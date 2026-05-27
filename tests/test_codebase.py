"""Tests for XYZ Codebase Context (AST + RAG)."""
import os
import tempfile
from pathlib import Path

from xyz.agent.codebase import parse_python_ast, analyze_codebase, CodeRAG, _ensure_dirs


SAMPLE_PY = '''
import os
import sys
from datetime import datetime

def greet(name: str) -> str:
    """Say hello to someone."""
    return f"Hello {name}"

class Calculator:
    """A simple calculator."""

    def add(self, a: int, b: int) -> int:
        return a + b

    def subtract(self, a: int, b: int) -> int:
        return a - b

async def fetch_data(url: str) -> dict:
    """Fetch data from a URL."""
    return {"status": "ok"}
'''


def test_parse_python_ast():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "sample.py")
        Path(path).write_text(SAMPLE_PY)
        result = parse_python_ast(path)
        assert "error" not in result
        assert result["path"] == path
        assert len(result["imports"]) >= 3
        assert len(result["functions"]) >= 2
        assert len(result["classes"]) >= 1

        # Check function details
        functions = {f["name"]: f for f in result["functions"]}
        assert "greet" in functions
        assert functions["greet"]["args"] == ["name"]
        assert "fetch_data" in functions
        assert functions["fetch_data"]["async"] is True

        # Check class details
        assert "Calculator" in {c["name"] for c in result["classes"]}
        calc = next(c for c in result["classes"] if c["name"] == "Calculator")
        assert len(calc["methods"]) == 2
        assert calc["methods"][0]["name"] == "add"
        assert calc["methods"][1]["name"] == "subtract"


def test_parse_non_python_file():
    result = parse_python_ast("/nonexistent/file.py")
    assert "error" in result


def test_parse_syntax_error():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "bad.py")
        Path(path).write_text("def broken(:")
        result = parse_python_ast(path)
        assert "error" in result


def test_analyze_codebase():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create Python files
        Path(os.path.join(tmpdir, "mod1.py")).write_text("def fn1(): pass\nclass Cls1: pass")
        Path(os.path.join(tmpdir, "mod2.py")).write_text("import os\ndef fn2(): pass")
        os.makedirs(os.path.join(tmpdir, "sub"), exist_ok=True)
        Path(os.path.join(tmpdir, "sub", "mod3.py")).write_text("class SubCls: pass")

        result = analyze_codebase(tmpdir)
        assert "error" not in result
        assert result["total_files"] >= 3
        assert result["function_count"] >= 2
        assert result["class_count"] >= 2
        assert result["import_count"] >= 1


def test_code_rag_build_and_search():
    with tempfile.TemporaryDirectory() as tmpdir:
        Path(os.path.join(tmpdir, "auth.py")).write_text("def authenticate(): pass\ndef login(): pass\nclass AuthManager: pass")
        Path(os.path.join(tmpdir, "db.py")).write_text("def connect_db(): pass\ndef query(): pass")
        original_cwd = os.getcwd()
        os.chdir(tmpdir)
        try:
            rag = CodeRAG()
            index = rag.build_index(tmpdir)
            assert "error" not in index
            stats = index.get("stats", {})
            assert stats.get("functions", 0) >= 4

            # Search for auth-related code
            results = rag.search("authenticate login")
            assert len(results) >= 1
            names = [r["name"] for r in results]
            assert "authenticate" in names or "login" in names or "AuthManager" in names

            # Search with no match
            results2 = rag.search("xyznonexistent")
            assert len(results2) >= 0
        finally:
            os.chdir(original_cwd)


def test_rag_get_relevant_context():
    with tempfile.TemporaryDirectory() as tmpdir:
        Path(os.path.join(tmpdir, "api.py")).write_text("def handle_request(): pass\ndef validate(): pass")
        original_cwd = os.getcwd()
        os.chdir(tmpdir)
        try:
            rag = CodeRAG()
            rag.build_index(tmpdir)
            ctx = rag.get_relevant_context("handle validate")
            assert "Relevant codebase context" in ctx
            assert "handle_request" in ctx or "validate" in ctx
        finally:
            os.chdir(original_cwd)


def test_ensure_dirs():
    _ensure_dirs()
    from xyz.agent.codebase import AST_CACHE_DIR, RAG_CACHE_DIR
    assert AST_CACHE_DIR.exists()
    assert RAG_CACHE_DIR.exists()
