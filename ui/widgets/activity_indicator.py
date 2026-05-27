"""Activity indicator widget with animations."""
from textual.widgets import Static
from textual.reactive import reactive
import asyncio


class ActivityIndicator(Static):
    """Animated activity indicator."""
    
    DEFAULT_CSS = """
    ActivityIndicator {
        color: #ff9500;
        text-style: bold;
        padding: 0 1;
    }
    
    ActivityIndicator.reading {
        color: #ff9500;
    }
    
    ActivityIndicator.writing {
        color: #00ff00;
    }
    
    ActivityIndicator.executing {
        color: #ffaa00;
    }
    
    ActivityIndicator.searching {
        color: #ff0000;
    }
    
    ActivityIndicator.thinking {
        color: #888888;
    }
    """
    
    activity_type = reactive("thinking")
    animation_frame = reactive(0)
    
    SPINNERS = {
        "thinking": ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "", "⠧", "⠇", "⠏"],
        "loading": ["◐", "◓", "", "◒"],
        "processing": ["⣾", "⣽", "⣻", "⢿", "⡿", "⣟", "⣯", "⣷"],
    }
    
    LABELS = {
        "thinking": "Thinking",
        "reading": "Reading",
        "writing": "Writing",
        "executing": "Executing",
        "searching": "Searching",
        "loading": "Loading",
        "processing": "Processing",
    }
    
    def __init__(self, activity_type: str = "thinking", **kwargs):
        super().__init__(**kwargs)
        self.activity_type = activity_type
        self._animation_task = None
    
    def on_mount(self) -> None:
        """Start animation."""
        self.add_class(self.activity_type)
        self._start_animation()
    
    def _start_animation(self):
        """Start spinner animation."""
        async def animate():
            spinner = self.SPINNERS.get(self.activity_type, self.SPINNERS["thinking"])
            label = self.LABELS.get(self.activity_type, "Working")
            
            while True:
                frame = spinner[self.animation_frame % len(spinner)]
                self.update(f"{frame} {label}...")
                self.animation_frame += 1
                await asyncio.sleep(0.1)
        
        self._animation_task = self.run_worker(animate)
    
    def set_activity(self, activity_type: str):
        """Change activity type."""
        self.remove_class(*self.LABELS.keys())
        self.activity_type = activity_type
        self.add_class(activity_type)
        self.animation_frame = 0
    
    def stop(self):
        """Stop animation."""
        if self._animation_task:
            self._animation_task.cancel()
        self.update("")
    
    def on_unmount(self) -> None:
        """Clean up animation task."""
        self.stop()
