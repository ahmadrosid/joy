# Joy's coding tools

Joy gives the model four tools: `read`, `write`, `edit`, and `bash`. The model
chooses a tool and supplies its arguments. aisuite validates those arguments and
executes the Python function. Joy sends the result—or an error—back to the model
so it can decide what to do next.

The workspace is the directory where you launch Joy. File tools stay inside that
directory; Bash runs with your user permissions and is not sandboxed.

## Read

Read lets Joy inspect a file before explaining or changing it.

```python
read(path="src/joy/cli.py", offset=10, limit=20)
```

| Argument | Required | Default | Purpose |
| --- | --- | --- | --- |
| `path` | Yes | — | File to read |
| `offset` | No | `1` | First line to return, counting from 1 |
| `limit` | No | `200` | Maximum number of lines to return |

The logic:

1. Require a positive offset and a limit between 1 and 2,000.
2. Resolve the path against the workspace. Reject paths or symlinks escaping it.
3. Check cancellation and reject files larger than 2 MB.
4. Read the file as UTF-8 and split it into lines.
5. Select the requested lines and add line numbers. The example returns lines 10–29.
6. Truncate output beyond 20,000 characters, adding an output-truncated marker.

Example result:

```text
10: def main():
11:     print("Hello")
```

`read(path="README.md")` reads up to the first 200 lines. An offset beyond the end
returns empty text. Missing files and invalid inputs become tool errors.

The implementation reads the whole file into memory before selecting lines. The
2 MB limit keeps that manageable.

## Write

Write creates a file or completely replaces an existing file's contents.

```python
write(path="src/hello.py", content='print("Hello")\n')
```

Both `path` and `content` are required.

The logic:

1. Resolve the path, enforce workspace boundaries, and check cancellation.
2. Encode the content as UTF-8 and reject content larger than 2 MB.
3. Create missing parent directories.
4. Write the content to a temporary file in the destination directory.
5. Preserve the target's existing permission bits, if it exists.
6. Atomically replace the target and clean up the temporary file.
7. Return confirmation, such as `Wrote src/hello.py.`

Atomic replacement prevents readers from seeing a partially written target file.
Writes and edits share a lock so Joy serializes its file mutations. Completed
writes are not undone by cancellation.

Use `write` for new files or complete rewrites. Use `edit` to change a specific section.

## Edit

Edit replaces one unique section of an existing file.

```python
edit(
    path="src/hello.py",
    old_text='print("Hello")',
    new_text='print("Hi")',
)
```

All three arguments are required. Setting `new_text=""` deletes the matched section.

The logic:

1. Enforce workspace boundaries, check cancellation, and reject files larger than 2 MB.
2. Read the file and remember its UTF-8 BOM and LF/CRLF newline style.
3. Normalize line endings for matching. Try an exact `old_text` match first.
4. If exact matching fails, try Pi-style matching: normalize Unicode with NFKC,
   strip trailing whitespace per line, and normalize Unicode quotes, dashes,
   and special spaces. Preserve leading indentation.
5. Reject empty or whitespace-only search text, missing matches, and ambiguous
   matches—including Unicode-equivalent duplicates. Include surrounding lines
   in `old_text` when more context is needed.
6. Replace the occurrence. During fuzzy matching, normalize only touched lines;
   preserve unrelated lines. Restore the BOM and newline style.
7. Reject unchanged results, check cancellation again, and verify the file still
   matches what was read before saving.
8. Save using the same atomic replacement as `write`, then return a unified diff.

Example result:

```diff
-print("Hello")
+print("Hi")
```

Joy should read the file before editing so it knows the current text. The shared
mutation lock serializes Joy's writes and edits; it does not lock out external editors.

Matching is adapted from [Pi's edit implementation](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/src/core/tools/edit-diff.ts).
Joy accepts one replacement per call; Pi also supports batches.

## Bash

Bash runs shell commands, including tests and Git commands.

```python
bash(command="python -m unittest discover -s tests", timeout=30)
```

`command` is required. `timeout` is optional and defaults to 30 seconds.

The logic:

1. Reject empty commands or timeouts outside 1–300 seconds.
2. Check cancellation before starting.
3. Run `bash -c` in the workspace, with standard input disabled. Commands that
   need interactive input will not work.
4. Capture stdout and stderr together in a temporary file.
5. Monitor the process for completion, timeout, or cancellation. Terminate the
   process group on timeout or cancellation, and clean up remaining child
   processes when the command finishes.
6. Return the completion reason, exit code, and captured output. Read at most
   20,001 output bytes and clip returned text to 20,000 characters with a marker.

Example result:

```text
Finished; exit code 0
Ran 9 tests
OK
```

A nonzero exit code is returned to the model so it can inspect the failure.
Timeout or cancellation stops execution but does not undo changes already made.

Bash is not restricted by the file tools' workspace checks. It can access or modify
anything your user permissions allow. Output limits cap what Joy returns, not how
much the command can write to its temporary output file before it stops. Process-group
cleanup uses POSIX APIs, so this implementation targets macOS and Linux.
