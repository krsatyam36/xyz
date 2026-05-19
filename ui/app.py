"""XYZ - AI Coding Runtime - Textual TUI Application"""
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static, Input, DataTable, Label
from textual.containers import Container, Vertical, Horizontal, ScrollableContainer
from textual.screen import Screen
from textual.binding import Binding
from textual.css.query import NoMatches
from textual.reactive import reactive
from textual import work
from textual.worker import Worker, get_current_worker

from datetime import datetime
import asyncio
import random

from ui.panels.header_panel import HeaderPanel
from ui.panels.chat_panel import ChatPanel
from ui.panels.input_panel import InputPanel
from ui.panels.status_bar import StatusBar
from ui.panels.command_palette import CommandPalette
from ui.widgets.stream_text import StreamText
from ui.widgets.activity_indicator import ActivityIndicator


class MainScreen(Screen):
    """Main chat screen with full interface."""
    
    CSS_PATH = "styles/main.tcss"
    
    BINDINGS = [
        Binding("ctrl+p", "toggle_palette", "Commands", show=True),
        Binding("ctrl+l", "clear_chat", "Clear", show=False),
        Binding("escape", "hide_palette", "Close", show=False),
    ]
    
    palette_visible = reactive(False)
    
    def compose(self) -> ComposeResult:
        """Create the main layout."""
        yield HeaderPanel(id="header-panel")
        yield ChatPanel(id="chat-panel")
        yield InputPanel(id="input-panel")
        yield StatusBar(id="status-bar")
        yield CommandPalette(id="command-palette")
    
    def on_mount(self) -> None:
        """Called when screen is mounted."""
        self.palette_visible = False
        self.query_one("#command-palette").display = False
        
        # Add welcome message
        chat_panel = self.query_one("#chat-panel", ChatPanel)
        chat_panel.add_welcome_message()
        
        # Focus input
        self.query_one("#message-input", Input).focus()
    
    def action_toggle_palette(self) -> None:
        """Toggle command palette visibility."""
        palette = self.query_one("#command-palette", CommandPalette)
        self.palette_visible = not self.palette_visible
        palette.display = self.palette_visible
        if self.palette_visible:
            palette.focus_filter()
    
    def action_hide_palette(self) -> None:
        """Hide command palette."""
        if self.palette_visible:
            self.palette_visible = False
            self.query_one("#command-palette", CommandPalette).display = False
            self.query_one("#message-input", Input).focus()
    
    def action_clear_chat(self) -> None:
        """Clear chat history."""
        chat_panel = self.query_one("#chat-panel", ChatPanel)
        chat_panel.clear_messages()
    
    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle message submission."""
        if event.input.id == "message-input":
            message = event.value.strip()
            if not message:
                return
            
            # Hide palette if visible
            if self.palette_visible:
                self.action_hide_palette()
            
            # Process command or message
            if message.startswith("/"):
                self._handle_command(message)
            else:
                self._handle_message(message)
            
            # Clear input
            event.input.value = ""
    
    def _handle_command(self, command: str) -> None:
        """Handle slash commands."""
        chat_panel = self.query_one("#chat-panel", ChatPanel)
        cmd = command.lower().split()[0]
        
        commands = {
            "/help": self._cmd_help,
            "/models": self._cmd_models,
            "/tools": self._cmd_tools,
            "/trust": self._cmd_trust,
            "/context": self._cmd_context,
            "/clear": self._cmd_clear,
            "/status": self._cmd_status,
            "/quit": self._cmd_quit,
            "/export": self._cmd_export,
            "/history": self._cmd_history,
            "/settings": self._cmd_settings,
        }
        
        handler = commands.get(cmd)
        if handler:
            handler(command)
        else:
            chat_panel.add_system_message(f"Unknown command: {cmd}")
    
    def _handle_message(self, message: str) -> None:
        """Handle user message."""
        chat_panel = self.query_one("#chat-panel", ChatPanel)
        
        # Add user message
        chat_panel.add_user_message(message)
        
        # Simulate AI response with streaming
        self._simulate_ai_response(message)
    
    @work(exclusive=True)
    async def _simulate_ai_response(self, user_message: str) -> None:
        """Simulate AI response with streaming effect."""
        chat_panel = self.query_one("#chat-panel", ChatPanel)
        status_bar = self.query_one("#status-bar", StatusBar)
        
        # Show thinking state
        status_bar.set_status("thinking")
        
        # Simulate processing delay
        await asyncio.sleep(0.5)
        
        # Create streaming response
        responses = [
            "I'll help you with that. Let me analyze your request and provide a comprehensive solution.\n\n",
            "Here's what I found:\n\n",
            "```python\n# Example code\ndef hello():\n    print('Hello from XYZ!')\n```\n\n",
            "This should work perfectly for your use case. Let me know if you need any modifications!",
        ]
        
        full_response = "".join(responses)
        
        # Stream the response
        await chat_panel.stream_assistant_message(full_response)
        
        # Update status
        status_bar.set_status("ready")
    
    def _cmd_help(self, command: str) -> None:
        """Show help."""
        chat_panel = self.query_one("#chat-panel", ChatPanel)
        help_text = """## Available Commands

