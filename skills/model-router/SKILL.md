---
name: model-router
description: Decides which model and effort level runs each step of a task, by keeping the step in the main chat or handing it to the router-scout, router-worker or router-expert subagent. Use whenever a task has a step worth delegating (searching, reading logs, running checks, routine edits with tests, review, hard debugging), when another skill's process reaches such a step, and when the user mentions lean mode, token use or routing.
---

# Model router

The aim is to spend fewer tokens with no loss of quality. Two facts drive every rule here:

- The main chat re-reads its whole history every turn, and the prompt cache makes that cheap. Each model has its own cache, so a model switch makes the next turn pay full price for the whole history. An effort change keeps the cache.
- A subagent starts with an empty context and its own cache. A short brief to it costs little and never disturbs the main chat's cache.

So the main chat keeps one model for the whole session, and work moves between models by delegation, never by `/model`. If the user wants to change the main model anyway, tell them to run `/compact` first so the new model reads a summary instead of the history.

## Decide

Find the step's row in `routing.md`: the active skill's table if it has one, otherwise the general table. Read the `Tier` column, or `Lean tier` while lean mode is on. Delegate only when all three hold:

1. The tier is a subagent, not `main`.
2. The row's check can confirm the result without trusting the subagent.
3. The work is much larger than the brief. A step the main chat would finish in under five tool calls stays in the main chat whatever the table says.

When no row fits, keep the step in the main chat. When unsure between two tiers, pick the higher one: overpaying costs the price difference, while a failed cheap attempt costs both runs.

Never run two subagents that edit the same files at once. Commits, pushes, branch changes and plan updates stay in the main chat.

## Brief

Every brief uses this template, with no section left out:

```
Goal: one sentence on what is true when the step is done.
Task type: the first column of the routing.md row used.
Skill: the skill to load first, or "none".
Read: the files and line ranges to read. Point at files rather than summarising them.
Change: what may be edited, or "nothing".
Done when: the exact check command, or the exact thing to find.
Constraints: rules that apply beyond the skill, such as files not to touch.
Ruled out: what has already been tried or excluded, with the evidence.
```

Leave out the main chat's reasoning about why the code is the way it is, especially for a review. A reviewer who knows the reasons accepts the code.

## Accept or escalate

Each subagent replies with `Result`, `Evidence` and `Notes`.

- Accept `done` only when Evidence shows the check passing. When the check is one cheap command, rerun it in the main chat before accepting.
- On `failed`, `blocked`, or `done` without evidence, escalate once to the next tier: router-scout to router-worker, router-worker to router-expert. The new brief includes the previous Evidence under "Ruled out".
- When the escalated attempt also fails, or router-expert fails, stop routing. Take the step into the main chat, run `git status` and `git diff` to see what the attempts left behind, and tell the user what was tried. Revert a failed attempt's changes only with the user's agreement.

Never escalate a step more than once.

## Log

A hook logs every routed step, including each escalation, when the subagent stops. It takes the task type from the brief's `Task type:` line, the tier from the agent's name and the result from the reply's `Result:` line. A brief without `Task type:` is not logged, so never leave the line out. Steps kept in the main chat are not logged.

When the user asks how routing is going or where their tokens went, run `python "<this skill's directory>/usage_report.py"`, adding `--since YYYY-MM-DD` for a recent window. It prints list-price spend per source and model from the transcripts, unrouted spawns, main-chat prompt size, cache misses, five-hour blocks, first-turn context per agent type, and the routed results. Point out any task type that fails on its tier more than about one time in four: that row should move up a tier in `routing.md`. Point out unrouted spawns that cost more than the router tiers together: that work should go through a tier.

## Other skills

A domain skill (engineer, writing, latex, web-ui-craft or any other) decides how the work is done. This skill decides only which model does each step. Name the domain skill in the brief's Skill line so the subagent loads and follows it.

## Lean mode

Lean mode is on from when the user asks for it until they end it. When it starts, tell them to run `/effort medium`, because the model cannot change its own effort, and say in one line that lean mode is on. An effort change keeps the cache. When the user ends it, tell them to run `/effort` with their usual level. If you cannot tell whether lean mode is on, for example after `/compact`, ask.
