"""XYZ - AI Coding Runtime - Full Agentic TUI"""
from textual.app import App, ComposeResult
from textual.widgets import Static, Input
from textual.screen import Screen
from textual.binding import Binding
from textual import work
import asyncio
import json
import os
import traceback

from xyz import __version__
from xyz.ui.panels.header_panel import HeaderPanel
from xyz.ui.panels.chat_panel import ChatPanel, ChatMessage
from xyz.ui.panels.input_panel import InputPanel
from xyz.ui.panels.status_bar import StatusBar
from xyz.ui.widgets.model_picker import ModelPickerModal
from xyz.config import discover_models
from xyz.gateway.providers import NIMProvider
from xyz.config import load_config, get_api_key, set_api_key, discover_models, save_config, validate_api_key
from xyz.agent.tools import TOOL_DEFINITIONS, TOOL_REGISTRY, execute_shell
from xyz.agent.safety import is_hard_blocked
from xyz.agent.memory import SessionMemory


AGENT_PROMPT = """You are XYZ, an expert AI coding assistant with file system access.

You have these tools:
- read_file(path) — read a file
- write_file(path, content) — create or overwrite a file
- list_directory(path) — list a directory
- execute_shell(command) — run a shell command
- search_files(pattern, path) — search files for a pattern

Rules:
1. For coding tasks, use tools to read files first, then make changes
2. Write complete, working code — never leave placeholders
3. After using tools, explain what was done
4. When creating projects, plan the structure first, then create files
5. For shell commands, prefer safe operations
"""


