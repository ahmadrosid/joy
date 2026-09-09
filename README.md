# Joy

A Python coding agent scaffold using aisuite, prompt_toolkit, and Rich.

## Run

```sh
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
joy
```

You can also launch with `python -m joy`. Type `/quit` or press Ctrl-D to exit.
Ctrl-C cancels the current input.
The gray input has one editable row and one blank row above and below.
Enter sends; Alt+Enter inserts a newline. Submitted messages appear in the
conversation above the input. User messages match the gray input styling;
assistant replies have a Joy label on the normal terminal background.
User text is displayed literally; assistant replies support Markdown and code blocks.

Use Python 3.10–3.13; aisuite's current docstring-parser dependency fails on 3.14.

## Test

```sh
python -m unittest discover -s tests
```

## Scope

The scaffold includes packaging, a terminal chat interface, and a smoke test.
Replies are clearly labeled demos; no model is connected yet.
A Thinking spinner simulates a 1.5-second wait before each reply. Ctrl-C cancels
the pending reply. The input stays visible and editable during the wait;
draft text is preserved, and Enter can send it once the reply finishes.
Model calls, code reading, code editing, and test-running tools are not implemented yet.
No API key is needed to run the scaffold. When connecting a model, install the
chosen provider's [aisuite extra](https://github.com/andrewyng/aisuite) and configure its API key.
