"""Turn a Claude Code transcript into a flat table of tool calls.

Schema notes, VERIFIED against real transcripts on 2026-07-28 rather than
assumed — the record shapes below are what the files actually contain:

  type=assistant  message.content is a list; entries with type="tool_use"
                  carry {id, name, input}.
  type=user       serves two different purposes, distinguished by a field:
                    promptSource present  -> a real human turn
                    toolUseResult present -> the result of a tool call
                  Measured on one session: 42 human turns, 363 tool results.
                  Conflating them would inflate turn counts by ~9x and make
                  tool_calls_per_turn meaningless.
  parentUuid      links records into a DAG; present on both branches.
  isSidechain     true for subagent traffic, which is separated out so a
                  subagent's work is not attributed to the main thread.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ToolCall:
    session: str
    project: str
    cwd: str | None
    git_branch: str | None
    version: str | None
    ts: str | None
    tool: str
    tool_use_id: str | None
    target: str | None          # file path or command, truncated
    turn: int                   # index of the human turn this falls under
    is_sidechain: bool
    is_error: bool | None = None
    result_chars: int | None = None
    stderr_nonempty: bool = False


@dataclass
class Session:
    session: str
    project: str
    path: str
    calls: list[ToolCall] = field(default_factory=list)
    turns: list[str] = field(default_factory=list)   # timestamps of human turns
    first_ts: str | None = None
    last_ts: str | None = None


def _target(tool: str, inp: dict) -> str | None:
    """A short fingerprint of what the call acted on. Never the full body."""
    if not isinstance(inp, dict):
        return None
    for key in ("file_path", "command", "pattern", "path", "url", "notebook_path"):
        v = inp.get(key)
        if isinstance(v, str):
            return v[:300]
    return None


def _error_of(result) -> tuple[bool | None, int | None, bool]:
    """(failed, size, stderr_nonempty) for one tool result.

    MEASURED 2026-07-28 against real transcripts, after a first version of this
    function reported error_rate 0.000 for every session — a metric structurally
    incapable of firing. What the transcripts actually contain:

      * failures arrive as a PLAIN STRING beginning "Error:" (19 in one
        344-result session: "Error: Exit code 1", "Error: Exit code 127",
        "Error: File has not been read yet"). The first version returned
        "unknown" for all strings, so every failure was discarded.
      * Bash successes are dicts of {stdout, stderr, interrupted, isImage,
        noOutputExpected}. There is no is_error or status key, so the first
        version's fallthrough scored all 344 as successes.

    stderr is returned SEPARATELY and is deliberately not treated as failure:
    plenty of well-behaved tools write warnings there, and deciding which is
    which needs judgement. This module reports counts, not verdicts — an
    unknown stays None rather than being folded into False.
    """
    if result is None:
        return None, None, False

    if isinstance(result, str):
        # Mechanical, not interpretive: the harness prefixes failures literally.
        return result.startswith("Error:"), len(result), False

    if isinstance(result, dict):
        size = len(json.dumps(result, default=str))
        stderr = result.get("stderr")
        stderr_ne = bool(isinstance(stderr, str) and stderr.strip())

        for key in ("is_error", "isError"):
            if isinstance(result.get(key), bool):
                return result[key], size, stderr_ne
        if result.get("interrupted") is True:
            return True, size, stderr_ne
        status = result.get("status")
        if isinstance(status, str):
            return status.lower() not in ("success", "ok", "completed"), size, stderr_ne
        return False, size, stderr_ne

    return None, None, False


def parse_transcript(path: str | Path) -> Session:
    path = Path(path)
    project = path.parent.name
    sess = Session(session=path.stem, project=project, path=str(path))

    turn = 0
    pending: dict[str, ToolCall] = {}

    with open(path, errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                # A truncated final line is normal for a live session; skip it
                # rather than failing the whole file.
                continue

            ts = r.get("timestamp")
            if ts:
                sess.first_ts = sess.first_ts or ts
                sess.last_ts = ts

            rtype = r.get("type")

            # A real human turn. See the module docstring: presence of
            # promptSource is what separates these from tool results.
            if rtype == "user" and r.get("promptSource") and not r.get("toolUseResult"):
                turn += 1
                if ts:
                    sess.turns.append(ts)
                continue

            if rtype == "user" and r.get("toolUseResult") is not None:
                err, size, stderr_ne = _error_of(r["toolUseResult"])
                # Attach the outcome to the call it belongs to. The link is the
                # tool_use id when available; transcripts do not always carry it
                # on the result, so fall back to the most recent open call.
                tid = None
                msg = r.get("message") or {}
                for c in (msg.get("content") or []) if isinstance(msg.get("content"), list) else []:
                    if isinstance(c, dict) and c.get("type") == "tool_result":
                        tid = c.get("tool_use_id")
                        break
                call = pending.pop(tid, None) if tid else None
                if call is None and pending:
                    call = pending.pop(next(reversed(pending)))
                if call is not None:
                    call.is_error = err
                    call.result_chars = size
                    call.stderr_nonempty = stderr_ne
                continue

            if rtype == "assistant":
                msg = r.get("message") or {}
                content = msg.get("content")
                if not isinstance(content, list):
                    continue
                for c in content:
                    if not (isinstance(c, dict) and c.get("type") == "tool_use"):
                        continue
                    call = ToolCall(
                        session=sess.session,
                        project=project,
                        cwd=r.get("cwd"),
                        git_branch=r.get("gitBranch"),
                        version=r.get("version"),
                        ts=ts,
                        tool=c.get("name") or "?",
                        tool_use_id=c.get("id"),
                        target=_target(c.get("name") or "", c.get("input") or {}),
                        turn=turn,
                        is_sidechain=bool(r.get("isSidechain")),
                    )
                    sess.calls.append(call)
                    if call.tool_use_id:
                        pending[call.tool_use_id] = call

    return sess


def archive_root() -> Path:
    base = os.environ.get("CLAUDE_TELEMETRY_ARCHIVE",
                          str(Path.home() / "claude-telemetry"))
    root = Path(base)
    return root / "raw" if (root / "raw").is_dir() else root


def find_transcripts(root: str | Path | None = None) -> list[Path]:
    root = Path(root) if root else archive_root()
    if not root.exists():
        raise FileNotFoundError(
            f"no transcript archive at {root}. Run "
            f"~/.claude/bin/archive-transcripts.sh first."
        )
    return sorted(root.rglob("*.jsonl"))
