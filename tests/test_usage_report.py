import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from usage_report import (
    UNKNOWN_AGENT_TYPE,
    Usage,
    cost_usd,
    format_report,
    read_turns,
    spend_by_source,
    unrouted_totals,
)

OPUS = "claude-opus-5-5"
HAIKU = "claude-haiku-5-5"
SMALL = Usage(input=1_000, write_5m=0, write_1h=0, read=0, output=1_000)
NO_TOKENS = Usage(input=0, write_5m=0, write_1h=0, read=0, output=0)


def assistant_line(
    usage: Usage,
    message_id: str = "msg_1",
    model: str = OPUS,
    time: str = "2026-11-10T09:15:00.000Z",
) -> dict[str, object]:
    return {
        "type": "assistant",
        "timestamp": time,
        "requestId": f"req_{message_id}",
        "message": {
            "id": message_id,
            "model": model,
            "usage": {
                "input_tokens": usage.input,
                "cache_creation_input_tokens": usage.write_5m + usage.write_1h,
                "cache_read_input_tokens": usage.read,
                "output_tokens": usage.output,
                "cache_creation": {
                    "ephemeral_5m_input_tokens": usage.write_5m,
                    "ephemeral_1h_input_tokens": usage.write_1h,
                },
            },
        },
    }


def write_lines(path: Path, lines: list[object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(
        line if isinstance(line, str) else json.dumps(line) + "\n" for line in lines
    )
    path.write_text(text, encoding="utf-8")


def write_main(projects: Path, session: str, lines: list[object]) -> None:
    write_lines(projects / "project" / f"{session}.jsonl", lines)


def write_agent(
    projects: Path, agent_id: str, agent_type: str | None, lines: list[object]
) -> None:
    folder = projects / "project" / "session" / "subagents"
    write_lines(folder / f"agent-{agent_id}.jsonl", lines)
    if agent_type is not None:
        meta = {"agentType": agent_type, "description": "step"}
        (folder / f"agent-{agent_id}.meta.json").write_text(
            json.dumps(meta), encoding="utf-8"
        )


def test_repeated_usage_lines_count_once(tmp_path: Path) -> None:
    line = assistant_line(SMALL)
    write_main(tmp_path, "first", [line, line, line])
    write_main(tmp_path, "resumed", [line, assistant_line(SMALL, "msg_2")])
    assert len(read_turns(tmp_path)) == 2


def test_prices_each_token_kind_at_its_rate() -> None:
    million = 1_000_000
    usage = Usage(
        input=million, write_5m=million, write_1h=million, read=million, output=million
    )
    assert cost_usd(OPUS, usage) == pytest.approx(4 + 5 + 8 + 0.20 + 20)


@pytest.mark.parametrize(
    ("prompt_tokens", "expected_usd"),
    [(100_000, 100_000 * 0.10 / 1e6 + 0.50), (100_001, 100_001 * 0.50 / 1e6 + 2.50)],
)
def test_haiku_prompts_over_100k_use_the_higher_rates(
    prompt_tokens: int, expected_usd: float
) -> None:
    usage = Usage(input=prompt_tokens, write_5m=0, write_1h=0, read=0, output=1_000_000)
    assert cost_usd(HAIKU, usage) == pytest.approx(expected_usd)


def test_unknown_model_is_unpriced() -> None:
    assert cost_usd("claude-opus-5", SMALL) is None


def test_unpriced_tokens_are_reported_apart_from_spend(tmp_path: Path) -> None:
    write_main(tmp_path, "s", [assistant_line(SMALL, model="claude-opus-5")])
    spend = spend_by_source(read_turns(tmp_path))[("main", "claude-opus-5")]
    assert spend.cost_usd == 0
    assert spend.unpriced_tokens == 2_000


@pytest.mark.parametrize(
    "bad_line",
    [
        'not json "assistant"\n',
        '["assistant"]\n',
        '{"type": "assistant"}\n',
        '{"type": "assistant", "message": {"id": "m", "model": "x", "usage": []}}\n',
        json.dumps(assistant_line(SMALL, "msg_x")).replace(
            '"2026-11-10T09:15:00.000Z"', "5"
        )
        + "\n",
        '{"type": "user", "message": {"content": "assistant"}}\n',
        json.dumps(assistant_line(SMALL, "msg_x", model="<synthetic>")) + "\n",
        json.dumps(assistant_line(SMALL, "msg_x", time="yesterday")) + "\n",
        json.dumps(assistant_line(SMALL, "msg_x")).replace("1000", "-1") + "\n",
        json.dumps(assistant_line(SMALL, "msg_x")).replace("1000", "true") + "\n",
    ],
)
def test_skips_malformed_and_synthetic_lines(tmp_path: Path, bad_line: str) -> None:
    write_main(tmp_path, "s", [bad_line, assistant_line(SMALL)])
    assert [turn.usage for turn in read_turns(tmp_path)] == [SMALL]


def test_usage_without_split_writes_counts_as_five_minute_writes(
    tmp_path: Path,
) -> None:
    line = assistant_line(NO_TOKENS)
    usage = line["message"]["usage"]  # type: ignore[index]
    del usage["cache_creation"]
    usage["cache_creation_input_tokens"] = 700
    write_main(tmp_path, "s", [line])
    assert read_turns(tmp_path)[0].usage.write_5m == 700


def test_agent_type_comes_from_metadata(tmp_path: Path) -> None:
    write_agent(tmp_path, "a1", "router-worker", [assistant_line(SMALL, "m1")])
    write_agent(tmp_path, "a2", None, [assistant_line(SMALL, "m2")])
    nested = tmp_path / "project" / "session" / "subagents" / "workflows" / "wf_1"
    write_lines(nested / "agent-a3.jsonl", [assistant_line(SMALL, "m3")])
    (nested / "agent-a3.meta.json").write_text("{broken", encoding="utf-8")
    sources = {turn.transcript: turn.source for turn in read_turns(tmp_path)}
    assert sources == {
        "agent-a1": "router-worker",
        "agent-a2": UNKNOWN_AGENT_TYPE,
        "agent-a3": UNKNOWN_AGENT_TYPE,
    }


def test_since_drops_earlier_turns(tmp_path: Path) -> None:
    lines: list[object] = [
        assistant_line(SMALL, "old", time="2026-11-07T23:59:59Z"),
        assistant_line(SMALL, "new", time="2026-11-08T00:00:00Z"),
    ]
    write_main(tmp_path, "s", lines)
    since = datetime(2026, 11, 8, tzinfo=UTC)
    assert [turn.time.day for turn in read_turns(tmp_path, since)] == [8]


def test_spend_counts_turns_and_spawns_per_source_and_model(tmp_path: Path) -> None:
    write_main(tmp_path, "s", [assistant_line(SMALL, "m0")])
    write_agent(tmp_path, "g1", "general-purpose", [assistant_line(SMALL, "m1")])
    write_agent(
        tmp_path,
        "g2",
        "general-purpose",
        [assistant_line(SMALL, "m2"), assistant_line(SMALL, "m3")],
    )
    write_agent(tmp_path, "w1", "router-worker", [assistant_line(SMALL, "m4")])
    spend = spend_by_source(read_turns(tmp_path))
    general = spend[("general-purpose", OPUS)]
    assert (general.turns, len(general.transcripts)) == (3, 2)
    assert general.cost_usd == pytest.approx(3 * (1_000 * 4 + 1_000 * 20) / 1e6)
    spawns, cost = unrouted_totals(spend)
    assert (spawns, cost) == (2, general.cost_usd)


def test_report_names_each_section(tmp_path: Path) -> None:
    unpriced = assistant_line(SMALL, "m2", model="claude-opus-5")
    write_main(tmp_path, "s", [assistant_line(SMALL), unpriced])
    report = format_report(read_turns(tmp_path))
    assert "Spend by source and model" in report
    assert "unpriced: 2.0k tokens" in report
    assert "Unrouted spawns: 0" in report


def test_report_on_no_turns_says_so() -> None:
    assert format_report([]) == "No assistant turns found."
