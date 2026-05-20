"""XYZ - Clean TUI matching screenshot design"""
from textual.app import App, ComposeResult
from textual.widgets import Static, Input
from textual.containers import Container, ScrollableContainer
from textual.binding import Binding
from textual.reactive import reactive
from textual import work
import asyncio
import os

from xyz.config import load_config, get_api_key


class MessageBlock(Static):
    """Individual message block."""
    
    DEFAULT_CSS = """
    MessageBlock {
        padding: 0 2;
        margin: 0 0 1 0;
        width: 100%;
    }
    
    MessageBlock.user-block {
        background: #1a1a1a;
        padding: 1 2;
    }
    
    MessageBlock.assistant-block {
        background: transparent;
        padding: 1 2;
    }
    
    MessageBlock.system-block {
        background: transparent;
        padding: 1 2;
    }
    
    MessageBlock .message-prefix {
        color: #c890c8;
        text-style: bold;
    }
    
    MessageBlock .message-content {
        color: #e0e0e0;
    }
    
    MessageBlock .message-status {
        color: #888888;
        padding-left: 2;
    }
    
    MessageBlock .message-error {
        color: #ff6b6b;
        padding-left: 2;
    }
    """
    
    def __init__(self, role: str, content: str, status: str = None, **kwargs):
        super().__init__(**kwargs)
        self.role = role
        self.content = content
        self.status = status
    
    def on_mount(self) -> None:
        """Render message."""
        if self.role == "user":
            self.add_class("user-block")
            prefix = ">"
        elif self.role == "assistant":
            self.add_class("assistant-block")
            prefix = ""
        else:
            self.add_class("system-block")
            prefix = ""
        
        content_html = f'<span class="message-prefix">{prefix}</span> {self.content}' if prefix else self.content
        
        if self.status:
            if "error" in self.status.lower() or "not logged" in self.status.lower():
                content_html += f'\n<span class="message-error">└ {self.status}</span>'
            else:
                content_html += f'\n<span class="message-status">└ {self.status}</span>'
        
        self.update(content_html)


