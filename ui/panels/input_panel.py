"""Input panel with prompt and message input."""
from textual.widgets import Input, Static
from textual.containers import Horizontal, Container
from textual.binding import Binding


class InputPanel(Container):
    """Centered input line with prompt symbol."""

    DEFAULT_CSS = """
    InputPanel {
        height: 3;
        padding: 0 2;
        margin: 1 0;
        background: transparent;
        align: center middle;
    }

    InputPanel #input-row {
        width: 80%;
        height: 3;
    }

    InputPanel #input-prompt {
        width: 2;
        color: #888888;
        content-align: left middle;
    }

    InputPanel #message-input {
        width: 1fr;
        border: none;
        background: transparent;
        color: #e0e0e0;
    }

    InputPanel #message-input:focus {
        border: none;
        background: transparent;
    }
    """

    def compose(self):
        """Create input line."""
        with Horizontal(id="input-row"):
            yield Static("> ", id="input-prompt")
            yield Input(
                placeholder="Type your message...",
                id="message-input",
            )

    def on_mount(self) -> None:
        """Focus the input."""
        self.query_one("#message-input", Input).focus()
