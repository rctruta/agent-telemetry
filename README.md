# agent-telemetry

Process metrics for coding-agent sessions, derived from the JSONL transcripts
Claude Code already writes.

## Why process metrics

Measuring whether an agent did a *good* job needs a grader, and graders are the
component that keeps failing — six documented incidents across three projects in
this lab, every one an interpretation step going wrong.

Process metrics need no interpretation. They are counts:

| metric | question it answers |
|---|---|
| `tool_calls_per_turn` | how much work happens between two human messages |
| `reads_before_first_edit` | did it explore before implementing |
| `repeated_commands` | is it thrashing on the same command |
| `error_rate` | how often tool calls come back failed |
| `seconds_to_first_write` | did it plan, or dive straight in |
| `edit_revisits` | how many times the same file was rewritten |

None require ground truth. None require judging output quality. Every one is
derived from the transcript at generation time rather than reconstructed after
the fact — which is the rule the graders in this lab broke.

## What this is for

Rules written in prose (`CLAUDE.md`, output styles, memory) are hypotheses about
agent behaviour. Each was added on a date. With `~/.claude` under version
control, rule-introduction dates are known, and these metrics can be compared
before and after. If a rule does not move its metric, the rule does not bind.

That is the measurement; this package produces the numbers for it.

## Use

```
uv run python -m agent_telemetry report          # summary across all sessions
uv run python -m agent_telemetry export out.parquet
```

Reads from `$CLAUDE_TELEMETRY_ARCHIVE/raw` (default `~/claude-telemetry/raw`),
which is populated by `~/.claude/bin/archive-transcripts.sh`.

## Privacy

Transcripts were verified on 2026-07-28 to contain credential-shaped strings.
This package reads them locally and its outputs carry only metadata — tool
names, counts, timestamps, paths — never tool output bodies. Do not commit raw
transcripts or exported frames containing them.