class MainScreen(Screen):
    CSS_PATH = "styles/main.tcss"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._provider = None
        self._awaiting_api_key = False

    def _get_provider(self):
        if self._provider is None:
            key = get_api_key()
            if key:
                self._provider = NIMProvider(key)
        return self._provider

    def compose(self) -> ComposeResult:
        yield HeaderPanel(id="header-panel")
        yield ChatPanel(id="chat-panel")
        yield InputPanel(id="input-panel")
        yield StatusBar(id="status-bar")

    def on_mount(self) -> None:
        chat = self.query_one("#chat-panel", ChatPanel)
        chat.add_welcome_message()
        config = load_config()
        bar = self.query_one("#status-bar", StatusBar)
        bar.current_model = config.default_model
        if not get_api_key():
            chat.add_system_message("Not logged in — run [bold #c890c8]/login[/]")
        self.query_one("#message-input", Input).focus()

    def action_clear_chat(self):
        self.query_one("#chat-panel", ChatPanel).clear_messages()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "message-input":
            return
        msg = event.value.strip()
        if not msg:
            return
        if self._awaiting_api_key:
            self._handle_api_key(msg)
            return
        if msg.startswith("/"):
            self._handle_command(msg)
        else:
            self._handle_message(msg)
        event.input.value = ""

    def _handle_command(self, cmd: str) -> None:
        chat = self.query_one("#chat-panel", ChatPanel)
        parts = cmd.split()
        command = parts[0].lower()
        handler = {
            "/help": lambda _: chat.add_system_message(
                "Commands: [bold #c890c8]/help /login /model /models /clear /status /init /quit[/]"
            ),
            "/init": lambda _: chat.add_system_message("✓ XYZ ready — run [bold #c890c8]/login[/]"),
            "/login": lambda _: (chat.add_system_message("Enter your NVIDIA NIM API key and press Enter"), setattr(self, "_awaiting_api_key", True), self.query_one("#message-input", Input).focus()),
            "/clear": lambda _: chat.clear_messages(),
            "/quit": lambda _: self.app.exit(),
            "/status": self._cmd_status,
            "/model": self._cmd_model,
            "/models": self._cmd_models,
        }.get(command)
        if handler:
            handler(cmd)
        else:
            chat.add_system_message(f"Unknown: {command}")

    def _cmd_status(self, _):
        chat = self.query_one("#chat-panel", ChatPanel)
        bar = self.query_one("#status-bar", StatusBar)
        s = bar.get_full_status()
        chat.add_system_message("Status:\n" + "\n".join(f"  {k}: {v}" for k, v in s.items()))

    def _cmd_model(self, cmd):
        self._show_model_picker()

    def _cmd_models(self, _):
        self._show_model_picker()

    def _show_model_picker(self):
        """Show interactive model picker modal."""
        chat = self.query_one("#chat-panel", ChatPanel)
        bar = self.query_one("#status-bar", StatusBar)
        
        cfg = load_config()
        current = cfg.default_model
        
        models = cfg.discovered_models or []
        if not models and get_api_key():
            try:
                models = discover_models(get_api_key())
            except Exception:
                pass
        if not models:
            from xyz.config import DEFAULT_MODELS
            models = list(DEFAULT_MODELS)
        
        if not models:
            chat.add_system_message("[red]No models available. Run /login first.[/]")
            return
        
        def on_select(selected):
            if selected:
                cfg.default_model = selected
                save_config(cfg)
                bar.current_model = selected
                chat.add_system_message(f"[green]✓ Model switched to: [bold]{selected}[/]")
        
        self.app.push_screen(ModelPickerModal(models, current, on_select))

    def _handle_message(self, text: str) -> None:
        chat = self.query_one("#chat-panel", ChatPanel)
        if not self._get_provider():
            chat.add_user_message(text)
            chat.add_system_message("Run [bold #c890c8]/login[/] first")
            return
        chat.add_user_message(text)
        self._agentic_loop(text)

    def _handle_api_key(self, key: str) -> None:
        chat = self.query_one("#chat-panel", ChatPanel)
        bar = self.query_one("#status-bar", StatusBar)
        inp = self.query_one("#message-input", Input)
        self._awaiting_api_key = False
        inp.value = ""
        if not key:
            chat.add_system_message("Cancelled")
            return
        chat.add_system_message("Validating...")
        if validate_api_key(key):
            set_api_key(key)
            self._provider = NIMProvider(key)
            chat.add_system_message("✓ Authenticated")
            discover_models(key)
            bar.set_status("ready")
        else:
            chat.add_system_message("Invalid key, try again")
            self._cmd_login("")

    def _cmd_login(self, _=None):
        chat = self.query_one("#chat-panel", ChatPanel)
        chat.add_system_message("Enter your NVIDIA NIM API key and press Enter")
        self._awaiting_api_key = True
        self.query_one("#message-input", Input).focus()

    # ── Agentic loop ────────────────────────────────────────────────────

    @work(exclusive=True)
    async def _agentic_loop(self, user_text: str) -> None:
        chat = self.query_one("#chat-panel", ChatPanel)
        bar = self.query_one("#status-bar", StatusBar)
        provider = self._get_provider()
        if not provider:
            return

        config = load_config()
        model = config.default_model
        display_model = model.split("/")[-1] if "/" in model else model

        messages = [
            {"role": "system", "content": AGENT_PROMPT.replace("{cwd}", os.getcwd())},
            {"role": "user", "content": user_text},
        ]

        for turn in range(15):
            bar.set_status("thinking")

            if turn > 0:
                chat.add_system_message(f"─ [bold]Step {turn + 1}[/] ─")

            msg = chat.start_assistant_message()
            content_parts = []
            tool_buffers = {}

            try:
                async for chunk in provider.chat_completion(
                    model=model,
                    messages=messages,
                    tools=TOOL_DEFINITIONS,
                    stream=True,
                ):
                    if not msg.is_mounted:
                        break
                    if chunk.startswith("__TOOL_CALL__:"):
                        raw = chunk[len("__TOOL_CALL__:"):-len("__")]
                        try:
                            tc = json.loads(raw)
                        except json.JSONDecodeError:
                            continue
                        idx = tc.get("index", 0)
                        if idx not in tool_buffers:
                            tool_buffers[idx] = {"id": "", "function": {"name": "", "arguments": ""}}
                        buf = tool_buffers[idx]
                        if "id" in tc:
                            buf["id"] = tc["id"]
                        if "function" in tc:
                            fn = tc["function"]
                            if "name" in fn:
                                buf["function"]["name"] += fn["name"]
                            if "arguments" in fn:
                                buf["function"]["arguments"] += fn["arguments"]
                    elif chunk.startswith("__USAGE__:"):
                        continue
                    else:
                        content_parts.append(chunk)
                        if msg.is_mounted:
                            msg.set_content("".join(content_parts))
                            chat.scroll_end(animate=False)

            except asyncio.CancelledError:
                raise
            except Exception as e:
                if msg.is_mounted:
                    msg.set_content(f"[#ff6b6b]Error: {e}[/]")
                bar.set_status("ready")
                return

            content = "".join(content_parts)

            # If model produced text and no tool calls, we're done
            if content.strip() and not tool_buffers:
                chat.messages.append({"role": "assistant", "content": content})
                bar.set_status("ready")
                return

            # If model produced no text and no tools, we're done
            if not content.strip() and not tool_buffers:
                msg.set_content("[#888888]No response[/]")
                bar.set_status("ready")
                return

            # If only tool calls (no text), remove the empty assistant message
            if not content.strip() and tool_buffers:
                msg.remove()
                msg = None

            # Add assistant message to context (empty string if no text)
            messages.append({"role": "assistant", "content": content})

            # Add tool call entries (non-final — we replace with results below)
            if tool_buffers:
                # Build OpenAI-style tool_calls for the context
                openai_calls = []
                for idx in sorted(tool_buffers.keys()):
                    tc = tool_buffers[idx]
                    name = tc["function"]["name"]
                    args_str = tc["function"]["arguments"]
                    call_id = tc["id"] or f"call_{idx}"

                    # Validate and try to parse arguments
                    try:
                        if args_str.strip():
                            json.loads(args_str)
                    except json.JSONDecodeError:
                        args_str = "{}"

                    openai_calls.append({
                        "id": call_id,
                        "type": "function",
                        "function": {"name": name, "arguments": args_str},
                    })

                # Attach tool_calls to the assistant message
                if openai_calls:
                    messages[-1]["tool_calls"] = openai_calls

                # Execute each tool and add results
                for idx in sorted(tool_buffers.keys()):
                    tc = tool_buffers[idx]
                    name = tc["function"]["name"]
                    args_str = tc["function"]["arguments"]

                    try:
                        args = json.loads(args_str) if args_str.strip() else {}
                    except json.JSONDecodeError:
                        chat.add_system_message(f"[#ff6b6b]Invalid args for {name}[/]")
                        args = {}

                    if not name:
                        continue

                    # Show what tool is being called
                    args_preview = ", ".join(f"{k}={v!r}" for k, v in list(args.items())[:3])
                    if len(args) > 3:
                        args_preview += ", …"
                    call_id = tc.get("id", f"call_{idx}")

                    chat.add_system_message(f"→ [bold]{name}[/]({args_preview})")

                    # Safety check for shell commands
                    if name == "execute_shell":
                        cmd = args.get("command", "")
                        blocked, reason = is_hard_blocked(cmd)
                        if blocked:
                            result = {"error": reason}
                            chat.add_system_message(f"[#ff6b6b]Blocked: {reason}[/]")
                        else:
                            result = execute_shell(**args)
                    else:
                        tool_fn = TOOL_REGISTRY.get(name)
                        if tool_fn:
                            try:
                                result = tool_fn(**args)
                            except Exception as e:
                                result = {"error": str(e)}
                        else:
                            result = {"error": f"Unknown tool: {name}"}

                    # Show result summary
                    if "error" in result:
                        chat.add_system_message(f"[#ff6b6b]{result['error']}[/]")
                    else:
                        summary = self._summarize_result(name, result)
                        chat.add_system_message(summary)

                    messages.append({
                        "role": "tool",
                        "content": json.dumps(result),
                        "tool_call_id": call_id,
                        "name": name,
                    })

        # Max turns reached
        bar.set_status("ready")

    def _summarize_result(self, name: str, result: dict) -> str:
        """Create a short summary of a tool result."""
        if name == "read_file":
            path = result.get("path", "")
            size = result.get("size", 0)
            truncated = result.get("truncated", False)
            text = f"Read {path} ({size} bytes)"
            if truncated:
                text += " [truncated]"
            return text
        elif name == "write_file":
            path = result.get("path", "")
            status = result.get("status", "")
            return f"[#00ff66]Written[/] {path} [{status}]"
        elif name == "list_directory":
            count = result.get("count", 0)
            path = result.get("path", "")
            return f"Listed {path}: {count} entries"
        elif name == "execute_shell":
            code = result.get("returncode", -1)
            stdout = result.get("stdout", "")
            stderr = result.get("stderr", "")
            icon = "[#00ff66]✓[/]" if code == 0 else "[#ff6b6b]✗[/]"
            text = f"{icon} Exit code {code}"
            if stdout:
                preview = stdout.strip()[:200]
                text += f"\n[#888888]{preview}[/]"
            if stderr:
                preview = stderr.strip()[:200]
                text += f"\n[#ff6b6b]{preview}[/]"
            return text
        elif name == "search_files":
            count = result.get("count", 0)
            files = result.get("files", [])
            text = f"Found {count} files"
            if files:
                text += "\n" + "\n".join(f"  {f}" for f in files[:10])
            return text
        return json.dumps(result, indent=2)[:300]


class XYZApp(App):
    CSS_PATH = "styles/app.tcss"
    TITLE = f"XYZ v{__version__}"
    BINDINGS = [Binding("q", "quit", "Quit", show=True)]

    def on_mount(self) -> None:
        self.install_screen(MainScreen(), name="main")
        self.push_screen("main")


def main():
    XYZApp().run()


if __name__ == "__main__":
    main()
