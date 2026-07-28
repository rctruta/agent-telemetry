# The retention finding — verified facts, for a write-up

**Status: raw material, not a draft.** Facts, numbers, commands, and the
reproduction steps. The framing and the words are Ramona's.

Everything below was measured on one macOS machine on 2026-07-28, or read from
official documentation on that date. Nothing is recalled. Where something was
not checked, it says so.

---

## The finding in one line

Claude Code writes a complete JSONL transcript of every session — and deletes
it after 30 days by default. Most users have never looked, so the deletion is
silent, and by the time anyone wants the history it is gone.

## Why it is worth telling other people

Three properties, and it needs all three to be interesting:

1. **It is on by default**, so it affects everyone who has not changed it.
2. **The deleted thing is valuable** and getting more so — agent session logs
   are the only record of how these tools actually behave in real work.
3. **It is invisible.** No warning, no prompt, no notification. Deletion runs
   at startup.

It is also a five-second fix, which makes it worth saying out loud rather than
studying.

---

## Verified facts

**Documentation** (`https://code.claude.com/docs/en/settings`, read
2026-07-28):

- setting key: **`cleanupPeriodDays`**
- default: **30**
- minimum: 1
- behaviour: Claude Code deletes session files older than this period **at
  startup**

**On this machine:**

- `~/.claude/settings.json` did **not** contain the key → default applied
- `~/.claude/.last-cleanup` contained `2026-07-28T16:26:08.639Z` — cleanup had
  run **that day, 12:26 local, during the session that found this**
- surviving transcripts: **7 files across 3 project directories**
- surviving span: 2026-05-10 → 2026-07-28
- surviving volume: **5,641 tool calls, 1,047 human turns**
- actual scope of work in that window: **six active repositories, daily use**
- three of those repos (`harness-bench`, `podcast-rag`, `ai-security-testbed`)
  had **no surviving transcript directory at all**

**Transcript content and location:**

- path: `~/.claude/projects/<url-encoded-cwd>/<session-id>.jsonl`
- one JSON object per line
- fields confirmed present: `type`, `sessionId`, `uuid`, `parentUuid`,
  `timestamp`, `cwd`, `gitBranch`, `version`, `permissionMode`, `promptSource`,
  `isSidechain`, `message.content[]` (with `tool_use` entries carrying
  `{id, name, input}`), `toolUseResult`
- one session measured: 1,604 records — **257 Bash, 66 Edit, 22 Read, 14
  Write**, 36 results carrying errors, spanning 3 days

**A finding that must travel with any advice to keep these files:**

- a scan for `sk-ant`, `sk-…`, `ghp_`, `gho_`, `AKIA`, and private-key headers
  matched **2 of 7 transcript files**
- cause: keys get pasted into prompts and echoed by commands during ordinary
  work
- consequence: **transcripts must never be committed or pushed.** Anyone told
  to preserve them must be told this in the same breath.

---

## The fix

```bash
# check what you have
cat ~/.claude/.last-cleanup
find ~/.claude/projects -name '*.jsonl' | wc -l
```

```bash
# stop the deletion (10 years)
python3 - <<'EOF'
import json, pathlib
p = pathlib.Path.home() / ".claude" / "settings.json"
s = json.loads(p.read_text()) if p.exists() else {}
s["cleanupPeriodDays"] = 3650
p.write_text(json.dumps(s, indent=2) + "\n")
print("cleanupPeriodDays =", s["cleanupPeriodDays"])
EOF
```

Archiving separately is the belt-and-braces version: a setting can be reset, a
config can be reinstalled, a default can change. `bin/archive-transcripts.sh`
in this repo's parent config does an append-only copy on session start and end.

---

## The second, larger point (optional for a write-up)

The transcripts are not just a backup. They are a behavioural dataset, and the
metrics that matter most need **no grader**:

| metric | why it needs no judgement |
|---|---|
| tool calls per human turn | a count |
| reads before first edit | a count |
| repeated identical commands | a count |
| error rate | a count, once failures are parsed correctly |

This matters because grading whether an agent did a *good* job requires an
interpretation step, and interpretation steps are where measurement of agents
tends to fail — six documented instances across three projects in this lab, all
the same shape: the grader reconstructed a fact instead of reading it.

Process metrics sidestep it. The honest limit, which belongs in any version of
this: **process is not quality.** A clean process metric does not mean the work
was good.

**A pointed use, if the write-up wants one:** rules written in prose
(`CLAUDE.md` and equivalents) are hypotheses about behaviour. Put the config
under version control, and every rule has an introduction date. Compare the
metric before and after. If the metric does not move, the rule does not bind.

---

## Two parser defects, if the write-up wants concrete texture

Both produced clean-looking, entirely false numbers, and both were found by
checking against real files rather than assuming the schema:

1. **`type=user` serves two purposes** — human turns *and* tool results.
   Measured in one session: **42 human turns vs 363 tool results.** Treating
   them alike inflates turn counts ~9× and makes any per-turn metric
   meaningless.

2. **Tool failures arrive as plain strings prefixed `"Error:"`** (e.g.
   `"Error: Exit code 127"`). Successful Bash results are dicts of
   `{stdout, stderr, interrupted, isImage, noOutputExpected}` with **no
   `is_error` or `status` key**. A parser looking only for an error flag
   reports **0.0% errors on every session** — a metric structurally incapable
   of firing. That is what the first version of `parse.py` did, and the number
   looked entirely plausible.

Both are regression-tested in `tests/test_parse.py`.

---

## Scope limits — do not overstate

- **One machine, one OS** (macOS, Claude Code 2.1.x). Not checked on Linux or
  Windows; not checked across versions.
- **`cleanupPeriodDays` applies to Claude Code.** Other agent tools were not
  examined for equivalent behaviour, with one partial exception: Google
  Antigravity keeps conversations at `~/.gemini/antigravity*/conversations/`
  as SQLite and protobuf (225 MB here). **Its retention behaviour was not
  determined.** Do not claim other tools do the same thing without checking.
- **n=7 sessions.** Enough to demonstrate the loss; not a dataset. Any
  behavioural claim from it is an illustration, not a result.
- **No causal claims.** Model version, task type, and repo all vary and none
  were controlled.
- The gate-versus-prose observation from 2026-07-28 (three mechanical gates
  fired and changed behaviour; several written instructions did not) is **one
  session**. Compelling, not evidence.
