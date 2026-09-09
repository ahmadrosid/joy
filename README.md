# Joy

A terminal coding assistant built with Python, aisuite, prompt_toolkit, and Rich.
Chat with GPT-5.6 Luna using streaming replies, Markdown, and conversation history.
Uses the Responses API with medium reasoning, preserving reasoning between tool calls.
The OpenAI SDK handles requests; aisuite defines and executes the four tools.

Includes four tools: **read** files, **write** files, **edit** text, and **bash**
to run commands and tests. Tool activity appears while replies stream.

## Run

Requires Python 3.10–3.13 and an OpenAI API key.

```sh
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
export OPENAI_API_KEY="your-api-key"
joy
```

Set the key in your shell; `.env` files are not loaded automatically.

## Usage

- **Enter** — send a message once the current reply finishes.
- **Alt+Enter** — insert a newline.
- **Ctrl+C** — cancel input or the pending reply.
- **Ctrl+D** on empty input or **/exit** — exit.

You can draft your next message while a reply streams. Conversation history lasts
until you exit. Cancelling stops further tool calls; completed file changes remain.
The API request may still finish in the background.

File tools operate inside the directory where you launch Joy. Bash runs with your
user permissions and a default 30-second timeout; it is not sandboxed.

Edit uses a unique text replacement with [Pi-style matching](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/src/core/tools/edit-diff.ts):
exact text first, then Unicode punctuation and trailing-whitespace normalization.
It preserves BOM/newline style, rejects ambiguous or unchanged replacements, and
returns a diff. Joy accepts one replacement per call; Pi also supports batches.

## Test

```sh
python -m unittest discover -s tests
```

Tests run without an API key or network access.
