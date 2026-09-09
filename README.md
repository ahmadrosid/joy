# Joy

A Python coding assistant using aisuite, prompt_toolkit, and Rich.

## Run

```sh
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
export OPENAI_API_KEY="your-api-key"
joy
```

You can also launch with `python -m joy`. Type `/quit` or press Ctrl-D to exit.
Ctrl-C cancels the current input.
The gray input has one editable row and one blank row above and below.
Enter sends; Alt+Enter inserts a newline. Submitted messages appear in the
conversation above the input. User messages match the gray input styling;
assistant replies appear on the normal terminal background without a name label.
User text is displayed literally; assistant replies support Markdown and code blocks.

Use Python 3.10–3.13; aisuite's current docstring-parser dependency fails on 3.14.

## Test

```sh
python -m unittest discover -s tests
```

## Chat

Joy uses [GPT-5.6 Luna](https://developers.openai.com/api/docs/models/gpt-5.6-luna)
through aisuite with model ID `openai:gpt-5.6-luna`.
The OpenAI provider is included when installing the project. Set `OPENAI_API_KEY`
in your shell; `.env` files are not loaded automatically.

Successful exchanges are kept in memory for follow-up questions until you exit.
The Thinking spinner runs until the first response text arrives. Text then streams
above the input, with the latest lines visible for long replies. The completed
reply is rendered as Markdown in the conversation. Input stays visible and
editable; your next draft is preserved until the response finishes.
Ctrl-C discards the pending reply immediately. The underlying synchronous API
request may continue until completion or its 60-second timeout; it cannot update
the conversation after cancellation. Partial text remains visible if streaming
fails or is cancelled, but failed and cancelled exchanges are excluded
from model history. API errors return you to the input without losing your draft.

Code reading, editing, and test-running tools are not implemented yet.
Tests use mocked replies and HTTP transport; they do not require an API key or
make network calls.
