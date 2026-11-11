# model-router

A Claude Code skill that sends delegable work to subagents on fixed models and effort levels, so the main chat keeps one model and its prompt cache stays warm.

- `agents/`: the three tiers. `router-scout` (haiku, low effort), `router-worker` (sonnet, medium), `router-expert` (opus, high). The scout is told never to edit, but it has Bash, so that rule rests on its instructions rather than its tools.
- `skills/model-router/SKILL.md`: when to delegate, the brief template, how to accept or escalate a result, and lean mode.
- `skills/model-router/routing.md`: which tier handles each task type normally and in lean mode, with tables for the engineer, writing, latex and web-ui-craft skills.
- `skills/model-router/router_log.py`: records routed steps and summarises results per task type and tier.
- `skills/model-router/spawn_hook.py`: a PreToolUse hook that runs a general-purpose subagent spawned without a model on sonnet, instead of the main chat's model. Named agents, forks and explicit models are left alone.
- `skills/model-router/result_hook.py`: a SubagentStop hook that logs each router subagent's step from the brief's `Task type:` line and the reply's `Result:` line.

## Install

Requires Python 3.12 or later and no third-party packages.

```
python scripts/install.py --dry-run
python scripts/install.py
```

The installer validates every file first, then copies the agents to `~/.claude/agents` and the skill to `~/.claude/skills/model-router`. Pass `--target DIR` to install elsewhere. It owns `agents/router-*.md` and the `.md` and `.py` files in `skills/model-router/`, and removes any of those the repository no longer ships. Everything else in the target is left alone.

It also registers the two hooks in `~/.claude/settings.json`, running them with the Python that ran the installer. It owns every hook whose command points into `skills/model-router/` and replaces those on each run; other settings and hooks are kept. If `settings.json` is not valid JSON, nothing is installed and the parse error is printed. The file is rewritten with two-space indentation when the hooks change.

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
