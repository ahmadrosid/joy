"""Exercise the real prompt loop without a physical terminal."""

import asyncio
import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch

from prompt_toolkit import PromptSession
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput
from prompt_toolkit.application import create_app_session

from joy.cli import main


class CliTest(unittest.TestCase):
    def test_prompt_and_exit(self):
        output = StringIO()
        original_prompt = PromptSession.prompt
        original_sleep = asyncio.sleep
        inputs = iter([
            "hello\x1b\rworld\r",
            "\x03",
            "[bold]literal[/bold]\r",
            "draft for later\r",
            "\x15/quit\r",
        ])
        defaults = []

        async def fast_sleep(seconds):
            await original_sleep(0.02)

        with create_pipe_input() as pipe:
            def prompt(session, *args, **kwargs):
                defaults.append(kwargs.get("default", ""))
                start = kwargs.get("pre_run")

                def feed():
                    if start:
                        start()
                    pipe.send_text(next(inputs))

                kwargs["pre_run"] = feed
                return original_prompt(session, *args, **kwargs)

            with create_app_session(input=pipe, output=DummyOutput()):
                with redirect_stdout(output), patch(
                    "joy.cli.asyncio.sleep", side_effect=fast_sleep
                ), patch.object(PromptSession, "prompt", prompt):
                    main()
        self.assertIn("Joy", output.getvalue())
        transcript = output.getvalue()
        self.assertRegex(transcript, r"› hello\s+world")
        self.assertIn("[bold]literal[/bold]", transcript)
        self.assertEqual(transcript.count("› "), 2)
        self.assertEqual(transcript.count("Joy\n"), 2)
        self.assertIn("Response cancelled.", transcript)
        self.assertEqual(transcript.count("Demo reply:"), 1)
        self.assertEqual(defaults[-1], "draft for later")
