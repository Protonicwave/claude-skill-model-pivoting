from pathlib import Path

from install import install, run

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL = Path("skills") / "model-router"
AGENT_NAMES = ["router-expert.md", "router-scout.md", "router-worker.md"]
SKILL_FILES = ["SKILL.md", "router_log.py", "routing.md"]


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
