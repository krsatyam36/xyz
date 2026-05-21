# XYZ TUI - Beautiful Terminal Interface

> A premium, modern terminal UI for AI coding assistant built with Textual

XYZ TUI is a beautiful, interactive terminal interface inspired by Claude Code, Cursor, and Warp AI. Built with Python and Textual framework, it provides a cinematic, hacker-style experience for AI-powered coding assistance.

---

## Features

- **Premium Visual Design** - Futuristic, minimal, hacker-style aesthetic
- **Full-Screen Terminal UI** - Complete terminal application with panels and widgets
- **Interactive Command Palette** - Floating command menu with filtering and keyboard navigation
- **Streaming Text Animation** - Real-time typing effect for AI responses
- **Activity Indicators** - Animated spinners for different operations
- **Status Bar** - Real-time system information display
- **Themeable** - Amber/orange color scheme with customizable styling
- **Keyboard Navigation** - Full keyboard support with shortcuts

---

## Installation

```bash
# Install dependencies
pip install textual rich

# Or use requirements.txt
pip install -r requirements.txt
```

---

## Quick Start

```bash
# Run the TUI application
python3 -m ui.app

# Or use the launcher
python3 ui/tui.py
```

---

## Interface Layout

```
┌─────────────────────────────────────────────────────────────────────┐
│  XYZ v0.1.0                                                         │
│  ┌─────────────────────────────────────────────────────────────────│
│  │  [Logo]  Welcome back!        │  What's new        │  Tips      ││
│  │          XYZ — AI Coding      │  • Connected to    │  Run /init ││
│  │          Assistant            │    NVIDIA NIM      │  to create ││
│  │          NVIDIA NIM Gateway   │  • 132 models      │  XYZ.md    ││
│  │          ~/projects/xyz       │  • Tool system     │            ││
│  └─────────────────────────────────────────────────────────────────┘│
│                                                                     │
│  > Type your message... (Shift+Enter for new line)                 │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │  Commands (type to search...)                          x        ││
│  │  /help          Show all commands                               ││
│  │  /models        Browse available models                         ││
│  │  /use <model>   Switch to a model                               ││
│  │  /tools         List available tools                            ││
│  │  /trust [on|off] Toggle trust mode                              ││
│  │  /context       Show context usage                              ││
│  │  /settings      Open settings                                   ││
│  │  /clear         Clear conversation                              ││
│  │  /export        Export conversation                             ││
│  │  /history       Show conversation history                       ││
│  │  /status        Show system status                              ││
│  │  /quit          Exit XYZ                                        ││
│  │  ↑/↓ navigate • Enter select • Esc close                        ││
│  └─────────────────────────────────────────────────────────────────┘│
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────────│
│  │  ● Model: qwen/qwen2.5-coder-32b  Context: 12.4k/128k  Tools:12 ││
│  └─────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────┘
```

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+P` | Open command palette |
| `Ctrl+L` | Clear chat |
| `Esc` | Close palette |
| `Enter` | Send message / Select command |
| `Shift+Enter` | New line in input |
| `↑/↓` | Navigate command list |
| `q` | Quit application |

---

## Slash Commands

| Command | Description |
|---------|-------------|
| `/help` | Show all commands |
| `/models` | Browse available models |
| `/use <model>` | Switch to a model |
| `/tools` | List available tools |
| `/trust [on|off]` | Toggle trust mode |
| `/context` | Show context usage |
| `/settings` | Open settings |
| `/clear` | Clear conversation |
| `/export` | Export conversation |
| `/history` | Show conversation history |
| `/status` | Show system status |
| `/quit` | Exit XYZ |

---

## Project Structure

```
ui/
├── app.py                 # Main Textual application
├── tui.py                 # TUI launcher
├── screens/               # Screen definitions
├── widgets/               # Reusable widgets
│   ├── stream_text.py     # Streaming text widget
│   └── activity_indicator.py  # Activity indicator widget
├── panels/                # UI panels
│   ├── header_panel.py    # Top header with welcome
│   ├── chat_panel.py      # Chat area with messages
│   ├── input_panel.py     # Input bar
│   ├── status_bar.py      # Bottom status bar
│   └── command_palette.py # Command palette
├── components/            # UI components
└── styles/                # CSS stylesheets
    ├── app.tcss           # Global styles
    └── main.tcss          # Main screen styles
```

---

## Color Palette

| Color | Hex | Usage |
|-------|-----|-------|
| Background | `#000000` | Pure black background |
| Surface | `#0a0a0a` | Panel backgrounds |
| Surface Lighter | `#1a1a1a` | Borders and separators |
| Accent | `#ff9500` | Amber/orange primary |
| Accent Lighter | `#ffb340` | Hover states |
| Text | `#ffffff` | Primary text |
| Text Muted | `#888888` | Secondary text |
| Success | `#00ff00` | Success indicators |
| Warning | `#ffaa00` | Warning indicators |
| Error | `#ff0000` | Error indicators |

---

## Customization

### Adding New Commands

1. Add command to `COMMANDS_LIST` in `app.py`
2. Add handler method `_cmd_<name>` in `MainScreen`
3. Register in `commands` dict in `_handle_command`

### Adding New Panels

1. Create panel class in `ui/panels/`
2. Define `DEFAULT_CSS` for styling
3. Add to `MainScreen.compose()` method

### Modifying Styles

Edit CSS files in `ui/styles/`:
- `app.tcss` - Global styles
- `main.tcss` - Main screen styles
- Panel-specific CSS in panel files

---

## Technical Details

### Framework
- **Textual** - Modern TUI framework for Python
- **Rich** - Terminal formatting and rendering

### Architecture
- Component-based design
- Reactive state management
- CSS styling system
- Keyboard event handling
- Async worker support

### Performance
- Efficient rendering with Textual
- Lazy loading of components
- Optimized CSS selectors
- Minimal repaints

---

## Development

### Running in Development Mode

```bash
textual run --dev ui/app.py
```

### Debugging

```bash
textual run --dev ui/app.py
# Opens browser-based inspector at http://localhost:8080
```

### Testing

```bash
pytest tests/
```

---

## Roadmap

- [ ] Backend integration with AI models
- [ ] File editing capabilities
- [ ] Git integration
- [ ] Plugin system
- [ ] Custom themes
- [ ] Multi-pane layout
- [ ] Syntax highlighting
- [ ] Auto-completion
- [ ] Session persistence
- [ ] Export to markdown/PDF

---

## Created By

**Kumar Satyam**
- Email: kumarsatyam3135@gmail.com

---

## License

MIT License
