#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
from typing import Any

import yaml

FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)
PLACEHOLDER_RE = re.compile(r"(?:^|[\s\[(<])(?:TODO|FIXME|TBD)(?:\s*[:\]>)-]|\s*$)", re.IGNORECASE)
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")
LOCAL_REF_RE = re.compile(r"`([^`]+)`")
LOCAL_REF_PREFIXES = ("scripts/", "assets/", "references/", "agents/", "./scripts/", "./assets/", "./references/", "./agents/")
PLUGIN_INSTALLATION = {"NOT_AVAILABLE", "AVAILABLE", "INSTALLED_BY_DEFAULT"}
PLUGIN_AUTHENTICATION = {"ON_INSTALL", "ON_USE"}
SKILL_AGENT_INTERFACE_FIELDS = ("display_name", "short_description", "default_prompt")
PLUGIN_REQUIRED_FIELDS = ("name", "version", "description", "repository", "license", "skills")
MARKETPLACE_PLUGIN_REQUIRED_FIELDS = ("name", "source", "policy", "category")


class ValidationReport:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, message: str) -> None:
        self.errors.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)

    def extend(self, other: "ValidationReport") -> None:
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)

    def apply_strict(self) -> None:
        if self.warnings:
            self.errors.extend(f"strict warning: {warning}" for warning in self.warnings)
            self.warnings = []

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": not self.errors,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "errors": self.errors,
            "warnings": self.warnings,
        }


def read_text(path: Path) -> tuple[str | None, str | None]:
    try:
        return path.read_text(encoding="utf-8"), None
    except Exception as exc:  # noqa: BLE001 - validator should report file failures
        return None, f"{path}: could not read file: {exc}"


def load_yaml_file(path: Path) -> tuple[Any | None, str | None]:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")), None
    except Exception as exc:  # noqa: BLE001 - validator should report parse failures
        return None, f"{path}: could not parse YAML: {exc}"


def load_json_file(path: Path) -> tuple[Any | None, str | None]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except Exception as exc:  # noqa: BLE001 - validator should report parse failures
        return None, f"{path}: could not parse JSON: {exc}"


def has_placeholder(value: Any) -> bool:
    if isinstance(value, str):
        return bool(PLACEHOLDER_RE.search(value))
    if isinstance(value, list):
        return any(has_placeholder(item) for item in value)
    if isinstance(value, dict):
        return any(has_placeholder(item) for item in value.values())
    return False


def placeholder_paths(value: Any, prefix: str = "") -> list[str]:
    paths: list[str] = []
    if isinstance(value, str):
        if PLACEHOLDER_RE.search(value):
            paths.append(prefix or "<root>")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            paths.extend(placeholder_paths(item, f"{prefix}[{index}]" if prefix else f"[{index}]"))
    elif isinstance(value, dict):
        for key, item in value.items():
            next_prefix = f"{prefix}.{key}" if prefix else str(key)
            paths.extend(placeholder_paths(item, next_prefix))
    return paths


def validate_name(value: Any, path: Path, field: str, report: ValidationReport, *, warn_style: bool = True) -> str | None:
    if not isinstance(value, str) or not value.strip():
        report.error(f"{path}: field '{field}' must be a non-empty string")
        return None
    name = value.strip()
    if "/" in name or name in {".", ".."}:
        report.error(f"{path}: field '{field}' must be a single path segment")
    elif not NAME_RE.match(name):
        message = f"{path}: field '{field}' should be lowercase hyphen-case"
        if warn_style:
            report.warn(message)
        else:
            report.error(message)
    return name


