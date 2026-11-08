# model-router

A Claude Code skill that sends delegable work to subagents on fixed models and effort levels, so the main chat keeps one model and its prompt cache stays warm.

- `agents/`: the three tiers. `router-scout` (haiku, low effort, no edits), `router-worker` (sonnet, medium), `router-expert` (opus, high).
- `skills/model-router/SKILL.md`: when to delegate, the brief template, how to accept or escalate a result, and lean mode.
- `skills/model-router/routing.md`: which tier handles each task type, with splits for the engineer, writing, latex and web-ui-craft skills.
- `skills/model-router/router_log.py`: records each routed step and summarises results per task type and tier.

## Install

Requires Python 3.12 or later and no third-party packages.

```
python scripts/install.py --dry-run
python scripts/install.py
```

The installer validates every file first, then copies the agents to `~/.claude/agents` and the skill to `~/.claude/skills/model-router`. Pass `--target DIR` to install elsewhere. Files in the target that this repository does not own are left alone.

## Use

- Lean mode: ask for it, then run `/effort medium`. Run `/effort` with your usual level to end it.
- Routing results: `python ~/.claude/skills/model-router/router_log.py summary`. A task type that fails on its tier more than about one time in four should move up a tier in `routing.md`; reinstall afterwards.
- To change a tier's model or effort, edit the `model` or `effort` line in its file under `agents/` and reinstall.

## Test

```
python -m pytest
python -m ruff check .
python -m ruff format --check .
python -m mypy
```
