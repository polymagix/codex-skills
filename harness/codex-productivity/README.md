# Codex Productivity Harness

This harness makes Codex behave closer to a Claude Code-style trusted local coding agent for Polymagix work, while keeping the main sandbox on.

It is not `danger-full-access`. The goal is to remove repetitive friction for routine trusted work without approving destructive commands by default.

## What It Changes

The launcher starts Codex with:

- `--sandbox workspace-write`
- `--ask-for-approval on-request`
- writable roots for Polymagix workspaces
- writable roots for user-level Codex skills, wrappers, and cache
- `GH_PROMPT_DISABLED=1`
- `GH_TOKEN` populated from `gh auth token` when available

The rules file allows common low-risk command prefixes used during normal engineering work:

- GitHub CLI read/write operations such as `gh api`, `gh repo create`, and PR inspection/commenting
- Git network operations such as `git fetch`, `git push`, and `git ls-remote`
- `uv run` and `uv sync`
- repository Markdown lint commands
- local skill validation wrappers

The rules intentionally do not allow broad shells, arbitrary Python execution, `rm`, `git reset --hard`, or other destructive operations.

## Files

```text
harness/codex-productivity/
  bin/codex-polymagix
  rules/productivity.rules
  install.sh
  README.md
```

## Install

From this repository:

```bash
harness/codex-productivity/install.sh
```

This installs:

- `~/.local/bin/codex-polymagix`
- a managed rules block in `~/.codex/rules/default.rules`

## Use

Start Codex for trusted Polymagix work:

```bash
codex-polymagix -C /home/peter/Work/polymagix/codex-skills
```

Add temporary writable roots when needed:

```bash
CODEX_EXTRA_ADD_DIRS=/some/other/workspace codex-polymagix -C /home/peter/Work/polymagix/codex-skills
```

## Why This Exists

The default Codex sandbox is safer than a fully trusted local agent, but it can be fatiguing for day-to-day repository maintenance:

- adjacent worktrees are not writable by default
- user-level Codex skill edits require approval
- `uv` and `gh` need network escalation
- keyring-backed GitHub auth may not be reachable from the sandbox

This harness makes those expectations explicit so future sessions start with the right operating contract.

## Security Boundary

Use this launcher only for repositories and directories you already trust. For unknown code, use the default Codex launcher or a stricter sandbox.
