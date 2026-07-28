"""Regression tests built from real transcript shapes.

The fixtures below are synthetic but their SHAPES were read off actual
transcripts on 2026-07-28, not invented. Two of these tests exist because the
first version of the parser was wrong in ways that produced clean-looking,
entirely false numbers.
"""
import json

import pytest

from agent_telemetry.metrics import session_metrics
from agent_telemetry.parse import parse_transcript

TS = "2026-07-28T10:%02d:00.000Z"


def rec(**kw):
    base = {"cwd": "/p", "gitBranch": "main", "version": "2.1.0",
            "isSidechain": False}
    base.update(kw)
    return base


def human(i, text="do the thing"):
    return rec(type="user", promptSource="sdk", timestamp=TS % i,
               message={"role": "user", "content": text})


def call(i, tool, tid, **inp):
    return rec(type="assistant", timestamp=TS % i,
               message={"role": "assistant",
                        "content": [{"type": "tool_use", "id": tid,
                                     "name": tool, "input": inp}]})


def result(i, tid, payload):
    return rec(type="user", timestamp=TS % i, toolUseResult=payload,
               message={"role": "user",
                        "content": [{"type": "tool_result", "tool_use_id": tid}]})


def write(tmp_path, records, name="s1.jsonl"):
    d = tmp_path / "proj"
    d.mkdir(exist_ok=True)
    p = d / name
    p.write_text("".join(json.dumps(r) + "\n" for r in records))
    return p


BASH_OK = {"stdout": "hello", "stderr": "", "interrupted": False,
           "isImage": False, "noOutputExpected": False}


def test_human_turns_are_not_confused_with_tool_results(tmp_path):
    """The distinction the whole per-turn metric rests on.

    Tool results are also type=user. Counting them as turns inflated turn
    counts ~9x in real data (42 human turns vs 363 results in one session).
    """
    p = write(tmp_path, [
        human(1),
        call(2, "Bash", "t1", command="ls"),
        result(3, "t1", BASH_OK),
        call(4, "Bash", "t2", command="pwd"),
        result(5, "t2", BASH_OK),
        human(6),
    ])
    s = parse_transcript(p)
    assert len(s.turns) == 2, "tool results must not count as human turns"
    m = session_metrics(s)
    assert m["human_turns"] == 2
    assert m["tool_calls"] == 2
    assert m["tool_calls_per_turn"] == 1.0


def test_error_strings_are_detected(tmp_path):
    """REGRESSION: the first parser reported error_rate 0.000 for every session.

    Tool failures arrive as a plain STRING prefixed "Error:". The first version
    returned "unknown" for strings and "success" for every dict, so the metric
    could not be non-zero under any input. A metric that cannot fire is not a
    measurement.
    """
    p = write(tmp_path, [
        human(1),
        call(2, "Bash", "t1", command="ls"),
        result(3, "t1", BASH_OK),
        call(4, "Bash", "t2", command="bun x"),
        result(5, "t2", "Error: Exit code 127\nbun not found"),
        call(6, "Write", "t3", file_path="/p/a.py"),
        result(7, "t3", "Error: File has not been read yet."),
    ])
    m = session_metrics(parse_transcript(p))
    assert m["errors"] == 2, "literal 'Error:' results must be counted as failures"
    assert m["results_seen"] == 3
    assert m["error_rate"] == pytest.approx(2 / 3, abs=0.01)


def test_error_rate_can_reach_zero_and_one(tmp_path):
    """Guards the other direction: the metric must span its range."""
    ok = write(tmp_path, [human(1), call(2, "Bash", "t1", command="ls"),
                          result(3, "t1", BASH_OK)], "ok.jsonl")
    bad = write(tmp_path, [human(1), call(2, "Bash", "t1", command="x"),
                           result(3, "t1", "Error: Exit code 1")], "bad.jsonl")
    assert session_metrics(parse_transcript(ok))["error_rate"] == 0.0
    assert session_metrics(parse_transcript(bad))["error_rate"] == 1.0


