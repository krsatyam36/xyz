"""Interactive model picker modal for Textual TUI."""
from textual.app import ComposeResult
from textual.containers import Container, ScrollableContainer
from textual.widgets import Static, Input
from textual.binding import Binding
from textual.screen import Screen


class ModelPickerItem(Static):
    """Single model item in the picker."""

    DEFAULT_CSS = """
    ModelPickerItem {
        height: 1;
        padding: 0 2;
    }
    ModelPickerItem:hover {
        background: $accent 20%;
    }
    ModelPickerItem.selected {
        background: $accent 30%;
    }
    """

    def __init__(self, model_name: str, is_active: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.model_name = model_name
        self.is_active = is_active

    def render(self) -> str:
        marker = "●" if self.is_active else " "
        return f"{marker} {self.model_name}"


class ModelPickerModal(Screen):
    """Modal screen for selecting a model with keyboard navigation."""

    BINDINGS = [
        Binding("escape", "close", "Cancel", priority=True),
        Binding("enter", "select", "Select", priority=True),
        Binding("up", "move_up", "Up", priority=True),
        Binding("down", "move_down", "Down", priority=True),
    ]

    DEFAULT_CSS = """
    ModelPickerModal {
        align: center middle;
        background: $surface 80%;
    }
    #picker-dialog {
        width: 60;
        height: auto;
        max-height: 70%;
        border: solid $accent;
        background: $surface;
        padding: 1;
    }
    #picker-title {
        width: 100%;
        padding: 0 1;
        text-style: bold;
    }
    #model-search {
        width: 100%;
        margin: 0 0 1 0;
    }
    #model-list {
        width: 100%;
        height: 8;
    }
    #picker-hint {
        width: 100%;
        padding: 0 1;
        color: $text-muted;
    }
    """

    def __init__(self, models: list, current_model: str = ""):
        super().__init__()
        self.models = models
        self.current_model = current_model
        self.selected_index = 0
        self.filter_text = ""
        self.filtered_models = list(models)

    def compose(self) -> ComposeResult:
        with Container(id="picker-dialog"):
            yield Static("Select Model (↑↓ navigate, Enter select, Esc cancel)", id="picker-title")
            yield Input(placeholder="Search models...", id="model-search")
            yield ScrollableContainer(id="model-list")
            yield Static("", id="picker-hint")

    def on_mount(self) -> None:
        self._update_list()
        self.query_one("#model-search", Input).focus()

    def _update_list(self) -> None:
        list_container = self.query_one("#model-list", ScrollableContainer)
        list_container.remove_children()

        filtered = [m for m in self.models if self.filter_text.lower() in m.lower()]
        if not filtered:
            filtered = self.models

        for i, model in enumerate(filtered):
            is_active = model == self.current_model
            item = ModelPickerItem(model, is_active, id=f"model-item-{i}")
            list_container.mount(item)

        self.filtered_models = filtered
        self._highlight_selected()

    def _highlight_selected(self) -> None:
        items = list(self.query("ModelPickerItem"))
        for i, item in enumerate(items):
            if i == self.selected_index:
                item.add_class("selected")
                self.query_one("#model-list", ScrollableContainer).scroll_to_widget(item)
            else:
                item.remove_class("selected")

    def action_move_up(self) -> None:
        if self.filtered_models:
            self.selected_index = (self.selected_index - 1) % len(self.filtered_models)
            self._highlight_selected()

    def action_move_down(self) -> None:
        if self.filtered_models:
            self.selected_index = (self.selected_index + 1) % len(self.filtered_models)
            self._highlight_selected()

    def action_select(self) -> None:
        if self.filtered_models:
            selected = self.filtered_models[self.selected_index]
            self.dismiss(selected)

    def action_close(self) -> None:
        self.dismiss(None)

    def on_input_changed(self, event: Input.Changed) -> None:
        self.filter_text = event.value
        self.selected_index = 0
        self._update_list()