def validate_skill(skill_dir: Path) -> ValidationReport:
    report = ValidationReport()
    skill_dir = skill_dir.expanduser().resolve()

    if not skill_dir.exists():
        report.error(f"{skill_dir}: directory does not exist")
        return report
    if not skill_dir.is_dir():
        report.error(f"{skill_dir}: not a directory")
        return report

    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        report.error(f"{skill_dir}: missing SKILL.md")
        return report

    text, read_error = read_text(skill_md)
    if read_error:
        report.error(read_error)
        return report
    assert text is not None

    match = FRONTMATTER_RE.match(text)
    if not match:
        report.error(f"{skill_md}: missing YAML frontmatter bounded by ---")
        metadata: dict[str, Any] = {}
    else:
        try:
            parsed = yaml.safe_load(match.group(1)) or {}
            if not isinstance(parsed, dict):
                report.error(f"{skill_md}: frontmatter must be a mapping")
                metadata = {}
            else:
                metadata = parsed
        except Exception as exc:  # noqa: BLE001 - validator should report parse failures
            report.error(f"{skill_md}: could not parse frontmatter YAML: {exc}")
            metadata = {}

    name = validate_name(metadata.get("name"), skill_md, "name", report)
    description = metadata.get("description")

    if name and name != skill_dir.name:
        report.warn(f"{skill_md}: skill name '{name}' differs from directory name '{skill_dir.name}'")

    if not isinstance(description, str) or not description.strip():
        report.error(f"{skill_md}: frontmatter field 'description' must be a non-empty string")
    elif PLACEHOLDER_RE.search(description):
        report.error(f"{skill_md}: description still contains unresolved placeholder text")

    placeholder_lines = [
        str(index)
        for index, line in enumerate(text.splitlines(), start=1)
        if PLACEHOLDER_RE.search(line)
    ]
    if placeholder_lines:
        report.warn(f"{skill_md}: file contains unresolved placeholders on lines {', '.join(placeholder_lines)}")

    validate_skill_agents_yaml(skill_dir, name, report)
    validate_local_references(skill_dir, skill_md, text, report)
    validate_scripts(skill_dir, report)
    return report


def validate_skill_agents_yaml(skill_dir: Path, name: str | None, report: ValidationReport) -> None:
    agents_yaml = skill_dir / "agents" / "openai.yaml"
    if not agents_yaml.exists():
        return

    data, err = load_yaml_file(agents_yaml)
    if err:
        report.error(err)
        return
    if not isinstance(data, dict):
        report.error(f"{agents_yaml}: top-level YAML value must be a mapping")
        return

    interface = data.get("interface")
    if interface is not None and not isinstance(interface, dict):
        report.error(f"{agents_yaml}: interface must be a mapping")
    elif isinstance(interface, dict):
        for key in SKILL_AGENT_INTERFACE_FIELDS:
            value = interface.get(key)
            if value is not None and not isinstance(value, str):
                report.error(f"{agents_yaml}: interface.{key} must be a string")
        default_prompt = interface.get("default_prompt")
        if isinstance(default_prompt, str) and name:
            token = f"${name}"
            if token not in default_prompt:
                report.warn(f"{agents_yaml}: interface.default_prompt should mention {token}")

    placeholder_locations = placeholder_paths(data)
    if placeholder_locations:
        report.warn(f"{agents_yaml}: unresolved placeholders at {', '.join(placeholder_locations)}")


def normalize_reference(raw: str) -> str | None:
    value = raw.strip().split()[0].strip("'\".,:;()[]{}<>")
    if not value or value.startswith(("/", "~", "$", "http://", "https://")):
        return None
    if value.startswith("./"):
        value = value[2:]
    if value.startswith(LOCAL_REF_PREFIXES):
        return value
    return None


def validate_local_references(skill_dir: Path, source_path: Path, text: str, report: ValidationReport) -> None:
    seen: set[str] = set()
    for match in LOCAL_REF_RE.finditer(text):
        reference = normalize_reference(match.group(1))
        if not reference or reference in seen:
            continue
        seen.add(reference)
        if not (skill_dir / reference).exists():
            report.warn(f"{source_path}: referenced local path does not exist: {reference}")


def is_executable(path: Path) -> bool:
    try:
        mode = path.stat().st_mode
    except OSError:
        return False
    return bool(mode & stat.S_IXUSR)


def run_check(command: list[str], path: Path) -> tuple[bool, str]:
    try:
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=20)
    except FileNotFoundError:
        return False, f"required command not found: {command[0]}"
    except subprocess.TimeoutExpired:
        return False, "syntax check timed out"
    if result.returncode == 0:
        return True, ""
    detail = (result.stderr or result.stdout).strip().splitlines()
    suffix = f": {detail[0]}" if detail else ""
    return False, f"{path}: syntax check failed{suffix}"


def validate_python_syntax(path: Path, report: ValidationReport) -> None:
    try:
        source = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        report.error(f"{path}: could not decode Python source: {exc}")
        return
    except OSError as exc:
        report.error(f"{path}: could not read Python source: {exc}")
        return

    try:
        compile(source, str(path), "exec")
    except SyntaxError as exc:
        report.error(f"{path}: Python syntax check failed: {exc.msg} at line {exc.lineno}")


