"""Chat panel with message display and streaming."""
from textual.widgets import Static, Input
from textual.containers import ScrollableContainer, Horizontal
from textual.reactive import reactive
import asyncio

from xyz.config import load_config


class ChatMessage(Static):
    """A single chat message — content renders synchronously."""

    DEFAULT_CSS = """
    ChatMessage {
        padding: 1 2;
        margin: 0 0 1 0;
        background: transparent;
    }

    ChatMessage.user {
        background: #1a1a1a;
    }
    """

    def __init__(self, role: str, content: str = "", **kwargs):
        rendered = self._format(role, content)
        super().__init__(rendered, **kwargs)
        self.role = role
        self.content = content

    @staticmethod
    def _format(role: str, content: str) -> str:
        if role == "user":
            return f"> {content}" if content else ">"
        if role == "system":
            return f"[#888888]{content}[/]" if content else ""
        return content

    def on_mount(self) -> None:
        if self.role == "user":
            self.add_class("user")

    def set_content(self, content: str) -> None:
        """Update displayed content — safe to call after mount."""
        self.content = content
        self.update(self._format(self.role, content))


class ChatPanel(ScrollableContainer):
    """Chat area — messages mount and stream here."""

    DEFAULT_CSS = """
    ChatPanel {
        height: 1fr;
        padding: 0 2;
        margin: 0 1;
        background: transparent;
        overflow-y: auto;
    }

    ChatPanel .welcome {
        padding: 2 4;
        color: #888888;
        content-align: center top;
    }

    ChatPanel #welcome-input-row {
        width: 60%;
        height: 3;
        margin: 1 auto;
        align: center middle;
    }

    ChatPanel #welcome-prompt {
        width: 2;
        color: #888888;
        content-align: left middle;
    }

    ChatPanel #welcome-input {
        width: 1fr;
        border: none;
        background: transparent;
        color: #e0e0e0;
    }

    ChatPanel #welcome-input:focus {
        border: none;
        background: transparent;
    }
    """

    messages: list = reactive([])

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._welcome = None
        self._welcome_input = None

    def compose(self):
        self._welcome = Static(classes="welcome")
        yield self._welcome
        with Horizontal(id="welcome-input-row"):
            yield Static("> ", id="welcome-prompt")
            yield Input(
                placeholder="Type your message...",
                id="welcome-input",
            )

    def on_mount(self) -> None:
        self.messages = []
        self.query_one("#welcome-input", Input).focus()

    def add_welcome_message(self):
        config = load_config()
        model_name = config.default_model.split("/")[-1] if "/" in config.default_model else config.default_model
        
        self._welcome.update(
            f"[#888888]Build · {model_name}[/]\n\n"
            "[#888888]tab[/] agents  [#888888]ctrl+p[/] commands\n\n\n"
            "[#ffaa00]●[/] [#888888]Tip[/] [#888888]Run [/][#e0e0e0]/connect[/][#888888] to add an AI provider and start coding[/]"
        )

    def add_user_message(self, content: str):
        self._hide_welcome_input()
        msg = ChatMessage("user", content)
        self.mount(msg)
        self.messages.append({"role": "user", "content": content})
        self.scroll_end(animate=False)

    def add_assistant_message(self, content: str):
        msg = ChatMessage("assistant", content)
        self.mount(msg)
        self.messages.append({"role": "assistant", "content": content})
        self.scroll_end(animate=False)

    def add_system_message(self, content: str):
        msg = ChatMessage("system", content)
        self.mount(msg)
        self.messages.append({"role": "system", "content": content})
        self.scroll_end(animate=False)

    def start_assistant_message(self) -> ChatMessage:
        """Create an empty assistant message for streaming into."""
        msg = ChatMessage("assistant", "")
        self.mount(msg)
        self.scroll_end(animate=False)
        return msg

    def _hide_welcome_input(self):
        """Hide the welcome input row when chat starts."""
        try:
            input_row = self.query_one("#welcome-input-row")
            input_row.display = False
        except Exception:
            pass

    def clear_messages(self):
        for child in list(self.query("ChatMessage")):
            child.remove()
        self.messages = []
        self.add_welcome_message()
        try:
            input_row = self.query_one("#welcome-input-row")
            input_row.display = True
            self.query_one("#welcome-input", Input).focus()
        except Exception:
            pass
