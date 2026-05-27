import os
import httpx
import orjson
from typing import AsyncGenerator, Optional
from xyz.agent.tools import TOOL_DEFINITIONS, TOOL_REGISTRY
from xyz.agent.parser import parse_tool_calls, extract_text_response
from xyz.agent.safety import is_hard_blocked, needs_confirmation
from xyz.agent.permissions import classify_command, AUTO_APPROVE_COMMANDS, ASK_COMMANDS, DENY_COMMANDS
from xyz.agent.memory import SessionMemory
from xyz.config import load_config


SYSTEM_PROMPT = """You are XYZ, an expert agentic AI coding assistant running in the terminal.

IDENTITY: You are XYZ. Always refer to yourself as XYZ. You are a capable coding assistant that can help with any programming task.

CAPABILITIES:
- Read, write, edit, and search files in the project
- Execute shell commands for builds, tests, git operations, etc.
- Search code using regex patterns and glob patterns
- Fetch web content and search the web for information
- Full file system and shell access within the working directory
- Semantic codebase search (AST analysis, function/class/import graph)
- Git blame analysis for debugging context
- Architectural memory - remembers codebase conventions across sessions

TOOLS AVAILABLE:
- read_file(path, offset?, limit?): Read file contents with optional line range
- write_file(path, content): Write/create a file
- edit_file(path, old_string, new_string): Precise text replacement in files
- apply_patch(patch_text): Apply unified diff patches
- list_directory(path): List directory contents
- execute_shell(command, description?): Run a shell command
- grep_files(pattern, path?, include?): Regex search across files
- glob_files(pattern, path?): Find files by glob pattern
- search_files(pattern, path?): Legacy file search
- webfetch(url): Fetch web content
- websearch(query): Search the web

PERMISSION TIERS (for shell commands):
- Auto-approved: ls, pwd, cd, cat, grep, git status, pytest, pip list, echo, curl (no pipe)
- Ask first: pip install, rm, git push, git commit, docker, chmod, apt-get, wget
- Denied: sudo, rm -rf /, shutdown, mkfs, dd, fork bombs, curl|bash

GUIDELINES:
1. Be helpful, direct, and conversational
2. For code changes, ALWAYS read the file first, then use edit_file for precise changes
3. When modifying code, prefer edit_file over write_file for targeted changes
4. Never execute dangerous commands (the safety system blocks them)
5. Be concise but thorough in explanations
6. When done with a task, clearly state what you accomplished
7. Commit messages should follow conventional commits format: type(scope): description

{memory_context}CURRENT WORKING DIRECTORY: {cwd}
"""

PLAN_AGENT_PROMPT = """You are XYZ in Plan mode. You analyze code and create plans without making changes.

GUIDELINES:
1. Analyze the codebase thoroughly before suggesting changes
2. Create detailed plans with specific file paths and code changes
3. Do NOT make any changes - only read files and suggest what to change
4. Focus on architecture, edge cases, and potential issues

{memory_context}CURRENT WORKING DIRECTORY: {cwd}
"""

EXPLORE_AGENT_PROMPT = """You are XYZ in Explore mode. You explore codebases to answer questions.

GUIDELINES:
1. Search and read files to understand the codebase
2. Answer questions concisely with file references
3. Do NOT make any changes
4. Use grep_files and glob_files extensively

{memory_context}CURRENT WORKING DIRECTORY: {cwd}
"""


