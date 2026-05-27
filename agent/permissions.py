"""Human-In-The-Loop (HITL) Permission Tiers for XYZ."""

import re
from typing import Optional
from dataclasses import dataclass

AUTO_APPROVE_COMMANDS = [
    "ls", "pwd", "cd", "cat", "head", "tail", "wc",
    "grep", "find", "which", "whoami", "uname", "echo", "date",
    "git status", "git log", "git diff", "git branch", "git show",
    "pip list", "pip show", "python --version",
    "hostname", "df", "du", "env", "printenv",
    "pytest", "ruff", "mypy", "flake8",
    "mkdir", "touch", "cp", "mv",
    "make", "cmake", "ninja",
]

ASK_COMMANDS = [
    "pip install", "pip3 install", "npm install", "pip uninstall",
    "rm", "rmdir", "git push", "git commit", "git reset",
    "git merge", "git rebase", "git checkout -b", "git branch -d",
    "git tag", "git fetch", "git pull",
    "docker", "kubectl", "helm",
    "chmod", "chown", "kill", "pkill",
    "systemctl", "service", "journalctl",
    "wget", "curl", "apt", "apt-get", "brew", "yum", "dnf",
]

DENY_REGEX_PATTERNS = [
    r"^\s*rm\s+(-rf?|--recursive|--force)\s+/($|\s)",
    r"^\s*sudo\s",
    r"^\s*shutdown\b",
    r"^\s*reboot\b",
    r"^\s*mkfs\b",
    r"^\s*dd\s+if=",
    r"^\s*:\(\s*\{\s*:|:&\s*\};:",
    r"^\s*>\s*/dev/sd",
    r"^\s*>\s*/dev/hd",
    r"^\s*mv\s+/\s",
    r"^\s*format\s",
    r"wget\s+.*\|\s*(sh|bash)",
    r"curl\s+.*\|\s*(sh|bash)",
    r"chmod\s+777\s+/($|\s)",
]


@dataclass
class PermissionResult:
    tier: str
    reason: str = ""
    command: str = ""

    def allow_auto(self) -> bool:
        return self.tier == "auto"

    def needs_ask(self) -> bool:
        return self.tier == "ask"

    def is_denied(self) -> bool:
        return self.tier == "deny"


def classify_command(command: str) -> PermissionResult:
    cmd_stripped = command.strip()
    cmd_lower = cmd_stripped.lower()

    # Check deny patterns first (regex)
    for pattern in DENY_REGEX_PATTERNS:
        if re.search(pattern, cmd_stripped, re.IGNORECASE):
            return PermissionResult(tier="deny", reason=f"Command is denied", command=cmd_stripped)

    # Check ask patterns
    for pattern in ASK_COMMANDS:
        if cmd_lower.startswith(pattern.lower()):
            return PermissionResult(tier="ask", reason=f"Needs approval: {pattern}", command=cmd_stripped)

    # Check auto-approve patterns
    for prefix in AUTO_APPROVE_COMMANDS:
        if cmd_lower.startswith(prefix.lower()):
            return PermissionResult(tier="auto", reason="Auto-approved", command=cmd_stripped)

    return PermissionResult(tier="ask", reason="Unknown command needs approval", command=cmd_stripped)
