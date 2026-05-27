import httpx
import asyncio
from typing import AsyncGenerator, Optional
from datetime import datetime


NIM_BASE_URL = "https://integrate.api.nvidia.com/v1"


class TokenTracker:
    def __init__(self):
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_tokens = 0
        self.request_count = 0
        self.session_start = datetime.now().isoformat()

    def update(self, usage: dict):
        self.total_prompt_tokens += usage.get("prompt_tokens", 0)
        self.total_completion_tokens += usage.get("completion_tokens", 0)
        self.total_tokens += usage.get("total_tokens", 0)
        self.request_count += 1

    @property
    def stats(self) -> dict:
        return {
            "prompt_tokens": self.total_prompt_tokens,
            "completion_tokens": self.total_completion_tokens,
            "total_tokens": self.total_tokens,
            "request_count": self.request_count,
            "session_start": self.session_start,
        }


tracker = TokenTracker()


class NIMProvider:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = httpx.AsyncClient(
            base_url=NIM_BASE_URL,
            timeout=120.0,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )

    async def close(self):
        await self.client.aclose()

    async def chat_completion(
        self,
        model: str,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        stream: bool = True,
    ) -> AsyncGenerator[str, None]:
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        async with self.client.stream("POST", "/chat/completions", json=payload) as resp:
            if resp.status_code != 200:
                error_body = await resp.aread()
                raise Exception(f"NIM API error {resp.status_code}: {error_body.decode()}")

            async for line in resp.aiter_lines():
                if not line or not line.startswith("data: "):
                    continue
                data = line[6:]
                if data == "[DONE]":
                    break
                try:
                    import orjson
                    chunk = orjson.loads(data)
                    choices = chunk.get("choices", [])
                    if choices:
                        delta = choices[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content

                        tool_calls = delta.get("tool_calls", None)
                        if tool_calls:
                            for tc in tool_calls:
                                yield f"__TOOL_CALL__:{orjson.dumps(tc).decode()}__"

                    usage = chunk.get("usage", None)
                    if usage:
                        tracker.update(usage)
                        yield f"__USAGE__:{orjson.dumps(usage).decode()}__"
                except Exception:
                    continue

    async def chat_completion_non_stream(
        self,
        model: str,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> dict:
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        for attempt in range(3):
            try:
                resp = await self.client.post("/chat/completions", json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("usage"):
                        tracker.update(data["usage"])
                    return data
                elif resp.status_code == 429:
                    await asyncio.sleep(2 ** attempt)
                else:
                    raise Exception(f"NIM API error {resp.status_code}: {resp.text}")
            except httpx.RequestError as e:
                if attempt == 2:
                    raise
                await asyncio.sleep(2 ** attempt)

        raise Exception("Max retries exceeded")

    async def list_models(self) -> list[str]:
        resp = await self.client.get("/models")
        if resp.status_code == 200:
            data = resp.json()
            return [m["id"] for m in data.get("data", [])]
        return []
