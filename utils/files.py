import os
import subprocess
from typing import Optional


def get_repo_info() -> dict:
    info = {"is_repo": False, "branch": "", "status": "", "files": []}
    try:
        result = subprocess.run(
            "git rev-parse --abbrev-ref HEAD",
            shell=True, capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            info["is_repo"] = True
            info["branch"] = result.stdout.strip()

        result = subprocess.run(
            "git status --porcelain",
            shell=True, capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            info["status"] = result.stdout.strip()
            info["files"] = [line for line in result.stdout.strip().split("\n") if line]
    except Exception:
        pass
    return info


def get_file_tree(path: str = ".", max_depth: int = 3) -> str:
    tree = []
    _build_tree(path, "", True, max_depth, tree)
    return "\n".join(tree)


def _build_tree(path: str, prefix: str, is_last: bool, max_depth: int, tree: list, current_depth: int = 0):
    if current_depth > max_depth:
        return

    name = os.path.basename(path) or path
    connector = "└── " if is_last else "├── "
    tree.append(f"{prefix}{connector}{name}")

    if os.path.isdir(path):
        try:
            entries = sorted(os.listdir(path))
            entries = [e for e in entries if not e.startswith(".") and e != "__pycache__" and e != "node_modules"]
            for i, entry in enumerate(entries):
                child_path = os.path.join(path, entry)
                is_last_child = i == len(entries) - 1
                extension = "    " if is_last else "│   "
                _build_tree(child_path, prefix + extension, is_last_child, max_depth, tree, current_depth + 1)
        except PermissionError:
            pass


def get_context_summary(path: str = ".") -> str:
    repo = get_repo_info()
    tree = get_file_tree(path, max_depth=2)

    summary = []
    summary.append(f"Working Directory: {os.path.abspath(path)}")
    if repo["is_repo"]:
        summary.append(f"Git Branch: {repo['branch']}")
        if repo["files"]:
            summary.append(f"Modified Files: {len(repo['files'])}")
    summary.append("")
    summary.append("Project Structure:")
    summary.append(tree)

    return "\n".join(summary)
