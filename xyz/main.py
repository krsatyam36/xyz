import sys
import os
import asyncio
import time
import socket
import subprocess
import json
import logging
import shlex
from pathlib import Path
from typing import Optional, Tuple
from datetime import datetime
from contextlib import contextmanager

import typer
import httpx
from rich.console import Console
from rich.rule import Rule
from rich.table import Table

from xyz.config import (
    ensure_dirs, load_config, save_config, get_api_key,
    set_api_key, validate_api_key, discover_models,
    list_sessions, delete_session, export_session,
    init_project_agents, get_config_paths, DEFAULT_MODELS,
    COMMANDS_DIR, AGENTS_DIR, CONFIG_FILE, SESSIONS_DIR, CACHE_DIR,
)
from xyz.ui.terminal import TerminalUI
from xyz.ui.model_picker import show_model_picker
from xyz.ui.themes import THEMES, list_themes
from xyz.agent.planner import AgentPlanner
from xyz.agent.memory import SessionMemory
from xyz.agent.tools import read_file, write_file, edit_file, execute_shell, grep_files, glob_files
from xyz.agent.safety import is_hard_blocked
from xyz.utils.files import get_context_summary

app = typer.Typer(
    name="xyz",
    help="XYZ - Open Source AI Coding Agent",
    add_completion=False,
    no_args_is_help=False,
)

console = Console()
logger = logging.getLogger(__name__)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


class GatewayManager:
    """Manages gateway process lifecycle with proper resource cleanup."""
    
    def __init__(self):
        self._process = None
        self._log_file = None
    
    def start(self, port: int) -> bool:
        """Start gateway server and verify it's running."""
        env = os.environ.copy()
        env["PYTHONPATH"] = str(Path(__file__).parent.parent)
        
        log_path = Path.home() / ".xyz" / "gateway.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            self._log_file = open(log_path, "w")
            self._process = subprocess.Popen(
                [sys.executable, "-m", "uvicorn", "xyz.gateway.app:app",
                 "--host", "127.0.0.1", "--port", str(port), "--log-level", "info"],
                env=env,
                stdout=self._log_file,
                stderr=subprocess.STDOUT,
            )
            logger.info(f"Started gateway process (PID: {self._process.pid}) on port {port}")
        except Exception as e:
            logger.error(f"Failed to start gateway: {e}")
            self._cleanup_log_file()
            return False
        
        # Verify gateway is running
        for i in range(30):
            time.sleep(0.3)
            if self._process.poll() is not None:
                console.print(f"[red]Gateway crashed. Log: {log_path}[/]")
                try:
                    console.print(f"[dim]{log_path.read_text()[:500]}[/]")
                except Exception:
                    pass
                self._cleanup_log_file()
                return False
            
            try:
                resp = httpx.get(f"http://127.0.0.1:{port}/health", timeout=1.0)
                if resp.status_code == 200:
                    logger.info("Gateway health check passed")
                    return True
            except Exception:
                continue
        
        console.print("[red]Gateway timed out starting[/]")
        self.stop()
        return False
    
    def stop(self):
        """Stop gateway server and clean up resources."""
        if self._process:
            try:
                self._process.terminate()
                self._process.wait(timeout=5)
                logger.info(f"Gateway process terminated (PID: {self._process.pid})")
            except subprocess.TimeoutExpired:
                logger.warning(f"Gateway process did not terminate, killing (PID: {self._process.pid})")
                self._process.kill()
                self._process.wait()
            self._process = None
        
        self._cleanup_log_file()
    
    def _cleanup_log_file(self):
        """Close log file handle to prevent resource leak."""
        if self._log_file:
            try:
                self._log_file.close()
            except Exception as e:
                logger.warning(f"Error closing log file: {e}")
            self._log_file = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()


_gateway_manager = None