| Command | Description |
|---------|-------------|
| `/help` | Show this help message |
| `/models` | Browse available models |
| `/use <model>` | Switch to a model |
| `/tools` | List available tools |
| `/trust [on|off]` | Toggle trust mode |
| `/context` | Show context usage |
| `/settings` | Open settings |
| `/clear` | Clear conversation |
| `/export` | Export conversation |
| `/history` | Show conversation history |
| `/status` | Show system status |
| `/quit` | Exit XYZ |

**Keyboard Shortcuts:**
- `Ctrl+P` - Open command palette
- `Ctrl+L` - Clear chat
- `Esc` - Close palette
- `Shift+Enter` - New line in input
"""
        chat_panel.add_system_message(help_text)
    
    def _cmd_models(self, command: str) -> None:
        """Show models."""
        chat_panel = self.query_one("#chat-panel", ChatPanel)
        models = [
            "meta/llama-3.3-70b-instruct",
            "meta/llama-3.1-405b-instruct",
            "qwen/qwen-2.5-coder-32b-instruct",
            "qwen/qwen-2.5-72b-instruct",
            "microsoft/phi-4",
            "google/gemma-2-27b-it",
            "mistralai/mistral-large-2-instruct",
            "deepseek-ai/deepseek-r1",
        ]
        
        text = "## Available Models\n\n"
        for i, model in enumerate(models, 1):
            marker = "●" if i == 1 else "○"
            text += f"{marker} `{model}`\n"
        
        chat_panel.add_system_message(text)
    
    def _cmd_tools(self, command: str) -> None:
        """Show tools."""
        chat_panel = self.query_one("#chat-panel", ChatPanel)
        tools = [
            ("read_file", "Read file contents"),
            ("write_file", "Write/create files"),
            ("list_directory", "List directory contents"),
            ("execute_shell", "Execute shell commands"),
            ("search_files", "Search for patterns in files"),
        ]
        
        text = "## Available Tools\n\n"
        for name, desc in tools:
            text += f"- **{name}** - {desc}\n"
        
        chat_panel.add_system_message(text)
    
    def _cmd_trust(self, command: str) -> None:
        """Toggle trust mode."""
        chat_panel = self.query_one("#chat-panel", ChatPanel)
        status_bar = self.query_one("#status-bar", StatusBar)
        
        parts = command.split()
        if len(parts) > 1:
            status = parts[1].lower()
            if status in ("on", "true", "1"):
                status_bar.set_trust(True)
                chat_panel.add_system_message("Trust mode: **ON**")
            elif status in ("off", "false", "0"):
                status_bar.set_trust(False)
                chat_panel.add_system_message("Trust mode: **OFF**")
        else:
            current = status_bar.toggle_trust()
            chat_panel.add_system_message(f"Trust mode: **{'ON' if current else 'OFF'}**")
    
    def _cmd_context(self, command: str) -> None:
        """Show context usage."""
        chat_panel = self.query_one("#chat-panel", ChatPanel)
        status_bar = self.query_one("#status-bar", StatusBar)
        
        context = status_bar.get_context_usage()
        text = f"## Context Usage\n\n"
        text += f"- **Used:** {context['used']}\n"
        text += f"- **Total:** {context['total']}\n"
        text += f"- **Available:** {context['available']}\n"
        text += f"- **Percentage:** {context['percentage']}%\n"
        
        chat_panel.add_system_message(text)
    
    def _cmd_clear(self, command: str) -> None:
        """Clear chat."""
        chat_panel = self.query_one("#chat-panel", ChatPanel)
        chat_panel.clear_messages()
        chat_panel.add_welcome_message()
    
    def _cmd_status(self, command: str) -> None:
        """Show system status."""
        chat_panel = self.query_one("#chat-panel", ChatPanel)
        status_bar = self.query_one("#status-bar", StatusBar)
        
        status = status_bar.get_full_status()
        text = "## System Status\n\n"
        for key, value in status.items():
            text += f"- **{key}:** {value}\n"
        
        chat_panel.add_system_message(text)
    
    def _cmd_quit(self, command: str) -> None:
        """Quit application."""
        self.app.exit()
    
    def _cmd_export(self, command: str) -> None:
        """Export conversation."""
        chat_panel = self.query_one("#chat-panel", ChatPanel)
        chat_panel.add_system_message("Export feature coming soon!")
    
    def _cmd_history(self, command: str) -> None:
        """Show history."""
        chat_panel = self.query_one("#chat-panel", ChatPanel)
        chat_panel.add_system_message("History feature coming soon!")
    
    def _cmd_settings(self, command: str) -> None:
        """Show settings."""
        chat_panel = self.query_one("#chat-panel", ChatPanel)
        chat_panel.add_system_message("Settings panel coming soon!")


class XYZApp(App):
    """XYZ AI Coding Runtime - Main Application."""
    
    CSS_PATH = "styles/app.tcss"
    
    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("ctrl+p", "toggle_palette", "Commands", show=True),
    ]
    
    TITLE = "XYZ v0.1.0"
    
    def on_mount(self) -> None:
        """Called when app is mounted."""
        self.install_screen(MainScreen(), name="main")
        self.push_screen("main")


def main():
    """Run the XYZ application."""
    app = XYZApp()
    app.run()


if __name__ == "__main__":
    main()
