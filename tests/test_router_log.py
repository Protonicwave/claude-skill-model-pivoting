import json
from pathlib import Path

from router_log import append_step, summarise


def test_appends_one_json_line_per_step(tmp_path: Path) -> None:
    log = tmp_path / "nested" / "log.jsonl"
    append_step(log, "search", "router-scout", "done")
    append_step(log, "edit", "router-worker", "failed")
    lines = log.read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["result"] for line in lines] == ["done", "failed"]


def test_summary_counts_results_per_task_type_and_tier(tmp_path: Path) -> None:
    log = tmp_path / "log.jsonl"
    append_step(log, "edit", "router-worker", "done")
    append_step(log, "edit", "router-worker", "failed")
    append_step(log, "edit", "router-expert", "done")
    summary = summarise(log)
    assert summary.counts[("edit", "router-worker")] == {"done": 1, "failed": 1}
    assert summary.counts[("edit", "router-expert")] == {"done": 1}
    assert summary.skipped_lines == 0


def test_summary_skips_malformed_lines(tmp_path: Path) -> None:
    log = tmp_path / "log.jsonl"
    append_step(log, "search", "router-scout", "done")
    with log.open("a", encoding="utf-8") as stream:
        stream.write("not json\n")
        stream.write('{"task_type": "search"}\n')
        stream.write("[1, 2]\n")
    summary = summarise(log)
    assert summary.counts[("search", "router-scout")] == {"done": 1}
    assert summary.skipped_lines == 3


def test_summary_of_missing_log_is_empty(tmp_path: Path) -> None:
    summary = summarise(tmp_path / "absent.jsonl")
    assert summary.counts == {}
    assert summary.skipped_lines == 0
