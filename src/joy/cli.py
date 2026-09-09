"""Terminal interface for the initial scaffold."""

import os
import sys
import time
from contextlib import aclosing

from prompt_toolkit import PromptSession
from prompt_toolkit.filters import Always, Condition
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.key_binding.key_processor import KeyPressEvent
from prompt_toolkit.layout import ConditionalContainer, Dimension, HSplit, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.output import ColorDepth
from prompt_toolkit.styles import Style
from prompt_toolkit.widgets import Frame
from rich.console import Console
from rich.markdown import Markdown
from rich.padding import Padding
from rich.text import Text

from joy.llm import MODEL, stream_reply


def main() -> None:
    console = Console(
        color_system="truecolor" if sys.stdout.isatty() else None,
        no_color=False,
    )
    if not os.environ.get("OPENAI_API_KEY"):
        console.print("[red]Set OPENAI_API_KEY in your environment before running joy.[/red]")
        return
    history = [{
        "role": "system",
        "content": "You are Joy, a concise coding assistant. Help with code and explain clearly. "
        "You currently have no tools to read files, edit code, or run tests. "
        "Never claim to have performed those actions.",
    }]
    answer = ""
    bindings = KeyBindings()
    waiting = False
    draft = ""

    @bindings.add("enter")
    def submit(event: KeyPressEvent) -> None:
        if not waiting:
            event.current_buffer.validate_and_handle()

    @bindings.add("escape", "enter")
    def newline(event: KeyPressEvent) -> None:
        event.current_buffer.insert_text("\n")

    session: PromptSession[str] = PromptSession(
        erase_when_done=True,
        multiline=True,
        placeholder="Ask Joy to do something…",
        prompt_continuation="  ",
        key_bindings=bindings,
        color_depth=ColorDepth.TRUE_COLOR,
        style=Style.from_dict({
            "frame.border": "bg:#393939 #393939",
            "placeholder": "#808080",
        }),
    )
    session.layout.current_window.height = Dimension.exact(1)
    session.layout.current_window.style = "bg:#393939 #ffffff"
    session.layout.current_window.dont_extend_height = Always()
    session.layout.container = HSplit([
        ConditionalContainer(
            Window(FormattedTextControl(lambda: [
                ("fg:ansigreen", "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"[int(time.monotonic() * 10) % 10]),
                ("", " Thinking… · You can type; Enter sends after the reply"),
            ]), height=2),
            filter=Condition(lambda: waiting and not answer),
        ),
        ConditionalContainer(
            HSplit([
                Window(FormattedTextControl(
                    lambda: [("", answer), ("[SetCursorPosition]", "")],
                    show_cursor=False,
                ), wrap_lines=True, height=Dimension(max=12), dont_extend_height=True,
                    get_line_prefix=lambda line, wrap: " "),
                Window(height=1),
            ]),
            filter=Condition(lambda: waiting and bool(answer)),
        ),
        Frame(session.layout.container),
    ])

    async def finish_wait(messages: list[dict[str, str]]) -> None:
        nonlocal answer
        try:
            async with aclosing(stream_reply(messages)) as stream:
                async for chunk in stream:
                    answer += chunk
                    session.app.invalidate()
        except Exception as error:
            session.app.exit(exception=error)
            return
        session.app.exit(result=session.default_buffer.text)

    console.print(f"[bold cyan]Joy[/bold cyan] — {MODEL}\n")
    console.print("Type /quit to exit. Ctrl-C cancels input; Ctrl-D exits.\n")
    console.print("[dim]Enter sends · Alt+Enter adds a new line[/dim]")
    while True:
        try:
            message = session.prompt("› ", default=draft, refresh_interval=0).strip()
            draft = ""
        except KeyboardInterrupt:
            draft = ""
            continue
        except EOFError:
            break
        if message == "/quit":
            break
        if message:
            console.print()
            console.print(Padding(
                Text("› " + message.replace("\n", "\n  ")),
                (1, 1),
                style="#ffffff on #393939",
            ))
            console.print()
            waiting = True
            answer = ""
            messages = [*history, {"role": "user", "content": message}]
            try:
                draft = session.prompt(
                    "› ",
                    refresh_interval=0.1,
                    pre_run=lambda: session.app.create_background_task(finish_wait(messages)),
                )
            except KeyboardInterrupt:
                draft = session.default_buffer.text
                if answer:
                    console.print(Padding(Markdown(answer), (0, 0, 0, 1)))
                console.print("[dim]Response cancelled.[/dim]\n")
                continue
            except EOFError:
                if answer:
                    console.print(Padding(Markdown(answer), (0, 0, 0, 1)))
                break
            except Exception as error:
                draft = session.default_buffer.text
                if answer:
                    console.print(Padding(Markdown(answer), (0, 0, 0, 1)))
                console.print(Text(str(error), style="red"))
                continue
            finally:
                waiting = False
            history = [*messages, {"role": "assistant", "content": answer}]
            console.print(Padding(Markdown(answer), (0, 0, 0, 1)))
            console.print()
