---
name: skill-validator
description: Use when the user asks to validate, check, QA, smoke-test, or prepare a Codex skill directory before use or publishing. Runs the bundled validator script, detects supported Python environment managers, and reports actionable validation results.
---

# Skill Validator

## Overview

Validate Codex skill directories with the bundled validator:

```bash
~/.codex/skills/skill-validator/scripts/validate-codex-skill <skill-dir>
```

Use this skill for user-level, repo-hosted, or downloaded Codex skills before relying on them or publishing them.

## Workflow

1. Identify the skill directory. If the user gives a skill name, first try `~/.codex/skills/<name>`.
2. Confirm the directory exists and contains `SKILL.md`.
3. Run `~/.codex/skills/skill-validator/scripts/validate-codex-skill <skill-dir>`.
4. If validation passes, report the skill is valid.
5. If validation fails, summarize actionable errors and file paths.

## Environment Manager Detection

The bundled script detects supported Python environment managers in this order:

1. `uv` - preferred; provides `PyYAML` without mutating the active Python environment.
2. `mise` - uses the active mise Python; `PyYAML` must already be installed there.
3. `asdf` - uses the active `python3` shim; `PyYAML` must already be installed there.
4. `pyenv` - uses the active `python3` shim; `PyYAML` must already be installed there.

If none are found, it exits with a message recommending `uv` plus alternatives.

## Current Validation Coverage

The bundled validator checks core skill structure and metadata, including:

- `SKILL.md` presence
- parseable YAML frontmatter
- required skill metadata such as `name` and `description`
- skill name versus directory name warning
- parseable `agents/openai.yaml`, when present
- `agents/openai.yaml` interface field types
- `default_prompt` mention of `$skill-name` warning
- TODO placeholder warnings

## Commands

Validate a user skill by name:

```bash
~/.codex/skills/skill-validator/scripts/validate-codex-skill ~/.codex/skills/skill-name
```

Validate an explicit skill directory:

```bash
~/.codex/skills/skill-validator/scripts/validate-codex-skill /path/to/skill-dir
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
