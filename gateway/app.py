import asyncio
import orjson
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from xyz import __version__
from .providers import NIMProvider, tracker
from .cache import response_cache

provider: Optional[NIMProvider] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global provider
    from xyz.config import get_api_key
    api_key = get_api_key()
    if not api_key:
        raise RuntimeError("No API key configured. Run 'xyz init' first.")
    provider = NIMProvider(api_key)
    yield
    if provider:
        await provider.close()


app = FastAPI(title="XYZ Gateway", version=__version__, lifespan=lifespan)


class ChatRequest(BaseModel):
    model: str
    messages: list[dict]
    tools: Optional[list[dict]] = None
    temperature: float = 0.1
    max_tokens: int = 4096
    stream: bool = True


@app.post("/v1/chat")
async def chat(req: ChatRequest):
    if not provider:
        raise HTTPException(500, "Provider not initialized")

    cache_key = response_cache._make_key(req.model, req.messages, temperature=req.temperature)
    if not req.stream:
        cached = response_cache.get(cache_key)
        if cached:
            return cached

    async def stream_response():
        full_content = ""
        tool_calls = []
        usage = None

        try:
            async for chunk in provider.chat_completion(
                model=req.model,
                messages=req.messages,
                tools=req.tools,
                temperature=req.temperature,
                max_tokens=req.max_tokens,
                stream=True,
            ):
                if chunk.startswith("__TOOL_CALL__:"):
                    tool_calls.append(chunk.replace("__TOOL_CALL__:", "").rstrip("__"))
                    yield f"data: {orjson.dumps({'type': 'tool_call', 'data': tool_calls[-1]}).decode()}\n\n"
                elif chunk.startswith("__USAGE__:"):
                    usage = orjson.loads(chunk.replace("__USAGE__:", "").rstrip("__"))
                    yield f"data: {orjson.dumps({'type': 'usage', 'data': usage}).decode()}\n\n"
                else:
                    full_content += chunk
                    yield f"data: {orjson.dumps({'type': 'token', 'data': chunk}).decode()}\n\n"
        except Exception as e:
            error_data = {"type": "error", "data": str(e)}
            yield f"data: {orjson.dumps(error_data).decode()}\n\n"

        final = {
            "type": "done",
            "content": full_content,
            "tool_calls": tool_calls,
            "usage": usage,
        }
        yield f"data: {orjson.dumps(final).decode()}\n\n"

    return StreamingResponse(stream_response(), media_type="text/event-stream")


@app.post("/v1/chat/non-stream")
async def chat_non_stream(req: ChatRequest):
    if not provider:
        raise HTTPException(500, "Provider not initialized")

    cache_key = response_cache._make_key(req.model, req.messages, temperature=req.temperature)
    cached = response_cache.get(cache_key)
    if cached:
        return cached

    result = await provider.chat_completion_non_stream(
        model=req.model,
        messages=req.messages,
        tools=req.tools,
        temperature=req.temperature,
        max_tokens=req.max_tokens,
    )

    response_cache.put(cache_key, result)
    return result


@app.get("/v1/models")
async def list_models():
    if not provider:
        raise HTTPException(500, "Provider not initialized")
    models = await provider.list_models()
    return {"models": models, "count": len(models)}


@app.get("/v1/stats")
async def get_stats():
    return {
        "tokens": tracker.stats,
        "cache": response_cache.stats,
    }


@app.post("/v1/cache/clear")
async def clear_cache():
    response_cache.clear()
    return {"status": "cleared"}


@app.get("/health")
async def health():
    return {"status": "ok", "provider": provider is not None}
