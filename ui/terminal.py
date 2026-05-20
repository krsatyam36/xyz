import sys
import time
import os
from rich.console import Console
from rich.text import Text
from rich.markdown import Markdown
from rich.rule import Rule
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.columns import Columns
from rich.box import SIMPLE, ROUNDED

from xyz.ui.themes import get_theme, THEMES, list_themes
from xyz.config import load_config, save_config
from xyz import __version__


STATUS_ICONS = {
    "ready": "●",
    "thinking": "",
    "tool:read_file": "📖",
    "tool:write_file": "✏️",
    "tool:list_directory": "📁",
    "tool:execute_shell": "⚡",
    "tool:search_files": "🔍",
    "tool:unknown": "",
}

STATUS_LABELS = {
    "ready": "Ready",
    "thinking": "Thinking",
    "tool:read_file": "Reading",
    "tool:write_file": "Writing",
    "tool:list_directory": "Listing",
    "tool:execute_shell": "Executing",
    "tool:search_files": "Searching",
    "tool:unknown": "Working",
}


PIXEL_ART = """
     ██████╗ ███████╗██╗   ██╗
     ██╔══██╗██╔════╝██║   ██║
     ██║  ██║█████╗  ██║   ██║
     ██║  ██║██╔══╝  ██╗ ██╔╝
     ██████╝███████╗ ╚████╝
     ╚═════╝ ╚══════╝  ╚═══╝
"""


COMMANDS_LIST = [
    ("/add-dir", "Add a new working directory"),
    ("/advisor", "Configure the Advisor Tool to consult a stronger model for guidance at key moments during a task"),
    ("/agents", "Manage agent configurations"),
    ("/background", "Send this session to the background and free the terminal"),
    ("/branch", "Create a branch of the current conversation at this point"),
    ("/btw", "Ask a quick side question without interrupting the main conversation"),
    ("/clear", "Start a new session with empty context; previous session stays on disk (resumable with /resume)"),
    ("/color", "Set the prompt bar color for this session"),
    ("/compact", "Free up context by summarizing the conversation so far"),
    ("/config", "Open config panel"),
    ("/context", "Visualize current context usage as a colored grid"),
    ("/copy", "Copy XYZ's last response to clipboard (or /copy N for the Nth-latest)"),
    ("/diff", "View uncommitted changes and per-turn diffs"),
    ("/doctor", "Diagnose and verify your XYZ installation and settings"),
    ("/effort", "Set effort level for model usage"),
    ("/exit", "Exit the CLI"),
    ("/export", "Export the current conversation to a file or clipboard"),
    ("/fast", "Toggle fast mode"),
    ("/feedback", "Submit feedback about XYZ"),
    ("/focus", "Toggle focus view (show only your prompt, a tool summary, and the final response)"),
    ("/goal", "Set a goal - keep working until the condition is met"),
    ("/help", "Show help and available commands"),
    ("/hooks", "View hook configurations for tool events"),
    ("/ide", "Manage IDE integrations and show status"),
    ("/install-github-app", "Set up XYZ GitHub Actions for a repository"),
    ("/keybindings", "Open or create your keybindings configuration file"),
    ("/login", "Sign in with your account"),
    ("/logout", "Sign out from your account"),
    ("/model", "Switch to a different model"),
    ("/models", "List available models"),
    ("/resume", "Resume a previous session"),
    ("/sessions", "List saved sessions"),
    ("/themes", "List or set a theme"),
    ("/trust", "Toggle trust mode for commands"),
    ("/undo", "Undo last file change"),
]


AGENTS_LIST = [
    ("@build", "Default agent with all tools enabled (Tab to switch)"),
    ("@plan", "Plan mode - analyze code without making changes"),
    ("@explore", "Explore mode - search and read code only"),
    ("@general", "General-purpose subagent for research tasks"),
]

TIPS = [
    "Type your message to start coding",
    "Use /help to see all commands",
    "Use /model to switch models",
    "Use /themes to change appearance",
    "Tab to switch between Build/Plan agents",
    "Use @ to mention files in your message",
]

