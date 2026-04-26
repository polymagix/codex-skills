#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys
from typing import Any

import yaml

FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)
PLACEHOLDER_RE = re.compile(r"(?:^|[\s\[(<])(?:TODO|FIXME|TBD)(?:\s*[:\]>)\-]|\s*$)", re.IGNORECASE)


def load_yaml_file(path: Path) -> tuple[Any | None, str | None]:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")), None
    except Exception as exc:  # noqa: BLE001 - validator should report parse failures
        return None, f"{path}: could not parse YAML: {exc}"


def validate_skill(skill_dir: Path, strict: bool) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    if not skill_dir.exists():
        return [f"{skill_dir}: directory does not exist"], warnings
    if not skill_dir.is_dir():
        return [f"{skill_dir}: not a directory"], warnings

    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        return [f"{skill_dir}: missing SKILL.md"], warnings

    text = skill_md.read_text(encoding="utf-8")
    match = FRONTMATTER_RE.match(text)
    if not match:
        errors.append(f"{skill_md}: missing YAML frontmatter bounded by ---")
        metadata: dict[str, Any] = {}
    else:
        try:
            parsed = yaml.safe_load(match.group(1)) or {}
            if not isinstance(parsed, dict):
                errors.append(f"{skill_md}: frontmatter must be a mapping")
                metadata = {}
            else:
                metadata = parsed
        except Exception as exc:  # noqa: BLE001 - validator should report parse failures
            errors.append(f"{skill_md}: could not parse frontmatter YAML: {exc}")
            metadata = {}

    name = metadata.get("name")
    description = metadata.get("description")

    if not isinstance(name, str) or not name.strip():
        errors.append(f"{skill_md}: frontmatter field 'name' must be a non-empty string")
    elif name != skill_dir.name:
        warnings.append(f"{skill_md}: skill name '{name}' differs from directory name '{skill_dir.name}'")

    if not isinstance(description, str) or not description.strip():
        errors.append(f"{skill_md}: frontmatter field 'description' must be a non-empty string")
    elif PLACEHOLDER_RE.search(description):
        errors.append(f"{skill_md}: description still contains unresolved placeholder text")

    placeholder_lines = [
        str(index)
        for index, line in enumerate(text.splitlines(), start=1)
        if PLACEHOLDER_RE.search(line)
    ]
    if placeholder_lines:
        warnings.append(f"{skill_md}: file contains unresolved placeholders on lines {', '.join(placeholder_lines)}")

    agents_yaml = skill_dir / "agents" / "openai.yaml"
    if agents_yaml.exists():
        data, err = load_yaml_file(agents_yaml)
        if err:
            errors.append(err)
        elif not isinstance(data, dict):
            errors.append(f"{agents_yaml}: top-level YAML value must be a mapping")
        else:
            interface = data.get("interface")
            if interface is not None and not isinstance(interface, dict):
                errors.append(f"{agents_yaml}: interface must be a mapping")
            elif isinstance(interface, dict):
                for key in ("display_name", "short_description", "default_prompt"):
                    value = interface.get(key)
                    if value is not None and not isinstance(value, str):
                        errors.append(f"{agents_yaml}: interface.{key} must be a string")
                default_prompt = interface.get("default_prompt")
                if isinstance(default_prompt, str) and isinstance(name, str):
                    token = f"${name}"
                    if token not in default_prompt:
                        warnings.append(f"{agents_yaml}: interface.default_prompt should mention {token}")

    if strict and warnings:
        errors.extend(f"strict warning: {warning}" for warning in warnings)
        warnings = []

    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Codex skill directories.")
    parser.add_argument("skill_dirs", nargs="+", type=Path)
    parser.add_argument("--strict", action="store_true", help="treat warnings as errors")
    args = parser.parse_args()

    all_errors: list[str] = []
    all_warnings: list[str] = []

    for skill_dir in args.skill_dirs:
        errors, warnings = validate_skill(skill_dir.expanduser().resolve(), args.strict)
        all_errors.extend(errors)
        all_warnings.extend(warnings)

    if all_errors:
        print("Skill validation failed:", file=sys.stderr)
        for error in all_errors:
            print(f"ERROR: {error}", file=sys.stderr)
        for warning in all_warnings:
            print(f"WARN: {warning}", file=sys.stderr)
        return 1

    if all_warnings:
        print("Skill is valid with warnings:")
        for warning in all_warnings:
            print(f"WARN: {warning}")
    else:
        print("Skill is valid!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
