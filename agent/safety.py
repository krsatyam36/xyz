import re

HARD_BLOCK_PATTERNS = [
    r'^rm\s+(-rf?|--recursive|--force)\s+/$',
    r'^rm\s+(-rf?|--recursive|--force)\s+/(\s|$)',
    r'^sudo\s',
    r'^shutdown\b',
    r'^reboot\b',
    r'^mkfs\b',
    r'^chmod\s+777\s+/$',
    r'^chmod\s+777\s+/\s',
    r'^dd\s+if=',
    r'^:()\s*\{\s*:|:&\s*\};:',
    r'^>\s*/dev/sd',
    r'^>\s*/dev/hd',
    r'^mv\s+/\s',
    r'^format\s',
    r'^del\s+/[fqs]\s+/f\s+c:\\',
    r'^wget\s+.*\|\s*(sh|bash)',
    r'^curl\s+.*\|\s*(sh|bash)',
]

HARD_BLOCK_KEYWORDS = [
    "rm -rf /",
    "rm -rf /*",
    "sudo rm",
    "mkfs",
    "shutdown -h",
    "reboot -f",
]

SAFE_COMMANDS = [
    "ls", "pwd", "cd", "cat", "head", "tail", "wc",
    "grep", "find", "which", "whoami", "uname",
    "git status", "git log", "git diff", "git branch",
    "pip list", "pip show", "python --version",
    "echo", "date", "hostname", "df", "du",
    "mkdir", "touch", "cp", "mv",
    "pip install", "pip3 install",
    "npm install", "npm run",
    "python", "python3",
    "pytest", "make",
    "curl", "wget",
]


def is_hard_blocked(command: str) -> tuple[bool, str]:
    cmd_stripped = command.strip()

    for keyword in HARD_BLOCK_KEYWORDS:
        if keyword.lower() in cmd_stripped.lower():
            return True, f"Command contains blocked pattern: '{keyword}'"

    for pattern in HARD_BLOCK_PATTERNS:
        if re.search(pattern, cmd_stripped, re.IGNORECASE):
            return True, f"Command matches blocked pattern"

    return False, ""


def is_safe_command(command: str) -> bool:
    cmd_stripped = command.strip().lower()
    for safe in SAFE_COMMANDS:
        if cmd_stripped.startswith(safe.lower()):
            return True
    return False


def needs_confirmation(command: str) -> bool:
    blocked, reason = is_hard_blocked(command)
    if blocked:
        return False

    if is_safe_command(command):
        return False

    return True
