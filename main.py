import sys
import os
import asyncio
import time
import socket
import subprocess
from pathlib import Path
from typing import Optional

import typer
import httpx
from rich.console import Console
from rich.rule import Rule
from prompt_toolkit import PromptSession
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style

from xyz.config import (
    ensure_dirs, load_config, save_config, get_api_key,
    set_api_key, validate_api_key, discover_models,
    list_sessions, DEFAULT_MODELS,
)
from xyz.ui.terminal import TerminalUI
from xyz.ui.themes import THEMES
from xyz.agent.planner import AgentPlanner
from xyz.agent.memory import SessionMemory
from xyz.utils.files import get_context_summary

app = typer.Typer(
    name="xyz",
    help="XYZ - Agentic AI Coding CLI",
    add_completion=False,
    no_args_is_help=False,
)

console = Console()

_gateway_process = None


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def start_gateway(port: int) -> bool:
    global _gateway_process
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).parent.parent)

    log_path = Path.home() / ".xyz" / "gateway.log"

    _gateway_process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "xyz.gateway.app:app",
         "--host", "127.0.0.1", "--port", str(port), "--log-level", "info"],
        env=env,
        stdout=open(log_path, "w"),
        stderr=subprocess.STDOUT,
    )

    for i in range(30):
        time.sleep(0.3)
        if _gateway_process.poll() is not None:
            console.print(f"[red]Gateway crashed. Log: {log_path}[/]")
            try:
                console.print(f"[dim]{log_path.read_text()[:500]}[/]")
            except Exception:
                pass
            return False
        try:
            resp = httpx.get(f"http://127.0.0.1:{port}/health", timeout=1.0)
            if resp.status_code == 200:
                return True
        except Exception:
            continue

    console.print("[red]Gateway timed out starting[/]")
    return False


def stop_gateway():
    global _gateway_process
    if _gateway_process:
        _gateway_process.terminate()
        try:
            _gateway_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _gateway_process.kill()


@app.callback()
def callback():
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


def run_chat(
    model: Optional[str] = None,
    session: Optional[str] = None,
):
    """Start an interactive chat session."""
    config = load_config()
    if not config.api_key_set or not get_api_key():
        console.print("[red]XYZ not initialized. Run 'xyz init' first.[/]")
        raise typer.Exit(1)

    port = find_free_port()
    config.gateway_port = port
    save_config(config)

    with console.status(f"[cyan]Starting gateway on port {port}...[/]"):
        if not start_gateway(port):
            raise typer.Exit(1)

    gateway_url = f"http://127.0.0.1:{port}"
    ui = TerminalUI()
    ui.show_banner()

    if model:
        config.default_model = model
        save_config(config)

    ui.show_model_info(config.default_model)

    planner = AgentPlanner(gateway_url)
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
        stop_gateway()


@app.command()
def chat(
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Model to use"),
    session: Optional[str] = typer.Option(None, "--session", "-s", help="Session ID to resume"),
):
    """Start an interactive chat session."""
    run_chat(model=model, session=session)


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
def models():
    """List available models."""
    config = load_config()
    api_key = get_api_key()
    if not api_key:
        console.print("[red]Not initialized. Run 'xyz init' first.[/]")
        raise typer.Exit(1)

    with console.status("[cyan]Fetching models...[/]"):
        discovered = discover_models(api_key)

    from rich.table import Table
    table = Table(title="[bold]Available Models[/]", border_style="blue")
    table.add_column("Model", style="cyan")
    table.add_column("Active", justify="center")

    for m in discovered[:50]:
        active = "●" if m == config.default_model else "○"
        table.add_row(m, f"[green]{active}[/]")

    console.print()
    console.print(table)
    console.print()


@app.command()
def sessions():
    """List saved sessions."""
    sessions_list = list_sessions()
    if not sessions_list:
        console.print("[yellow]No saved sessions.[/]")
        return

    from rich.table import Table
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
def undo(session_id: str = typer.Argument(..., help="Session ID")):
    """Undo the last file write in a session."""
    session = SessionMemory.load(session_id)
    if not session:
        console.print(f"[red]Session {session_id} not found[/]")
        raise typer.Exit(1)

    from xyz.agent.tools import write_file
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


