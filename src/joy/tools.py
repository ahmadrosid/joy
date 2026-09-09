"""Local coding tools. Bash runs with the current user's permissions."""

import os
import signal
import subprocess
import tempfile
import time
import unicodedata
from contextlib import suppress
from difflib import unified_diff
from pathlib import Path
from threading import Event, Lock

from aisuite.utils.tools import Tools

OUTPUT_LIMIT = 20_000
FILE_LIMIT = 2_000_000
# ponytail: serialize file mutations globally; use per-file locks if concurrency grows.
MUTATION_LOCK = Lock()


def _lf(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _fuzzy(text: str) -> str:
    # Matching rules adapted from Pi's coding-agent/src/core/tools/edit-diff.ts.
    text = "\n".join(line.rstrip() for line in unicodedata.normalize("NFKC", text).split("\n"))
    substitutions = {char: replacement for chars, replacement in (
        ("‘’‚‛", "'"), ("“”„‟", '"'), ("‐‑‒–—―−", "-"),
        ("\u00a0\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u202f\u205f\u3000", " "),
    ) for char in chars}
    return text.translate(str.maketrans(substitutions))


def _replace(original: str, old_text: str, new_text: str) -> str:
    bom = "\ufeff" if original.startswith("\ufeff") else ""
    body = original[len(bom):]
    first_lf = body.find("\n")
    ending = "\r\n" if first_lf > 0 and body[first_lf - 1] == "\r" else "\n"
    body, old_text, new_text = map(_lf, (body, old_text, new_text))
    fuzzy_body, fuzzy_old = _fuzzy(body), _fuzzy(old_text)
    if not old_text or not fuzzy_old:
        raise ValueError("old_text must contain non-whitespace text.")
    if fuzzy_body.count(fuzzy_old) > 1:
        raise ValueError("old_text matches multiple places. Include more surrounding context.")
    if old_text in body:
        updated = body.replace(old_text, new_text, 1)
    else:
        start = fuzzy_body.find(fuzzy_old)
        if start < 0:
            raise ValueError("old_text was not found. Read the file and retry.")
        end = start + len(fuzzy_old)
        # Rebuild only touched lines so normalization cannot alter unrelated code.
        first = fuzzy_body.count("\n", 0, start)
        last = fuzzy_body.count("\n", 0, end - 1)
        line_start = fuzzy_body.rfind("\n", 0, start) + 1
        line_end = fuzzy_body.find("\n", end - 1)
        line_end = len(fuzzy_body) if line_end < 0 else line_end + 1
        lines = body.split("\n")
        prefix = "\n".join(lines[:first]) + ("\n" if first else "")
        suffix = "\n".join(lines[last + 1:])
        updated = prefix + fuzzy_body[line_start:start] + new_text + fuzzy_body[end:line_end] + suffix
    if updated == body:
        raise ValueError("No changes: the replacement is identical to the original.")
    return bom + updated.replace("\n", ending)


def _clip(text: str) -> str:
    return text if len(text) <= OUTPUT_LIMIT else text[:OUTPUT_LIMIT] + "\n[output truncated]"


def _save(path: Path, content: str) -> None:
    data = content.encode("utf-8")
    if len(data) > FILE_LIMIT:
        raise ValueError("File content exceeds the 2 MB limit.")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as file:
            temporary = Path(file.name)
            file.write(data)
        if path.exists():
            temporary.chmod(path.stat().st_mode & 0o777)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def create_tools(workspace: Path, cancelled: Event) -> Tools:
    root = workspace.resolve()

    def resolve(path: str) -> Path:
        target = (root / path).resolve()
        if not target.is_relative_to(root):
            raise ValueError("Path must stay inside the workspace.")
        if cancelled.is_set():
            raise InterruptedError("Cancelled.")
        return target

    def read(path: str, offset: int = 1, limit: int = 200) -> str:
        """Read a UTF-8 file with line numbers; offset is 1-based, limit is at most 2000."""
        if offset < 1 or not 1 <= limit <= 2000:
            raise ValueError("offset must be positive; limit must be between 1 and 2000.")
        target = resolve(path)
        if target.stat().st_size > FILE_LIMIT:
            raise ValueError("File exceeds the 2 MB limit. Use bash to inspect a section.")
        lines = target.read_text(encoding="utf-8").splitlines()
        return _clip("\n".join(
            f"{index}: {line}" for index, line in
            enumerate(lines[offset - 1:offset - 1 + limit], start=offset)
        ))

    def write(path: str, content: str) -> str:
        """Create or overwrite a UTF-8 file, creating parent directories if needed."""
        with MUTATION_LOCK:
            _save(resolve(path), content)
        return f"Wrote {path}."

    def edit(path: str, old_text: str, new_text: str) -> str:
        """Replace unique old_text with new_text. Exact match first, then tolerate trailing
        whitespace and Unicode quote/dash/space differences. Include context for uniqueness.
        Preserves BOM and newline style; returns a unified diff. Read the file first.
        """
        with MUTATION_LOCK:
            target = resolve(path)
            if target.stat().st_size > FILE_LIMIT:
                raise ValueError("File exceeds the 2 MB limit.")
            original = target.read_bytes().decode("utf-8")
            updated = _replace(original, old_text, new_text)
            if cancelled.is_set():
                raise InterruptedError("Cancelled.")
            if target.read_bytes().decode("utf-8") != original:
                raise ValueError("File changed during editing. Read it and retry.")
            _save(target, updated)
        diff = "".join(unified_diff(original.splitlines(keepends=True),
                                    updated.splitlines(keepends=True),
                                    fromfile=path, tofile=path))
        return _clip(f"Edited {path}.\n{diff}")

    def bash(command: str, timeout: int = 30) -> str:
        """Run a noninteractive Bash command in the workspace; timeout is 1–300 seconds."""
        if not command.strip() or not 1 <= timeout <= 300:
            raise ValueError("Provide a command and a timeout between 1 and 300 seconds.")
        if cancelled.is_set():
            raise InterruptedError("Cancelled.")
        with tempfile.TemporaryFile() as output:
            process = subprocess.Popen(
                ["bash", "-c", command], cwd=root, stdin=subprocess.DEVNULL,
                stdout=output, stderr=subprocess.STDOUT, start_new_session=True,
            )
            deadline = time.monotonic() + timeout
            reason = ""
            try:
                while process.poll() is None:
                    if cancelled.wait(0.05):
                        reason = "Cancelled"
                        break
                    if time.monotonic() >= deadline:
                        reason = "Timed out"
                        break
            finally:
                # Kill the process group, including children holding the output file open.
                with suppress(ProcessLookupError):
                    os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            output.seek(0)
            text = output.read(OUTPUT_LIMIT + 1).decode("utf-8", errors="replace")
            return f"{reason or 'Finished'}; exit code {process.returncode}\n{_clip(text)}"

    return Tools([read, write, edit, bash])
