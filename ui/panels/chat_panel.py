"""Chat panel with message display and streaming."""
from textual.widgets import Static
from textual.containers import ScrollableContainer
from textual.reactive import reactive
import asyncio


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
    }
    """

    messages: list = reactive([])

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._welcome = None

    def compose(self):
        self._welcome = Static(classes="welcome")
        yield self._welcome

    def on_mount(self) -> None:
        self.messages = []

    def add_welcome_message(self):
        self._welcome.update(
            "[#c890c8 bold]Welcome to XYZ![/]\n\n"
            "[#888888]Type a message or /help for commands.[/]\n\n"
            "[#888888]To connect, run:[/] [#c890c8]/login[/]"
        )

    def add_user_message(self, content: str):
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

    def clear_messages(self):
        for child in list(self.query("ChatMessage")):
            child.remove()
        self.messages = []
        self.add_welcome_message()
