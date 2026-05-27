from dataclasses import dataclass


@dataclass
class Theme:
    name: str
    description: str
    primary: str
    secondary: str
    accent: str
    border: str
    bg: str
    panel_bg: str
    text: str
    muted: str
    success: str
    warning: str
    error: str
    thinking: str
    executing: str
    reading: str
    writing: str


THEMES = {
    "claude": Theme(
        name="Claude",
        description="Claude Code inspired - warm copper/orange tones",
        primary="bold bright_red",
        secondary="bright_yellow",
        accent="bright_red",
        border="bright_red",
        bg="black",
        panel_bg="grey11",
        text="grey93",
        muted="grey50",
        success="bright_green",
        warning="bright_yellow",
        error="bright_red",
        thinking="bright_yellow",
        executing="bright_cyan",
        reading="bright_magenta",
        writing="bright_yellow",
    ),
    "midnight": Theme(
        name="Midnight",
        description="Deep dark blues and soft whites",
        primary="bold blue",
        secondary="cyan",
        accent="magenta",
        border="blue",
        bg="black",
        panel_bg="grey15",
        text="white",
        muted="grey50",
        success="green",
        warning="yellow",
        error="red",
        thinking="blue",
        executing="cyan",
        reading="magenta",
        writing="yellow",
    ),
    "obsidian": Theme(
        name="Obsidian",
        description="Pure dark with warm accents",
        primary="bold white",
        secondary="bright_yellow",
        accent="bright_red",
        border="grey50",
        bg="black",
        panel_bg="grey11",
        text="grey93",
        muted="grey50",
        success="bright_green",
        warning="bright_yellow",
        error="bright_red",
        thinking="grey63",
        executing="bright_cyan",
        reading="bright_magenta",
        writing="bright_yellow",
    ),
    "aurora": Theme(
        name="Aurora",
        description="Northern lights inspired greens and purples",
        primary="bold green",
        secondary="bright_magenta",
        accent="bright_cyan",
        border="green",
        bg="black",
        panel_bg="grey7",
        text="white",
        muted="grey50",
        success="bright_green",
        warning="yellow",
        error="red",
        thinking="green",
        executing="bright_magenta",
        reading="bright_cyan",
        writing="yellow",
    ),
    "solarized": Theme(
        name="Solarized",
        description="Classic solarized dark palette",
        primary="bold cyan",
        secondary="yellow",
        accent="magenta",
        border="blue",
        bg="black",
        panel_bg="#073642",
        text="#839496",
        muted="#586e75",
        success="#859900",
        warning="#b58900",
        error="#dc322f",
        thinking="#268bd2",
        executing="#2aa198",
        reading="#6c71c4",
        writing="#b58900",
    ),
    "monokai": Theme(
        name="Monokai",
        description="Vibrant monokai colors",
        primary="bold bright_yellow",
        secondary="bright_green",
        accent="bright_magenta",
        border="yellow",
        bg="black",
        panel_bg="#272822",
        text="#f8f8f2",
        muted="#75715e",
        success="#a6e22e",
        warning="#f4bf75",
        error="#f92672",
        thinking="#66d9ef",
        executing="#a6e22e",
        reading="#ae81ff",
        writing="#f4bf75",
    ),
}

DEFAULT_THEME = "claude"


def get_theme(name: str) -> Theme:
    return THEMES.get(name, THEMES[DEFAULT_THEME])


def list_themes() -> list[dict]:
    return [
        {"name": t.name, "description": t.description}
        for t in THEMES.values()
    ]
