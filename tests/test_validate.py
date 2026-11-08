from pathlib import Path

import pytest
from validate import validate

REPO_ROOT = Path(__file__).resolve().parent.parent


def write_agent(root: Path, name: str, fields: dict[str, str]) -> None:
    agents = root / "agents"
    agents.mkdir(parents=True, exist_ok=True)
    lines = [
        "---",
        *(f"{key}: {value}" for key, value in fields.items()),
        "---",
        "Body.",
    ]
    (agents / f"{name}.md").write_text("\n".join(lines), encoding="utf-8")


def valid_fields(name: str) -> dict[str, str]:
    return {
        "name": name,
        "description": "Does a thing.",
        "model": "haiku",
        "effort": "low",
    }


def test_accepts_repository_agents() -> None:
    assert validate(REPO_ROOT) == []


def test_accepts_full_model_id(tmp_path: Path) -> None:
    write_agent(tmp_path, "a", {**valid_fields("a"), "model": "claude-opus-5-5"})
    assert validate(tmp_path) == []


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        ("model", "gpt-5", "unknown model 'gpt-5'"),
        ("effort", "extreme", "unknown effort 'extreme'"),
        ("name", "other", "name 'other' does not match file name 'a'"),
    ],
)
def test_rejects_bad_value(
    tmp_path: Path, field: str, value: str, expected: str
) -> None:
    write_agent(tmp_path, "a", {**valid_fields("a"), field: value})
    errors = validate(tmp_path)
    assert len(errors) == 1
    assert expected in errors[0]


def test_rejects_missing_field(tmp_path: Path) -> None:
    fields = valid_fields("a")
    del fields["effort"]
    write_agent(tmp_path, "a", fields)
    assert any("missing field 'effort'" in error for error in validate(tmp_path))


def test_rejects_file_without_frontmatter(tmp_path: Path) -> None:
    (tmp_path / "agents").mkdir()
    (tmp_path / "agents" / "a.md").write_text("No frontmatter.", encoding="utf-8")
    assert any("no frontmatter" in error for error in validate(tmp_path))


def test_rejects_repository_without_agents(tmp_path: Path) -> None:
    assert any("no agent files" in error for error in validate(tmp_path))


def write_skill(root: Path, description: str, tiers: list[str]) -> None:
    skill = root / "skills" / "model-router"
    skill.mkdir(parents=True)
    frontmatter = ["---", "name: model-router", f"description: {description}", "---"]
    (skill / "SKILL.md").write_text(
        "\n".join([*frontmatter, "Body."]), encoding="utf-8"
    )
    rows = [f"| task {index} | {tier} | check |" for index, tier in enumerate(tiers)]
    table = ["| Task | Tier | Check |", "|---|---|---|", *rows]
    (skill / "routing.md").write_text("\n".join(table), encoding="utf-8")


def test_accepts_tiers_naming_agents_or_main(tmp_path: Path) -> None:
    write_agent(tmp_path, "a", valid_fields("a"))
    write_skill(tmp_path, "Routes work.", ["a", "main"])
    assert validate(tmp_path) == []


def test_rejects_tier_naming_unknown_agent(tmp_path: Path) -> None:
    write_agent(tmp_path, "a", valid_fields("a"))
    write_skill(tmp_path, "Routes work.", ["a", "router-ghost"])
    errors = validate(tmp_path)
    assert len(errors) == 1
    assert "unknown tier 'router-ghost'" in errors[0]


def test_rejects_routing_file_without_table(tmp_path: Path) -> None:
    write_agent(tmp_path, "a", valid_fields("a"))
    write_skill(tmp_path, "Routes work.", [])
    (tmp_path / "skills" / "model-router" / "routing.md").write_text(
        "No table.", encoding="utf-8"
    )
    assert any("no routing rows" in error for error in validate(tmp_path))


def test_rejects_over_long_skill_description(tmp_path: Path) -> None:
    write_agent(tmp_path, "a", valid_fields("a"))
    write_skill(tmp_path, "x" * 1537, ["a"])
    assert any("description is 1537 characters" in e for e in validate(tmp_path))
