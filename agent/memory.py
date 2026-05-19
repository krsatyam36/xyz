import uuid
from datetime import datetime
from typing import Optional
from xyz.config import save_session, load_session


class SessionMemory:
    def __init__(self, session_id: Optional[str] = None):
        self.id = session_id or str(uuid.uuid4())[:8]
        self.created = datetime.now().isoformat()
        self.messages: list[dict] = []
        self.file_history: dict[str, list[str]] = {}
        self.context_files: list[str] = []

    def add_message(self, role: str, content: str, **kwargs):
        msg = {"role": role, "content": content, "timestamp": datetime.now().isoformat()}
        msg.update(kwargs)
        self.messages.append(msg)

    def get_messages(self) -> list[dict]:
        return self.messages

    def track_file_write(self, path: str, old_content: Optional[str]):
        if path not in self.file_history:
            self.file_history[path] = []
        self.file_history[path].append(old_content)

    def undo_last_write(self, path: str) -> Optional[str]:
        if path in self.file_history and self.file_history[path]:
            old_content = self.file_history[path].pop()
            return old_content
        return None

    def save(self):
        save_session(self.id, {
            "id": self.id,
            "created": self.created,
            "messages": self.messages,
            "file_history": {k: [v for v in vals] for k, vals in self.file_history.items()},
            "context_files": self.context_files,
        })

    @classmethod
    def load(cls, session_id: str) -> Optional["SessionMemory"]:
        data = load_session(session_id)
        if not data:
            return None
        session = cls(session_id=data["id"])
        session.created = data.get("created", session.created)
        session.messages = data.get("messages", [])
        session.file_history = data.get("file_history", {})
        session.context_files = data.get("context_files", [])
        return session
