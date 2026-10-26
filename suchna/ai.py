"""The only door to the model: a local Ollama server running Gemma."""

import time
from dataclasses import dataclass

from ollama import AsyncClient

from suchna.config import get_settings


class AiUnavailable(Exception):
    pass


@dataclass
class Reply:
    content: str
    latency_ms: int


async def chat(messages: list[dict], *, schema: dict | None = None, temperature: float = 0.0,
               num_predict: int = 1200, num_ctx: int = 8192) -> Reply:
    s = get_settings()
    if not s.ai_enabled:
        raise AiUnavailable("AI is turned off")
    started = time.perf_counter()
    try:
        resp = await AsyncClient(host=s.ollama_host, timeout=s.ollama_timeout_seconds).chat(
            model=s.ollama_model, messages=messages, format=schema, think=False, keep_alive=s.ollama_keep_alive,
            options={"temperature": temperature, "num_ctx": num_ctx, "num_predict": num_predict},
        )
    except Exception as e:
        raise AiUnavailable(f"{type(e).__name__}: {e}") from e
    return Reply(resp.message.content or "", int((time.perf_counter() - started) * 1000))


async def health() -> dict:
    s = get_settings()
    base = {"model": s.ollama_model, "local": s.ai_is_local, "enabled": s.ai_enabled}
    if not s.ai_enabled:
        return base | {"available": False, "message": "AI is off. Run Suchna locally with Ollama to read notices."}
    try:
        models = [m.model for m in (await AsyncClient(host=s.ollama_host, timeout=3).list()).models]
    except Exception:
        return base | {"available": False, "message": "Ollama isn't running. Notices will wait in the queue."}
    ok = s.ollama_model in models
    return base | {"available": ok, "message": "Gemma reads your notices, on this computer." if ok
                   else f"Run: ollama pull {s.ollama_model}"}
