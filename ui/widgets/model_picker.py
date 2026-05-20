"""Interactive model picker modal for Textual TUI."""
from textual.app import ComposeResult
from textual.containers import Container, ScrollableContainer
from textual.widgets import Static, Button, Input
from textual.binding import Binding
from textual.widgets._button import ButtonVariant
from textual import __version__ as textual_version


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


class ModelPickerModal(Static):
    """Modal dialog for selecting a model with keyboard navigation."""
    
    BINDINGS = [
        Binding("escape", "close", "Cancel", priority=True),
        Binding("enter", "select", "Select"),
        Binding("up", "move_up", "Up"),
        Binding("down", "move_down", "Down"),
        Binding("k", "move_up", "Up"),
        Binding("j", "move_down", "Down"),
    ]
    
    DEFAULT_CSS = """
    ModelPickerModal {
        width: 60;
        height: 16;
        border: solid $accent;
        background: $surface;
        align: center middle;
    }
    ModelPickerModal > Container {
        width: 100%;
        height: 100%;
    }
    """
    
    def __init__(self, models: list, current_model: str = "", on_select=None, **kwargs):
        super().__init__(**kwargs)
        self.models = models
        self.current_model = current_model
        self.on_select = on_select
        self.selected_index = 0
        self.filter_text = ""
    
    def compose(self) -> ComposeResult:
        yield Container(
            Static("Select Model (↑↓ navigate, Enter select, Esc cancel)", id="picker-title"),
            Input(placeholder="Search models...", id="model-search"),
            ScrollableContainer(id="model-list"),
            Static("", id="picker-hint"),
            id="picker-container"
        )
    
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
            list_container.append(item)
        
        self.filtered_models = filtered
        self._highlight_selected()
    
    def _highlight_selected(self) -> None:
        for i, item in enumerate(self.query("ModelPickerItem")):
            if i == self.selected_index:
                item.add_class("selected")
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


def show_model_picker_modal(app, models: list, current_model: str = "", on_select=None):
    """Show the model picker modal and return the selected model."""
    modal = ModelPickerModal(models, current_model, on_select)
    app.push_screen(modal)
    return modal