class AgentPlanner:
    def __init__(self, gateway_url: str, agent_mode: str = "build"):
        self.gateway_url = gateway_url
        self.session: SessionMemory = SessionMemory()
        self.agent_mode = agent_mode

    def _get_system_prompt(self) -> str:
        cwd = os.getcwd()
        try:
            from xyz.agent.memory_store import get_memory_context
            memory = get_memory_context(max_rules=10)
            memory_context = memory + "\n\n" if memory else ""
        except Exception:
            memory_context = ""
        if self.agent_mode == "plan":
            return PLAN_AGENT_PROMPT.format(cwd=cwd, memory_context=memory_context)
        elif self.agent_mode == "explore":
            return EXPLORE_AGENT_PROMPT.format(cwd=cwd, memory_context=memory_context)
        return SYSTEM_PROMPT.format(cwd=cwd, memory_context=memory_context)

    def _get_tools(self):
        if self.agent_mode == "explore":
            return [t for t in TOOL_DEFINITIONS if t["function"]["name"] in
                    ("read_file", "grep_files", "glob_files", "search_files", "list_directory")]
        if self.agent_mode == "plan":
            return [t for t in TOOL_DEFINITIONS if t["function"]["name"] not in
                    ("write_file", "edit_file", "apply_patch", "execute_shell")]
        return TOOL_DEFINITIONS

    async def process(
        self,
        user_input: str,
        model: str,
        trust_mode: bool = False,
        on_status=None,
        on_token=None,
    ) -> AsyncGenerator[str, None]:
        config = load_config()
        system_msg = {
            "role": "system",
            "content": self._get_system_prompt(),
        }

        self.session.add_message("user", user_input)
        messages = [system_msg] + self.session.get_messages()

        max_turns = 10 if self.agent_mode == "build" else 5
        turn = 0

        while turn < max_turns:
            turn += 1
            if on_status:
                on_status("thinking")

            full_response = ""
            tool_calls = []

            async with httpx.AsyncClient(timeout=120.0) as client:
                payload = {
                    "model": model,
                    "messages": messages,
                    "tools": self._get_tools(),
                    "temperature": 0.1,
                    "max_tokens": 8192,
                    "stream": True,
                }

                async with client.stream("POST", f"{self.gateway_url}/v1/chat", json=payload) as resp:
                    async for line in resp.aiter_lines():
                        if not line or not line.startswith("data: "):
                            continue
                        try:
                            data = orjson.loads(line[6:])
                            if data["type"] == "token":
                                full_response += data["data"]
                                if on_token:
                                    on_token(data["data"])
                            elif data["type"] == "tool_call":
                                tool_calls.append(orjson.loads(data["data"]))
                            elif data["type"] == "usage":
                                pass
                            elif data["type"] == "done":
                                full_response = data.get("content", full_response)
                                if data.get("tool_calls"):
                                    tool_calls = [orjson.loads(tc) for tc in data["tool_calls"]]
                            elif data["type"] == "error":
                                yield f"\nError: {data.get('data', 'Unknown error')}\n"
                                return
                        except Exception:
                            continue

            if not tool_calls:
                try:
                    tool_calls = parse_tool_calls(full_response)
                except Exception as e:
                    yield f"\nError parsing tool call: {str(e)}\n"
                    return

            if not tool_calls:
                text = extract_text_response(full_response)
                self.session.add_message("assistant", text)
                self.session.save()
                if not on_token:
                    yield text
                return

            messages.append({"role": "assistant", "content": full_response})

            for tc in tool_calls:
                name = tc.get("name", "")
                args = tc.get("args", {})

                if not name:
                    continue

                if on_status:
                    on_status(f"tool:{name}")

                if name == "execute_shell":
                    cmd = args.get("command", "")
                    blocked, reason = is_hard_blocked(cmd)
                    if blocked:
                        yield f"\n[BLOCKED] {reason}\n"
                        result = {"error": reason}
                    else:
                        perm = classify_command(cmd)
                        if perm.is_denied():
                            yield f"\n[BLOCKED] {perm.reason}\n"
                            result = {"error": perm.reason}
                        elif perm.needs_ask() and not trust_mode:
                            yield f"\n[CONFIRM] Execute: {cmd}\n[y/n]: "
                            return
                        from xyz.agent.tools import execute_shell
                        result = execute_shell(cmd, args.get("description", ""), args.get("timeout", 60000))
                        output = result.get("stdout", "") + result.get("stderr", "")
                        if output:
                            yield f"\n{output[:1000]}\n"
                elif name in TOOL_REGISTRY:
                    try:
                        result = TOOL_REGISTRY[name](**{k: v for k, v in args.items() if v is not None})
                    except Exception as e:
                        result = {"error": str(e)}
                        yield f"\nError executing {name}: {str(e)}\n"
                        continue

                    if name == "read_file":
                        content = result.get("content", "")
                        if content:
                            yield f"\n{content[:2000]}\n"
                    elif name in ("edit_file",):
                        if "error" in result:
                            yield f"\n[EDIT ERROR] {result['error']}\n"
                        else:
                            yield f"\n✓ Edited {result['path']}\n"
                    elif name == "write_file":
                        yield f"\n✓ {result['status']} {result['path']}\n"
                    elif name == "list_directory":
                        entries = result.get("entries", [])
                        if entries:
                            lines = []
                            for e in entries:
                                icon = "📁" if e["type"] == "directory" else "📄"
                                lines.append(f"  {icon} {e['name']}")
                            yield f"\n" + "\n".join(lines) + "\n"
                    elif name in ("grep_files", "search_files"):
                        files = result.get("files", [])
                        if files:
                            yield f"\n" + "\n".join(f"  {f}" for f in files[:20]) + "\n"
                    elif name == "glob_files":
                        files = result.get("files", [])
                        if files:
                            yield f"\n" + "\n".join(f"  {f}" for f in files[:20]) + "\n"
                else:
                    result = {"error": f"Unknown tool: {name}"}
                    yield f"\nUnknown tool: {name}\n"

                if name == "write_file" and isinstance(result, dict) and "old_content" in result:
                    self.session.track_file_write(args.get("path", ""), result["old_content"])
                    result_for_model = {k: v for k, v in result.items() if k != "old_content"}
                elif name == "edit_file" and isinstance(result, dict) and "old_content" in result:
                    self.session.track_file_write(args.get("path", ""), result["old_content"])
                    result_for_model = {k: v for k, v in result.items() if k != "old_content"}
                else:
                    result_for_model = result

                messages.append({
                    "role": "tool",
                    "content": str(result_for_model),
                    "name": name,
                })

            if on_status:
                on_status("thinking")
