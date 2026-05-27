"""Playbook system for XYZ - reusable multi-step AI agent workflows."""

import os
import json
import yaml
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field

from xyz.config import PLAYBOOKS_DIR


class PlaybookStep(BaseModel):
    instruction: str
    mode: str = "build"
    confirm: bool = False
    retry_on_fail: bool = False
    max_loops: int = 1
    failure_detection: str = ""
    success_condition: str = ""


class Playbook(BaseModel):
    name: str
    description: str = ""
    author: str = ""
    version: str = "1.0.0"
    steps: list[PlaybookStep] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


def get_playbook_path(name: str) -> Path:
    return PLAYBOOKS_DIR / f"{name}.yml"


def save_playbook(playbook: Playbook) -> Path:
    path = get_playbook_path(playbook.name)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        yaml.dump(playbook.model_dump(), f, default_flow_style=False, sort_keys=False)
    return path


def load_playbook(name: str) -> Optional[Playbook]:
    path = get_playbook_path(name)
    if not path.exists():
        return None
    with open(path) as f:
        data = yaml.safe_load(f)
    return Playbook(**data)


def list_playbooks() -> list[dict]:
    playbooks = []
    for f in sorted(PLAYBOOKS_DIR.glob("*.yml")):
        try:
            pb = load_playbook(f.stem)
            if pb:
                playbooks.append({
                    "name": pb.name,
                    "description": pb.description,
                    "steps": len(pb.steps),
                    "author": pb.author,
                    "version": pb.version,
                    "tags": pb.tags,
                })
        except Exception:
            continue
    return playbooks


def delete_playbook(name: str) -> bool:
    path = get_playbook_path(name)
    if path.exists():
        path.unlink()
        return True
    return False


