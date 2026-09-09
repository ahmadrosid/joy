"""Streaming OpenAI reasoning with aisuite tools, without blocking terminal input."""

import asyncio
import json
import re
from collections.abc import AsyncIterator
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from queue import Queue
from threading import Event, Thread

from openai import OpenAI, APIConnectionError, APIStatusError, APITimeoutError

from joy.tools import create_tools

MODEL = "openai:gpt-5.6-luna"


@dataclass(frozen=True)
class ToolEvent:
    name: str
    status: str


def _error_message(error: Exception) -> str:
    # Preserve useful diagnostics from wrapped errors without printing raw messages.
    seen = set()
    while id(error) not in seen:
        seen.add(id(error))
        cause = error.__cause__ or error.__context__
        if cause is None or isinstance(error, (APIStatusError, APIConnectionError)):
            break
        error = cause
    if isinstance(error, APIStatusError):
        hints = {
            400: "The API rejected the request parameters.",
            401: "The API rejected your API key.",
            403: "Your account lacks permission for this request.",
            404: f"Check access to {MODEL} and your API base URL.",
            429: "Rate limit or quota exceeded; check API usage and billing.",
        }
        details = []
        for key in ("code", "param"):
            value = getattr(error, key, None)
            # Show identifiers only; raw provider messages can contain credentials.
            if isinstance(value, str) and re.fullmatch(r"[a-zA-Z_][a-zA-Z_0-9.\[\]]{0,100}", value):
                details.append(f"{key}={value}")
        return f"HTTP {error.status_code}: {hints.get(error.status_code, 'API request failed.')} " + " ".join(details)
    if isinstance(error, APITimeoutError):
        return "The API request timed out. Try again."
    if isinstance(error, APIConnectionError):
        return "Could not connect to the API. Check your connection and API base URL."
    if isinstance(error, ValueError) and str(error) in {
        "Empty or incomplete response", "Incomplete tool call",
    }:
        return str(error) + "."
    return f"Local error: {type(error).__name__}. Check the installed dependencies and configuration."


async def stream_reply(messages: list[dict]) -> AsyncIterator[str | ToolEvent]:
    result: Queue[str | ToolEvent | Exception | None] = Queue()
    cancelled = Event()
    workspace = Path.cwd()

    def request() -> None:
        client = None
        try:
            client = OpenAI(timeout=60.0, max_retries=0)
            toolbox = create_tools(workspace, cancelled)
            conversation = list(messages)
            for _ in range(16):
                if cancelled.is_set():
                    return
                text = ""
                completed = None
                with client.responses.create(
                    model=MODEL.split(":", 1)[1], input=conversation, stream=True,
                    reasoning={"effort": "medium"}, store=False,
                    include=["reasoning.encrypted_content"],
                    tools=[{"type": "function", **tool["function"], "strict": False}
                           for tool in toolbox.tools()],
                    parallel_tool_calls=False,
                ) as stream:
                    for event in stream:
                        if cancelled.is_set():
                            return
                        if event.type in ("response.output_text.delta", "response.refusal.delta"):
                            text += event.delta
                            result.put(event.delta)
                        elif event.type == "response.completed":
                            completed = event.response
                        elif event.type in ("response.failed", "response.incomplete", "error"):
                            raise ValueError("Empty or incomplete response")
                if completed is None or completed.status != "completed":
                    raise ValueError("Empty or incomplete response")
                calls = [item for item in completed.output if item.type == "function_call"]
                if not calls:
                    if not text.strip():
                        raise ValueError("Empty or incomplete response")
                    return
                if len(calls) > 8 or any(not call.call_id for call in calls):
                    raise ValueError("Incomplete tool call")
                # Replay all output, including encrypted reasoning, before tool results.
                conversation.extend(item.model_dump(exclude_none=True) for item in completed.output)
                for call in calls:
                    if cancelled.is_set():
                        return
                    name = call.name
                    result.put(ToolEvent(name, "running"))
                    try:
                        output = toolbox.execute({"function": {
                            "name": name, "arguments": call.arguments,
                        }})[0]
                        status = "finished"
                    except Exception as error:
                        output = f"Tool error: {error}"
                        status = "failed"
                    result.put(ToolEvent(name, status))
                    conversation.append({"type": "function_call_output", "call_id": call.call_id,
                                         "output": json.dumps(output)})
                if text:
                    result.put("\n\n")
            result.put(RuntimeError("Reached the 16-step limit. Ask Joy to continue."))
        except Exception as error:
            result.put(RuntimeError(
                "OpenAI could not return a reply. " + _error_message(error)
            ))
        finally:
            if client is not None:
                with suppress(Exception):
                    client.close()
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
