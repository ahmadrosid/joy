"""Terminal interface for the initial scaffold."""

import asyncio
import sys
import time

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


def main() -> None:
    console = Console(
        color_system="truecolor" if sys.stdout.isatty() else None,
        no_color=False,
    )
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
            filter=Condition(lambda: waiting),
        ),
        Frame(session.layout.container),
    ])

    async def finish_wait() -> None:
        await asyncio.sleep(1.5)
        session.app.exit(result=session.default_buffer.text)

    console.print("[bold cyan]Joy[/bold cyan] — coding agent scaffold\n")
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
            console.print("[bold green]Joy[/bold green]")
            waiting = True
            try:
                draft = session.prompt(
                    "› ",
                    refresh_interval=0.1,
                    pre_run=lambda: session.app.create_background_task(finish_wait()),
                )
            except KeyboardInterrupt:
                console.print("[dim]Response cancelled.[/dim]\n")
                continue
            except EOFError:
                break
            finally:
                waiting = False
            console.print(Markdown("**Demo reply:** AI is not connected yet. Your message appears above."))
            console.print()
