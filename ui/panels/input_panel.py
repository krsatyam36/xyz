"""Input panel with multiline support and modern styling."""
from textual.widgets import Input, Static, Label
from textual.containers import Horizontal, Vertical
from textual.binding import Binding


class InputPanel(Vertical):
    """Bottom input panel with message input."""
    
    DEFAULT_CSS = """
    InputPanel {
        height: auto;
        padding: 1 2;
        margin: 0 1 1 1;
        border: round $accent;
        background: $surface;
    }
    
    InputPanel .input-container {
        height: auto;
        padding: 0 1;
    }
    
    InputPanel #message-input {
        width: 100%;
        height: 3;
        border: none;
        background: transparent;
        color: $text;
        padding: 0 1;
    }
    
    InputPanel #message-input:focus {
        border: none;
        background: transparent;
    }
    
    InputPanel .input-hint {
        color: $text-muted;
        padding: 0 1;
        margin-top: 1;
    }
    
    InputPanel .prompt-symbol {
        color: $success;
        text-style: bold;
        padding-right: 1;
    }
    """
    
    BINDINGS = [
        Binding("shift+enter", "newline", "New Line", show=False),
    ]
    
    def compose(self):
        """Create input panel."""
        yield Horizontal(
            Static(">", classes="prompt-symbol"),
            Input(
                placeholder="Type your message... (Shift+Enter for new line)",
                id="message-input",
            ),
            classes="input-container",
        )
        yield Static("Press Enter to send • Ctrl+P for commands • Esc to cancel", classes="input-hint")
    
    def action_newline(self):
        """Add newline to input."""
        input_widget = self.query_one("#message-input", Input)
        current_value = input_widget.value
        input_widget.value = current_value + "\n"
        # Move cursor to end
        input_widget.cursor_position = len(input_widget.value)
