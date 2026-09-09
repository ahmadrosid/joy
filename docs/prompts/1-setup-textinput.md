Build a terminal text input for a Python coding agent using prompt_toolkit and Rich.

Design:
- A full-width gray input area with background #393939.
- Exactly three rows: one blank row above, one editable row, and one blank row below.
- White input text with a “› ” prefix.
- Placeholder: “Ask Joy to do something…”
- No visible border.

Implementation:
- Use PromptSession with true-color rendering.
- Set the input window height to Dimension.exact(1) and dont_extend_height to Always().
- Wrap the existing session layout container in a Frame.
- Set both the Frame border foreground and background to #393939. Its hidden borders provide the blank rows above and below.
- Do not add extra padding or a Box wrapper.

Behavior:
- Enter submits.
- Alt+Enter inserts a newline, but the visible editable area stays one row tall.
- Ctrl+C cancels input.
- Ctrl+D on empty input or /exit exits.
- Use Rich for output outside the input area.

Keep it minimal. For now, respond to submitted text with “Agent functionality is not connected yet.” Do not implement AI calls or coding tools.