"""Header panel with logo, welcome message, what's new, and tips."""
from textual.widgets import Static, Container
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
import os


class HeaderPanel(Container):
    """Top header panel with welcome section."""
    
    DEFAULT_CSS = """
    HeaderPanel {
        height: auto;
        max-height: 12;
        padding: 1 2;
        border: round $accent;
        margin: 1 1 0 1;
        background: $surface;
    }
    
    HeaderPanel .header-content {
        height: 100%;
    }
    
    HeaderPanel .welcome-section {
        width: 40%;
        height: 100%;
        padding: 1 2;
    }
    
    HeaderPanel .logo {
        width: 8;
        height: 6;
        content-align: center middle;
        color: $text;
    }
    
    HeaderPanel .welcome-title {
        color: $text;
        text-style: bold;
        margin-bottom: 1;
    }
    
    HeaderPanel .welcome-subtitle {
        color: $text-muted;
        margin-bottom: 1;
    }
    
    HeaderPanel .welcome-info {
        color: $text-muted;
    }
    
    HeaderPanel .whats-new-section {
        width: 35%;
        height: 100%;
        padding: 1 2;
        border-left: vkey $accent;
    }
    
    HeaderPanel .whats-new-title {
        color: $accent;
        text-style: bold;
        margin-bottom: 1;
    }
    
    HeaderPanel .whats-new-item {
        color: $text-muted;
        margin-bottom: 1;
    }
    
    HeaderPanel .tips-section {
        width: 25%;
        height: 100%;
        padding: 1 2;
        border: round $accent;
        margin-left: 1;
    }
    
    HeaderPanel .tips-title {
        color: $accent;
        text-style: bold;
        margin-bottom: 1;
    }
    
    HeaderPanel .tips-item {
        color: $text-muted;
        margin-bottom: 1;
    }
    """
    
    def compose(self):
        """Create header layout."""
        yield Container(
            self._create_welcome_section(),
            self._create_whats_new_section(),
            self._create_tips_section(),
            classes="header-content",
        )
    
    def _create_welcome_section(self):
        """Create welcome section with logo."""
        logo_art = """
        ╔══╗
        ║╗║
        ║╚╝║
        ╚══╝
        """.strip()
        
        cwd = os.getcwd()
        home = os.path.expanduser("~")
        display_path = cwd.replace(home, "~", 1) if cwd.startswith(home) else cwd
        
        return Container(
            Static(logo_art, classes="logo"),
            Static("Welcome back!", classes="welcome-title"),
            Static("XYZ — AI Coding Assistant", classes="welcome-subtitle"),
            Static("NVIDIA NIM Gateway • Multi-Model Runtime", classes="welcome-info"),
            Static(display_path, classes="welcome-info"),
            classes="welcome-section",
        )
    
    def _create_whats_new_section(self):
        """Create what's new section."""
        items = [
            "Connected to NVIDIA NIM",
            "132 models available",
            "Tool system ready",
            "Context window optimized",
        ]
        
        content = [Static("What's new", classes="whats-new-title")]
        for item in items:
            content.append(Static(f"• {item}", classes="whats-new-item"))
        
        content.append(Static("Type /help to get started", classes="whats-new-item"))
        
        return Container(*content, classes="whats-new-section")
    
    def _create_tips_section(self):
        """Create tips section."""
        tips = [
            "Run /init to create a XYZ.md file with instructions for the agent",
            "Run /models to browse available models",
        ]
        
        content = [Static("Tips for getting started", classes="tips-title")]
        for tip in tips:
            content.append(Static(tip, classes="tips-item"))
        
        return Container(*content, classes="tips-section")
