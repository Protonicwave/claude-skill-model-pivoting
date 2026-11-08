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
