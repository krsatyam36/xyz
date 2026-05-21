"""Header panel with large centered XYZ ASCII logo."""
from textual.widgets import Static
from textual.containers import Vertical
import os

from xyz import __version__


XYZ_LOGO = """
██╗   ██╗██╗
██║   ██║██║
██║   ██║██║
╚██╗ ██╔╝██║
 ╚████╔╝ ██║
  ╚═══╝  ╚═╝
"""


class HeaderPanel(Vertical):
    """Header with large centered XYZ logo."""

    DEFAULT_CSS = """
    HeaderPanel {
        height: auto;
        padding: 1 2;
        margin: 0 1;
        background: transparent;
        content-align: center top;
    }

    HeaderPanel #logo {
        color: #888888;
        text-style: bold;
        content-align: center middle;
        width: 100%;
    }

    HeaderPanel #logo .light {
        color: #e0e0e0;
    }
    """

    def compose(self):
        """Create header with logo."""
        logo_text = self._build_logo()
        yield Static(logo_text, id="logo")

    def _build_logo(self) -> str:
        """Build the XYZ logo with light/dark blocks like opencode."""
        logo_lines = XYZ_LOGO.strip().split("\n")
        result_lines = []
        for line in logo_lines:
            styled_line = line.replace("█", "[#888888]█[/]").replace("╗", "[#888888]╗[/]").replace("║", "[#888888]║[/]").replace("╝", "[#888888]╝[/]").replace("╔", "[#888888][/]").replace("╚", "[#888888]╚[/]")
            result_lines.append(styled_line)
        return "\n".join(result_lines)
