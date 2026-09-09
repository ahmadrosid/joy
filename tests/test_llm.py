"""Exercise aisuite and OpenAI serialization without a network request."""

import asyncio
import json
import unittest
from threading import Event
from unittest.mock import patch

import aisuite
import httpx

from joy.llm import MODEL, stream_reply


async def collect_reply(messages):
    return "".join([chunk async for chunk in stream_reply(messages)])


class LlmTest(unittest.IsolatedAsyncioTestCase):
    async def test_provider_request_and_errors(self):
        client_class = aisuite.Client
        messages = [{"role": "user", "content": "Hello"}]
        payloads = []

        for status, content in [(200, "Hello back"), (401, "private-key"),
                                (200, None), (200, "truncated")]:
            with self.subTest(status=status, content=content):
                def respond(request):
                    payloads.append(json.loads(request.content))
                    self.assertEqual(request.url.path, "/v1/chat/completions")
                    if status != 200:
                        return httpx.Response(status, json={"error": {"message": content}})
                    events = []
                    for text, finish in [("Hello", None), (" back", None), (None, "stop")]:
                        events.append("data: " + json.dumps({
                            "id": "test", "object": "chat.completion.chunk", "created": 0,
                            "model": "gpt-5.6-luna",
                            "choices": [{"index": 0,
                                         "finish_reason": None if content == "truncated" else finish,
                                         "delta": {"content": text if content else None}}],
                        }) + "\n\n")
                    return httpx.Response(200, text="".join(events) + "data: [DONE]\n\n",
                                          headers={"content-type": "text/event-stream"})

                transport = httpx.Client(transport=httpx.MockTransport(respond))

                def client(provider_configs):
                    config = provider_configs["openai"]
                    self.assertEqual(config, {"timeout": 60.0, "max_retries": 0})
                    return client_class(provider_configs={"openai": {
                        **config, "api_key": "test-key",
                        "base_url": "https://api.openai.com/v1",
                        "http_client": transport,
                    }})

                with patch("joy.llm.aisuite.Client", side_effect=client):
                    if status == 200 and content == "Hello back":
                        self.assertEqual([part async for part in stream_reply(messages)],
                                         ["Hello", " back"])
                    else:
                        with self.assertRaisesRegex(RuntimeError, "OpenAI could not") as error:
                            await collect_reply(messages)
                        self.assertNotIn("private-key", str(error.exception))
                self.assertTrue(transport.is_closed)
                self.assertEqual(payloads[-1], {
                    "model": MODEL.split(":", 1)[1], "messages": messages, "stream": True,
                })

    async def test_cancel_does_not_wait_for_sync_request(self):
        started, release, finished = Event(), Event(), Event()

        def slow_client(**kwargs):
            started.set()
            try:
                release.wait(2)
                raise RuntimeError("late request failure")
            finally:
                finished.set()

        with patch("joy.llm.aisuite.Client", side_effect=slow_client):
            task = asyncio.create_task(collect_reply([{"role": "user", "content": "Hello"}]))
            try:
                for _ in range(100):
                    if started.is_set():
                        break
                    await asyncio.sleep(0.01)
                self.assertTrue(started.is_set())
                task.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await asyncio.wait_for(task, timeout=0.2)
                self.assertFalse(finished.is_set())
            finally:
                release.set()
                while not finished.is_set():
                    await asyncio.sleep(0.01)
