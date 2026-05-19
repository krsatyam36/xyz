import httpx
import orjson
from typing import AsyncGenerator
from xyz.agent.tools import TOOL_DEFINITIONS, TOOL_REGISTRY
from xyz.agent.parser import parse_tool_calls, extract_text_response
from xyz.agent.safety import is_hard_blocked, needs_confirmation
from xyz.agent.memory import SessionMemory
from xyz.config import load_config


SYSTEM_PROMPT = """You are XYZ, an expert agentic AI coding assistant running in the terminal.

IDENTITY: You are XYZ. Always refer to yourself as XYZ. You are a capable coding assistant that can help with any programming task.

CAPABILITIES:
- You can read and write files, execute shell commands, search code, and list directories
- You can answer questions, explain concepts, debug code, and write new code
- You can help with any development workflow
- You have full access to the file system and shell within the working directory

TOOLS AVAILABLE:
- read_file(path): Read file contents
- write_file(path, content): Write/create a file
- list_directory(path): List directory contents
- execute_shell(command): Run a shell command
- search_files(pattern, path): Search for patterns in files

GUIDELINES:
1. Be helpful, direct, and conversational
2. Use tools when they add value - don't hesitate to use them
3. For file modifications, read the file first, then write the updated version
4. Never execute dangerous commands (the safety system will block them anyway)
5. Be concise but thorough in your explanations
6. When done with a task, clearly state what you accomplished
7. If you don't know something, say so honestly
8. Always identify yourself as XYZ when asked

CURRENT WORKING DIRECTORY: {cwd}
"""


class AgentPlanner:
    def __init__(self, gateway_url: str):
        self.gateway_url = gateway_url
        self.session: SessionMemory = SessionMemory()

    async def process(
        self,
        user_input: str,
        model: str,
        trust_mode: bool = False,
        on_status=None,
        on_token=None,
    ) -> AsyncGenerator[str, None]:
        config = load_config()
        import os
        system_msg = {
            "role": "system",
            "content": SYSTEM_PROMPT.format(cwd=os.getcwd()),
        }

        self.session.add_message("user", user_input)
        messages = [system_msg] + self.session.get_messages()

        max_turns = 10
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
                    "tools": TOOL_DEFINITIONS,
                    "temperature": 0.1,
                    "max_tokens": 4096,
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
                        if needs_confirmation(cmd) and not trust_mode:
                            yield f"\n[CONFIRM] Execute: {cmd}\n[y/n]: "
                            return
                        from xyz.agent.tools import execute_shell
                        result = execute_shell(cmd)
                        output = result.get("stdout", "") + result.get("stderr", "")
                        if output:
                            yield f"\n{output[:1000]}\n"
                elif name in TOOL_REGISTRY:
                    result = TOOL_REGISTRY[name](**args)
                    if name == "read_file":
                        content = result.get("content", "")
                        if content:
                            yield f"\n{content[:2000]}\n"
                    elif name == "write_file":
                        yield f"\n"
                    elif name == "list_directory":
                        entries = result.get("entries", [])
                        if entries:
                            lines = []
                            for e in entries:
                                icon = "📁" if e["type"] == "directory" else "📄"
                                lines.append(f"  {icon} {e['name']}")
                            yield f"\n" + "\n".join(lines) + "\n"
                    elif name == "search_files":
                        files = result.get("files", [])
                        if files:
                            yield f"\n" + "\n".join(f"  {f}" for f in files[:20]) + "\n"
                else:
                    result = {"error": f"Unknown tool: {name}"}
                    yield f"\nUnknown tool: {name}\n"

                if name == "write_file" and isinstance(result, dict) and "old_content" in result:
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
