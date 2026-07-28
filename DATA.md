# What data exists, what it can support, and what it cannot

Written 2026-07-28 for the MLOps World talk (*The Cost of Prose in Guiding AI
Agents*). Assume you remember nothing. Every claim here was measured on this
machine on the date given; nothing is recalled or assumed.

---

## 1. Where the data is

| what | path | format | size |
|---|---|---|---|
| Claude Code transcripts (live) | `~/.claude/projects/<encoded-cwd>/<session-id>.jsonl` | JSONL, one record per line | 94 MB |
| Claude Code transcripts (archive) | `~/claude-telemetry/raw/` | same, append-only mirror | 80 MB |
| Hook events | `~/claude-telemetry/events/YYYY-MM.jsonl` | JSONL, one line per event | new |
| Antigravity snapshots | `~/claude-telemetry/antigravity/<YYYY-MM-DD>/` | SQLite + protobuf | 269 MB |
| Agent config history | `~/.claude` (git repo) | git | — |

Archives refresh on Claude Code SessionStart and SessionEnd. Nothing is ever
deleted from them.

**Everything is local. Nothing is pushed anywhere.** See §7.

---

## 2. The single most important caveat

**The historical record is mostly gone, and it is not recoverable.**

`cleanupPeriodDays` defaults to **30**, and Claude Code deletes transcripts
older than that at startup. It ran on 2026-07-28 at 16:26 UTC — during the
session that discovered this — and what survives is:

> **7 transcripts, 3 project directories, 5,641 tool calls, 1,047 human turns,
> spanning 2026-05-10 to 2026-07-28.**

That covers six active repos and 2.5 months of daily work. Most of it is not
there. Sessions for `harness-bench`, `podcast-rag`, and `ai-security-testbed`
have no surviving transcript directory at all.

**Do not describe this as a longitudinal dataset.** It is a baseline of n=7
plus whatever accrues after 2026-07-28. If the talk needs before/after
evidence, the "before" mostly does not exist. Say so.

Retention is now 3650 days, so this stops being true going forward.

---

## 3. Claude Code transcript schema (VERIFIED, not assumed)

One JSON object per line. Fields confirmed present in real files:

| field | meaning |
|---|---|
| `type` | `assistant`, `user`, `attachment`, `mode`, `queue-operation`, ... |
| `sessionId`, `uuid`, `parentUuid` | message DAG — reconstructs branches and retries |
| `timestamp` | ISO 8601, UTC |
| `cwd`, `gitBranch` | **the cross-project join key** |
| `version` | Claude Code version — confounder control across time |
| `permissionMode`, `promptSource` | plan mode? human-typed prompt? |
| `isSidechain` | subagent traffic |
| `message.content[]` | entries with `type: "tool_use"` carry `{id, name, input}` |
| `toolUseResult` | the result payload |

**Two schema traps that produced entirely false numbers before being caught:**

1. **`type=user` means two different things.** With `promptSource` → a real
   human turn. With `toolUseResult` → the result of a tool call. Measured in
   one session: **42 human turns vs 363 tool results.** Conflating them
   inflates turn counts ~9× and makes any per-turn metric meaningless.

2. **Tool failures are plain strings beginning `"Error:"`**, e.g.
   `"Error: Exit code 127"`. Successful Bash results are dicts of
   `{stdout, stderr, interrupted, isImage, noOutputExpected}` with **no
   `is_error` or `status` key**. A parser that only looks for an error flag
   reports a 0.0% error rate on every session — which is what the first
   version of `parse.py` did.

Both are regression-tested in `tests/test_parse.py`.

---

## 4. What the metrics mean, and why there is no grader

Run: `python -m agent_telemetry report` (or `export out.parquet`).

| metric | definition | supports the claim |
|---|---|---|
| `tool_calls_per_turn` | tool calls ÷ human turns | how long the agent runs unsupervised |
| `reads_before_first_edit` | Read/Grep/Glob calls before the first Edit/Write | whether "explore before implementing" was followed |
| `repeated_commands` | repeats of the same (tool, target) | thrashing |
| `edit_revisits` | files written more than once | churn |
| `error_rate` | failed ÷ classifiable results | how often calls fail |
| `seconds_to_first_write` | session start → first write | dive-in vs plan |
| `stderr_nonempty` | results with non-empty stderr | reported separately, **not** an error |

**Why this design.** Judging whether an agent did a *good* job requires a
grader, and graders are the component that keeps failing here — six documented
incidents across three projects, every one an interpretation step going wrong.
These metrics are counts read out of the record the behaviour produced. No
ground truth is reconstructed. Nothing is judged.

