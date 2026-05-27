"""Tests for XYZ tools."""
import os
import tempfile
from pathlib import Path
from xyz.agent.tools import (
    read_file,
    write_file,
    edit_file,
    list_directory,
    grep_files,
    glob_files,
    execute_shell,
    search_files,
)


def test_write_and_read_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "test.txt")
        result = write_file(path=path, content="hello world")
        assert result["status"] == "created"
        assert result["size"] == 11

        result = read_file(path=path)
        assert result["content"] == "hello world"
        assert result["size"] == 11


def test_edit_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "test.txt")
        write_file(path=path, content="hello world\nfoo bar\nbaz qux")

        result = edit_file(path=path, old_string="foo bar", new_string="edited line")
        assert result["status"] == "modified"

        content = read_file(path=path)["content"]
        assert "edited line" in content
        assert "foo bar" not in content


def test_edit_file_not_found():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "test.txt")
        write_file(path=path, content="hello world")
        result = edit_file(path=path, old_string="not found", new_string="replace")
        assert "error" in result


def test_list_directory():
    with tempfile.TemporaryDirectory() as tmpdir:
        Path(os.path.join(tmpdir, "file1.txt")).write_text("a")
        Path(os.path.join(tmpdir, "file2.txt")).write_text("b")
        os.makedirs(os.path.join(tmpdir, "subdir"))

        result = list_directory(path=tmpdir)
        assert result["count"] == 3
        names = [e["name"] for e in result["entries"]]
        assert "file1.txt" in names
        assert "file2.txt" in names
        assert "subdir" in names


def test_grep_files():
    with tempfile.TemporaryDirectory() as tmpdir:
        Path(os.path.join(tmpdir, "a.py")).write_text("def hello():\n    pass")
        Path(os.path.join(tmpdir, "b.py")).write_text("def world():\n    pass")
        Path(os.path.join(tmpdir, "c.txt")).write_text("hello world")

        result = grep_files(pattern="hello", path=tmpdir)
        assert result["count"] >= 1
        assert any("a.py" in f or "c.txt" in f for f in result["files"])


def test_glob_files():
    with tempfile.TemporaryDirectory() as tmpdir:
        Path(os.path.join(tmpdir, "a.py")).write_text("")
        Path(os.path.join(tmpdir, "b.py")).write_text("")
        Path(os.path.join(tmpdir, "c.txt")).write_text("")

        result = glob_files(pattern="*.py", path=tmpdir)
        assert result["count"] == 2


def test_execute_shell():
    result = execute_shell(command="echo hello")
    assert result["returncode"] == 0
    assert "hello" in result["stdout"]


def test_search_files():
    with tempfile.TemporaryDirectory() as tmpdir:
        Path(os.path.join(tmpdir, "test.py")).write_text("import os\nimport sys")
        result = search_files(pattern="import", path=tmpdir)
        assert result["count"] >= 1
