"""Compact header panel with welcome info."""
from textual.widgets import Static
from textual.containers import Horizontal
import os

from xyz import __version__


class HeaderPanel(Horizontal):
    """Compact header with version, model, and path info."""

    DEFAULT_CSS = """
    HeaderPanel {
        height: 3;
        padding: 0 2;
        margin: 0 1;
        background: #0d0d0d;
    }

    HeaderPanel #header-left {
        width: 1fr;
        color: #c890c8;
        text-style: bold;
        content-align: left middle;
    }

    HeaderPanel #header-right {
        width: auto;
        color: #888888;
        content-align: right middle;
    }
    """

    def compose(self):
        """Create compact header."""
        cwd = os.getcwd()
        home = os.path.expanduser("~")
        display_path = cwd.replace(home, "~", 1) if cwd.startswith(home) else cwd

        yield Static(f"XYZ v{__version__}  —  {display_path}", id="header-left")
        yield Static("meta/llama-3.3-70b-instruct", id="header-right")
