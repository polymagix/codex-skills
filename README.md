# Polymagix Codex Skills

Reusable Codex skills and plugins maintained by Polymagix.

## Available Plugins

### Skill Validator

`skill-validator` packages a Codex skill that validates skills, plugins, marketplaces, and GitHub-ready Codex skill repositories before use or publishing.

It includes a bundled validator script that detects supported Python environment managers in this order:

1. `uv`
2. `mise`
3. `asdf`
4. `pyenv`

If no supported manager is found, the script exits with an actionable setup message. `uv` is preferred because it can provide `PyYAML` without mutating the active Python environment.

## Validation Coverage

Current coverage includes:

- `SKILL.md` presence and YAML frontmatter parsing
- required skill metadata: `name` and `description`
- skill and plugin naming checks
- optional `agents/openai.yaml` parsing and interface field validation
- unresolved placeholder detection
- local path reference checks for skill files
- script executable bit warnings
- shell syntax checks with `bash -n`
- Python syntax checks without writing bytecode
- plugin `.codex-plugin/plugin.json` validation
- plugin `skills` path validation
- marketplace `.agents/plugins/marketplace.json` validation
- marketplace local source path checks
- marketplace policy enum validation
- `--json` output for agents and CI-style harnesses
- `--strict` mode to treat warnings as failures

## Repository Layout

```text
.agents/plugins/marketplace.json
plugins/skill-validator/
  .codex-plugin/plugin.json
  skills/skill-validator/
    SKILL.md
    agents/openai.yaml
    scripts/validate-codex-skill
    scripts/basic_validate_skill.py
```

## Install In Codex

After this repository is published to GitHub, add it as a plugin marketplace:

```bash
codex plugin marketplace add polymagix/codex-skills --sparse .agents/plugins --sparse plugins/skill-validator
```

Then open the Codex plugin directory, choose `Polymagix Codex Skills`, and install `Skill Validator`.

For direct skill installation during local testing, use `$skill-installer` with the skill path:

```text
$skill-installer install https://github.com/polymagix/codex-skills/tree/main/plugins/skill-validator/skills/skill-validator
```

Restart Codex after installing or changing skills if they do not appear immediately.

## Validate Locally

Validate the whole repository:

```bash
plugins/skill-validator/skills/skill-validator/scripts/validate-codex-skill --repo .
```

Validate a single skill directory:

```bash
plugins/skill-validator/skills/skill-validator/scripts/validate-codex-skill \
  plugins/skill-validator/skills/skill-validator
```

Emit JSON:

```bash
plugins/skill-validator/skills/skill-validator/scripts/validate-codex-skill --json --repo .
```

## License

MIT
