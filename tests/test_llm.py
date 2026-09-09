"""Exercise real OpenAI Responses serialization without network access."""

import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from threading import Event
from unittest.mock import patch

import httpx
from openai import OpenAI

from joy.llm import MODEL, ToolEvent, stream_reply


def sse(events):
    return httpx.Response(200, text=''.join(
        f'event: {event["type"]}\ndata: {json.dumps(event)}\n\n' for event in events
    ), headers={'content-type': 'text/event-stream'})


def completed(output=(), status='completed'):
    return {'type': 'response.' + status, 'response': {
        'id': 'resp_test', 'object': 'response', 'created_at': 0,
        'status': status, 'output': list(output),
    }}


async def collect_reply(messages):
    return ''.join([chunk async for chunk in stream_reply(messages) if isinstance(chunk, str)])


class LlmTest(unittest.IsolatedAsyncioTestCase):
    def client_patch(self, respond):
        transport = httpx.Client(transport=httpx.MockTransport(respond))
        self.addCleanup(transport.close)
        return patch('joy.llm.OpenAI', side_effect=lambda **config: OpenAI(
            **config, api_key='test-key', base_url='https://api.openai.com/v1',
            http_client=transport,
        ))

    async def test_reasoning_survives_tool_call_and_continuation(self):
        payloads = []
        reasoning = {'type': 'reasoning', 'id': 'rs_1', 'summary': [],
                     'encrypted_content': 'opaque-reasoning'}
        call = {'type': 'function_call', 'id': 'fc_1', 'call_id': 'call_1',
                'name': 'write', 'arguments': json.dumps({'path': 'hello.txt', 'content': 'hello'}),
                'status': 'completed'}

        def respond(request):
            self.assertEqual(request.url.path, '/v1/responses')
            payload = json.loads(request.content)
            payloads.append(payload)
            self.assertEqual(payload['reasoning'], {'effort': 'medium'})
            self.assertFalse(payload['store'])
            self.assertEqual(payload['include'], ['reasoning.encrypted_content'])
            self.assertNotIn('reasoning_effort', payload)
            self.assertEqual([tool['name'] for tool in payload['tools']], ['read', 'write', 'edit', 'bash'])
            self.assertTrue(all(tool['strict'] is False for tool in payload['tools']))
            if len(payloads) == 1:
                return sse([
                    {'type': 'response.function_call_arguments.delta', 'delta': '{"path":'},
                    {'type': 'response.function_call_arguments.delta', 'delta': '"hello.txt"}'},
                    completed([reasoning, call]),
                ])
            self.assertEqual(payload['input'][-3:-1], [reasoning, call])
            self.assertEqual(payload['input'][-1]['type'], 'function_call_output')
            self.assertEqual(payload['input'][-1]['call_id'], 'call_1')
            self.assertIn('Wrote hello.txt', payload['input'][-1]['output'])
            return sse([{'type': 'response.output_text.delta', 'delta': 'Created it.'}, completed()])

        with tempfile.TemporaryDirectory() as directory:
            with patch('joy.llm.Path.cwd', return_value=Path(directory)), self.client_patch(respond):
                chunks = [chunk async for chunk in stream_reply([{'role': 'user', 'content': 'Create it'}])]
            self.assertEqual(chunks, [ToolEvent('write', 'running'), ToolEvent('write', 'finished'), 'Created it.'])
            self.assertEqual((Path(directory) / 'hello.txt').read_text(), 'hello')
        self.assertEqual(len(payloads), 2)

    async def test_provider_request_and_errors(self):
        messages = [{'role': 'user', 'content': 'Hello'}]
        for status, mode in [(200, 'ok'), (401, 'error'), (400, 'error'), (404, 'error'),
                             (429, 'error'), (200, 'empty'), (200, 'truncated'),
                             (200, 'failed'), (200, 'incomplete')]:
            with self.subTest(status=status, mode=mode):
                def respond(request):
                    payload = json.loads(request.content)
                    self.assertEqual(payload['model'], MODEL.split(':', 1)[1])
                    self.assertEqual(payload['input'], messages)
                    self.assertTrue(payload['stream'])
                    if status != 200:
                        return httpx.Response(status, json={'error': {
                            'message': 'private-key', 'code': 'unsupported_parameter', 'param': 'tools',
                        }})
                    events = [] if mode == 'empty' else [
                        {'type': 'response.output_text.delta', 'delta': 'Hello'},
                        {'type': 'response.output_text.delta', 'delta': ' back'},
                    ]
                    if mode != 'truncated':
                        events.append(completed(status=mode if mode in ('failed', 'incomplete') else 'completed'))
                    return sse(events)

                with self.client_patch(respond):
                    if mode == 'ok':
                        self.assertEqual([part async for part in stream_reply(messages)], ['Hello', ' back'])
                    else:
                        with self.assertRaisesRegex(RuntimeError, 'OpenAI could not') as error:
                            await collect_reply(messages)
                        self.assertNotIn('private-key', str(error.exception))
                        if status != 200:
                            self.assertIn(f'HTTP {status}', str(error.exception))
                            self.assertIn('unsupported_parameter', str(error.exception))

    async def test_incomplete_stream_does_not_execute_tool(self):
        call = {'type': 'function_call', 'id': 'fc_1', 'call_id': 'call_1',
                'name': 'write', 'arguments': '{"path":"bad.txt","content":"bad"}'}
        with self.client_patch(lambda request: sse([
            {'type': 'response.output_item.done', 'output_index': 0, 'item': call},
        ])), patch('joy.llm.create_tools') as tools:
            tools.return_value.tools.return_value = []
            with self.assertRaises(RuntimeError):
                await collect_reply([{'role': 'user', 'content': 'write'}])
            tools.return_value.execute.assert_not_called()

    async def test_cancel_does_not_wait_for_sync_request(self):
        started, release, finished = Event(), Event(), Event()

        def slow_client(**kwargs):
            started.set()
            try:
                release.wait(2)
                raise RuntimeError('late request failure')
            finally:
                finished.set()

        with patch('joy.llm.OpenAI', side_effect=slow_client):
            task = asyncio.create_task(collect_reply([{'role': 'user', 'content': 'Hello'}]))
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
