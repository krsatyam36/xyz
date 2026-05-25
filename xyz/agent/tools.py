import os
import json
import re
import shutil
import subprocess
import hashlib
import shlex
import logging
from pathlib import Path
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file. Supports reading specific line ranges for large files.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to read"},
                    "offset": {"type": "integer", "description": "Line number to start from (1-indexed)", "default": None},
                    "limit": {"type": "integer", "description": "Maximum number of lines to read", "default": None},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Create a new file or overwrite an existing one.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to write"},
                    "content": {"type": "string", "description": "Content to write"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "Perform precise edits to files by replacing exact text matches. The primary way to modify code.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to edit"},
                    "old_string": {"type": "string", "description": "The exact text to replace"},
                    "new_string": {"type": "string", "description": "The text to replace it with"},
                },
                "required": ["path", "old_string", "new_string"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "apply_patch",
            "description": "Apply a patch/diff to files. Uses unified diff format.",
            "parameters": {
                "type": "object",
                "properties": {
                    "patch_text": {"type": "string", "description": "The patch text in unified diff format"},
                },
                "required": ["patch_text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "List files and directories in a path",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path to list"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "execute_shell",
            "description": "Execute a shell command and return the output",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Shell command to execute"},
                    "description": {"type": "string", "description": "Clear description of what this command does", "default": ""},
                    "timeout": {"type": "integer", "description": "Timeout in milliseconds", "default": 60000},
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grep_files",
            "description": "Search file contents using regular expressions. Fast content search across the codebase.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Regex pattern to search for"},
                    "path": {"type": "string", "description": "Directory to search in", "default": "."},
                    "include": {"type": "string", "description": "File pattern to include (e.g. *.py, *.{ts,tsx})", "default": None},
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "glob_files",
            "description": "Find files by pattern matching using glob patterns like **/*.js or src/**/*.ts",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Glob pattern to match files against"},
                    "path": {"type": "string", "description": "Directory to search in", "default": "."},
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_files",
            "description": "Legacy search for patterns in files using grep. Prefer grep_files for newer usage.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Search pattern"},
                    "path": {"type": "string", "description": "Directory to search in", "default": "."},
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "webfetch",
            "description": "Fetch and read web page content from a URL",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The URL to fetch content from"},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "websearch",
            "description": "Search the web for information. Use for finding current events or information beyond training data.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "preview_diff",
            "description": "Preview changes before applying them. Shows a visual diff of proposed modifications.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to preview changes for"},
                    "new_content": {"type": "string", "description": "Proposed new content"},
                },
                "required": ["path", "new_content"],
            },
        },
    },
]

READ_LIMIT = 10000
SHELL_TIMEOUT = 60
SEARCH_LIMIT = 10000
MAX_PATH_DEPTH = 5


def _validate_path(path: str, allow_parent: bool = False) -> tuple[bool, str]:
    """Validate that path is safe and within working directory."""
    try:
        p = Path(path).resolve()
        cwd = Path.cwd().resolve()
        
        # Check if path is within working directory or subdirectories
        try:
            p.relative_to(cwd)
        except ValueError:
            if not allow_parent:
                return False, f"Path '{path}' is outside working directory"
        
        return True, ""
    except Exception as e:
        return False, f"Invalid path: {str(e)}"


def read_file(path: str, offset: Optional[int] = None, limit: Optional[int] = None) -> dict:
    """Read file contents with optional validation."""
    valid, error = _validate_path(path)
    if not valid:
        return {"error": error}
    
    try:
        p = Path(path).resolve()
        if not p.exists():
            return {"error": f"File not found: {path}"}
        if not p.is_file():
            return {"error": f"Not a file: {path}"}

        content = p.read_text()

        if offset is not None or limit is not None:
            lines = content.splitlines(keepends=True)
            start = (offset - 1) if offset else 0
            end = start + limit if limit else len(lines)
            content = "".join(lines[start:end])

        truncated = len(content) > READ_LIMIT

        return {
            "path": str(p),
            "size": len(content),
            "content": content[:READ_LIMIT],
            "truncated": truncated,
            "lines": len(content.splitlines()),
        }
    except Exception as e:
        logger.error(f"Error reading file {path}: {e}")
        return {"error": str(e)}


