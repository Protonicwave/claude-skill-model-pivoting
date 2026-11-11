import json
from pathlib import Path
from typing import Any

import pytest
from install import PYTHON_PATH, install, run

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL = Path("skills") / "model-router"
AGENT_NAMES = ["router-expert.md", "router-scout.md", "router-worker.md"]
SKILL_FILES = [
    "SKILL.md",
    "hook_input.py",
    "result_hook.py",
    "router_log.py",
    "routing.md",
    "spawn_hook.py",
]


def test_dry_run_lists_files_and_writes_nothing(tmp_path: Path) -> None:
    report = install(REPO_ROOT, tmp_path, dry_run=True)
    assert sorted(path.name for path in report.copied) == sorted(
        AGENT_NAMES + SKILL_FILES
    )
    assert list(tmp_path.iterdir()) == []


def test_copies_agents_and_skill_into_target(tmp_path: Path) -> None:
    install(REPO_ROOT, tmp_path, dry_run=False)
    relatives = [Path("agents") / name for name in AGENT_NAMES]
    relatives += [SKILL / name for name in SKILL_FILES]
    for relative in relatives:
        assert (tmp_path / relative).read_bytes() == (REPO_ROOT / relative).read_bytes()


def test_overwrites_existing_copy(tmp_path: Path) -> None:
    stale = tmp_path / "agents" / "router-scout.md"
    stale.parent.mkdir(parents=True)
    stale.write_text("stale", encoding="utf-8")
    install(REPO_ROOT, tmp_path, dry_run=False)
    assert stale.read_bytes() == (REPO_ROOT / "agents" / "router-scout.md").read_bytes()


def test_leaves_unrelated_target_files_alone(tmp_path: Path) -> None:
    other = tmp_path / "agents" / "mine.md"
    other.parent.mkdir(parents=True)
    other.write_text("keep", encoding="utf-8")
    install(REPO_ROOT, tmp_path, dry_run=False)
    assert other.read_text(encoding="utf-8") == "keep"


def test_removes_router_files_the_repository_no_longer_has(tmp_path: Path) -> None:
    old_agent = tmp_path / "agents" / "router-retired.md"
    old_skill_file = tmp_path / SKILL / "old.md"
    for path in (old_agent, old_skill_file):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("old", encoding="utf-8")
    report = install(REPO_ROOT, tmp_path, dry_run=False)
    assert not old_agent.exists()
    assert not old_skill_file.exists()
    assert sorted(report.removed) == sorted([old_agent, old_skill_file])


def test_skips_stray_files_in_the_skill_directory(tmp_path: Path) -> None:
    source = tmp_path / "source"
    (source / "agents").mkdir(parents=True)
    (source / "agents" / "router-a.md").write_text("a", encoding="utf-8")
    (source / SKILL).mkdir(parents=True)
    for name in ("SKILL.md", "SKILL.md~", "notes.txt"):
        (source / SKILL / name).write_text(name, encoding="utf-8")
    report = install(source, tmp_path / "target", dry_run=True)
    assert sorted(path.name for path in report.copied) == ["SKILL.md", "router-a.md"]


def test_refuses_to_install_when_validation_fails(tmp_path: Path) -> None:
    source = tmp_path / "source"
    (source / "agents").mkdir(parents=True)
    target = tmp_path / "target"
    assert run(source, target, dry_run=False) == 1
    assert not target.exists()


def test_run_installs_valid_repository(tmp_path: Path) -> None:
    assert run(REPO_ROOT, tmp_path, dry_run=False) == 0
    assert (tmp_path / SKILL / "SKILL.md").is_file()


FOREIGN_SESSION_HOOK = {
    "hooks": [{"type": "command", "command": "python other.py", "timeout": 5}]
}
FOREIGN_BASH_HOOK = {
    "matcher": "Bash",
    "hooks": [{"type": "command", "command": "guard.sh"}],
}

# Shapes Claude Code would reject; the installer keeps them rather than judge.
ODD_GROUPS = [
    {"matcher": "Odd", "hooks": "not a list"},
    {"matcher": "Odder", "hooks": ["not an object"]},
]


def write_settings(target: Path, document: object) -> Path:
    path = target / "settings.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


