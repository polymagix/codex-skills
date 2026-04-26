---
name: skill-validator
description: Use when the user asks to validate, check, QA, smoke-test, or prepare a Codex skill, plugin, marketplace, or skill repository before use or publishing. Runs the bundled validator script, detects supported Python environment managers, and reports actionable validation results.
---

# Skill Validator

## Overview

Validate Codex skill directories and plugin repositories with the bundled validator:

```bash
~/.codex/skills/skill-validator/scripts/validate-codex-skill <skill-dir>
~/.codex/skills/skill-validator/scripts/validate-codex-skill --repo <repo-dir>
```

Use this skill for user-level, repo-hosted, or downloaded Codex skills before relying on them or publishing them. Use `--repo` when validating a GitHub-ready repository that contains plugins, marketplaces, or multiple skills.

## Workflow

1. Identify whether the target is a skill directory or repository.
2. If the user gives a skill name, first try `~/.codex/skills/<name>`.
3. Run `~/.codex/skills/skill-validator/scripts/validate-codex-skill <skill-dir>` for one or more skill directories.
4. Run `~/.codex/skills/skill-validator/scripts/validate-codex-skill --repo <repo-dir>` for plugin repositories.
5. Use `--json` when the caller needs machine-readable output.
6. Use `--strict` when warnings should fail validation.
7. If validation passes, report the target is valid.
8. If validation fails, summarize actionable errors and file paths.

## Environment Manager Detection

The bundled script detects supported Python environment managers in this order:

1. `uv` - preferred; provides `PyYAML` without mutating the active Python environment.
2. `mise` - uses the active mise Python; `PyYAML` must already be installed there.
3. `asdf` - uses the active `python3` shim; `PyYAML` must already be installed there.
4. `pyenv` - uses the active `python3` shim; `PyYAML` must already be installed there.

If none are found, it exits with a message recommending `uv` plus alternatives.

## Current Validation Coverage

The bundled validator checks:

- `SKILL.md` presence
- parseable YAML frontmatter
- required skill metadata such as `name` and `description`
- skill and plugin name safety and hyphen-case style
- skill name versus directory name warnings
- parseable `agents/openai.yaml`, when present
- `agents/openai.yaml` interface field types
- `default_prompt` mention of `$skill-name` warnings
- unresolved placeholder warnings
- local path references in skill Markdown for `scripts/`, `assets/`, `references/`, and `agents/`
- executable bit warnings for files under `scripts/`
- shell syntax via `bash -n`
- Python syntax via in-memory compilation
- plugin `.codex-plugin/plugin.json` structure in `--repo` mode
- plugin `skills` path existence in `--repo` mode
- `.agents/plugins/marketplace.json` structure in `--repo` mode
- local marketplace source path existence in `--repo` mode
- marketplace policy enum values in `--repo` mode

## Commands

Validate a user skill by name:

```bash
~/.codex/skills/skill-validator/scripts/validate-codex-skill ~/.codex/skills/skill-name
```

Validate an explicit skill directory:

```bash
~/.codex/skills/skill-validator/scripts/validate-codex-skill /path/to/skill-dir
```

Validate a plugin repository:

```bash
~/.codex/skills/skill-validator/scripts/validate-codex-skill --repo /path/to/repo
```

Emit machine-readable output:

```bash
~/.codex/skills/skill-validator/scripts/validate-codex-skill --json --repo /path/to/repo
```

Treat warnings as failures:

```bash
~/.codex/skills/skill-validator/scripts/validate-codex-skill --strict /path/to/skill-dir
```

## Guardrails

- Do not install dependencies ad hoc with global `pip` when `uv` is available.
- Do not modify a skill during validation unless the user asks for fixes.
- Do not print secrets if validation output or files expose environment-specific data.
- If the bundled validator is missing, report that the skill installation is incomplete.
