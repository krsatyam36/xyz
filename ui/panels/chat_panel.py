"""Chat panel with message display and streaming support."""
from textual.widgets import Static, ScrollableContainer
from textual.containers import Vertical
from textual.reactive import reactive
from rich.markdown import Markdown
from rich.console import Console
from rich.text import Text
import asyncio


class ChatMessage(Static):
    """Individual chat message widget."""
    
    DEFAULT_CSS = """
    ChatMessage {
        padding: 1 2;
        margin: 0 0 1 0;
        border: round $surface-lighter;
        background: $surface;
    }
    
    ChatMessage.user-message {
        border: round $accent;
        background: $surface;
    }
    
    ChatMessage.assistant-message {
        border: round $success;
        background: $surface;
    }
    
    ChatMessage.system-message {
        border: round $warning;
        background: $surface;
    }
    
    ChatMessage .message-header {
        color: $text-muted;
        text-style: bold;
        margin-bottom: 1;
    }
    
    ChatMessage .message-content {
        color: $text;
    }
    """
    
    def __init__(self, role: str, content: str, **kwargs):
        super().__init__(**kwargs)
        self.role = role
        self.content = content
    
    def on_mount(self) -> None:
        """Render message content."""
        self._render_message()
    
    def _render_message(self):
        """Render message based on role."""
        if self.role == "user":
            self.add_class("user-message")
            header = "You"
        elif self.role == "assistant":
            self.add_class("assistant-message")
            header = "XYZ"
        else:
            self.add_class("system-message")
            header = "System"
        
        # Create message content
        content_widget = Static(classes="message-content")
        content_widget.update(self.content)
        
        # Add header and content
        self.mount(Static(header, classes="message-header"))
        self.mount(content_widget)


class ChatPanel(ScrollableContainer):
    """Main chat area with message display."""
    
    DEFAULT_CSS = """
    ChatPanel {
        height: 1fr;
        padding: 1 2;
        margin: 0 1;
        border: round $surface-lighter;
        background: $surface;
        overflow-y: auto;
    }
    
    ChatPanel .welcome-message {
        padding: 2 4;
        text-align: center;
        color: $text-muted;
    }
    
    ChatPanel .welcome-title {
        color: $accent;
        text-style: bold;
        margin-bottom: 1;
    }
    
    ChatPanel .welcome-text {
        color: $text-muted;
        margin-bottom: 2;
    }
    
    ChatPanel .activity-indicator {
        padding: 1 2;
        color: $text-muted;
        text-style: italic;
    }
    """
    
    messages = reactive([])
    
    def compose(self):
        """Create chat panel."""
        yield Static(classes="welcome-message")
    
    def on_mount(self) -> None:
        """Initialize chat panel."""
        self.messages = []
    
    def add_welcome_message(self):
        """Add welcome message to chat."""
        welcome = self.query_one(".welcome-message", Static)
        welcome.update(
            "Welcome to XYZ AI Coding Assistant!\n\n"
            "Type your message below or use /help to see available commands.\n\n"
            "I can help you with:\n"
            "• Reading and writing files\n"
            "• Executing shell commands\n"
            "• Searching code\n"
            "• Answering programming questions\n\n"
            "Let's get started!"
        )
    
    def add_user_message(self, content: str):
        """Add user message to chat."""
        msg = ChatMessage("user", content)
        self.mount(msg)
        self.messages.append({"role": "user", "content": content})
        self.scroll_end(animate=True)
    
    def add_assistant_message(self, content: str):
        """Add assistant message to chat."""
        msg = ChatMessage("assistant", content)
        self.mount(msg)
        self.messages.append({"role": "assistant", "content": content})
        self.scroll_end(animate=True)
    
    def add_system_message(self, content: str):
        """Add system message to chat."""
        msg = ChatMessage("system", content)
        self.mount(msg)
        self.messages.append({"role": "system", "content": content})
        self.scroll_end(animate=True)
    
    async def stream_assistant_message(self, content: str, delay: float = 0.02):
        """Stream assistant message with typing effect."""
        # Create message widget
        msg = ChatMessage("assistant", "")
        self.mount(msg)
        
        # Get content widget
        content_widget = msg.query_one(".message-content", Static)
        
        # Stream content character by character
        streamed_content = ""
        for char in content:
            streamed_content += char
            content_widget.update(streamed_content)
            self.scroll_end(animate=False)
            await asyncio.sleep(delay)
        
        # Add to messages
        self.messages.append({"role": "assistant", "content": content})
    
    def add_activity_indicator(self, activity: str):
        """Add activity indicator."""
        indicator = Static(f"[{activity}]", classes="activity-indicator")
        self.mount(indicator)
        self.scroll_end(animate=True)
        return indicator
    
    def remove_activity_indicator(self, indicator):
        """Remove activity indicator."""
        indicator.remove()
    
    def clear_messages(self):
        """Clear all messages."""
        for child in self.query("ChatMessage"):
            child.remove()
        for child in self.query(".activity-indicator"):
            child.remove()
        self.messages = []
        self.add_welcome_message()
