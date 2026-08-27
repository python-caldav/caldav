#!/usr/bin/env python3
"""Claude Code `UserPromptSubmit` hook: record one prompt in `.prompts/`.

`prepare-ai-repository` installs a copy of this script into a repository as
`.claude/hooks/record-prompt.py` and points `.claude/settings.json` at it.
Edit the original bundled with ai-prompt-auto-commit, not the installed copy:
the copy is overwritten on every run of `prepare-ai-repository`.

The hook payload arrives as JSON on stdin and the prompt is written to

    <repo root>/.prompts/<timestamp>_<model>.txt

Two things this script is careful about:

* Only genuine user-authored turns are recorded.  Claude Code also submits
  machine-injected turns through this hook — task notifications, peer
  messages, auto-continuation, scheduled wakeups — and those are not prompts.
* The model name is read out of the session transcript.  There is no model in
  the hook payload, and guessing produces an attribution record that quietly
  lies; `unknown` is written instead when it cannot be established.

Nothing is ever written to stdout: for `UserPromptSubmit`, stdout is injected
into the conversation as additional context.  Failures are reported on stderr
and the hook still exits 0, because a recording hook must not block a prompt.

Depends on the standard library only, so that a repository using
ai-prompt-auto-commit needs nothing beyond the Python it already requires.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

HOOK_VERSION = "0.0.9"  # replaced with the package version at install time

PROMPTS_DIRECTORY = ".prompts"
FILE_EXTENSION = ".txt"
UNKNOWN_MODEL = "unknown"

# A model name goes into a filename, where `_` separates it from the timestamp
# and `/` would be a directory.  Gateway and proxy setups report ids such as
# "anthropic/claude-opus-5", so anything outside this set is folded to `-`.
UNSAFE_IN_FILENAME = re.compile(r"[^A-Za-z0-9.@+-]+")

# `source` names who authored the turn.  `user` is the interactive composer and
# `sdk` the non-interactive entrypoint (`-p` / Agent SDK); both are the human.
# Everything else — `system` (task notifications, peer/channel messages,
# auto-continuation), `loop_wakeup`, `schedule_wakeup`, `poll_event` — is
# machine-injected.  The field is documented as possibly absent while it rolls
# out, so a payload without it falls through to the prefix check below.
HUMAN_SOURCES = frozenset({"user", "sdk"})

# Machine-injected turns are wrapped in one of these tags.  Belt and braces for
# payloads that carry no `source`.
SYNTHETIC_PREFIXES = (
    "<task-notification>",
    "<bash-input>",
    "<bash-stdout>",
    "<bash-stderr>",
    "<local-command-caveat>",
    "<system-reminder>",
)

# Transcripts grow without bound, and this runs on every prompt, so only the
# tail is read; a full scan is the fallback when the tail holds no answer.
TAIL_BYTES = 1 << 20


def _model_of(line: str) -> str:
    """Return the model of a transcript line, or "" if it names none."""
    try:
        entry = json.loads(line)
    except ValueError:
        return ""
    if not isinstance(entry, dict) or entry.get("type") != "assistant":
        return ""
    if entry.get("isSidechain"):
        return ""  # a subagent's model, not the one answering this prompt
    message = entry.get("message")
    model = message.get("model", "") if isinstance(message, dict) else ""
    if not isinstance(model, str) or model.startswith("<"):
        return ""  # placeholders such as "<synthetic>"
    return model


def _last_model(lines: list[str]) -> str:
    for line in reversed(lines):
        model = _model_of(line)
        if model:
            return model
    return ""


def _tail_lines(path: Path) -> list[str]:
    with path.open("rb") as fh:
        if path.stat().st_size > TAIL_BYTES:
            fh.seek(-TAIL_BYTES, 2)
            fh.readline()  # discard the partial line the seek landed in
        return fh.read().decode("utf-8", "replace").splitlines()


def model_from_transcript(transcript_path: str) -> str:
    """Return the model of the most recent main-agent turn in the transcript.

    Falls back to `unknown`, which is what the first prompt of a session gets:
    no assistant has spoken yet.
    """
    if not transcript_path:
        return UNKNOWN_MODEL
    path = Path(transcript_path)
    if not path.is_file():
        return UNKNOWN_MODEL
    try:
        model = _last_model(_tail_lines(path))
        if not model and path.stat().st_size > TAIL_BYTES:
            model = _last_model(path.read_text(encoding="utf-8", errors="replace").splitlines())
    except OSError:
        return UNKNOWN_MODEL  # an unreadable transcript costs the name, not the prompt
    return _safe_model(model) if model else UNKNOWN_MODEL


def _safe_model(model: str) -> str:
    # Leading dots too: a model name must not become a hidden file or "..".
    return UNSAFE_IN_FILENAME.sub("-", model).strip("-.") or UNKNOWN_MODEL


def should_record(payload: dict) -> bool:
    """True when the payload carries a prompt the human actually wrote."""
    source = payload.get("source")
    if source is not None and source not in HUMAN_SOURCES:
        return False
    prompt = payload.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        return False
    return not prompt.lstrip().startswith(SYNTHETIC_PREFIXES)


def repo_root(cwd: str) -> Path | None:
    """The git root containing *cwd*, or *cwd* itself outside a repository.

    None when the payload names a directory that does not exist: guessing
    somewhere else to write would file the prompt under an unrelated project.
    """
    fallback = Path(cwd) if cwd else Path.cwd()
    if not fallback.is_dir():
        return None
    try:
        toplevel = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=fallback,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return fallback
    return Path(toplevel) if toplevel else fallback


def _write_new(prompts_dir: Path, timestamp: str, model: str, text: str) -> Path:
    """Write to `<timestamp>_<model>.txt`, sequence-numbered if that is taken.

    Creating the file exclusively is what makes the sequence safe: two sessions
    recording into the same repository in the same second would otherwise both
    see a free name and one would overwrite the other.
    """
    for seq in range(1000):
        suffix = "" if seq == 0 else f"-{seq:03d}"
        dest = prompts_dir / f"{timestamp}{suffix}_{model}{FILE_EXTENSION}"
        try:
            fd = os.open(dest, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        except FileExistsError:
            continue
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        return dest
    raise OSError(f"no free prompt filename for {timestamp} in {prompts_dir}")


def record(payload: dict) -> Path | None:
    """Write the prompt to `.prompts/`; return the file, or None if skipped."""
    if not should_record(payload):
        return None
    root = repo_root(payload.get("cwd", ""))
    if root is None:
        return None
    prompts_dir = root / PROMPTS_DIRECTORY
    prompts_dir.mkdir(parents=True, exist_ok=True)
    model = model_from_transcript(payload.get("transcript_path", ""))
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    return _write_new(prompts_dir, timestamp, model, payload["prompt"].rstrip("\n") + "\n")


def main() -> int:
    try:
        # The payload is UTF-8 JSON whatever the locale claims, so decode it as
        # UTF-8 rather than letting a cp1252 stdin lose the prompt.
        raw = sys.stdin.buffer.read().decode("utf-8", "replace")
        payload = json.loads(raw or "{}")
    except ValueError:
        return 0  # not our payload; say nothing
    if not isinstance(payload, dict):
        return 0
    try:
        record(payload)
    except Exception as error:  # never block a prompt over a recording failure
        print(f"record-prompt: {error}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
