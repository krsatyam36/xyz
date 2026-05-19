"""Command palette with filtering and keyboard navigation."""
from textual.widgets import Static, Input, DataTable
from textual.containers import Vertical, Horizontal
from textual.binding import Binding
from textual.reactive import reactive
from textual.screen import ModalScreen
import asyncio


class CommandPalette(Vertical):
    """Floating command palette inside the terminal."""
    
    DEFAULT_CSS = """
    CommandPalette {
        width: 60;
        height: 20;
        border: round $accent;
        background: $surface;
        padding: 1;
        display: none;
    }
    
    CommandPalette .palette-header {
        height: 3;
        padding: 0 1;
        border-bottom: solid $accent;
    }
    
    CommandPalette .palette-title {
        color: $text;
        text-style: bold;
    }
    
    CommandPalette .palette-hint {
        color: $text-muted;
    }
    
    CommandPalette #palette-filter {
        width: 100%;
        border: none;
        background: transparent;
        color: $text;
        padding: 0 1;
    }
    
    CommandPalette #palette-filter:focus {
        border: none;
        background: transparent;
    }
    
    CommandPalette #command-table {
        height: 1fr;
        border: none;
        background: transparent;
    }
    
    CommandPalette .palette-footer {
        height: 3;
        padding: 0 1;
        border-top: solid $surface-lighter;
        color: $text-muted;
    }
    """
    
    BINDINGS = [
        Binding("escape", "close", "Close", show=False),
        Binding("up", "navigate_up", "Up", show=False),
        Binding("down", "navigate_down", "Down", show=False),
        Binding("enter", "select_command", "Select", show=False),
    ]
    
    commands = [
        ("/help", "Show all commands"),
        ("/models", "Browse available models"),
        ("/use <model>", "Switch to a model"),
        ("/tools", "List available tools"),
        ("/trust [on|off]", "Toggle trust mode"),
        ("/context", "Show context usage"),
        ("/settings", "Open settings"),
        ("/clear", "Clear conversation"),
        ("/export", "Export conversation"),
        ("/history", "Show conversation history"),
        ("/status", "Show system status"),
        ("/quit", "Exit XYZ"),
    ]
    
    filtered_commands = reactive([])
    selected_index = reactive(0)
    
    def compose(self):
        """Create command palette."""
        yield Horizontal(
            Static("Commands", classes="palette-title"),
            Static("(type to search...)", classes="palette-hint"),
            classes="palette-header",
        )
        yield Input(placeholder="Search commands...", id="palette-filter")
        yield DataTable(id="command-table")
        yield Static("↑/↓ navigate • Enter select • Esc close", classes="palette-footer")
    
    def on_mount(self) -> None:
        """Initialize command palette."""
        self._setup_table()
        self._update_filtered_commands("")
    
    def _setup_table(self):
        """Setup command table."""
        table = self.query_one("#command-table", DataTable)
        table.add_columns("Command", "Description")
        table.zebra_stripes = True
        table.cursor_type = "row"
        table.show_header = False
    
    def _update_filtered_commands(self, filter_text: str):
        """Update filtered commands based on search text."""
        filter_lower = filter_text.lower().lstrip("/")
        
        self.filtered_commands = [
            cmd for cmd in self.commands
            if filter_lower in cmd[0].lower().lstrip("/") or filter_lower in cmd[1].lower()
        ]
        
        self._update_table()
    
    def _update_table(self):
        """Update command table with filtered commands."""
        table = self.query_one("#command-table", DataTable)
        table.clear()
        
        for cmd, desc in self.filtered_commands:
            table.add_row(cmd, desc)
        
        # Select first row
        if self.filtered_commands:
            table.move_cursor(row=0)
    
    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle filter input changes."""
        if event.input.id == "palette-filter":
            self._update_filtered_commands(event.value)
    
    def action_close(self) -> None:
        """Close command palette."""
        self.display = False
        # Focus back to main input
        try:
            self.screen.query_one("#message-input").focus()
        except Exception:
            pass
    
    def action_navigate_up(self) -> None:
        """Navigate up in command list."""
        table = self.query_one("#command-table", DataTable)
        if table.cursor_row > 0:
            table.move_cursor(row=table.cursor_row - 1)
    
    def action_navigate_down(self) -> None:
        """Navigate down in command list."""
        table = self.query_one("#command-table", DataTable)
        if table.cursor_row < len(self.filtered_commands) - 1:
            table.move_cursor(row=table.cursor_row + 1)
    
    def action_select_command(self) -> None:
        """Select current command."""
        table = self.query_one("#command-table", DataTable)
        if table.cursor_row < len(self.filtered_commands):
            cmd = self.filtered_commands[table.cursor_row][0]
            self.display = False
            
            # Insert command into main input
            try:
                main_input = self.screen.query_one("#message-input")
                main_input.value = cmd
                main_input.focus()
            except Exception:
                pass
    
    def focus_filter(self) -> None:
        """Focus the filter input."""
        self.query_one("#palette-filter", Input).focus()
        self.query_one("#palette-filter", Input).value = ""
