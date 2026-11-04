# AGENTS.md

This file provides guidance to AI coding agents (Claude Code, Cursor, Copilot, Antigravity, etc.) when working with code in this repository.

> **Scope:** This file configures agents working on the `an-front` repository (Next.js + TypeScript front-end). The reusable assets referenced below live in `/home/mr/.agents/skills/<skill-name>/SKILL.md` and are shared globally; this file only wires those skills to the intents that occur in this repo. It is not a copy of the skills themselves.

## Skill-Driven Execution Model

Agents work in a **skill-driven model** powered by the `skill` tool and the global skills directory at `/home/mr/.agents/skills`.

### Core Rules

- If a task matches a skill, you MUST invoke it
- Skills are located at `/home/mr/.agents/skills/<skill-name>/SKILL.md`
- Never implement directly if a skill applies
- Always follow the skill instructions exactly (do not partially apply them)
- For destructive/safety-relevant actions (migrations, experiments, gateway changes) skills may require explicit consent; honor it

## Intent → Skill Mapping

The agent should automatically map user intent to the most relevant skill(s):

### Explore in the codebase

- Use the codebase knowledge graph for structural code queries,
  Who calls X?/
  What does X call? /
  Full call context /
  Find by name pattern /
  Dead code /
  Cross-service edges /
  Impact of local changes /
  Risk-classified trace /
  Text search / → `codebase-memory`

### Discovery & Investigation

- dont use `grep` or `ls` and other terminal command
- "Where is X / what calls Y / find this" → `caveman-explore` (cold-start, broad localization)
- Always use prefix `linux terminal` and `bach` commands with `rtk` → `shell-commands` (prefix with `rtk`)
- Unknown cause, intermittent bug, perf regression, evidence-ranked diagnosis → `investigate-first`
- "Is there a skill for X / how do I do X" → `find-skills`
- Understand the skill catalog / what modes exist → `caveman-help`

### Building Features

- New behavior / product slice / integration (avoid overbuilding) → `lean-build`
- well-scoped feature where the simplest working solution wins → `ponytail`

### Fixing Bugs

- Small bug / narrow behavior change (narrowest layer) → `surgical-patch`
- Ambiguous or root-cause-unknown failure → `investigate-first` first, then `surgical-patch`

### Refactoring

- Restructure / extract / move ownership while preserving behavior → `safe-refactor`

### Migrations

- Schema / data / API / protocol / config / dependency changes needing rollback → `migration`

### Code Review

- Review a diff / PR → `caveman-review` (terse) or mainstream review flow
- Review a diff for bugs → `cavecrew` (reviewer subagent)
- Code Review and Quality and Security → `code-review-and-quality`

### Committing

- "Write a commit / commit message" → `caveman-commit`

### Communication Style

- "Be brief / terse / caveman" → `caveman` (+ `caveman-compress` for memory files)
- Delegate to compressed-output subagents → `cavecrew`

### Validation & Delivery

- Prove work meets acceptance without scope creep → `verify-and-stop`

### Caveman Cloud (LLM spend observability)

- Set up LLM spend tracking → `caveman-setup`
- Label LLM workflows → `caveman-discover`
- Review Caveman evidence (costs/score/traces) → `caveman-evidence-review`
- Manage experiments → `caveman-manage`
- Evaluate an optimization observation → `caveman-optimize`
- Lower agent token cost → `caveman-learn`
- Show session token usage → `caveman-stats`

## Lifecycle Mapping (Implicit)

The agent must internally follow this lifecycle on feature tasks, invoking skills at each gate:

| Phase                                   | Skill(s)                                                     |
| --------------------------------------- | ------------------------------------------------------------ |
| DEFINE — confirm the work and scope     | `lean-build` / `ponytail`                                    |
| INVESTIGATE — understand before editing | `investigate-first` / `caveman-explore`                      |
| BUILD — implement narrow outcome        | `lean-build`, `surgical-patch`, `safe-refactor`, `migration` |
| VERIFY — prove acceptance               | `verify-and-stop`, `surgical-patch` (regression proof)       |
| REVIEW — check the diff                 | `caveman-review` / `cavecrew` (reviewer)                     |
| COMMIT — write the message              | `caveman-commit`                                             |

## Execution Model

For every request:

1. Determine if any skill applies (even a small probability)
2. Invoke the appropriate skill using the `skill` tool
3. Follow the skill workflow strictly
4. Only proceed to implementation after required investigation/spec/acceptance steps are complete
5. For safety-relevant skills (migration, caveman-manage, caveman-optimize, caveman-setup), present the plan and respect explicit user consent before mutating

## Anti-Rationalization

The following thoughts are incorrect and must be ignored:

- "This is too small for a skill"
- "I can just quickly implement this"
- "I'll gather context first"

Correct behavior:

- Always check for and use skills first

This keeps agent behavior consistent and enforces workflow discipline (investigate → build → verify → review → commit).
