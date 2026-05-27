"""Status bar with model info and system status."""
from textual.widgets import Static
from textual.containers import Horizontal
from textual.reactive import reactive
from datetime import datetime
import asyncio


class StatusBar(Horizontal):
    """Bottom status bar with system information."""

    DEFAULT_CSS = """
    StatusBar {
        height: 3;
        padding: 0 2;
        margin: 0 1;
        background: transparent;
    }

    StatusBar .status-item {
        padding: 0 2;
        color: #888888;
    }

    StatusBar .status-value {
        color: #e0e0e0;
    }

    StatusBar .status-right {
        padding: 0 2;
        color: #888888;
    }

    StatusBar .status-indicator {
        margin-right: 1;
    }

    StatusBar .status-indicator.ready {
        color: #00ff00;
    }

    StatusBar .status-indicator.thinking {
        color: #ffaa00;
    }
    """
    
    current_model = reactive("qwen/qwen2.5-coder-32b-instruct")
    context_used = reactive(12400)
    context_total = reactive(128000)
    tools_count = reactive(12)
    trust_mode = reactive(False)
    current_status = reactive("ready")
    
    def compose(self):
        """Create status bar."""
        yield Static("●", classes="status-indicator ready", id="status-indicator")
        yield Static(classes="status-item")
        yield Static(classes="status-right", id="status-right")
    
    def on_mount(self) -> None:
        """Initialize status bar."""
        self._update_display()
        self._start_clock()
    
    def _update_display(self):
        """Update status bar display."""
        items = self.query(".status-item")
        
        # Model
        model_short = self.current_model.split("/")[-1] if "/" in self.current_model else self.current_model
        if items:
            items[0].update(f"Model: {model_short}")
        
        # Right side - time
        right = self.query_one("#status-right", Static)
        current_time = datetime.now().strftime("%I:%M %p")
        right.update(f"{current_time}")
    
    def _start_clock(self):
        """Start clock update timer."""
        async def update_clock():
            while True:
                await asyncio.sleep(30)
                self._update_display()
        
        self.run_worker(update_clock)
    
    def set_status(self, status: str):
        """Set current status. Safe to call during teardown."""
        self.current_status = status
        try:
            indicator = self.query_one("#status-indicator", Static)
            if status == "ready":
                indicator.update("●")
                indicator.remove_class("thinking", "busy")
                indicator.add_class("ready")
            elif status == "thinking":
                indicator.update("◌")
                indicator.remove_class("ready", "busy")
                indicator.add_class("thinking")
            elif status == "busy":
                indicator.update("◉")
                indicator.remove_class("ready", "thinking")
                indicator.add_class("busy")
            self._update_display()
        except Exception:
            pass
    
    def set_trust(self, enabled: bool):
        """Set trust mode."""
        self.trust_mode = enabled
        self._update_display()
    
    def toggle_trust(self) -> bool:
        """Toggle trust mode."""
        self.trust_mode = not self.trust_mode
        self._update_display()
        return self.trust_mode
    
    def get_context_usage(self) -> dict:
        """Get context usage information."""
        used_k = self.context_used / 1000
        total_k = self.context_total / 1000
        available_k = (self.context_total - self.context_used) / 1000
        percentage = (self.context_used / self.context_total) * 100
        
        return {
            "used": f"{used_k:.1f}k tokens",
            "total": f"{total_k:.0f}k tokens",
            "available": f"{available_k:.1f}k tokens",
            "percentage": f"{percentage:.1f}",
        }
    
    def get_full_status(self) -> dict:
        """Get full status information."""
        return {
            "Model": self.current_model,
            "Context Used": f"{self.context_used} tokens",
            "Context Total": f"{self.context_total} tokens",
            "Tools": self.tools_count,
            "Trust Mode": "ON" if self.trust_mode else "OFF",
            "Status": self.current_status,
        }
