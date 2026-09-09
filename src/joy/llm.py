"""OpenAI chat through aisuite, without blocking terminal input."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import suppress
from queue import Queue
from threading import Event, Thread

import aisuite

MODEL = "openai:gpt-5.6-luna"


async def stream_reply(messages: list[dict[str, str]]) -> AsyncIterator[str]:
    result: Queue[str | Exception | None] = Queue()
    cancelled = Event()

    def request() -> None:
        client = None
        try:
            client = aisuite.Client(provider_configs={
                "openai": {"timeout": 60.0, "max_retries": 0},
            })
            has_text = completed = False
            with client.chat.completions.create(
                model=MODEL, messages=messages, stream=True,
            ) as stream:
                for chunk in stream:
                    if cancelled.is_set():
                        return
                    if not chunk.choices:
                        continue
                    choice = chunk.choices[0]
                    text = choice.delta.content or getattr(choice.delta, "refusal", None)
                    if text:
                        has_text = has_text or bool(text.strip())
                        result.put(text)
                    if choice.finish_reason == "stop":
                        completed = True
            if not has_text or not completed:
                raise ValueError("Empty or incomplete response")
        except Exception:
            result.put(RuntimeError(
                "OpenAI could not return a reply. Check your API key, model access, "
                "quota, and connection, then try again."
            ))
        finally:
            provider = client.providers.get("openai") if client else None
            if provider is not None:
                with suppress(Exception):
                    provider.client.close()
            result.put(None)

    # ponytail: cancelling discards the result; the sync request ends at its timeout.
    # Use a cancellable async provider if server-request cancellation is needed.
    Thread(target=request, daemon=True).start()
    try:
        while True:
            while result.empty():
                await asyncio.sleep(0.05)
            chunk = result.get_nowait()
            if chunk is None:
                break
            if isinstance(chunk, Exception):
                raise chunk
            yield chunk
    finally:
        cancelled.set()
