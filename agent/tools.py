import os
import json
import shutil
from pathlib import Path
from typing import Optional
from datetime import datetime


TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to read"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file. Creates the file if it doesn't exist, overwrites if it does.",
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
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_files",
            "description": "Search for a pattern in files",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Search pattern"},
                    "path": {"type": "string", "description": "Directory to search in"},
                },
                "required": ["pattern"],
            },
        },
    },
]


def read_file(path: str) -> dict:
    try:
        p = Path(path).resolve()
        if not p.exists():
            return {"error": f"File not found: {path}"}
        if not p.is_file():
            return {"error": f"Not a file: {path}"}
        content = p.read_text()
        return {
            "path": str(p),
            "size": len(content),
            "content": content[:10000],
            "truncated": len(content) > 10000,
        }
    except Exception as e:
        return {"error": str(e)}


def write_file(path: str, content: str) -> dict:
    try:
        p = Path(path).resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        old_content = None
        if p.exists():
            old_content = p.read_text()
        p.write_text(content)
        return {
            "path": str(p),
            "status": "created" if not old_content else "modified",
            "size": len(content),
            "old_content": old_content,
        }
    except Exception as e:
        return {"error": str(e)}


def list_directory(path: str) -> dict:
    try:
        p = Path(path).resolve()
        if not p.exists():
            return {"error": f"Directory not found: {path}"}
        if not p.is_dir():
            return {"error": f"Not a directory: {path}"}
        entries = []
        for entry in p.iterdir():
            entries.append({
                "name": entry.name,
                "type": "directory" if entry.is_dir() else "file",
                "size": entry.stat().st_size if entry.is_file() else 0,
            })
        return {"path": str(p), "entries": entries, "count": len(entries)}
    except Exception as e:
        return {"error": str(e)}


def execute_shell(command: str) -> dict:
    import subprocess
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=60,
            cwd=os.getcwd(),
        )
        return {
            "command": command,
            "returncode": result.returncode,
            "stdout": result.stdout[:10000],
            "stderr": result.stderr[:5000],
            "truncated": len(result.stdout) > 10000 or len(result.stderr) > 5000,
        }
    except subprocess.TimeoutExpired:
        return {"error": f"Command timed out after 60s: {command}"}
    except Exception as e:
        return {"error": str(e)}


def search_files(pattern: str, path: str = ".") -> dict:
    import subprocess
    try:
        result = subprocess.run(
            f"grep -r '{pattern}' {path} --include='*.py' --include='*.js' --include='*.ts' --include='*.md' --include='*.json' --include='*.txt' -l",
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        files = result.stdout.strip().split("\n") if result.stdout.strip() else []
        return {"pattern": pattern, "files": files, "count": len(files)}
    except Exception as e:
        return {"error": str(e)}


TOOL_REGISTRY = {
    "read_file": read_file,
    "write_file": write_file,
    "list_directory": list_directory,
    "execute_shell": execute_shell,
    "search_files": search_files,
}