# Any: parsed JSON whose shape each test asserts as it reads it.
def read_settings(target: Path) -> dict[str, Any]:
    document = json.loads((target / "settings.json").read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    return document


def router_commands(document: dict[str, Any]) -> dict[tuple[str, str | None], str]:
    commands = {}
    for event, groups in document["hooks"].items():
        for group in groups:
            hooks = [hook for hook in group["hooks"] if isinstance(hook, dict)]
            for hook in hooks:
                if "/skills/model-router/" in hook["command"]:
                    commands[(event, group.get("matcher"))] = hook["command"]
    return commands


def test_registers_router_hooks_in_new_settings(tmp_path: Path) -> None:
    assert run(REPO_ROOT, tmp_path, dry_run=False) == 0
    commands = router_commands(read_settings(tmp_path))
    assert set(commands) == {("PreToolUse", "Agent"), ("SubagentStop", None)}
    for command in commands.values():
        python, script = command.split('" "')
        assert python == f'"{PYTHON_PATH}'
        assert Path(script.rstrip('"')).is_file()


@pytest.mark.parametrize("text", ["", "  \n"])
def test_empty_settings_file_counts_as_empty_object(tmp_path: Path, text: str) -> None:
    (tmp_path / "settings.json").write_text(text, encoding="utf-8")
    assert run(REPO_ROOT, tmp_path, dry_run=False) == 0
    assert len(router_commands(read_settings(tmp_path))) == 2


def test_keeps_foreign_settings_and_hooks(tmp_path: Path) -> None:
    write_settings(
        tmp_path,
        {
            "model": "opus",
            "hooks": {
                "SessionStart": [FOREIGN_SESSION_HOOK],
                "PreToolUse": [FOREIGN_BASH_HOOK, *ODD_GROUPS],
                "Stop": [],
            },
            "theme": "dark",
        },
    )
    assert run(REPO_ROOT, tmp_path, dry_run=False) == 0
    document = read_settings(tmp_path)
    assert list(document) == ["model", "hooks", "theme"]
    assert document["hooks"]["SessionStart"] == [FOREIGN_SESSION_HOOK]
    assert document["hooks"]["PreToolUse"][:3] == [FOREIGN_BASH_HOOK, *ODD_GROUPS]
    assert document["hooks"]["Stop"] == []
    assert len(router_commands(document)) == 2


def test_replaces_router_hooks_from_an_earlier_install(tmp_path: Path) -> None:
    old_hook = {"type": "command", "command": "py /old/skills/model-router/gone.py"}
    shared_group = {"matcher": "Bash", "hooks": [old_hook, *FOREIGN_BASH_HOOK["hooks"]]}
    write_settings(
        tmp_path,
        {
            "hooks": {
                "PreToolUse": [shared_group],
                "Notification": [{"hooks": [old_hook]}],
            }
        },
    )
    assert run(REPO_ROOT, tmp_path, dry_run=False) == 0
    hooks = read_settings(tmp_path)["hooks"]
    assert "Notification" not in hooks
    assert hooks["PreToolUse"][0] == FOREIGN_BASH_HOOK
    assert "/old/" not in json.dumps(hooks)
    assert len(router_commands({"hooks": hooks})) == 2


def test_second_install_leaves_settings_unchanged(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_settings(tmp_path, {"hooks": {"SessionStart": [FOREIGN_SESSION_HOOK]}})
    run(REPO_ROOT, tmp_path, dry_run=False)
    first = (tmp_path / "settings.json").read_bytes()
    capsys.readouterr()
    assert run(REPO_ROOT, tmp_path, dry_run=False) == 0
    assert (tmp_path / "settings.json").read_bytes() == first
    assert f"Unchanged {tmp_path / 'settings.json'}" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("{not json", "not valid JSON"),
        ("[]", "expected a JSON object"),
        ('{"hooks": []}', '"hooks"'),
        ('{"hooks": {"PreToolUse": {}}}', '"hooks.PreToolUse"'),
        ('{"hooks": {"PreToolUse": ["x"]}}', '"hooks.PreToolUse"'),
    ],
)
def test_refuses_unreadable_settings_before_copying(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], text: str, message: str
) -> None:
    (tmp_path / "settings.json").write_text(text, encoding="utf-8")
    assert run(REPO_ROOT, tmp_path, dry_run=False) == 1
    assert message in capsys.readouterr().out
    assert sorted(path.name for path in tmp_path.iterdir()) == ["settings.json"]
    assert (tmp_path / "settings.json").read_text(encoding="utf-8") == text


def test_dry_run_reports_settings_change_and_writes_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = write_settings(tmp_path, {"hooks": {}})
    assert run(REPO_ROOT, tmp_path, dry_run=True) == 0
    output = capsys.readouterr().out
    assert f"Would update {path}" in output
    assert f"Would copy {tmp_path / SKILL / 'SKILL.md'}" in output
    assert path.read_text(encoding="utf-8") == '{"hooks": {}}'
    assert sorted(p.name for p in tmp_path.iterdir()) == ["settings.json"]


def test_run_reports_copied_removed_and_updated_files(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    retired = tmp_path / SKILL / "retired.py"
    retired.parent.mkdir(parents=True)
    retired.write_text("old", encoding="utf-8")
    assert run(REPO_ROOT, tmp_path, dry_run=False) == 0
    output = capsys.readouterr().out
    assert f"Copied {tmp_path / SKILL / 'spawn_hook.py'}" in output
    assert f"Removed {retired}" in output
    assert f"Updated {tmp_path / 'settings.json'}" in output


def test_reads_settings_written_with_a_byte_order_mark(tmp_path: Path) -> None:
    document = {"hooks": {"SessionStart": [FOREIGN_SESSION_HOOK]}}
    (tmp_path / "settings.json").write_text(json.dumps(document), encoding="utf-8-sig")
    assert run(REPO_ROOT, tmp_path, dry_run=False) == 0
    assert read_settings(tmp_path)["hooks"]["SessionStart"] == [FOREIGN_SESSION_HOOK]