def find_free_port() -> int:
    """Find an available port on the system."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


@app.callback()
def callback():
    """Global callback for app initialization."""
    ensure_dirs()


@app.command(name="init")
def cmd_init():
    """Initialize XYZ and set up API key."""
    ui = TerminalUI()
    ui.show_banner()

    api_key = ui.show_auth_prompt()
    if not api_key:
        console.print("[red]No API key provided.[/]")
        raise typer.Exit(1)

    with console.status("[cyan]Validating API key...[/]"):
        if not validate_api_key(api_key):
            console.print("[red]Invalid API key. Please try again.[/]")
            raise typer.Exit(1)

    set_api_key(api_key)

    with console.status("[cyan]Discovering models...[/]"):
        models = discover_models(api_key)

    ui.show_auth_success(len(models))

    config = load_config()
    if models:
        preferred_models = [
            "meta/llama-3.3-70b-instruct",
            "meta/llama-3.1-405b-instruct",
            "meta/llama-3.1-70b-instruct",
            "qwen/qwen-2.5-coder-32b-instruct",
            "qwen/qwen-2.5-72b-instruct",
            "microsoft/phi-4",
            "google/gemma-2-27b-it",
            "mistralai/mistral-large-2-instruct",
            "deepseek-ai/deepseek-r1",
        ]
        for preferred in preferred_models:
            if any(preferred.lower() in m.lower() for m in models):
                config.default_model = next(m for m in models if preferred.lower() in m.lower())
                break
        else:
            config.default_model = models[0]
        save_config(config)

    console.print(f"[green]✓ Default model: {config.default_model}[/]")
    console.print()
    init_project_agents()


def run_chat(
    model: Optional[str] = None,
    session: Optional[str] = None,
    agent_mode: str = "build",
):
    """Start an interactive chat session."""
    global _gateway_manager
    
    config = load_config()
    if not config.api_key_set or not get_api_key():
        console.print("[red]XYZ not initialized. Run 'xyz init' first.[/]")
        raise typer.Exit(1)

    port = find_free_port()
    config.gateway_port = port
    save_config(config)

    _gateway_manager = GatewayManager()
    
    with console.status(f"[cyan]Starting gateway on port {port}...[/]"):
        if not _gateway_manager.start(port):
            raise typer.Exit(1)

    gateway_url = f"http://127.0.0.1:{port}"
    ui = TerminalUI()
    ui.show_banner()

    if model:
        config.default_model = model
        save_config(config)

    ui.show_model_info(config.default_model)

    planner = AgentPlanner(gateway_url, agent_mode=agent_mode)
    if session:
        loaded = SessionMemory.load(session)
        if loaded:
            planner.session = loaded
            ui.print_success(f"Resumed session: {session}")
        else:
            ui.print_warning(f"Session {session} not found")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    ui.start_status_bar()

    try:
        while True:
            ui.update_status_bar()
            try:
                user_input = ui.get_input()
            except (EOFError, KeyboardInterrupt):
                break

            if not user_input:
                continue

            if user_input.startswith("/"):
                ui.update_status_bar()
                should_continue = _handle_command(user_input, ui, planner, config, gateway_url)
                if not should_continue:
                    break
                continue

            if user_input.lower() in ("quit", "exit"):
                break

            ui.console.print()

            try:
                async def run_and_print():
                    ui.current_status = "thinking"
                    ui.update_status_bar()
                    async for output in planner.process(
                        user_input,
                        config.default_model,
                        trust_mode=config.trust_mode,
                        on_status=lambda s: setattr(ui, "current_status", s) or ui.update_status_bar(),
                        on_token=lambda t: ui.stream_text(t),
                    ):
                        if output.startswith("\n["):
                            pass
                        elif output.startswith("[CONFIRM]"):
                            ui.console.print(output, end="", markup=False)
                        else:
                            ui.stream_text(output)
                    ui.console.print()
                    ui.current_status = "ready"
                    ui.update_status_bar()

                loop.run_until_complete(run_and_print())
            except Exception as e:
                logger.exception(f"Error processing input: {e}")
                ui.print_error(str(e))
                ui.current_status = "ready"
                ui.update_status_bar()

            ui.console.print()
            ui.console.print(Rule(style=ui.theme.muted))
            ui.console.print()

    except KeyboardInterrupt:
        console.print()
        console.print("[yellow]Session interrupted.[/]")
    finally:
        ui.stop_status_bar()
        loop.close()
        if _gateway_manager:
            _gateway_manager.stop()
            _gateway_manager = None


@app.command()
def chat(
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Model to use"),
    session: Optional[str] = typer.Option(None, "--session", "-s", help="Session ID to resume"),
):
    """Start an interactive chat session."""
    run_chat(model=model, session=session)


@app.command()
def run(
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Model to use"),
    session: Optional[str] = typer.Option(None, "--session", "-s", help="Session ID to resume"),
):
    """Start chat (alias for 'chat')."""
    run_chat(model=model, session=session)


@app.command()
def plan(
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Model to use"),
    session: Optional[str] = typer.Option(None, "--session", "-s", help="Session ID to resume"),
):
    """Start a planning session (read-only, no changes)."""
    run_chat(model=model, session=session, agent_mode="plan")


@app.command()
def explore(
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Model to use"),
    session: Optional[str] = typer.Option(None, "--session", "-s", help="Session ID to resume"),
):
    """Start an exploration session (read-only search)."""
    run_chat(model=model, session=session, agent_mode="explore")


@app.command()
def models():
    """Browse and select available models interactively."""
    api_key = get_api_key()
    if not api_key:
        console.print("[red]Not initialized. Run 'xyz init' first.[/]")
        raise typer.Exit(1)

    console.print("[dim]Loading models...[/]")
    selected = show_model_picker(api_key)
    if selected:
        config = load_config()
        config.default_model = selected
        save_config(config)
        console.print(f"[green]✓ Switched to model: {selected}[/]")


@app.command()
def themes():
    """List and manage themes."""
    ui = TerminalUI()
    ui.show_themes_list()

    theme_name = ui.get_input("Set theme (or empty to cancel): ")
    if theme_name and theme_name.lower() in THEMES:
        ui.set_theme(theme_name.lower())
        ui.print_success(f"Theme set to: {theme_name}")


@app.command()
def sessions():
    """List saved sessions."""
    sessions_list = list_sessions()
    if not sessions_list:
        console.print("[yellow]No saved sessions.[/]")
        return

    table = Table(title="[bold]Sessions[/]", border_style="blue")
    table.add_column("ID", style="cyan")
    table.add_column("Created")
    table.add_column("Messages", justify="right")

    for s in sessions_list:
        table.add_row(s["id"], s["created"][:19], str(s["messages"]))

    console.print()
    console.print(table)
    console.print()


@app.command()
def session_delete(
    session_id: str = typer.Argument(..., help="Session ID to delete"),
):
    """Delete a saved session."""
    if delete_session(session_id):
        console.print(f"[green]✓ Deleted session {session_id}[/]")
    else:
        console.print(f"[red]Session {session_id} not found[/]")


@app.command()
def session_export(
    session_id: str = typer.Argument(..., help="Session ID to export"),
):
    """Export a session to markdown."""
    md = export_session(session_id)
    if md:
        export_path = f"xyz-session-{session_id}.md"
        Path(export_path).write_text(md)
        console.print(f"[green]✓ Exported to {export_path}[/]")
    else:
        console.print(f"[red]Session {session_id} not found[/]")


@app.command()
def undo(session_id: str = typer.Argument(..., help="Session ID")):
    """Undo the last file write in a session."""
    session = SessionMemory.load(session_id)
    if not session:
        console.print(f"[red]Session {session_id} not found[/]")
        raise typer.Exit(1)

    undone = False
    for path in list(session.file_history.keys()):
        old_content = session.undo_last_write(path)
        if old_content is not None:
            write_file(path, old_content)
            console.print(f"[green]✓ Undid changes to {path}[/]")
            undone = True
            break

    if not undone:
        console.print("[yellow]Nothing to undo.[/]")
    else:
        session.save()


@app.command()
def doctor():
    """Diagnose and verify XYZ installation."""
    console.print("[bold]XYZ Diagnostics[/]")
    console.print()

    config = load_config()
    api_key = get_api_key()

    checks = [
        ("Config file", CONFIG_FILE.exists()),
        ("API key set", config.api_key_set),
        ("API key available", api_key is not None),
        ("Sessions directory", SESSIONS_DIR.exists()),
        ("Cache directory", CACHE_DIR.exists()),
        ("Python version", sys.version_info >= (3, 10)),
    ]

    for name, passed in checks:
        status = "[green]✓[/]" if passed else "[red]✗[/]"
        console.print(f"  {status} {name}")

    if api_key:
        console.print()
        with console.status("[cyan]Validating API key...[/]"):
            valid = validate_api_key(api_key)
        status = "[green]✓[/]" if valid else "[red]✗[/]"
        console.print(f"  {status} API key valid")

    console.print()
    console.print(f"[dim]Config: {CONFIG_FILE}[/]")
    console.print(f"[dim]Sessions: {len(list_sessions())} total[/]")
    console.print(f"[dim]Default model: {config.default_model}[/]")


@app.command()
def version():
    """Show version information."""
    from xyz import __version__
    console.print(f"[bold]XYZ v{__version__}[/]")
    console.print(f"[dim]Python {sys.version.split()[0]}[/]")


# Command dispatcher for slash commands
COMMAND_HANDLERS = {}


def register_command(name: str):
    """Decorator to register slash command handlers."""
    def decorator(func):
        COMMAND_HANDLERS[name] = func
        return func
    return decorator


def _handle_command(cmd: str, ui: TerminalUI, planner, config, gateway_url: str) -> bool:
    """Returns True if session should continue, False to exit."""
    parts = cmd.split()
    command = parts[0].lower()

    handler = COMMAND_HANDLERS.get(command)
    if handler:
        try:
            return handler(ui, planner, config, gateway_url, parts)
        except Exception as e:
            logger.exception(f"Error executing command {command}")
            ui.print_error(f"Error: {str(e)}")
            return True
    
    ui.print_error(f"Unknown command: {command}")
    return True


@register_command("/quit")
@register_command("/exit")
@register_command("/q")
def _cmd_exit(ui, planner, config, gateway_url, parts):
    return False


@register_command("/help")
def _cmd_help(ui, planner, config, gateway_url, parts):
    from xyz.ui.terminal import COMMANDS_LIST
    ui.console.print()
    table = Table(box=None, padding=(0, 2), show_header=False, collapse_padding=True)
    table.add_column("Command", style=ui.theme.secondary, width=22)
    table.add_column("Description", style=ui.theme.muted)
    for cmd, desc in COMMANDS_LIST:
        table.add_row(cmd, desc)
    ui.console.print(table)
    ui.console.print()
    return True


@register_command("/init")
def _cmd_init_project(ui, planner, config, gateway_url, parts):
    result = init_project_agents()
    if result:
        ui.print_success("Created AGENTS.md with project context")
    else:
        ui.print_success("AGENTS.md already exists")
    return True


@register_command("/model")
@register_command("/models")
def _cmd_model_selector(ui, planner, config, gateway_url, parts):
    api_key = get_api_key()
    if not api_key:
        ui.print_error("Not initialized. Run 'xyz init' first.")
        return True
    
    selected = show_model_picker(api_key)
    if selected:
        config.default_model = selected
        save_config(config)
        ui.model_name = selected
        ui.show_model_info(selected)
        ui.print_success(f"Switched to: {selected}")
    return True


@register_command("/themes")
def _cmd_themes(ui, planner, config, gateway_url, parts):
    ui.show_themes_list()
    if len(parts) >= 2:
        theme_name = parts[1].lower()
        if theme_name in THEMES:
            ui.set_theme(theme_name)
            ui.print_success(f"Theme set to: {theme_name}")
    return True


@register_command("/trust")
def _cmd_trust(ui, planner, config, gateway_url, parts):
    if len(parts) < 2:
        config.trust_mode = not config.trust_mode
    else:
        config.trust_mode = parts[1].lower() in ("on", "true", "1")
    save_config(config)
    status = "ON" if config.trust_mode else "OFF"
    ui.print_success(f"Trust mode: {status}")
    return True


@register_command("/sessions")
def _cmd_sessions(ui, planner, config, gateway_url, parts):
    sessions_list = list_sessions()
    if sessions_list:
        table = Table(title="[bold]Sessions[/]", border_style="blue", box=None, padding=(0, 2))
        table.add_column("ID", style="cyan")
        table.add_column("Created")
        table.add_column("Messages", justify="right")
        for s in sessions_list[:10]:
            table.add_row(s["id"], s["created"][:19], str(s["messages"]))
        console.print()
        console.print(table)
        console.print()
    else:
        console.print("[yellow]No saved sessions.[/]")
    return True


@register_command("/resume")
def _cmd_resume(ui, planner, config, gateway_url, parts):
    if len(parts) < 2:
        ui.print_error("Usage: /resume <session-id>")
        return True
    loaded = SessionMemory.load(parts[1])
    if loaded:
        planner.session = loaded
        ui.print_success(f"Resumed session: {parts[1]}")
    else:
        ui.print_warning(f"Session {parts[1]} not found")
    return True


@register_command("/new")
@register_command("/clear")
def _cmd_clear(ui, planner, config, gateway_url, parts):
    planner.session = SessionMemory()
    ui.print_success("Conversation cleared")
    return True


@register_command("/undo")
def _cmd_undo(ui, planner, config, gateway_url, parts):
    session = planner.session
    if not session.file_history:
        ui.print_warning("Nothing to undo")
    else:
        for path in list(session.file_history.keys()):
            old_content = session.undo_last_write(path)
            if old_content is not None:
                write_file(path, old_content)
                ui.print_success(f"Undid changes to {path}")
                break
        session.save()
    return True


@register_command("/redo")
def _cmd_redo(ui, planner, config, gateway_url, parts):
    session = planner.session
    if not session.redo_stack:
        ui.print_warning("Nothing to redo")
    else:
        for path in list(session.redo_stack.keys()):
            content = session.redo_last_write(path)
            if content is not None:
                write_file(path, content)
                ui.print_success(f"Redid changes to {path}")
                break
        session.save()
    return True


@register_command("/compact")
def _cmd_compact(ui, planner, config, gateway_url, parts):
    session = planner.session
    if len(session.messages) < 4:
        ui.print_warning("Not enough messages to compact")
        return True
    summary = f"[Session compacted at {datetime.now().isoformat()[:19]}]"
    session.messages = session.messages[:2] + [{"role": "system", "content": summary, "timestamp": datetime.now().isoformat()}]
    session.save()
    ui.print_success("Session compacted")
    return True


@register_command("/export")
def _cmd_export(ui, planner, config, gateway_url, parts):
    md = export_session(planner.session.id)
    if md:
        export_path = f"xyz-session-{planner.session.id}.md"
        Path(export_path).write_text(md)
        ui.print_success(f"Exported to {export_path}")
    else:
        ui.print_error("Nothing to export")
    return True


@register_command("/context")
def _cmd_context(ui, planner, config, gateway_url, parts):
    ctx = get_context_summary()
    console.print(ctx)
    return True


@register_command("/config")
def _cmd_config(ui, planner, config, gateway_url, parts):
    paths = get_config_paths()
    ui.console.print()
    ui.console.print(f"[{ui.theme.primary}]XYZ Configuration[/]")
    ui.console.print()
    for name, path in paths.items():
        ui.console.print(f"  [{ui.theme.secondary}]{name}[/]: [{ui.theme.muted}]{path}[/]")
    ui.console.print()
    return True


@register_command("/diff")
def _cmd_diff(ui, planner, config, gateway_url, parts):
    result = execute_shell("git diff --stat 2>/dev/null || echo 'Not a git repository'")
    output = result.get("stdout", "") + result.get("stderr", "")
    if output.strip():
        console.print(output.strip()[:2000])
    else:
        ui.print_success("No uncommitted changes")
    return True


@register_command("/doctor")
def _cmd_doctor(ui, planner, config, gateway_url, parts):
    config = load_config()
    api_key = get_api_key()
    checks = [
        ("Config file", CONFIG_FILE.exists()),
        ("API key set", config.api_key_set),
        ("API key available", api_key is not None),
        ("Sessions dir", SESSIONS_DIR.exists()),
        ("Cache dir", CACHE_DIR.exists()),
    ]
    console.print(f"[{ui.theme.primary}]XYZ Diagnostics[/]")
    console.print()
    for name, passed in checks:
        icon = "[green]✓[/]" if passed else "[red]✗[/]"
        console.print(f"  {icon} {name}")
    console.print()
    console.print(f"[dim]Config: {CONFIG_FILE}[/]")
    console.print(f"[dim]Model: {config.default_model}[/]")
    return True


@register_command("/effort")
def _cmd_effort(ui, planner, config, gateway_url, parts):
    levels = ["auto", "low", "medium", "high", "max"]
    if len(parts) >= 2:
        level = parts[1].lower()
        if level in levels:
            config.effort_level = level  # Fixed typo: effor_level -> effort_level
            save_config(config)
            ui.print_success(f"Effort level: {level}")
        else:
            ui.print_error(f"Valid levels: {', '.join(levels)}")
    else:
        ui.print_success(f"Effort level: {config.effort_level}")  # Fixed typo
    return True


@register_command("/fast")
def _cmd_fast(ui, planner, config, gateway_url, parts):
    config.fast_mode = not config.fast_mode
    save_config(config)
    status = "ON" if config.fast_mode else "OFF"
    ui.print_success(f"Fast mode: {status}")
    return True


@register_command("/feedback")
def _cmd_feedback(ui, planner, config, gateway_url, parts):
    ui.print_success("Feedback: https://github.com/krsatyam36/xyz/issues")
    return True


@register_command("/focus")
def _cmd_focus(ui, planner, config, gateway_url, parts):
    ui.print_warning("Focus mode toggled")
    return True


@register_command("/goal")
def _cmd_goal(ui, planner, config, gateway_url, parts):
    if len(parts) >= 2:
        goal = " ".join(parts[1:])
        ui.print_success(f"Goal set: {goal}")
    else:
        ui.print_warning("Usage: /goal <description>")
    return True


@register_command("/hooks")
def _cmd_hooks(ui, planner, config, gateway_url, parts):
    ui.print_success("Tool hooks: No custom hooks configured")
    return True


@register_command("/ide")
def _cmd_ide(ui, planner, config, gateway_url, parts):
    ui.print_success("IDE Integration: Terminal mode active")
    return True


@register_command("/keybindings")
def _cmd_keybindings(ui, planner, config, gateway_url, parts):
    keybindings = {
        "ctrl+c": "Interrupt/Cancel",
        "Up/Down": "Navigate history",
        "Tab": "Autocomplete",
        "/help": "Show help",
        "/quit": "Exit XYZ",
        "/undo": "Undo last change",
        "/redo": "Redo last undo",
        "/clear": "New session",
    }
    ui.console.print()
    ui.console.print(f"[{ui.theme.primary}]Keybindings[/]")
    ui.console.print()
    for key, action in keybindings.items():
        ui.console.print(f"  [{ui.theme.secondary}]{key}[/]  [{ui.theme.muted}]{action}[/]")
    ui.console.print()
    return True


@register_command("/login")
def _cmd_login(ui, planner, config, gateway_url, parts):
    api_key = ui.show_auth_prompt()
    if not api_key:
        ui.print_error("No API key provided.")
        return True
    with console.status("[cyan]Validating API key...[/]"):
        if not validate_api_key(api_key):
            ui.print_error("Invalid API key.")
            return True
    set_api_key(api_key)
    models = discover_models(api_key)
    ui.print_success(f"✓ Logged in. {len(models)} models available.")
    return True


@register_command("/logout")
def _cmd_logout(ui, planner, config, gateway_url, parts):
    config.api_key_set = False
    save_config(config)
    try:
        import keyring
        keyring.delete_password("xyz-cli", "nim_api_key")
    except Exception:
        pass
    ui.print_success("Logged out")
    return True


@register_command("/branch")
def _cmd_branch(ui, planner, config, gateway_url, parts):
    new_session = SessionMemory()
    new_session.messages = planner.session.messages.copy()
    planner.session = new_session
    ui.print_success(f"New branch started: {new_session.id}")
    return True


@register_command("/background")
def _cmd_background(ui, planner, config, gateway_url, parts):
    ui.print_warning("Background mode: not supported in CLI mode")
    return True


@register_command("/btw")
def _cmd_btw(ui, planner, config, gateway_url, parts):
    if len(parts) >= 2:
        question = " ".join(parts[1:])
        ui.print_success(f"Side question noted: {question}")
    else:
        ui.print_warning("Usage: /btw <question>")
    return True


@register_command("/copy")
def _cmd_copy(ui, planner, config, gateway_url, parts):
    if planner.session.messages:
        last = planner.session.messages[-1]
        content = last.get("content", "")
        try:
            import pyperclip
            pyperclip.copy(content[:5000])
            ui.print_success("Copied to clipboard")
        except ImportError:
            ui.print_warning("Clipboard not available. Install pyperclip.")
    else:
        ui.print_warning("No messages to copy")
    return True


@register_command("/advisor")
def _cmd_advisor(ui, planner, config, gateway_url, parts):
    ui.print_warning("Advisor: Not configured. Use a stronger model for guidance.")
    return True


@register_command("/agents")
def _cmd_agents(ui, planner, config, gateway_url, parts):
    from xyz.ui.terminal import AGENTS_LIST
    ui.console.print()
    ui.console.print(f"[{ui.theme.primary}]Available Agents[/]")
    ui.console.print()
    for name, desc in AGENTS_LIST:
        ui.console.print(f"  [{ui.theme.secondary}]{name}[/]  [{ui.theme.muted}]{desc}[/]")
    ui.console.print()
    return True


@register_command("/color")
def _cmd_color(ui, planner, config, gateway_url, parts):
    colors = ["red", "green", "yellow", "blue", "magenta", "cyan", "white"]
    if len(parts) >= 2:
        color = parts[1].lower()
        if color in colors:
            config_obj = load_config()
            save_config(config_obj)
            ui.print_success(f"Color set to: {color}")
        else:
            ui.print_error(f"Valid colors: {', '.join(colors)}")
    else:
        ui.print_success("Prompt bar color can be set with /color <name>")
    return True


@register_command("/install-github-app")
def _cmd_github_app(ui, planner, config, gateway_url, parts):
    ui.print_success("GitHub App: https://github.com/apps/xyz-app")
    return True


@register_command("/add-dir")
def _cmd_add_dir(ui, planner, config, gateway_url, parts):
    if len(parts) >= 2:
        directory = parts[1]
        if os.path.isdir(directory):
            ui.print_success(f"Added directory: {directory}")
        else:
            ui.print_error(f"Directory not found: {directory}")
    else:
        ui.print_error("Usage: /add-dir <path>")
    return True


@register_command("/share")
def _cmd_share(ui, planner, config, gateway_url, parts):
    session_id = planner.session.id
    share_data = {
        "id": session_id,
        "timestamp": datetime.now().isoformat(),
        "model": load_config().default_model,
        "messages": planner.session.messages[-10:] if planner.session.messages else [],
    }
    share_path = Path.home() / ".xyz" / f"share-{session_id}.json"
    share_path.write_text(json.dumps(share_data, indent=2))
    ui.print_success(f"Session {session_id} shared. File: {share_path}")
    return True


@register_command("/unshare")
def _cmd_unshare(ui, planner, config, gateway_url, parts):
    session_id = planner.session.id
    share_path = Path.home() / ".xyz" / f"share-{session_id}.json"
    if share_path.exists():
        share_path.unlink()
        ui.print_success(f"Session {session_id} unshared")
    else:
        ui.print_warning("Session not shared")
    return True


@register_command("/connect")
def _cmd_connect(ui, planner, config, gateway_url, parts):
    ui.print_success("Connect to provider")
    api_key = ui.show_auth_prompt()
    if api_key and validate_api_key(api_key):
        set_api_key(api_key)
        models = discover_models(api_key)
        ui.print_success(f"✓ Connected. {len(models)} models available.")
    return True


@register_command("/details")
def _cmd_details(ui, planner, config, gateway_url, parts):
    ui.print_warning("Details toggled")
    return True


def cli():
    """CLI entry point that defaults to TUI if no command given."""
    if len(sys.argv) == 1:
        from xyz.ui.app import main as run_tui
        run_tui()
    else:
        app()


if __name__ == "__main__":
    cli()