def test_stderr_is_not_counted_as_failure(tmp_path):
    """Warnings go to stderr. Calling that a failure would need judgement."""
    p = write(tmp_path, [
        human(1),
        call(2, "Bash", "t1", command="build"),
        result(3, "t1", {**BASH_OK, "stderr": "warning: deprecated flag"}),
    ])
    m = session_metrics(parse_transcript(p))
    assert m["errors"] == 0
    assert m["stderr_nonempty"] == 1, "stderr must still be reported, separately"


def test_unknown_outcome_is_not_folded_into_success(tmp_path):
    """A result the parser cannot classify must not inflate the success count."""
    p = write(tmp_path, [
        human(1),
        call(2, "Bash", "t1", command="ls"),
        result(3, "t1", 12345),          # neither str nor dict
    ])
    m = session_metrics(parse_transcript(p))
    assert m["results_seen"] == 0, "unclassifiable results must be excluded, not passed"
    assert m["error_rate"] is None


def test_reads_before_first_edit(tmp_path):
    """The mechanical form of 'explore before you implement'."""
    p = write(tmp_path, [
        human(1),
        call(2, "Read", "t1", file_path="/p/a.py"),
        result(3, "t1", BASH_OK),
        call(4, "Grep", "t2", pattern="foo"),
        result(5, "t2", BASH_OK),
        call(6, "Edit", "t3", file_path="/p/a.py"),
        result(7, "t3", BASH_OK),
        call(8, "Read", "t4", file_path="/p/b.py"),   # after the edit: excluded
        result(9, "t4", BASH_OK),
    ])
    assert session_metrics(parse_transcript(p))["reads_before_first_edit"] == 2


def test_zero_reads_before_edit_is_zero_not_none(tmp_path):
    """Diving straight into an edit must be visible as 0, not absent."""
    p = write(tmp_path, [human(1), call(2, "Edit", "t1", file_path="/p/a.py"),
                         result(3, "t1", BASH_OK)])
    assert session_metrics(parse_transcript(p))["reads_before_first_edit"] == 0


def test_subagent_calls_excluded_from_main_thread(tmp_path):
    """A subagent's exploration must not be credited to the main thread."""
    side = rec(type="assistant", timestamp=TS % 4, isSidechain=True,
               message={"role": "assistant",
                        "content": [{"type": "tool_use", "id": "s1",
                                     "name": "Read", "input": {"file_path": "/p/z"}}]})
    p = write(tmp_path, [human(1), call(2, "Edit", "t1", file_path="/p/a.py"),
                         result(3, "t1", BASH_OK), side])
    m = session_metrics(parse_transcript(p))
    assert m["tool_calls"] == 1
    assert m["sidechain_calls"] == 1
    assert m["reads_before_first_edit"] == 0


def test_repeated_commands_and_edit_revisits(tmp_path):
    p = write(tmp_path, [
        human(1),
        call(2, "Bash", "t1", command="pytest"),
        result(3, "t1", BASH_OK),
        call(4, "Bash", "t2", command="pytest"),
        result(5, "t2", BASH_OK),
        call(6, "Edit", "t3", file_path="/p/a.py"),
        result(7, "t3", BASH_OK),
        call(8, "Edit", "t4", file_path="/p/a.py"),
        result(9, "t4", BASH_OK),
    ])
    m = session_metrics(parse_transcript(p))
    assert m["repeated_commands"] == 2   # one repeat of pytest, one of the edit
    assert m["edit_revisits"] == 1


def test_truncated_final_line_does_not_fail(tmp_path):
    """Live sessions are read mid-write; a partial last line is normal."""
    d = tmp_path / "proj"
    d.mkdir()
    p = d / "s.jsonl"
    p.write_text(json.dumps(human(1)) + "\n" + '{"type":"assist')
    assert session_metrics(parse_transcript(p))["human_turns"] == 1