That is also the honest limit: **these measure process, not quality.** A
session with a low error rate and many reads may still have produced garbage.
Do not let a process metric stand in for an outcome claim.

Where a metric cannot be computed it is `None`, deliberately. `None` is not
zero — do not average it away.

---

## 5. The study the data can actually support

**Design: rules as natural experiments.**

`~/.claude` is now a git repo, so from 2026-07-28 forward every change to
`CLAUDE.md`, `settings.json`, hooks, and output styles has a commit date. A
rule is a hypothesis about behaviour. Compare a metric before and after the
commit that introduced it.

Worked example: *"Explore → Plan → Implement"* predicts `reads_before_first_edit`
rises after the rule lands. If it does not move, **the rule does not bind** —
which is the talk's thesis, stated as a number instead of an anecdote.

**Complementary and stronger: gate-block events.** `~/claude-telemetry/events/`
records `PermissionDenied` with the reason. Prose cannot produce a denial
record; only a mechanical gate can. The contrast between "rules written down"
and "rules that fired" is the sharpest evidence available here.

Supporting observation already in hand, from 2026-07-28: three mechanical gates
fired and changed behaviour (branch protection, pre-push tests, identity guard),
and the pre-push gate directly caused three real defects to be found. Several
prose instructions in `CLAUDE.md` were not followed in the same session. That
is one session — an illustration, **not** a result.

### What the data cannot support

- **No causal claim without a controlled comparison.** Model version, task
  type, and repo all vary. `version` and `cwd` are recorded so they can be
  controlled for; they have not been.
- **No cross-tool comparison yet.** Antigravity data is stored but not parsed
  (§6). Do not compare Claude Code to Antigravity from these numbers.
- **No ML.** n=7 sessions. Even at n=200 the right tools are descriptive
  statistics, before/after comparison, and changepoint detection. Reaching for
  a model here would be decoration.
- **n=1 on gate evidence.** Compelling, and a single session.

---

## 6. Antigravity — archived, not yet parsed

Snapshotted to `~/claude-telemetry/antigravity/<date>/`, dated directories with
hardlinks between snapshots (binary formats are rewritten in place, so a plain
mirror would let a rewrite destroy history).

Surveyed 2026-07-28:

- `antigravity/conversations/` — 68 MB, 13 files
- `antigravity-ide/conversations/` — **157 MB**, the larger body of work
- `brain/` — agent memory, 482 files
- plus `knowledge/`, `implicit/`, `code_tracker/`, `annotations/`, `config/`
- excluded: `extensions/`, `bin/`, and the Chrome `browser-profile` (cookies
  and credentials, no research value)

**Format:** `.db` files are **plain SQLite and readable** — tables include
`steps` (150 rows in the one inspected), `trajectory_meta`, `gen_metadata`,
`executor_metadata`. `.pb` files are protobuf with no published schema and are
the harder half.

**Status: unparsed.** The SQLite half looks tractable and would give a genuine
second tool for comparison. Effort unknown. Nothing in this document depends
on it.

**Note:** all 11 original conversation files carried a 2026-06-18 mtime. Not
investigated. Do not assume that is the true span of the work.

---

## 7. Privacy — read before publishing anything

**Session transcripts contain credential-shaped strings.** VERIFIED
2026-07-28: a scan for `sk-ant`, `ghp_`, `AKIA`, and private-key headers hit
2 of 7 transcript files. Keys get pasted and echoed during ordinary work.

Therefore:

- `~/.claude` tracks **config only**; `projects/`, `sessions/`, `history.jsonl`
  are gitignored.
- `agent-telemetry` gitignores `*.jsonl`, `*.parquet`, `raw/`.
- The archive at `~/claude-telemetry/` is **not** a git repo and must not be
  pushed.
- Hook events store metadata only — tool names, timestamps, denial reasons, and
  a 200-character target fingerprint. Never tool output.
- **Before publishing any extract**, re-run the credential scan on the exact
  artifact being published. Metrics frames carry command text in `target`.

Antigravity conversations have **not** been scanned. Treat them as sensitive.

---

## 8. Reproducing the numbers

```bash
cd ~/Projects/agent-telemetry
.venv/bin/python -m agent_telemetry report
.venv/bin/python -m agent_telemetry export sessions.parquet   # gitignored
.venv/bin/python -m pytest tests/ -q                          # 10 tests
```

Manual refresh (normally automatic on session start/end):

```bash
~/.claude/bin/archive-transcripts.sh
~/.claude/bin/archive-antigravity.sh
```
