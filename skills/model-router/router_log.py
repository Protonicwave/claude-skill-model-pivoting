"""Record routed steps and summarise how each tier performs.

Record a step:  python router_log.py add <task-type> <tier> <done|failed|blocked>
Summarise:      python router_log.py summary

The log is one JSON object per line at ~/.claude/model-router/log.jsonl,
outside every project so no repository gains a stray file.
"""

import argparse
import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, get_args

Result = Literal["done", "failed", "blocked"]
RESULTS: tuple[str, ...] = get_args(Result)
DEFAULT_LOG_PATH = Path.home() / ".claude" / "model-router" / "log.jsonl"


@dataclass
class Summary:
    counts: dict[tuple[str, str], Counter[str]] = field(default_factory=dict)
    skipped_lines: int = 0


def append_step(log_path: Path, task_type: str, tier: str, result: Result) -> None:
    entry = {
        "time": datetime.now(UTC).isoformat(timespec="seconds"),
        "task_type": task_type,
        "tier": tier,
        "result": result,
    }
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(entry) + "\n")


def parse_entry(line: str) -> tuple[str, str, str] | None:
    """Return (task_type, tier, result) for a well-formed line, else None."""
    try:
        entry = json.loads(line)
    except json.JSONDecodeError:
        return None
    if not isinstance(entry, dict):
        return None
    task_type, tier, result = (
        entry.get(key) for key in ("task_type", "tier", "result")
    )
    if isinstance(task_type, str) and isinstance(tier, str) and isinstance(result, str):
        return task_type, tier, result
    return None


def summarise(log_path: Path) -> Summary:
    """Count results per (task type, tier). A missing log is an empty summary."""
    counts: defaultdict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    skipped_lines = 0
    if not log_path.exists():
        return Summary()
    with log_path.open(encoding="utf-8") as stream:
        for line in stream:
            parsed = parse_entry(line)
            if parsed is None:
                skipped_lines += 1
                continue
            task_type, tier, result = parsed
            counts[(task_type, tier)][result] += 1
    return Summary(counts=dict(counts), skipped_lines=skipped_lines)


def format_summary(summary: Summary) -> str:
    if not summary.counts:
        return "No routed steps logged yet."
    lines = [f"{'Task type':<24} {'Tier':<16} {'done':>5} {'failed':>7} {'blocked':>8}"]
    for (task_type, tier), results in sorted(summary.counts.items()):
        lines.append(
            f"{task_type:<24} {tier:<16} {results['done']:>5} "
            f"{results['failed']:>7} {results['blocked']:>8}"
        )
    if summary.skipped_lines:
        lines.append(f"Skipped {summary.skipped_lines} malformed line(s).")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Record or summarise routed steps.")
    commands = parser.add_subparsers(dest="command", required=True)
    add = commands.add_parser("add")
    add.add_argument("task_type")
    add.add_argument("tier")
    add.add_argument("result", choices=RESULTS)
    commands.add_parser("summary")
    arguments = parser.parse_args()

    if arguments.command == "add":
        append_step(
            DEFAULT_LOG_PATH, arguments.task_type, arguments.tier, arguments.result
        )
    else:
        print(format_summary(summarise(DEFAULT_LOG_PATH)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