def write_file(path: str, content: str) -> dict:
    """Write file with validation."""
    valid, error = _validate_path(path)
    if not valid:
        return {"error": error}
    
    try:
        p = Path(path).resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        old_content = None
        if p.exists():
            old_content = p.read_text()
        p.write_text(content)
        logger.info(f"Wrote file: {p}")
        return {
            "path": str(p),
            "status": "created" if not old_content else "modified",
            "size": len(content),
            "old_content": old_content,
        }
    except Exception as e:
        logger.error(f"Error writing file {path}: {e}")
        return {"error": str(e)}


def edit_file(path: str, old_string: str, new_string: str) -> dict:
    """Edit file with validation."""
    valid, error = _validate_path(path)
    if not valid:
        return {"error": error}
    
    try:
        p = Path(path).resolve()
        if not p.exists():
            return {"error": f"File not found: {path}"}
        content = p.read_text()

        if old_string not in content:
            return {"error": f"oldString not found in content. The text '{old_string[:50]}...' was not found in {path}"}

        if content.count(old_string) > 1:
            return {"error": "Found multiple matches for oldString. Provide more surrounding context to identify the correct match."}

        new_content = content.replace(old_string, new_string, 1)
        p.write_text(new_content)
        logger.info(f"Edited file: {p}")
        return {
            "path": str(p),
            "status": "modified",
            "size": len(new_content),
            "old_content": old_string,
        }
    except Exception as e:
        logger.error(f"Error editing file {path}: {e}")
        return {"error": str(e)}


def apply_patch(patch_text: str) -> dict:
    """Apply patch with validation."""
    try:
        temp_patch = Path("/tmp") / f"xyz_patch_{hashlib.md5(patch_text.encode()).hexdigest()[:8]}"
        temp_patch.write_text(patch_text)
        result = subprocess.run(
            ["patch", "-p0", "-i", str(temp_patch)],
            capture_output=True, text=True, timeout=30
        )
        temp_patch.unlink(missing_ok=True)
        if result.returncode == 0:
            logger.info("Patch applied successfully")
            return {"status": "applied", "output": result.stdout.strip()}
        return {"error": result.stderr.strip() or result.stdout.strip()}
    except Exception as e:
        logger.error(f"Error applying patch: {e}")
        return {"error": str(e)}


def list_directory(path: str) -> dict:
    """List directory with validation."""
    valid, error = _validate_path(path)
    if not valid:
        return {"error": error}
    
    try:
        p = Path(path).resolve()
        if not p.exists():
            return {"error": f"Directory not found: {path}"}
        if not p.is_dir():
            return {"error": f"Not a directory: {path}"}
        entries = []
        for entry in sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name)):
            entries.append({
                "name": entry.name,
                "type": "directory" if entry.is_dir() else "file",
                "size": entry.stat().st_size if entry.is_file() else 0,
                "modified": datetime.fromtimestamp(entry.stat().st_mtime).isoformat()[:19],
            })
        return {"path": str(p), "entries": entries, "count": len(entries)}
    except Exception as e:
        logger.error(f"Error listing directory {path}: {e}")
        return {"error": str(e)}


def execute_shell(command: str, description: str = "", timeout: int = 60000) -> dict:
    """Execute shell command safely."""
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout / 1000,
            cwd=os.getcwd(),
        )
        stdout = result.stdout[:SEARCH_LIMIT]
        stderr = result.stderr[:SEARCH_LIMIT]
        logger.info(f"Executed command: {command[:100]}...")
        return {
            "command": command,
            "returncode": result.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "truncated": len(result.stdout) > SEARCH_LIMIT or len(result.stderr) > SEARCH_LIMIT,
        }
    except subprocess.TimeoutExpired:
        logger.error(f"Command timed out: {command}")
        return {"error": f"Command timed out after {timeout/1000}s: {command}"}
    except Exception as e:
        logger.error(f"Error executing command: {e}")
        return {"error": str(e)}


def grep_files(pattern: str, path: str = ".", include: Optional[str] = None) -> dict:
    """Search files safely with escaped patterns."""
    valid, error = _validate_path(path)
    if not valid:
        return {"error": error}
    
    try:
        # Escape pattern for shell safety
        escaped_pattern = shlex.quote(pattern)
        escaped_path = shlex.quote(path)
        
        cmd = f"grep -r {escaped_pattern} {escaped_path}"
        if include:
            for ext in include.split(","):
                cmd += f" --include={shlex.quote(ext.strip())}"
        cmd += " -l 2>/dev/null"

        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        files = [f for f in result.stdout.strip().split("\n") if f] if result.stdout.strip() else []

        logger.info(f"Grep found {len(files)} files matching pattern")
        return {
            "pattern": pattern,
            "files": files[:200],
            "count": len(files),
            "truncated": len(files) > 200,
        }
    except Exception as e:
        logger.error(f"Error searching files: {e}")
        return {"error": str(e)}


