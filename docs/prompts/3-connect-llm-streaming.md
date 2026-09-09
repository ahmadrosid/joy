Continue from the existing chat TUI. Replace demo replies with real, streaming OpenAI responses through aisuite. Preserve the input layout, user message styling, and keyboard controls from the previous prompts.

LLM connection:

- Install the OpenAI provider through `aisuite[openai]`.
- Use model `openai:gpt-5.6-luna` with `client.chat.completions.create(..., stream=True)`.
- Read `OPENAI_API_KEY` from the environment. Show a clear setup message if it is missing; never print or store the key.
- Keep successful user/assistant exchanges in memory and include them in subsequent requests.
- Use a concise coding-assistant system prompt. State that file reading, editing, and test execution are not available yet.
- Set a 60-second request timeout and disable automatic retries.

Streaming UX:

- Replace the simulated delay with the actual request.
- Show the existing Thinking animation until the first text arrives, retaining the blank line beneath it.
- Replace the animation with response text that grows as chunks arrive.
- Keep the input visible and editable throughout streaming. Preserve the next draft and allow Enter to submit only after the response finishes.
- Use prompt_toolkit to render the streaming preview and input together. Keep the latest response lines visible when the preview grows, without pushing the input off-screen.
- After completion, render the full response once as Rich Markdown in terminal scrollback. Avoid duplicate output.
- Remove the green “Joy” label from assistant messages, but keep the application header.
- Give assistant text one leading space on every rendered line, both during streaming and after completion. Keep its normal terminal background.

Cancellation and errors:

- Ctrl+C stops displaying the pending response immediately and preserves the draft. Keep any partial response visible with a cancellation message.
- API errors return to the input with a readable error message and preserve the draft and partial response.
- Do not add failed, cancelled, empty, or incomplete responses to conversation history.
- Ignore empty stream events and handle refusal text. Detect streams that end without successful completion.
- Close streams and clients when finished. Discard late results after cancellation so they cannot affect a later turn.
- aisuite's synchronous requests must not block the UI. Use a small standard-library worker and queue to deliver chunks to the async UI. Document that cancellation may leave an in-flight request running until the next chunk or timeout.

Keep the implementation minimal, with the LLM request code separate from the TUI. Do not add coding tools, persistent chat storage, or another provider.

Extend the tests to cover streamed chunks, conversation history, missing credentials, API errors, incomplete streams, cancellation, and draft preservation. Mock network responses so tests need no API key. Update the README with installation, key setup, and run instructions.
