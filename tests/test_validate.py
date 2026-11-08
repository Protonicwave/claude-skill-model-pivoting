from pathlib import Path

import pytest
from validate import read_frontmatter, validate

REPO_ROOT = Path(__file__).resolve().parent.parent
TABLE_HEADER = ["| Task type | Tier | Lean tier | Check |", "|---|---|---|---|"]


def write_agent(root: Path, name: str, fields: dict[str, str]) -> None:
    agents = root / "agents"
    agents.mkdir(parents=True, exist_ok=True)
    lines = ["---", *(f"{key}: {value}" for key, value in fields.items()), "---"]
    (agents / f"{name}.md").write_text("\n".join([*lines, "Body."]), encoding="utf-8")


def valid_fields(name: str) -> dict[str, str]:
    return {
        "name": name,
        "description": "Does a thing.",
        "model": "haiku",
        "effort": "low",
    }


def write_skill(root: Path, description: str, rows: list[str]) -> None:
    skill = root / "skills" / "model-router"
    skill.mkdir(parents=True, exist_ok=True)
    frontmatter = ["---", "name: model-router", f"description: {description}", "---"]
    (skill / "SKILL.md").write_text(
        "\n".join([*frontmatter, "Body."]), encoding="utf-8"
    )
    (skill / "routing.md").write_text(
        "\n".join([*TABLE_HEADER, *rows]), encoding="utf-8"
    )


def write_repository(root: Path, rows: list[str] | None = None) -> None:
    write_agent(root, "a", valid_fields("a"))
    write_skill(root, "Routes work.", rows or ["| search | a | a | check |"])


def test_accepts_repository() -> None:
    assert validate(REPO_ROOT) == []


def test_accepts_minimal_repository(tmp_path: Path) -> None:
    write_repository(tmp_path)
    assert validate(tmp_path) == []


def test_accepts_full_model_id(tmp_path: Path) -> None:
    write_repository(tmp_path)
    write_agent(tmp_path, "a", {**valid_fields("a"), "model": "claude-opus-5-5"})
    assert validate(tmp_path) == []


def test_reads_quoted_values() -> None:
    fields = read_frontmatter("---\nmodel: \"haiku\"\neffort: 'low'\n---\n")
    assert fields == {"model": "haiku", "effort": "low"}


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        ("model", "gpt-5", "unknown model 'gpt-5'"),
        ("effort", "extreme", "unknown effort 'extreme'"),
        ("name", "other", "name 'other' does not match file name 'a'"),
        ("description", ">", "multi-line value for 'description'"),
    ],
)
def test_rejects_bad_agent_value(
    tmp_path: Path, field: str, value: str, expected: str
) -> None:
    write_repository(tmp_path)
    write_agent(tmp_path, "a", {**valid_fields("a"), field: value})
    errors = validate(tmp_path)
    assert len(errors) == 1
    assert expected in errors[0]


def test_rejects_missing_field(tmp_path: Path) -> None:
    write_repository(tmp_path)
    fields = valid_fields("a")
    del fields["effort"]
    write_agent(tmp_path, "a", fields)
    assert any("missing field 'effort'" in error for error in validate(tmp_path))


def test_rejects_agent_without_frontmatter(tmp_path: Path) -> None:
    write_repository(tmp_path)
    (tmp_path / "agents" / "a.md").write_text("No frontmatter.", encoding="utf-8")
    assert any("no frontmatter" in error for error in validate(tmp_path))


def test_rejects_repository_without_agents(tmp_path: Path) -> None:
    write_skill(tmp_path, "Routes work.", ["| search | main | main | check |"])
    assert any("no agent files" in error for error in validate(tmp_path))


@pytest.mark.parametrize("name", ["SKILL.md", "routing.md"])
def test_rejects_missing_skill_file(tmp_path: Path, name: str) -> None:
    write_repository(tmp_path)
    (tmp_path / "skills" / "model-router" / name).unlink()
    errors = validate(tmp_path)
    assert len(errors) == 1
    assert f"{name}: missing" in errors[0]


def test_accepts_main_tier(tmp_path: Path) -> None:
    write_repository(tmp_path, ["| design | main | a | review |"])
    assert validate(tmp_path) == []


@pytest.mark.parametrize(
    ("row", "expected"),
    [
        ("| search | ghost | a | check |", "unknown tier 'ghost'"),
        ("| search | a | ghost | check |", "unknown tier 'ghost'"),
        ("| Find files | a | a | check |", "task type 'Find files' is not"),
        ("| search |", "has 1 cells, expected 4"),
    ],
)
def test_rejects_bad_routing_row(tmp_path: Path, row: str, expected: str) -> None:
    write_repository(tmp_path, [row])
    errors = validate(tmp_path)
    assert len(errors) == 1
    assert expected in errors[0]


def test_rejects_routing_file_without_table(tmp_path: Path) -> None:
    write_repository(tmp_path)
    routing = tmp_path / "skills" / "model-router" / "routing.md"
    routing.write_text("No table.", encoding="utf-8")
    assert any("no routing rows" in error for error in validate(tmp_path))


def test_rejects_over_long_skill_description(tmp_path: Path) -> None:
    write_repository(tmp_path)
    write_skill(tmp_path, "x" * 1537, ["| search | a | a | check |"])
    assert any("description is 1537 characters" in e for e in validate(tmp_path))


def test_unclosed_frontmatter_is_not_frontmatter() -> None:
    assert read_frontmatter("---\nmodel: haiku\n") is None