BUILTIN_PLAYBOOKS: list[Playbook] = [
    Playbook(
        name="create-pr",
        description="Create a GitHub Pull Request: branch, commit, push, and open PR with summary",
        author="xyz",
        version="1.0.0",
        tags=["git", "github", "pr", "devops"],
        steps=[
            PlaybookStep(instruction="Check the current git status and diff to understand what changes have been made and what needs to be committed", mode="explore"),
            PlaybookStep(instruction="Create a new git branch with a descriptive name based on the changes being made", mode="build"),
            PlaybookStep(instruction="Stage all changes and commit them with a conventional commit message following the pattern: type(scope): description", mode="build"),
            PlaybookStep(instruction="Push the branch to origin and use the gh CLI to create a Pull Request with a detailed summary of the changes, including what was changed, why, and any testing notes", mode="build", retry_on_fail=True, max_loops=2, failure_detection="gh:.*(error|failed|not found|auth)"),
        ],
    ),
    Playbook(
        name="blame-debug",
        description="Debug an issue using git blame and commit history analysis",
        author="xyz",
        version="1.0.0",
        tags=["debug", "git", "blame"],
        steps=[
            PlaybookStep(instruction="First, identify the failing code by reading error messages and relevant source files", mode="explore"),
            PlaybookStep(instruction="Run git blame on the identified files to see who last modified each line and when", mode="explore"),
            PlaybookStep(instruction="Read the commit history and messages for the identified commits to understand the context and intent behind the changes", mode="explore"),
            PlaybookStep(instruction="Based on the blame analysis and commit history, diagnose the root cause of the issue", mode="plan"),
            PlaybookStep(instruction="Implement the fix and verify it resolves the issue", mode="build"),
        ],
    ),
    Playbook(
        name="code-review",
        description="Run a comprehensive code review: check git diff, lint, test, and generate a review report",
        author="xyz",
        version="1.0.0",
        tags=["review", "quality", "testing"],
        steps=[
            PlaybookStep(instruction="Check the current git diff to understand what files have been changed and what the changes are about", mode="explore"),
            PlaybookStep(instruction="Run ruff check on the project to identify any linting issues. Fix any issues found.", mode="build"),
            PlaybookStep(instruction="Run mypy type checking on the project and fix any type errors", mode="build"),
            PlaybookStep(instruction="Run pytest to check if all tests pass. Report any failures.", mode="explore"),
            PlaybookStep(instruction="Based on the git diff, lint results, type check results, and test results, provide a comprehensive code review summary. Include recommendations for improvements.", mode="build"),
        ],
    ),
    Playbook(
        name="refactor-module",
        description="Refactor a Python module: analyze, plan, and execute refactoring with testing",
        author="xyz",
        version="1.0.0",
        tags=["refactor", "cleanup"],
        steps=[
            PlaybookStep(instruction="Analyze the project structure and identify which module to refactor. Look for files that are too large, have duplication, or have low cohesion.", mode="plan"),
            PlaybookStep(instruction="Create a detailed refactoring plan with specific file changes, new files to create, and the order of operations", mode="plan"),
            PlaybookStep(instruction="Execute the refactoring plan step by step. Make sure to preserve all existing functionality.", mode="build"),
            PlaybookStep(instruction="Run the existing tests to verify nothing is broken after the refactoring", mode="explore"),
        ],
    ),
    Playbook(
        name="add-api-endpoint",
        description="Add a new API endpoint with tests, documentation, and validation",
        author="xyz",
        version="1.0.0",
        tags=["api", "backend"],
        steps=[
            PlaybookStep(instruction="Analyze the existing API structure to understand patterns, routing, and validation conventions", mode="explore"),
            PlaybookStep(instruction="Create a plan for the new endpoint including route, request/response models, validation, and error handling", mode="plan"),
            PlaybookStep(instruction="Implement the new API endpoint following the project's existing patterns", mode="build"),
            PlaybookStep(instruction="Write tests for the new endpoint covering success cases, validation errors, and edge cases", mode="build"),
            PlaybookStep(instruction="Run the tests to verify everything works correctly", mode="explore"),
        ],
    ),
    Playbook(
        name="debug-issue",
        description="Systematically debug an issue: reproduce, diagnose, fix, and verify",
        author="xyz",
        version="1.0.0",
        tags=["debug", "fix"],
        steps=[
            PlaybookStep(instruction="Reproduce the issue by understanding the error message, reading relevant code, and identifying the root cause", mode="explore"),
            PlaybookStep(instruction="Create a clear diagnosis of the bug including the root cause, affected files, and the fix approach", mode="plan"),
            PlaybookStep(instruction="Implement the fix for the bug", mode="build"),
            PlaybookStep(instruction="Run the existing tests to verify the fix doesn't break anything", mode="explore"),
            PlaybookStep(instruction="Write a new test that covers the bug scenario to prevent regression", mode="build"),
        ],
    ),
    Playbook(
        name="add-tests",
        description="Add comprehensive tests for a module or feature",
        author="xyz",
        version="1.0.0",
        tags=["testing", "quality"],
        steps=[
            PlaybookStep(instruction="Analyze the module to understand its functionality, interfaces, and edge cases", mode="explore"),
            PlaybookStep(instruction="Create a test plan covering unit tests, integration tests, and edge cases", mode="plan"),
            PlaybookStep(instruction="Implement the test cases following the project's testing conventions", mode="build"),
            PlaybookStep(instruction="Run the tests to verify they all pass", mode="explore"),
        ],
    ),
    Playbook(
        name="setup-project",
        description="Initialize a new project with proper structure, dependencies, and configuration",
        author="xyz",
        version="1.0.0",
        tags=["setup", "initialize"],
        steps=[
            PlaybookStep(instruction="Analyze the current directory to understand what exists and what needs to be set up", mode="explore"),
            PlaybookStep(instruction="Create a project structure plan including directory layout, dependency choices, and tooling configuration", mode="plan"),
            PlaybookStep(instruction="Set up the project structure, create necessary configuration files, and install dependencies", mode="build"),
            PlaybookStep(instruction="Verify the setup by running a basic test or build command", mode="explore"),
        ],
    ),
]


def init_builtin_playbooks():
    count = 0
    for pb in BUILTIN_PLAYBOOKS:
        path = get_playbook_path(pb.name)
        if not path.exists():
            save_playbook(pb)
            count += 1
    return count