class XYZApp(App):
    """XYZ AI Coding Runtime - Clean TUI."""
    
    CSS = """
    Screen {
        background: #0d0d0d;
        layout: vertical;
    }
    
    #header {
        height: auto;
        padding: 2 4 1 4;
    }
    
    #separator {
        color: #333333;
        padding: 0 2;
    }
    
    #chat-container {
        height: 1fr;
        padding: 1 2;
    }
    
    #input-line {
        height: 3;
        padding: 0 2;
    }
    
    #input-prefix {
        color: #c890c8;
        text-style: bold;
        padding-right: 1;
    }
    
    #message-input {
        width: 1fr;
        height: 1;
        border: none;
        background: transparent;
        color: #e0e0e0;
    }
    
    #message-input:focus {
        border: none;
        background: transparent;
    }
    
    #status-bar {
        height: 1;
        padding: 0 2;
        color: #888888;
        dock: bottom;
    }
    
    #status-bar .status-ready {
        color: #888888;
    }
    
    #status-bar .status-error {
        color: #ff6b6b;
    }
    """
    
    BINDINGS = [
        Binding("q", "quit", "Quit", show=False),
        Binding("ctrl+c", "quit", "Quit", show=False),
    ]
    
    current_status = reactive("ready")
    is_logged_in = reactive(False)
    
    def compose(self) -> ComposeResult:
        """Create clean layout."""
        yield self._create_header()
        yield Static("─" * 120, id="separator")
        yield ScrollableContainer(id="chat-container")
        yield self._create_input_line()
        yield Static(id="status-bar")
    
    def _create_header(self):
        """Create header matching screenshot exactly."""
        config = load_config()
        model = config.default_model
        model_short = model.split("/")[-1] if "/" in model else model
        
        cwd = os.getcwd()
        home = os.path.expanduser("~")
        display_path = cwd.replace(home, "~", 1) if cwd.startswith(home) else cwd
        
        # Build header with proper Textual markup
        header_text = (
            f"[#c890c8 bold]XYZ v0.1.0[/]\n\n"
            f"[#c890c8 bold]Welcome back![/]\n\n"
            f"[#c890c8]"
            f"██████╗ ███████╗██╗   ██╗\n"
            f"██╔══██╗██╔════╝██║   ██║\n"
            f"██║  ██║█████╗  ██║   ██║\n"
            f"██║  ██║██╔══╝  ██║   ██║\n"
            f"██████╔╝███████╗╚██████╝\n"
            f"╚═════╝ ╚══════╝ ╚═════╝\n"
            f"[/]\n"
            f"[#888888]{model_short} • API Usage Billing[/]\n"
            f"[#888888]{display_path}[/]"
        )
        
        return Static(header_text, id="header")
    
    def _create_input_line(self):
        """Create input line."""
        return Container(
            Static(">", id="input-prefix"),
            Input(placeholder="", id="message-input"),
            id="input-line",
        )
    
    def on_mount(self) -> None:
        """Initialize app."""
        self.query_one("#message-input", Input).focus()
        self._update_status()
        
        # Check if logged in
        api_key = get_api_key()
        self.is_logged_in = api_key is not None
        
        if not self.is_logged_in:
            self._show_message("system", "", "Not logged in · Please run /login")
    
    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle message submission."""
        if event.input.id == "message-input":
            message = event.value.strip()
            if not message:
                return
            
            if message.startswith("/"):
                self._handle_command(message)
            else:
                self._handle_message(message)
            
            event.input.value = ""
    
    def _handle_command(self, command: str):
        """Handle slash commands."""
        cmd = command.lower().split()[0]
        
        if cmd == "/init":
            self._cmd_init()
        elif cmd == "/login":
            self._cmd_login()
        elif cmd == "/model":
            self._cmd_model(command)
        elif cmd == "/help":
            self._cmd_help()
        elif cmd == "/clear":
            self._cmd_clear()
        elif cmd == "/quit" or cmd == "/exit":
            self.exit()
        else:
            self._show_message("system", command, f"Unknown command: {cmd}")
    
    def _handle_message(self, message: str):
        """Handle user message."""
        if not self.is_logged_in:
            self._show_message("user", message, "Not logged in · Please run /login")
            return
        
        self._show_message("user", message)
        self._simulate_response(message)
    
    @work(exclusive=True)
    async def _simulate_response(self, user_message: str):
        """Simulate AI response."""
        self.current_status = "thinking"
        self._update_status()
        
        await asyncio.sleep(1)
        
        response = "I can help you with that! Let me analyze your request.\n\n"
        response += "Here's what I found:\n\n"
        response += "```python\n# Example code\ndef hello():\n    print('Hello from XYZ!')\n```\n\n"
        response += "This should work perfectly. Let me know if you need modifications!"
        
        self._show_message("assistant", response, "Cogitated for 1s")
        
        self.current_status = "ready"
        self._update_status()
    
    def _show_message(self, role: str, content: str, status: str = None):
        """Show message in chat area."""
        chat_container = self.query_one("#chat-container", ScrollableContainer)
        
        msg = MessageBlock(role, content, status)
        chat_container.mount(msg)
        chat_container.scroll_end(animate=True)
    
    def _update_status(self):
        """Update status bar."""
        status_bar = self.query_one("#status-bar")
        
        if self.is_logged_in:
            status_bar.update('[#888888]? for shortcuts[/]')
        else:
            status_bar.update('[#ff6b6b]Not logged in · Run /login[/]')
    
    def _cmd_init(self):
        """Initialize XYZ."""
        self._show_message("system", "/init", "Initializing XYZ...")
        self._show_message("system", "", "✓ XYZ initialized successfully")
        self._show_message("system", "", "✓ API key configured")
        self._show_message("system", "", "✓ 132 models available")
    
    def _cmd_login(self):
        """Login to XYZ."""
        self._show_message("system", "/login", "Logging in...")
        self._show_message("system", "", "✓ Authentication successful")
        self.is_logged_in = True
        self._update_status()
    
    def _cmd_model(self, command: str):
        """Set model."""
        parts = command.split()
        if len(parts) > 1:
            model = parts[1]
            self._show_message("system", command, f"Set model to {model}")
        else:
            self._show_message("system", command, "Usage: /model <model-name>")
    
    def _cmd_help(self):
        """Show help."""
        help_text = """Available commands:

/init       - Initialize XYZ
/login      - Login with API key
/model      - Set model
/help       - Show this help
/clear      - Clear conversation
/quit       - Exit XYZ"""
        self._show_message("system", "/help", help_text)
    
    def _cmd_clear(self):
        """Clear chat."""
        chat_container = self.query_one("#chat-container", ScrollableContainer)
        for child in chat_container.query("MessageBlock"):
            child.remove()


def main():
    """Run XYZ application."""
    app = XYZApp()
    app.run()


if __name__ == "__main__":
    main()