WHAT_NEW = [
    "Added plugin dependency enforcement: `xyz plugin disable` now refuses when another enabled plugin depends on the ...",
    "Added projected context cost (per-turn and per-invocation token estimates) to the `/plugin` marketplace browse pane ...",
    "Added `worktree.bgIsolation: \"none\"` setting to let background sessions edit the working copy directly without `Ente...`",
    "/release-notes for more",
]


class TerminalUI:
    def __init__(self):
        self.console = Console(force_terminal=True, soft_wrap=True)
        config = load_config()
        self.theme = get_theme(config.theme)
        self.token_stats = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "request_count": 0,
        }
        self.current_status = "ready"
        self.model_name = config.default_model
        self.response_buffer = ""
        self.last_tool_output = ""
        self._live = None

    def set_theme(self, theme_name: str):
        self.theme = get_theme(theme_name)
        config = load_config()
        config.theme = theme_name
        save_config(config)

    def _get_header_info(self):
        cwd = os.getcwd()
        home = os.path.expanduser("~")
        display_path = cwd.replace(home, "~", 1) if cwd.startswith(home) else cwd
        model_short = self.model_name.split("/")[-1] if "/" in self.model_name else self.model_name
        return display_path, model_short

    def show_banner(self):
        display_path, model_short = self._get_header_info()
        
        left_content = (
            f"[{self.theme.primary}]XYZ v{__version__}[/]\n\n"
            f"[{self.theme.primary}]Welcome back![/]\n\n"
            f"[{self.theme.accent}]{PIXEL_ART}[/]\n\n"
            f"[{self.theme.muted}]{model_short}[/] [{self.theme.muted}]• API Usage Billing[/]\n"
            f"[{self.theme.muted}]{display_path}[/]"
        )
        
        right_content = (
            f"[{self.theme.primary}]Tips for getting started[/]\n"
            f"[{self.theme.muted}]Run /init to create a XYZ.md file with instructions for XYZ[/]\n\n"
            f"[{self.theme.primary}]What's new[/]\n"
        )
        for item in WHAT_NEW:
            right_content += f"[{self.theme.muted}]{item}[/]\n"
            
        columns = Columns([left_content, right_content], padding=(0, 4))
        panel = Panel(columns, border_style=self.theme.primary, box=SIMPLE, padding=(1, 2))
        
        self.console.print()
        self.console.print(panel)
        self.console.print()
        self.console.print(Rule(style=self.theme.muted))
        self.console.print()

    def show_auth_prompt(self) -> str:
        display_path, model_short = self._get_header_info()
        
        left_content = (
            f"[{self.theme.primary}]XYZ v{__version__}[/]\n\n"
            f"[{self.theme.primary}]Welcome to XYZ[/]\n\n"
            f"[{self.theme.accent}]{PIXEL_ART}[/]\n\n"
            f"[{self.theme.muted}]{model_short}[/] [{self.theme.muted}]• API Usage Billing[/]\n"
            f"[{self.theme.muted}]{display_path}[/]"
        )
        
        right_content = (
            f"[{self.theme.primary}]Get started[/]\n"
            f"[{self.theme.muted}]Enter your NVIDIA NIM API key to get started.[/]\n"
            f"[{self.theme.muted}]Get one at: https://build.nvidia.com[/]\n\n"
            f"[{self.theme.primary}]Tips[/]\n"
        )
        for tip in TIPS:
            right_content += f"[{self.theme.muted}]• {tip}[/]\n"
            
        columns = Columns([left_content, right_content], padding=(0, 4))
        panel = Panel(columns, border_style=self.theme.primary, box=SIMPLE, padding=(1, 2))
        
        self.console.print()
        self.console.print(panel)
        self.console.print()
        self.console.print(Rule(style=self.theme.muted))
        self.console.print()
        
        return self.console.input(f"[{self.theme.secondary}]API Key: [/]").strip()

    def show_auth_success(self, model_count: int):
        self.console.print(f"[{self.theme.success}]✓ Authentication successful[/]")
        self.console.print(f"[{self.theme.success}]✓ {model_count} models discovered[/]")
        self.console.print()

    def show_model_info(self, model: str):
        self.model_name = model
        model_short = model.split("/")[-1] if "/" in model else model
        self.console.print(f"[{self.theme.muted}]Using {model}[/] [{self.theme.muted}]• /model to change[/]")
        self.console.print()

    def show_themes_list(self):
        self.console.print()
        self.console.print(f"[{self.theme.primary}]Available Themes[/]")
        self.console.print()
        config = load_config()
        for t in list_themes():
            active = "●" if t["name"].lower() == config.theme else "○"
            self.console.print(f"  {active} [{self.theme.primary}]{t['name']}[/] - {t['description']}")
        self.console.print()

    def show_help(self):
        self.console.print()
        
        table = Table(box=None, padding=(0, 2), show_header=False, collapse_padding=True)
        table.add_column("Command", style=self.theme.secondary, width=22)
        table.add_column("Description", style=self.theme.muted)
        
        for cmd, desc in COMMANDS_LIST:
            table.add_row(cmd, desc)
        
        self.console.print(table)
        self.console.print()

    def print_response(self, text: str):
        self.console.print()
        self.console.print(Markdown(text))
        self.console.print()

    def print_error(self, msg: str):
        self.console.print(f"[{self.theme.error}]Error: {msg}[/]")

    def print_success(self, msg: str):
        self.console.print(f"[{self.theme.success}]{msg}[/]")

    def print_warning(self, msg: str):
        self.console.print(f"[{self.theme.warning}]{msg}[/]")

    def print_tool_start(self, name: str, detail: str = ""):
        self.console.print(f"[{self.theme.muted}] {name}[/] [{self.theme.muted}]{detail}[/]")

    def print_tool_done(self, name: str, detail: str = ""):
        self.console.print(f"[{self.theme.success}]✓ {name}[/] [{self.theme.muted}]{detail}[/]")

    def get_input(self, prompt: str = "> ") -> str:
        try:
            return self.console.input(f"[{self.theme.secondary}]{prompt}[/]").strip()
        except (EOFError, KeyboardInterrupt):
            return ""

    def confirm(self, msg: str) -> bool:
        result = self.console.input(f"[{self.theme.warning}]{msg} [y/n]: [/]").strip().lower()
        return result in ("y", "yes")

    def stream_text(self, text: str):
        self.console.print(text, end="", markup=False)

    def print_separator(self):
        self.console.print(Rule(style=self.theme.muted))

    def render_status_bar(self) -> Panel:
        icon = STATUS_ICONS.get(self.current_status, STATUS_ICONS["ready"])
        label = STATUS_LABELS.get(self.current_status, STATUS_LABELS["ready"])

        model_short = self.model_name.split("/")[-1] if "/" in self.model_name else self.model_name

        if self.current_status == "ready":
            status_text = f"[{self.theme.success}]●[/] [{self.theme.muted}]Ready[/]"
        elif self.current_status.startswith("tool:"):
            tool_name = self.current_status.replace("tool:", "")
            status_text = f"[{self.theme.executing}]{icon}[/] [{self.theme.executing}]{label}[/] [{self.theme.muted}]· {tool_name}[/]"
        else:
            spinner = "⠋⠹⠼⠴⠦⠏"[int(time.time() * 4) % 10]
            status_text = f"[{self.theme.thinking}]{spinner}[/] [{self.theme.thinking}]{label}[/]"

        content = f"{status_text}  [{self.theme.muted}]·[/]  [{self.theme.primary}]{model_short}[/]"
        return Panel(content, style=self.theme.muted, padding=(0, 1), box=SIMPLE)

    def start_status_bar(self):
        if self._live is None:
            self._live = Live(self.render_status_bar(), console=self.console, auto_refresh=False)
            self._live.start()

    def update_status_bar(self):
        if self._live:
            self._live.update(self.render_status_bar())
            self._live.refresh()

    def stop_status_bar(self):
        if self._live:
            self._live.stop()
            self._live = None
            self.console.print()
