# RETRACTED: "Claude Code is silently deleting your agent history"

**Status: retracted 2026-07-28, the same day it was written. Kept because the
error is more useful than the claim was.**

## What was claimed

That Claude Code's `cleanupPeriodDays` default of 30 had already destroyed most
of 2.5 months of daily work across six repositories, leaving 7 surviving
transcripts, and that cleanup had run mid-session and taken data with it.

## What was actually true

**No data was deleted. There is no evidence any has ever been lost on this
machine.**

The claim rested on two facts and one inference. The facts:

- `~/.claude/.last-cleanup` contained `2026-07-28T16:26:08.639Z` (12:26 EDT)
- only 7 transcripts existed across 3 project directories

The inference — that the first caused the second — was wrong, and was never
checked before being written down and committed.

**What checking would have shown, and did once Ramona pushed back:**

| check | result |
|---|---|
| `~/.claude/projects` dir mtime | **2026-07-10**. Removing any file or subdirectory inside updates this. It was not touched. |
| individual project dir mtimes | 2026-07-18, 2026-07-16, 2026-06-22 — none recent |
| oldest surviving transcript | oldest record **2026-05-10, 78 days old**, against a 30-day default — still present |
| what actually happened at that timestamp | **9 × `compact_boundary` records, `trigger: auto`, `preTokens: 1,001,037`** — context compaction, which is what she said she witnessed |

`.last-cleanup` records that the cleanup routine **ran**. It does not record
that anything was **deleted**. Those are different facts, and only one was
present.

**Why 7 files was never alarming.** Sessions here are long-lived and resumed.
A single transcript spans **2026-06-10 → 2026-07-28: 48 days, 80 MB, 9
auto-compactions**. Work on three repositories that appeared to have "no
surviving history" is inside that one file, because those edits were made from
one worktree `cwd`. File count is not session count and is not history.

**The mechanism, correctly stated.** Retention keys on **file mtime**, and
resuming a session resets it. The transcript whose oldest record is 2026-05-10
has an mtime of 2026-07-23. Active sessions never age out. Only genuinely
abandoned ones are at risk — a far smaller and less interesting exposure.

## What survives the retraction

- `cleanupPeriodDays` does default to **30**, deleting at startup. Verified in
  the documentation, not disputed.
- Raising it and archiving remain cheap insurance for abandoned sessions and
  against a default changing. Both are in place and cost nothing.
- **Transcripts contain credential-shaped strings** — a scan matched 2 of 7
  files. This is independently verified and unaffected by the retraction.
  Anyone advised to preserve transcripts must be told this at the same time.
- The parser defects and the schema traps in `DATA.md` §3 stand; they were
  measured directly.

## The lesson actually worth sharing

Not "your logs are being deleted." That was false. The lesson is the shape of
the error:

**A log entry saying a process ran is not evidence that the process did
anything.** `.last-cleanup` is a timestamp of execution. Deletion leaves its own
evidence — directory mtimes — and that evidence was one command away and never
collected. The alarming reading was adopted because the alarming reading was
available.

Three properties made it convincing, and none of them are truth:

1. **A real default.** `cleanupPeriodDays: 30` genuinely exists, so the story
   had a mechanism.
2. **A real correlation.** The timestamp really was from that day.
3. **A confirming absence.** 7 files really is few — but "few files" and
   "deleted files" produce the same observation, and only one was tested.

The falsifying check cost one `stat` call. It was run only after the person who
had actually watched it happen said *"not sure the cleanup happened mid session
as you claimed — verify."* She was right; she had watched compaction, and the
transcript records compaction nine times.

**Generalised:** when an inferred cause and an observed effect are both
plausible, the check that separates them is usually cheap, and skipping it is
usually what turns a plausible story into a published false one. Cost here:
one command, and the claim was already committed and pushed to a repository
before anyone ran it.
