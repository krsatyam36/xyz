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
        yield StatusBar(id="status-bar")

    def on_mount(self) -> None:
        chat = self.query_one("#chat-panel", ChatPanel)
        chat.add_welcome_message()
        config = load_config()
        bar = self.query_one("#status-bar", StatusBar)
        bar.current_model = config.default_model
        if not get_api_key():
            chat.add_system_message("Not logged in — run [bold #c890c8]/login[/]")

    def action_clear_chat(self):
        self.query_one("#chat-panel", ChatPanel).clear_messages()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id not in ["message-input", "welcome-input"]:
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
            "/help": self._cmd_help,
            "/init": lambda _: chat.add_system_message("✓ XYZ ready — run [bold #c890c8]/login[/]"),
            "/login": self._cmd_login,
            "/logout": self._cmd_logout,
            "/connect": self._cmd_connect,
            "/clear": lambda _: chat.clear_messages(),
            "/new": lambda _: chat.clear_messages(),
            "/quit": lambda _: self.app.exit(),
            "/exit": lambda _: self.app.exit(),
            "/status": self._cmd_status,
            "/model": self._cmd_model,
            "/models": self._cmd_models,
            "/themes": self._cmd_themes,
            "/trust": self._cmd_trust,
            "/sessions": self._cmd_sessions,
            "/resume": self._cmd_resume,
            "/undo": self._cmd_undo,
            "/redo": self._cmd_redo,
            "/context": self._cmd_context,
            "/compact": self._cmd_compact,
            "/export": self._cmd_export,
            "/config": self._cmd_config,
            "/diff": self._cmd_diff,
            "/doctor": self._cmd_doctor,
            "/effort": self._cmd_effort,
            "/fast": self._cmd_fast,
            "/goal": self._cmd_goal,
            "/feedback": self._cmd_feedback,
            "/focus": self._cmd_focus,
            "/hooks": self._cmd_hooks,
            "/ide": self._cmd_ide,
            "/keybindings": self._cmd_keybindings,
            "/branch": self._cmd_branch,
            "/background": self._cmd_background,
            "/btw": self._cmd_btw,
            "/copy": self._cmd_copy,
            "/advisor": self._cmd_advisor,
            "/agents": self._cmd_agents,
            "/color": self._cmd_color,
            "/share": self._cmd_share,
            "/unshare": self._cmd_unshare,
            "/add-dir": self._cmd_add_dir,
            "/install-github-app": self._cmd_install_github_app,
            "/details": self._cmd_details,
            "/scaffold": self._cmd_scaffold,
            "/review": self._cmd_review,
        }.get(command)
        if handler:
            handler(cmd)
        else:
            chat.add_system_message(f"Unknown command: {command}. Type [bold]/help[/] for available commands.")

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
        
        self.app.push_screen(ModelPickerModal(models, current), on_select)

    def _focus_input(self):
        """Focus the active input field (welcome or chat input)."""
        try:
            chat = self.query_one("#chat-panel", ChatPanel)
            welcome_input = chat.query_one("#welcome-input", Input)
            if welcome_input.display:
                welcome_input.focus()
                return
        except Exception:
            pass

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
        try:
            inp = chat.query_one("#welcome-input", Input)
        except Exception:
            return
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
        self._focus_input()

    def _cmd_help(self, _):
        chat = self.query_one("#chat-panel", ChatPanel)
        chat.add_system_message(
            "[bold]Available Commands:[/]\n\n"
            "[bold #c890c8]/help[/]          Show this help\n"
            "[bold #c890c8]/login[/]          Sign in with API key\n"
            "[bold #c890c8]/logout[/]         Sign out\n"
            "[bold #c890c8]/connect[/]        Connect a provider\n"
            "[bold #c890c8]/model[/]          Change AI model\n"
            "[bold #c890c8]/models[/]         List available models\n"
            "[bold #c890c8]/themes[/]         List or set a theme\n"
            "[bold #c890c8]/trust[/]          Toggle trust mode\n"
            "[bold #c890c8]/sessions[/]       List saved sessions\n"
            "[bold #c890c8]/resume[/]         Resume a session\n"
            "[bold #c890c8]/new[/]            New session\n"
            "[bold #c890c8]/clear[/]          Clear chat\n"
            "[bold #c890c8]/undo[/]           Undo last file change\n"
            "[bold #c890c8]/redo[/]           Redo last undo\n"
            "[bold #c890c8]/context[/]        Show repository context\n"
            "[bold #c890c8]/compact[/]        Compact session context\n"
            "[bold #c890c8]/export[/]         Export conversation\n"
            "[bold #c890c8]/config[/]         Show config paths\n"
            "[bold #c890c8]/diff[/]           View uncommitted changes\n"
            "[bold #c890c8]/doctor[/]         Diagnose installation\n"
            "[bold #c890c8]/effort[/]         Set effort level\n"
            "[bold #c890c8]/fast[/]           Toggle fast mode\n"
            "[bold #c890c8]/goal[/]           Set session goal\n"
            "[bold #c890c8]/status[/]         Show status\n"
            "[bold #c890c8]/quit[/]           Exit XYZ"
        )

    def _cmd_logout(self, _):
        chat = self.query_one("#chat-panel", ChatPanel)
        from xyz.config import clear_api_key
        clear_api_key()
        self._provider = None
        chat.add_system_message("✓ Logged out")

    def _cmd_connect(self, _):
        chat = self.query_one("#chat-panel", ChatPanel)
        chat.add_system_message(
            "[bold]Connect a Provider[/]\n\n"
            "XYZ supports multiple AI providers:\n"
            "• [bold]NVIDIA NIM[/] - Run [bold]/login[/] to connect\n"
            "• [bold]OpenAI[/] - Set OPENAI_API_KEY env var\n"
            "• [bold]Anthropic[/] - Set ANTHROPIC_API_KEY env var\n\n"
            "Run [bold]/login[/] to connect with NVIDIA NIM"
        )

    def _cmd_themes(self, cmd):
        chat = self.query_one("#chat-panel", ChatPanel)
        from xyz.ui.themes import list_themes, get_theme, DEFAULT_THEME
        config = load_config()
        
        if len(cmd.split()) > 1:
            theme_name = cmd.split()[1].lower()
            themes = {t["name"].lower(): t["name"] for t in list_themes()}
            if theme_name in themes:
                config.theme = themes[theme_name]
                save_config(config)
                chat.add_system_message(f"[green]✓ Theme set to: [bold]{config.theme}[/]")
            else:
                chat.add_system_message(f"[red]Unknown theme: {theme_name}[/]")
        else:
            themes = list_themes()
            current = config.theme or DEFAULT_THEME
            msg = "[bold]Available Themes:[/]\n\n"
            for t in themes:
                marker = "●" if t["name"].lower() == current.lower() else "○"
                msg += f"{marker} [bold]{t['name']}[/] - {t['description']}\n"
            msg += f"\nCurrent: [bold]{current}[/]\n"
            msg += "Usage: [bold]/themes <name>[/]"
            chat.add_system_message(msg)

    def _cmd_trust(self, cmd):
        chat = self.query_one("#chat-panel", ChatPanel)
        bar = self.query_one("#status-bar", StatusBar)
        config = load_config()
        
        if len(cmd.split()) > 1:
            val = cmd.split()[1].lower()
            if val in ["on", "true", "yes"]:
                config.trust_mode = True
                bar.set_trust(True)
                chat.add_system_message("[green]✓ Trust mode: ON[/]")
            elif val in ["off", "false", "no"]:
                config.trust_mode = False
                bar.set_trust(False)
                chat.add_system_message("[yellow]✓ Trust mode: OFF[/]")
            else:
                chat.add_system_message("[red]Usage: /trust [on/off][/]")
        else:
            config.trust_mode = not config.trust_mode
            bar.set_trust(config.trust_mode)
            status = "ON" if config.trust_mode else "OFF"
            chat.add_system_message(f"Trust mode: [bold]{status}[/]")
        save_config(config)

    def _cmd_sessions(self, _):
        chat = self.query_one("#chat-panel", ChatPanel)
        from xyz.agent.memory import list_sessions
        sessions = list_sessions()
        if not sessions:
            chat.add_system_message("No saved sessions")
        else:
            msg = "[bold]Saved Sessions:[/]\n\n"
            for s in sessions:
                msg += f"[bold]{s['id']}[/] - {s.get('created', 'unknown')}\n"
            chat.add_system_message(msg)

    def _cmd_resume(self, cmd):
        chat = self.query_one("#chat-panel", ChatPanel)
        if len(cmd.split()) < 2:
            chat.add_system_message("[red]Usage: /resume <session-id>[/]")
        else:
            session_id = cmd.split()[1]
            chat.add_system_message(f"Resuming session: [bold]{session_id}[/]")

    def _cmd_undo(self, _):
        chat = self.query_one("#chat-panel", ChatPanel)
        chat.add_system_message("[yellow]Undo feature coming soon[/]")

    def _cmd_redo(self, _):
        chat = self.query_one("#chat-panel", ChatPanel)
        chat.add_system_message("[yellow]Redo feature coming soon[/]")

    def _cmd_context(self, _):
        chat = self.query_one("#chat-panel", ChatPanel)
        cwd = os.getcwd()
        chat.add_system_message(f"[bold]Repository Context:[/]\n\nPath: {cwd}")

    def _cmd_compact(self, _):
        chat = self.query_one("#chat-panel", ChatPanel)
        chat.add_system_message("[yellow]Context compaction coming soon[/]")

    def _cmd_export(self, _):
        chat = self.query_one("#chat-panel", ChatPanel)
        chat.add_system_message("[yellow]Export feature coming soon[/]")

    def _cmd_config(self, _):
        chat = self.query_one("#chat-panel", ChatPanel)
        config_path = os.path.expanduser("~/.xyz/config.json")
        chat.add_system_message(f"[bold]Config Paths:[/]\n\nConfig: {config_path}")

    def _cmd_diff(self, _):
        chat = self.query_one("#chat-panel", ChatPanel)
        result = execute_shell(command="git diff --stat")
        if result.get("returncode") == 0 and result.get("stdout"):
            chat.add_system_message(f"[bold]Uncommitted Changes:[/]\n\n{result['stdout']}")
        else:
            chat.add_system_message("No uncommitted changes")

    def _cmd_doctor(self, _):
        chat = self.query_one("#chat-panel", ChatPanel)
        import sys
        from xyz import __version__
        msg = f"[bold]XYZ Doctor[/]\n\n"
        msg += f"Version: {__version__}\n"
        msg += f"Python: {sys.version}\n"
        msg += f"Platform: {sys.platform}\n"
        msg += f"API Key: {'Set' if get_api_key() else 'Not set'}\n"
        chat.add_system_message(msg)

    def _cmd_effort(self, cmd):
        chat = self.query_one("#chat-panel", ChatPanel)
        config = load_config()
        if len(cmd.split()) > 1:
            level = cmd.split()[1].lower()
            if level in ["auto", "low", "medium", "high", "max"]:
                config.effort_level = level
                save_config(config)
                chat.add_system_message(f"[green]✓ Effort level: {level}[/]")
            else:
                chat.add_system_message("[red]Valid levels: auto, low, medium, high, max[/]")
        else:
            chat.add_system_message(f"Current effort: [bold]{config.effort_level}[/]")

    def _cmd_fast(self, _):
        chat = self.query_one("#chat-panel", ChatPanel)
        config = load_config()
        config.fast_mode = not config.fast_mode
        save_config(config)
        status = "ON" if config.fast_mode else "OFF"
        chat.add_system_message(f"Fast mode: [bold]{status}[/]")

    def _cmd_goal(self, cmd):
        chat = self.query_one("#chat-panel", ChatPanel)
        if len(cmd.split()) > 1:
            goal = " ".join(cmd.split()[1:])
            chat.add_system_message(f"[green]✓ Goal set:[/] {goal}")
        else:
            chat.add_system_message("[red]Usage: /goal <description>[/]")

    def _cmd_feedback(self, _):
        chat = self.query_one("#chat-panel", ChatPanel)
        chat.add_system_message("[yellow]Feedback feature coming soon[/]")

    def _cmd_focus(self, _):
        chat = self.query_one("#chat-panel", ChatPanel)
        chat.add_system_message("[yellow]Focus mode coming soon[/]")

    def _cmd_hooks(self, _):
        chat = self.query_one("#chat-panel", ChatPanel)
        chat.add_system_message("[yellow]Hooks feature coming soon[/]")

    def _cmd_ide(self, _):
        chat = self.query_one("#chat-panel", ChatPanel)
        chat.add_system_message("IDE integration: [yellow]Not connected[/]")

    def _cmd_keybindings(self, _):
        chat = self.query_one("#chat-panel", ChatPanel)
        chat.add_system_message(
            "[bold]Keybindings:[/]\n\n"
            "tab     - Agents\n"
            "ctrl+p  - Commands\n"
            "ctrl+c  - Cancel\n"
            "q       - Quit"
        )

    def _cmd_branch(self, _):
        chat = self.query_one("#chat-panel", ChatPanel)
        chat.add_system_message("[yellow]Branch feature coming soon[/]")

    def _cmd_background(self, _):
        chat = self.query_one("#chat-panel", ChatPanel)
        chat.add_system_message("[yellow]Background mode coming soon[/]")

    def _cmd_btw(self, cmd):
        chat = self.query_one("#chat-panel", ChatPanel)
        if len(cmd.split()) > 1:
            question = " ".join(cmd.split()[1:])
            chat.add_system_message(f"[yellow]Side question:[/] {question}")
        else:
            chat.add_system_message("[red]Usage: /btw <question>[/]")

    def _cmd_copy(self, _):
        chat = self.query_one("#chat-panel", ChatPanel)
        chat.add_system_message("[yellow]Copy feature coming soon[/]")

    def _cmd_advisor(self, _):
        chat = self.query_one("#chat-panel", ChatPanel)
        chat.add_system_message("Advisor: [yellow]Not available[/]")

    def _cmd_agents(self, _):
        chat = self.query_one("#chat-panel", ChatPanel)
        chat.add_system_message(
            "[bold]Available Agents:[/]\n\n"
            "• [bold]Build[/] - Write and modify code\n"
            "• [bold]Plan[/] - Plan architecture\n"
            "• [bold]Explore[/] - Explore codebase"
        )

    def _cmd_color(self, cmd):
        chat = self.query_one("#chat-panel", ChatPanel)
        if len(cmd.split()) > 1:
            color = cmd.split()[1]
            chat.add_system_message(f"[yellow]Color feature coming soon[/]")
        else:
            chat.add_system_message("[red]Usage: /color <name>[/]")

    def _cmd_share(self, _):
        chat = self.query_one("#chat-panel", ChatPanel)
        chat.add_system_message("[yellow]Share feature coming soon[/]")

    def _cmd_unshare(self, _):
        chat = self.query_one("#chat-panel", ChatPanel)
        chat.add_system_message("[yellow]Unshare feature coming soon[/]")

    def _cmd_add_dir(self, cmd):
        chat = self.query_one("#chat-panel", ChatPanel)
        if len(cmd.split()) > 1:
            path = cmd.split()[1]
            chat.add_system_message(f"[yellow]Add directory feature coming soon[/]")
        else:
            chat.add_system_message("[red]Usage: /add-dir <path>[/]")

    def _cmd_install_github_app(self, _):
        chat = self.query_one("#chat-panel", ChatPanel)
        chat.add_system_message("[yellow]GitHub App setup coming soon[/]")

    def _cmd_details(self, _):
        chat = self.query_one("#chat-panel", ChatPanel)
        chat.add_system_message("[yellow]Details toggle coming soon[/]")

    def _cmd_scaffold(self, cmd):
        chat = self.query_one("#chat-panel", ChatPanel)
        parts = cmd.split()
        if len(parts) < 3:
            chat.add_system_message(
                "[bold]Scaffold a new project[/]\n\n"
                "Usage: [bold]/scaffold <template> <name>[/]\n\n"
                "Available templates:\n"
                "• [bold]python[/] - Python project\n"
                "• [bold]fastapi[/] - FastAPI project\n"
                "• [bold]react[/] - React project\n"
                "• [bold]nextjs[/] - Next.js project"
            )
        else:
            template = parts[1]
            name = parts[2]
            from xyz.agent.tools import scaffold_project
            result = scaffold_project(template, name)
            if "error" in result:
                chat.add_system_message(f"[red]{result['error']}[/]")
            else:
                chat.add_system_message(f"[green]✓ Project '{name}' scaffolded at {result['path']}[/]")

    def _cmd_review(self, cmd):
        chat = self.query_one("#chat-panel", ChatPanel)
        parts = cmd.split()
        if len(parts) < 2:
            chat.add_system_message("[red]Usage: /review <path> [focus][/]\n\nFocus options: general, security, performance, style")
        else:
            path = parts[1]
            focus = parts[2] if len(parts) > 2 else "general"
            from xyz.agent.tools import review_code
            result = review_code(path, focus)
            if "error" in result:
                chat.add_system_message(f"[red]{result['error']}[/]")
            else:
                chat.add_system_message(f"[bold]Code Review:[/]\n\n{result['review']}")

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
