from pathlib import Path

from install import install

REPO_ROOT = Path(__file__).resolve().parent.parent
AGENT_NAMES = ["router-expert.md", "router-scout.md", "router-worker.md"]
SKILL_FILES = ["SKILL.md", "router_log.py", "routing.md"]


def test_dry_run_lists_files_and_writes_nothing(tmp_path: Path) -> None:
    copied = install(REPO_ROOT, tmp_path, dry_run=True)
    assert sorted(path.name for path in copied) == sorted(AGENT_NAMES + SKILL_FILES)
    assert list(tmp_path.iterdir()) == []


def test_copies_agents_into_target(tmp_path: Path) -> None:
    install(REPO_ROOT, tmp_path, dry_run=False)
    for name in AGENT_NAMES:
        source = (REPO_ROOT / "agents" / name).read_bytes()
        assert (tmp_path / "agents" / name).read_bytes() == source


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


def test_copies_skill_into_target(tmp_path: Path) -> None:
    install(REPO_ROOT, tmp_path, dry_run=False)
    relative = Path("skills") / "model-router"
    for name in SKILL_FILES:
        source = (REPO_ROOT / relative / name).read_bytes()
        assert (tmp_path / relative / name).read_bytes() == source