def validate_scripts(skill_dir: Path, report: ValidationReport) -> None:
    scripts_dir = skill_dir / "scripts"
    if not scripts_dir.is_dir():
        return

    scripts = sorted(
        path
        for path in scripts_dir.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    )
    for script in scripts:
        if not is_executable(script):
            report.warn(f"{script}: script is not executable")

        if script.suffix == ".py":
            validate_python_syntax(script, report)
            continue

        first_line = ""
        try:
            with script.open("r", encoding="utf-8") as handle:
                first_line = handle.readline().strip()
        except UnicodeDecodeError:
            continue
        except OSError as exc:
            report.error(f"{script}: could not read script: {exc}")
            continue

        if script.suffix in {".sh", ".bash"} or "bash" in first_line or " sh" in first_line or first_line.endswith("/sh"):
            ok, message = run_check(["bash", "-n", str(script)], script)
            if not ok:
                report.error(message)


def validate_plugin(plugin_dir: Path) -> ValidationReport:
    report = ValidationReport()
    plugin_dir = plugin_dir.expanduser().resolve()

    manifest = plugin_dir / ".codex-plugin" / "plugin.json"
    if not manifest.is_file():
        report.error(f"{plugin_dir}: missing .codex-plugin/plugin.json")
        return report

    data, err = load_json_file(manifest)
    if err:
        report.error(err)
        return report
    if not isinstance(data, dict):
        report.error(f"{manifest}: top-level JSON value must be an object")
        return report

    for field in PLUGIN_REQUIRED_FIELDS:
        if field not in data:
            report.error(f"{manifest}: missing required field '{field}'")

    name = validate_name(data.get("name"), manifest, "name", report)
    if name and name != plugin_dir.name:
        report.warn(f"{manifest}: plugin name '{name}' differs from directory name '{plugin_dir.name}'")

    version = data.get("version")
    if isinstance(version, str) and version.strip() and not VERSION_RE.match(version):
        report.warn(f"{manifest}: version should look like semantic versioning, e.g. 0.1.0")

    skills_path = data.get("skills")
    if skills_path is not None:
        if not isinstance(skills_path, str) or not skills_path.strip():
            report.error(f"{manifest}: skills must be a non-empty string path")
        elif os.path.isabs(skills_path):
            report.error(f"{manifest}: skills path must be relative to plugin root")
        else:
            resolved = (plugin_dir / skills_path).resolve()
            try:
                resolved.relative_to(plugin_dir)
            except ValueError:
                report.error(f"{manifest}: skills path must stay inside the plugin directory")
            if not resolved.exists():
                report.error(f"{manifest}: skills path does not exist: {skills_path}")

    interface = data.get("interface")
    if interface is not None and not isinstance(interface, dict):
        report.error(f"{manifest}: interface must be an object")
    elif isinstance(interface, dict):
        for field in ("displayName", "shortDescription", "developerName", "category"):
            value = interface.get(field)
            if value is not None and not isinstance(value, str):
                report.error(f"{manifest}: interface.{field} must be a string")
        default_prompt = interface.get("defaultPrompt")
        if default_prompt is not None and not (
            isinstance(default_prompt, list) and all(isinstance(item, str) for item in default_prompt)
        ):
            report.error(f"{manifest}: interface.defaultPrompt must be a list of strings")

    placeholder_locations = placeholder_paths(data)
    if placeholder_locations:
        report.warn(f"{manifest}: unresolved placeholders at {', '.join(placeholder_locations)}")

    return report


