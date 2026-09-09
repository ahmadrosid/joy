Extend the existing terminal input into a chat experience. Preserve its current layout, colors, spacing, and keyboard controls.

Conversation:
- Render submitted user messages as static blocks matching the input’s appearance: #393939 background, #ffffff text, “› ” prefix, and matching padding.
- Display the complete user message literally, including multiline text.
- Show assistant replies under a green “Joy” label on the normal terminal background.
- Use Rich Markdown for assistant replies.
- Clear the submitted input to avoid duplicate messages, and retain the conversation in terminal scrollback.

Simulated replies:
- Wait 1.5 seconds before displaying a clearly labeled demo reply.
- Show an animated “Thinking…” indicator above the input, with one blank line below it.
- Keep the input visible and editable while waiting.
- Preserve the next draft; Enter submits only after the pending reply finishes.
- Ctrl+C cancels the pending reply and removes the loading indicator cleanly.

Use prompt_toolkit to render loading and input together, and Rich for static messages. Keep the implementation minimal; do not connect an AI model yet.

Extend the existing test to cover conversation rendering, cancellation, and draft preservation.