def glob_files(pattern: str, path: str = ".") -> dict:
    """Find files by pattern."""
    valid, error = _validate_path(path)
    if not valid:
        return {"error": error}
    
    try:
        import glob as glob_module
        search_path = os.path.join(path, pattern) if path != "." else pattern
        matches = sorted(glob_module.glob(search_path, recursive=True))
        matches = [m for m in matches if os.path.isfile(m)]

        logger.info(f"Glob found {len(matches)} files matching pattern")
        return {
            "pattern": pattern,
            "files": matches[:200],
            "count": len(matches),
            "truncated": len(matches) > 200,
        }
    except Exception as e:
        logger.error(f"Error globbing files: {e}")
        return {"error": str(e)}


def search_files(pattern: str, path: str = ".") -> dict:
    """Legacy file search."""
    return grep_files(pattern=pattern, path=path)


def webfetch(url: str) -> dict:
    """Fetch web content."""
    try:
        import httpx
        resp = httpx.get(url, timeout=30.0, follow_redirects=True)
        if resp.status_code == 200:
            content_type = resp.headers.get("content-type", "")
            text = resp.text
            logger.info(f"Fetched URL: {url}")
            return {
                "url": url,
                "status_code": resp.status_code,
                "content": text[:SEARCH_LIMIT],
                "truncated": len(text) > SEARCH_LIMIT,
                "content_type": content_type,
            }
        return {"error": f"HTTP {resp.status_code}: {resp.reason_phrase}"}
    except Exception as e:
        logger.error(f"Error fetching URL: {e}")
        return {"error": str(e)}


def websearch(query: str) -> dict:
    """Search the web."""
    try:
        import httpx
        resp = httpx.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query},
            timeout=15.0,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        if resp.status_code == 200:
            from html.parser import HTMLParser

            class ResultParser(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.results = []
                    self._capture = False
                    self._text = ""

                def handle_starttag(self, tag, attrs):
                    attrs_dict = dict(attrs)
                    if tag == "a" and "result__a" in attrs_dict.get("class", ""):
                        self._capture = True
                        self._text = ""

                def handle_data(self, data):
                    if self._capture:
                        self._text += data

                def handle_endtag(self, tag):
                    if self._capture and tag == "a":
                        self.results.append(self._text.strip())
                        self._capture = False

            parser = ResultParser()
            parser.feed(resp.text)
            results = parser.results[:20]

            logger.info(f"Web search found {len(results)} results for: {query}")
            return {
                "query": query,
                "results": results,
                "count": len(results),
            }
        return {"error": f"Search failed: HTTP {resp.status_code}"}
    except Exception as e:
        logger.error(f"Error searching web: {e}")
        return {"error": str(e)}


def preview_diff(path: str, new_content: str) -> dict:
    """Preview changes before applying."""
    valid, error = _validate_path(path)
    if not valid:
        return {"error": error}
    
    try:
        import difflib
        p = Path(path).resolve()
        if p.exists():
            old_content = p.read_text()
        else:
            old_content = ""
        
        diff = difflib.unified_diff(
            old_content.splitlines(keepends=True),
            new_content.splitlines(keepends=True),
            fromfile=f"{path} (original)",
            tofile=f"{path} (modified)",
            lineterm="",
        )
        diff_text = "\n".join(diff)
        
        logger.info(f"Generated diff for: {path}")
        return {
            "path": str(p),
            "has_changes": old_content != new_content,
            "diff": diff_text[:SEARCH_LIMIT],
            "truncated": len(diff_text) > SEARCH_LIMIT,
        }
    except Exception as e:
        logger.error(f"Error previewing diff: {e}")
        return {"error": str(e)}


TOOL_REGISTRY = {
    "read_file": read_file,
    "write_file": write_file,
    "edit_file": edit_file,
    "apply_patch": apply_patch,
    "list_directory": list_directory,
    "execute_shell": execute_shell,
    "grep_files": grep_files,
    "glob_files": glob_files,
    "search_files": search_files,
    "webfetch": webfetch,
    "websearch": websearch,
    "preview_diff": preview_diff,
}
