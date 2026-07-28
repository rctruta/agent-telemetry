"""CLI: `python -m agent_telemetry report|export`."""
import sys

import pandas as pd

from agent_telemetry.metrics import session_metrics
from agent_telemetry.parse import find_transcripts, parse_transcript


def frame() -> pd.DataFrame:
    rows = [session_metrics(parse_transcript(p)) for p in find_transcripts()]
    if not rows:
        raise SystemExit("no transcripts found in the archive")
    return pd.DataFrame(rows).sort_values("start")


def main(argv: list[str]) -> int:
    cmd = argv[1] if len(argv) > 1 else "report"
    df = frame()

    if cmd == "export":
        out = argv[2] if len(argv) > 2 else "sessions.parquet"
        df.to_parquet(out, index=False)
        print(f"wrote {out} ({len(df)} sessions, {len(df.columns)} columns)")
        return 0

    pd.set_option("display.width", 200, "display.max_columns", 50)
    cols = ["start", "project", "human_turns", "tool_calls", "tool_calls_per_turn",
            "reads_before_first_edit", "read_write_ratio", "repeated_commands",
            "edit_revisits", "error_rate", "span_hours"]
    view = df[cols].copy()
    view["start"] = view["start"].str.slice(0, 16)
    view["project"] = view["project"].str.replace("-Users-ramona-Projects-", "", regex=False).str.slice(0, 28)
    print(view.to_string(index=False))

    print(f"\n{len(df)} sessions | {int(df.tool_calls.sum())} tool calls | "
          f"{int(df.human_turns.sum())} human turns")
    tpt = df.tool_calls_per_turn.dropna()
    if len(tpt):
        print(f"tool calls per human turn: median {tpt.median():.1f}, "
              f"max {tpt.max():.1f}")
    rb = df.reads_before_first_edit.dropna()
    if len(rb):
        zero = int((rb == 0).sum())
        print(f"reads before first edit: median {rb.median():.0f} | "
              f"{zero}/{len(rb)} sessions edited with ZERO prior reads")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