def _handle_command(cmd: str, ui: TerminalUI, planner, config, gateway_url: str) -> bool:
    """Returns True if session should continue, False to exit."""
    parts = cmd.split()
    command = parts[0].lower()

    if command in ("/quit", "/exit"):
        return False

    if command == "/model":
        _interactive_model_selector(ui, config, planner)
        return True

    if command == "/models":
        api_key = get_api_key()
        if not api_key:
            ui.print_error("Not initialized. Run 'xyz init' first.")
            return True
        with console.status("[cyan]Fetching models...[/]"):
            models = discover_models(api_key)
        from rich.table import Table
        table = Table(title="[bold]Available Models[/]", border_style="blue", box=None, padding=(0, 2))
        table.add_column("Model", style="cyan")
        table.add_column("Active", justify="center")
        for m in models[:50]:
            active = "●" if m == config.default_model else "○"
            table.add_row(m, f"[green]{active}[/]")
        console.print()
        console.print(table)
        console.print()
        return True

    if command == "/themes":
        ui.show_themes_list()
        if len(parts) >= 2:
            theme_name = parts[1].lower()
            if theme_name in THEMES:
                ui.set_theme(theme_name)
                ui.print_success(f"Theme set to: {theme_name}")
        return True

    if command == "/trust":
        if len(parts) < 2:
            config.trust_mode = not config.trust_mode
        else:
            config.trust_mode = parts[1].lower() in ("on", "true", "1")
        save_config(config)
        status = "ON" if config.trust_mode else "OFF"
        ui.print_success(f"Trust mode: {status}")
        return True

    if command == "/sessions":
        sessions_list = list_sessions()
        if sessions_list:
            from rich.table import Table
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

    if command == "/resume":
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

    if command == "/context":
        ctx = get_context_summary()
        console.print(ctx)
        return True

    if command == "/clear":
        planner.session = SessionMemory()
        ui.print_success("Conversation cleared")
        return True

    if command == "/compact":
        ui.print_warning("Compact not implemented yet")
        return True

    if command == "/export":
        ui.print_warning("Export not implemented yet")
        return True

    if command == "/help":
        ui.show_help()
        return True

    if command == "/undo":
        session = planner.session
        if not session.file_history:
            ui.print_warning("Nothing to undo")
        else:
            from xyz.agent.tools import write_file
            for path in list(session.file_history.keys()):
                old_content = session.undo_last_write(path)
                if old_content is not None:
                    write_file(path, old_content)
                    ui.print_success(f"Undid changes to {path}")
                    break
            session.save()
        return True

    if command == "/config":
        ui.print_warning("Config panel not implemented yet")
        return True

    if command == "/diff":
        ui.print_warning("Diff view not implemented yet")
        return True

    if command == "/doctor":
        ui.print_warning("Doctor diagnostics not implemented yet")
        return True

    if command == "/effort":
        ui.print_warning("Effort level not implemented yet")
        return True

    if command == "/fast":
        ui.print_warning("Fast mode not implemented yet")
        return True

    if command == "/feedback":
        ui.print_warning("Feedback submission not implemented yet")
        return True

    if command == "/focus":
        ui.print_warning("Focus mode not implemented yet")
        return True

    if command == "/goal":
        ui.print_warning("Goal setting not implemented yet")
        return True

    if command == "/hooks":
        ui.print_warning("Hooks configuration not implemented yet")
        return True

    if command == "/ide":
        ui.print_warning("IDE integration not implemented yet")
        return True

    if command == "/keybindings":
        ui.print_warning("Keybindings not implemented yet")
        return True

    if command == "/login":
        ui.print_warning("Login not implemented yet")
        return True

    if command == "/logout":
        ui.print_warning("Logout not implemented yet")
        return True

    if command == "/branch":
        ui.print_warning("Branching not implemented yet")
        return True

    if command == "/background":
        ui.print_warning("Background mode not implemented yet")
        return True

    if command == "/btw":
        ui.print_warning("Side question mode not implemented yet")
        return True

    if command == "/copy":
        ui.print_warning("Copy not implemented yet")
        return True

    if command == "/advisor":
        ui.print_warning("Advisor tool not implemented yet")
        return True

    if command == "/agents":
        ui.print_warning("Agent management not implemented yet")
        return True

    if command == "/color":
        ui.print_warning("Color setting not implemented yet")
        return True

    if command == "/install-github-app":
        ui.print_warning("GitHub app installation not implemented yet")
        return True

    if command == "/add-dir":
        ui.print_warning("Add directory not implemented yet")
        return True

    ui.print_error(f"Unknown command: {command}")
    ui.show_help()
    return True


def _interactive_model_selector(ui: TerminalUI, config, planner):
    """Interactive model selector like Claude Code."""
    api_key = get_api_key()
    if not api_key:
        ui.print_error("Not initialized. Run 'xyz init' first.")
        return

    with console.status("[cyan]Fetching models...[/]"):
        models = discover_models(api_key)

    if not models:
        ui.print_error("No models available.")
        return

    current_model = config.default_model

    ui.console.print()
    ui.console.print(f"[{ui.theme.primary}]Select model[/]")
    ui.console.print(f"[{ui.theme.muted}]Switch models. Applies to this session.[/]")
    ui.console.print()

    for i, m in enumerate(models[:20], 1):
        marker = "✓" if m == current_model else " "
        ui.console.print(f"  [{ui.theme.secondary}]{i}.[/] [{ui.theme.text}]{m}[/] [{ui.theme.muted}]{marker}[/]")

    ui.console.print()
    ui.console.print(f"[{ui.theme.muted}]Enter number to select, or 'q' to cancel[/]")

    choice = ui.get_input("> ")
    if choice.lower() == "q":
        return

    try:
        idx = int(choice) - 1
        if 0 <= idx < len(models):
            selected = models[idx]
            config.default_model = selected
            save_config(config)
            ui.model_name = selected
            ui.show_model_info(selected)
            ui.print_success(f"Switched to: {selected}")
        else:
            ui.print_error("Invalid selection.")
    except ValueError:
        ui.print_error("Please enter a valid number.")


@app.command()
def run(
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Model to use"),
    session: Optional[str] = typer.Option(None, "--session", "-s", help="Session ID to resume"),
):
    """Start chat (alias for 'chat')."""
    run_chat(model=model, session=session)


def cli():
    """CLI entry point that defaults to chat if no command given."""
    if len(sys.argv) == 1:
        run_chat()
    else:
        app()


if __name__ == "__main__":
    cli()
