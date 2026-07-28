"""Session-level process metrics. Counts only — no grader, no ground truth.

Every metric here is derived from the transcript that recorded the behaviour,
not reconstructed from an opinion about what should have happened. That is the
distinction that matters: the graders in this lab failed by re-deriving facts
they should have read. These read.

Where a metric cannot be computed, it is None. None is not zero, and callers
must not average it away — an unmeasurable session is not a well-behaved one.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime

from agent_telemetry.parse import Session

# Tools that inspect rather than change things. Used for the explore-before-edit
# metric, which is the mechanical form of the "Explore -> Plan -> Implement"
# instruction in CLAUDE.md.
READ_TOOLS = {"Read", "Grep", "Glob", "NotebookRead", "WebFetch", "WebSearch", "ToolSearch"}
WRITE_TOOLS = {"Edit", "Write", "NotebookEdit", "MultiEdit"}


def _dt(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def session_metrics(s: Session) -> dict:
    # Subagent traffic is excluded: a subagent's tool calls are its own
    # behaviour, and folding them in would credit the main thread with
    # exploration it did not do.
    calls = [c for c in s.calls if not c.is_sidechain]
    n = len(calls)
    tools = Counter(c.tool for c in calls)

    first_write_i = next((i for i, c in enumerate(calls) if c.tool in WRITE_TOOLS), None)
    reads_before = (
        sum(1 for c in calls[:first_write_i] if c.tool in READ_TOOLS)
        if first_write_i is not None else None
    )

    start = _dt(s.first_ts)
    first_write_dt = _dt(calls[first_write_i].ts) if first_write_i is not None else None
    secs_to_write = (
        (first_write_dt - start).total_seconds()
        if start and first_write_dt else None
    )

    # Thrashing: the same command or file acted on repeatedly by the same tool.
    sig = Counter((c.tool, c.target) for c in calls if c.target)
    repeated = sum(v - 1 for v in sig.values() if v > 1)

    # Churn: distinct files touched more than once by a write tool.
    wf = Counter(c.target for c in calls if c.tool in WRITE_TOOLS and c.target)
    edit_revisits = sum(v - 1 for v in wf.values() if v > 1)

    known = [c for c in calls if c.is_error is not None]
    errors = sum(1 for c in known if c.is_error)

    turns = max(len(s.turns), 0)
    span = None
    if start and (end := _dt(s.last_ts)):
        span = (end - start).total_seconds()

    return {
        "session": s.session,
        "project": s.project,
        "cwd": next((c.cwd for c in calls if c.cwd), None),
        "branch": next((c.git_branch for c in calls if c.git_branch), None),
        "version": next((c.version for c in calls if c.version), None),
        "start": s.first_ts,
        "span_hours": round(span / 3600, 2) if span is not None else None,
        "human_turns": turns,
        "tool_calls": n,
        # The circling metric. High values mean long unsupervised stretches.
        "tool_calls_per_turn": round(n / turns, 1) if turns else None,
        "reads_before_first_edit": reads_before,
        "seconds_to_first_write": round(secs_to_write) if secs_to_write is not None else None,
        "repeated_commands": repeated,
        "edit_revisits": edit_revisits,
        "error_rate": round(errors / len(known), 3) if known else None,
        "errors": errors,
        "results_seen": len(known),
        # Reported separately and NOT counted as failure: warnings legitimately
        # go to stderr, and separating them needs judgement this module does
        # not have.
        "stderr_nonempty": sum(1 for c in calls if c.stderr_nonempty),
        "bash": tools.get("Bash", 0),
        "read": sum(tools.get(t, 0) for t in READ_TOOLS),
        "write": sum(tools.get(t, 0) for t in WRITE_TOOLS),
        "read_write_ratio": (
            round(sum(tools.get(t, 0) for t in READ_TOOLS)
                  / sum(tools.get(t, 0) for t in WRITE_TOOLS), 2)
            if sum(tools.get(t, 0) for t in WRITE_TOOLS) else None
        ),
        "sidechain_calls": sum(1 for c in s.calls if c.is_sidechain),
    }
