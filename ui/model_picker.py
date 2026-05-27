"""Interactive model picker with keyboard navigation."""
import os
from typing import Optional

from prompt_toolkit import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.layout import Layout, Window, FormattedTextControl, WindowAlign
from prompt_toolkit.layout.containers import HSplit, VSplit, Float, FloatContainer, Window
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.styles import Style as PtStyle

from xyz.config import load_config, save_config, discover_models, get_api_key, DEFAULT_MODELS


STYLE = PtStyle([
    ("title", "bold #c890c8"),
    ("subtitle", "#888888"),
    ("model-name", "#e0e0e0"),
    ("model-name.selected", "bold #ffffff bg:#333333"),
    ("model-name.active", "bold #c890c8"),
    ("model-provider", "#666666"),
    ("model-provider.selected", "#999999 bg:#333333"),
    ("indicator", "#44ff66"),
    ("indicator.inactive", "#444444"),
    ("search", "#c890c8"),
    ("search-text", "#ffffff"),
    ("help-text", "#666666"),
    ("counter", "#888888"),
    ("divider", "#333333"),
    ("cursor-line", "bg:#333333"),
])


def show_model_picker(api_key: Optional[str] = None) -> Optional[str]:
    """Show an interactive model picker with keyboard navigation.

    Returns the selected model ID or None if cancelled.
    """
    if api_key:
        models = discover_models(api_key)
    else:
        api_key = get_api_key()
        if api_key:
            models = discover_models(api_key)
        else:
            models = DEFAULT_MODELS.copy()

    if not models:
        return None

    config = load_config()
    current_model = config.default_model

    selected_index = 0
    search_text = ""
    filtered_models = list(models)
    is_searching = False

    for i, m in enumerate(models):
        if m == current_model:
            selected_index = i
            break

    def get_filtered():
        if not search_text:
            return list(models)
        st = search_text.lower()
        return [m for m in models if st in m.lower()]

    def format_model(index: int, model_id: str, is_current: bool) -> list:
        result = []
        is_selected = index == selected_index
        prefix = "  "

        if is_current:
            result.append(("class:indicator", "● "))
        else:
            result.append(("class:indicator.inactive", "○ "))

        if is_selected:
            result.append(("class:cursor-line", "▸ " if not is_current else "▸ "))
        else:
            result.append(("", "  "))

        parts = model_id.split("/", 1)
        provider = parts[0] if len(parts) > 1 else ""
        name = parts[1] if len(parts) > 1 else model_id

        if is_selected:
            result.append(("class:model-name.selected", model_id))
        elif is_current:
            result.append(("class:model-name.active", model_id))
        else:
            result.append(("class:model-name", model_id))

        if is_current:
            result.append(("class:indicator", "  (active)"))

        return result

    def get_formatted_models():
        fm = get_filtered()
        if not fm:
            return [("class:help-text", "  No models match your search")]
        result = []
        for i, m in enumerate(fm):
            is_current = m == current_model
            result.extend(format_model(
                models.index(m) if m in models else 0,
                m, is_current
            ))
            result.append(("", "\n"))
        return result

    kb = KeyBindings()

    @kb.add("up")
    def _go_up(event):
        nonlocal selected_index
        fm = get_filtered()
        if fm:
            idx = max(0, selected_index - 1)
            while idx >= 0 and models[idx] not in fm:
                idx -= 1
            selected_index = max(0, idx)

    @kb.add("down")
    def _go_down(event):
        nonlocal selected_index
        fm = get_filtered()
        if fm:
            idx = selected_index + 1
            while idx < len(models) and models[idx] not in fm:
                idx += 1
            selected_index = min(len(models) - 1, idx)

    @kb.add("enter")
    def _select(event):
        fm = get_filtered()
        if fm and selected_index < len(models):
            event.app.exit(result=models[selected_index])
        else:
            event.app.exit(result=None)

    @kb.add("escape")
    def _cancel(event):
        event.app.exit(result=None)

    @kb.add("tab")
    def _toggle_search(event):
        nonlocal is_searching
        is_searching = not is_searching

    @kb.add("/")
    def _search_focus(event):
        nonlocal is_searching
        is_searching = True

    @kb.add(Keys.BackSpace)
    def _backspace(event):
        nonlocal search_text, selected_index
        if is_searching and search_text:
            search_text = search_text[:-1]
            fm = get_filtered()
            if fm and models[selected_index] not in fm:
                selected_index = models.index(fm[0]) if fm[0] in models else 0

    @kb.add(Keys.Any)
    def _insert(event):
        nonlocal search_text, selected_index
        if is_searching:
            key = event.key
            if len(key) == 1 and key.isprintable():
                search_text += key
                fm = get_filtered()
                if fm and models[selected_index] not in fm:
                    selected_index = models.index(fm[0]) if fm[0] in models else 0

    def get_title_bar():
        result = []
        result.append(("class:title", "  Select Model\n"))
        result.append(("class:subtitle", "  Browse with ↑↓  Enter to select  Esc to cancel  / to search\n"))
        if search_text:
            result.append(("class:search", "  Search: "))
            result.append(("class:search-text", search_text))
            result.append(("class:help-text", "  (Backspace to clear, Esc to cancel)\n"))
        result.append(("class:divider", "\n"))
        return result

    def get_footer():
        fm = get_filtered()
        total = len(models)
        shown = len(fm)
        result = []
        result.append(("class:divider", "\n"))
        result.append(("class:help-text",
            f"  ↑↓ Navigate  Enter Select  Esc Cancel  / Search  "
            f"({shown}/{total} models)"))
        return result

    def get_content():
        result = []
        result.extend(get_title_bar())
        fm = get_filtered()
        if not fm:
            result.append(("class:help-text", "  No models match your search\n"))
        else:
            start = max(0, selected_index - 8)
            end = min(len(models), selected_index + 8)
            display_range = range(start, end)
            for i in display_range:
                m = models[i]
                is_current = m == current_model
                is_selected = i == selected_index
                cursor = "▸" if is_selected else " "
                indicator = "●" if is_current else "○"
                name_style = "class:model-name.selected" if is_selected else (
                    "class:model-name.active" if is_current else "class:model-name"
                )
                provider_style = "class:model-provider.selected" if is_selected else "class:model-provider"
                bg = " bg:#333333" if is_selected else ""

                active_tag = "  (active)" if is_current else ""
                active_style = "class:indicator" if is_current else ""

                display_name = m
                result.extend([
                    ("", f"  {indicator} "),
                    (name_style + bg, f"{cursor} {display_name}"),
                    (active_style + bg, active_tag),
                    ("", "\n"),
                ])
        result.extend(get_footer())
        return result

    control = FormattedTextControl(get_content, show_cursor=False)

    root = FloatContainer(
        content=Window(
            content=control,
            align=WindowAlign.LEFT,
            dont_extend_height=False,
            style="bg:#1a1a1a",
        ),
        floats=[],
    )

    layout = Layout(root)

    app = Application(
        layout=layout,
        key_bindings=kb,
        style=STYLE,
        mouse_support=False,
        full_screen=False,
    )

    try:
        result = app.run()
        return result
    except (EOFError, KeyboardInterrupt):
        return None