def validate_marketplace(repo_dir: Path, plugin_dirs: list[Path]) -> ValidationReport:
    report = ValidationReport()
    marketplace = repo_dir / ".agents" / "plugins" / "marketplace.json"
    if not marketplace.exists():
        return report
    if not marketplace.is_file():
        report.error(f"{marketplace}: not a file")
        return report

    data, err = load_json_file(marketplace)
    if err:
        report.error(err)
        return report
    if not isinstance(data, dict):
        report.error(f"{marketplace}: top-level JSON value must be an object")
        return report

    if not isinstance(data.get("name"), str) or not data.get("name", "").strip():
        report.error(f"{marketplace}: field 'name' must be a non-empty string")

    plugins = data.get("plugins")
    if not isinstance(plugins, list):
        report.error(f"{marketplace}: field 'plugins' must be an array")
        return report

    known_plugin_names = {path.name for path in plugin_dirs}
    for index, entry in enumerate(plugins):
        prefix = f"{marketplace}: plugins[{index}]"
        if not isinstance(entry, dict):
            report.error(f"{prefix} must be an object")
            continue
        for field in MARKETPLACE_PLUGIN_REQUIRED_FIELDS:
            if field not in entry:
                report.error(f"{prefix}: missing required field '{field}'")
        name = validate_name(entry.get("name"), marketplace, f"plugins[{index}].name", report)
        if name and known_plugin_names and name not in known_plugin_names:
            report.warn(f"{prefix}: references plugin '{name}' that was not found under plugins/")

        source = entry.get("source")
        if isinstance(source, dict):
            source_kind = source.get("source")
            if not isinstance(source_kind, str) or not source_kind.strip():
                report.error(f"{prefix}: source.source must be a non-empty string")
            source_path = source.get("path")
            if source_kind == "local":
                if not isinstance(source_path, str) or not source_path.strip():
                    report.error(f"{prefix}: local source.path must be a non-empty string")
                elif os.path.isabs(source_path):
                    report.error(f"{prefix}: local source.path must be relative")
                elif not (repo_dir / source_path).resolve().exists():
                    report.error(f"{prefix}: local source.path does not exist: {source_path}")
        elif source is not None:
            report.error(f"{prefix}: source must be an object")

        policy = entry.get("policy")
        if isinstance(policy, dict):
            installation = policy.get("installation")
            authentication = policy.get("authentication")
            if installation not in PLUGIN_INSTALLATION:
                report.error(f"{prefix}: policy.installation must be one of {', '.join(sorted(PLUGIN_INSTALLATION))}")
            if authentication not in PLUGIN_AUTHENTICATION:
                report.error(f"{prefix}: policy.authentication must be one of {', '.join(sorted(PLUGIN_AUTHENTICATION))}")
        elif policy is not None:
            report.error(f"{prefix}: policy must be an object")

    placeholder_locations = placeholder_paths(data)
    if placeholder_locations:
        report.warn(f"{marketplace}: unresolved placeholders at {', '.join(placeholder_locations)}")

    return report


def discover_repo(repo_dir: Path) -> tuple[list[Path], list[Path]]:
    plugin_dirs = sorted(
        path for path in (repo_dir / "plugins").glob("*")
        if path.is_dir() and (path / ".codex-plugin" / "plugin.json").is_file()
    )
    skill_dirs: set[Path] = set()
    for path in (repo_dir / "skills").glob("*"):
        if path.is_dir() and (path / "SKILL.md").is_file():
            skill_dirs.add(path.resolve())
    for plugin in plugin_dirs:
        for path in (plugin / "skills").glob("*"):
            if path.is_dir() and (path / "SKILL.md").is_file():
                skill_dirs.add(path.resolve())
    return plugin_dirs, sorted(skill_dirs)


def validate_repo(repo_dir: Path) -> ValidationReport:
    report = ValidationReport()
    repo_dir = repo_dir.expanduser().resolve()
    if not repo_dir.exists():
        report.error(f"{repo_dir}: repository directory does not exist")
        return report
    if not repo_dir.is_dir():
        report.error(f"{repo_dir}: not a directory")
        return report

    plugin_dirs, skill_dirs = discover_repo(repo_dir)
    if not plugin_dirs and not skill_dirs:
        report.warn(f"{repo_dir}: no Codex plugins or skills were discovered")

    for plugin_dir in plugin_dirs:
        report.extend(validate_plugin(plugin_dir))
    for skill_dir in skill_dirs:
        report.extend(validate_skill(skill_dir))
    report.extend(validate_marketplace(repo_dir, plugin_dirs))
    return report


def print_human(report: ValidationReport, repo_mode: bool) -> None:
    noun = "Repository" if repo_mode else "Skill"
    if report.errors:
        print(f"{noun} validation failed:", file=sys.stderr)
        for error in report.errors:
            print(f"ERROR: {error}", file=sys.stderr)
        for warning in report.warnings:
            print(f"WARN: {warning}", file=sys.stderr)
        return

    if report.warnings:
        print(f"{noun} is valid with warnings:")
        for warning in report.warnings:
            print(f"WARN: {warning}")
    else:
        print(f"{noun} is valid!")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Codex skill and plugin repositories.")
    parser.add_argument("skill_dirs", nargs="*", type=Path, help="skill directory/directories to validate")
    parser.add_argument("--repo", type=Path, help="validate a repository containing Codex plugins and/or skills")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    parser.add_argument("--strict", action="store_true", help="treat warnings as errors")
    args = parser.parse_args()

    if not args.repo and not args.skill_dirs:
        parser.error("provide at least one skill directory or --repo <path>")

    report = ValidationReport()
    repo_mode = bool(args.repo)

    if args.repo:
        report.extend(validate_repo(args.repo))
    for skill_dir in args.skill_dirs:
        report.extend(validate_skill(skill_dir))

    if args.strict:
        report.apply_strict()

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print_human(report, repo_mode)

    return 1 if report.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
