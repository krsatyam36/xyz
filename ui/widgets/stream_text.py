"""Stream text widget with typing animation effect."""
from textual.widgets import Static
from textual.reactive import reactive
import asyncio


class StreamText(Static):
    """Text widget with streaming/typing animation."""
    
    DEFAULT_CSS = """
    StreamText {
        color: #ffffff;
        padding: 0;
    }
    
    StreamText .cursor {
        color: #ff9500;
        text-style: bold;
    }
    """
    
    full_text = reactive("")
    displayed_text = reactive("")
    streaming = reactive(False)
    cursor_visible = reactive(True)
    
    def __init__(self, text: str = "", speed: float = 0.02, **kwargs):
        super().__init__(**kwargs)
        self.full_text = text
        self.speed = speed
        self._stream_task = None
    
    async def stream(self, text: str, speed: float = None):
        """Stream text with typing effect."""
        if speed:
            self.speed = speed
        
        self.streaming = True
        self.full_text = text
        self.displayed_text = ""
        
        for i, char in enumerate(text):
            self.displayed_text += char
            self.update(self.displayed_text + ("█" if self.cursor_visible else " "))
            await asyncio.sleep(self.speed)
        
        self.streaming = False
        self.update(self.displayed_text)
    
    def watch_cursor_visible(self, visible: bool):
        """Update cursor visibility."""
        if self.streaming:
            cursor = "█" if visible else " "
            self.update(self.displayed_text + cursor)
    
    def on_mount(self) -> None:
        """Start cursor blink animation."""
        async def blink_cursor():
            while self.streaming or self.cursor_visible:
                await asyncio.sleep(0.5)
                if self.streaming:
                    self.cursor_visible = not self.cursor_visible
        
        self._stream_task = self.run_worker(blink_cursor)
    
    def on_unmount(self) -> None:
        """Clean up streaming task."""
        if self._stream_task:
            self._stream_task.cancel()
