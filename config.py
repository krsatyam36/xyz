import os
import json
import keyring
import shutil
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field

XYZ_DIR = Path.home() / ".xyz"
CONFIG_FILE = XYZ_DIR / "config.json"
SESSIONS_DIR = XYZ_DIR / "sessions"
CACHE_DIR = XYZ_DIR / "cache"
LOGS_DIR = XYZ_DIR / "logs"
PROVIDERS_DIR = XYZ_DIR / "providers"
COMMANDS_DIR = XYZ_DIR / "commands"
AGENTS_DIR = XYZ_DIR / "agents"
THEMES_DIR = XYZ_DIR / "themes"
PLUGINS_DIR = XYZ_DIR / "plugins"

SERVICE_NAME = "xyz-cli"
KEYRING_KEY = "nim_api_key"

DEFAULT_MODELS = [
    "meta/llama-3.3-70b-instruct",
    "meta/llama-3.1-405b-instruct",
    "meta/llama-3.1-70b-instruct",
    "meta/llama-3.1-8b-instruct",
    "nvidia/llama-3.1-nemotron-70b-instruct",
    "qwen/qwen-2.5-coder-32b-instruct",
    "qwen/qwen-2.5-72b-instruct",
    "microsoft/phi-4",
    "google/gemma-2-27b-it",
    "mistralai/mistral-large-2-instruct",
    "deepseek-ai/deepseek-r1",
]

VISION_MODELS = [
    "meta/llama-3.2-90b-vision-instruct",
    "meta/llama-3.2-11b-vision-instruct",
    "neva-22b",
]


class XYZConfig(BaseModel):
    api_key_set: bool = False
    default_model: str = "meta/llama-3.3-70b-instruct"
    vision_model: str = "meta/llama-3.2-90b-vision-instruct"
    gateway_port: int = 0
    trust_mode: bool = False
    theme: str = "claude"
    discovered_models: list[str] = Field(default_factory=list)
    last_model_fetch: Optional[str] = None
    effor_level: str = "auto"
    fast_mode: bool = False
    compact_auto: bool = True
    share_enabled: str = "manual"
    autoupdate: bool = True


def ensure_dirs():
    XYZ_DIR.mkdir(exist_ok=True)
    SESSIONS_DIR.mkdir(exist_ok=True)
    CACHE_DIR.mkdir(exist_ok=True)
    LOGS_DIR.mkdir(exist_ok=True)
    PROVIDERS_DIR.mkdir(exist_ok=True)
    COMMANDS_DIR.mkdir(exist_ok=True)
    AGENTS_DIR.mkdir(exist_ok=True)
    THEMES_DIR.mkdir(exist_ok=True)
    PLUGINS_DIR.mkdir(exist_ok=True)


def load_config() -> XYZConfig:
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text())
            return XYZConfig(**data)
        except Exception:
            return XYZConfig()
    return XYZConfig()


def save_config(config: XYZConfig):
    CONFIG_FILE.write_text(config.model_dump_json(indent=2))


def get_api_key() -> Optional[str]:
    api_key_from_env = os.environ.get("XYZ_API_KEY")
    if api_key_from_env:
        return api_key_from_env
    try:
        return keyring.get_password(SERVICE_NAME, KEYRING_KEY)
    except Exception:
        return None


def set_api_key(key: str):
    keyring.set_password(SERVICE_NAME, KEYRING_KEY, key)
    config = load_config()
    config.api_key_set = True
    save_config(config)


def validate_api_key(key: str) -> bool:
    import httpx
    try:
        resp = httpx.get(
            "https://integrate.api.nvidia.com/v1/models",
            headers={"Authorization": f"Bearer {key}"},
            timeout=10.0
        )
        return resp.status_code == 200
    except Exception:
        return False


def discover_models(api_key: str) -> list[str]:
    import httpx
    try:
        resp = httpx.get(
            "https://integrate.api.nvidia.com/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=15.0
        )
        if resp.status_code == 200:
            data = resp.json()
            models = [m["id"] for m in data.get("data", [])]
            config = load_config()
            config.discovered_models = models
            from datetime import datetime
            config.last_model_fetch = datetime.now().isoformat()
            save_config(config)
            return models
    except Exception:
        pass
    return DEFAULT_MODELS.copy()


def get_session_file(session_id: str) -> Path:
    return SESSIONS_DIR / f"{session_id}.json"


def save_session(session_id: str, data: dict):
    get_session_file(session_id).write_text(json.dumps(data, indent=2))


def load_session(session_id: str) -> Optional[dict]:
    path = get_session_file(session_id)
    if path.exists():
        return json.loads(path.read_text())
    return None


def list_sessions() -> list[dict]:
    sessions = []
    for f in SESSIONS_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text())
            sessions.append({
                "id": f.stem,
                "created": data.get("created", ""),
                "messages": len(data.get("messages", [])),
            })
        except Exception:
            continue
    return sorted(sessions, key=lambda x: x["created"], reverse=True)


def delete_session(session_id: str) -> bool:
    path = get_session_file(session_id)
    if path.exists():
        path.unlink()
        return True
    return False


def get_config_paths() -> dict:
    return {
        "config": str(CONFIG_FILE),
        "sessions": str(SESSIONS_DIR),
        "cache": str(CACHE_DIR),
        "logs": str(LOGS_DIR),
        "providers": str(PROVIDERS_DIR),
        "commands": str(COMMANDS_DIR),
        "agents": str(AGENTS_DIR),
    }


def export_session(session_id: str) -> Optional[str]:
    data = load_session(session_id)
    if not data:
        return None
    lines = [f"# XYZ Session: {session_id}", f"# Created: {data.get('created', '')}", ""]
    for msg in data.get("messages", []):
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        lines.append(f"### {role.upper()}")
        lines.append("")
        lines.append(content)
        lines.append("")
    return "\n".join(lines)


def init_project_agents():
    agents_md = Path.cwd() / "AGENTS.md"
    if not agents_md.exists():
        content = f"""# XYZ Project Context

## Project
{Path.cwd().name}

## Tech Stack
- Python 3.10+
- NVIDIA NIM API for AI inference

## Conventions
- Follow existing code patterns
- Use type hints in Python
- Keep functions focused and well-named
- Write tests for new functionality

## Running
```bash
pip install -e ".[dev]"
pytest tests/
```
"""
        agents_md.write_text(content)
        return True
    return False
