#!/usr/bin/env python3
"""repo-onboarding: Repository self-validation helper (validate.py).

Checks that the packaged skill is internally consistent before it is shipped:
  - SKILL.md has a valid YAML frontmatter block with the required fields.
  - SKILL.md respects the skill authoring rules (line budget, no em/en dashes).
  - No unresolved TODO / placeholder markers remain in shipped files.
  - Every relative Markdown link in README files resolves to a real file.
  - The example repo-map index parses as JSON and declares the required keys.

Uses only the Python 3 standard library so it runs anywhere the skill runs.

Usage:
  python3 scripts/validate.py [repo_root]
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import List

REQUIRED_FRONTMATTER_FIELDS = ("name", "description")
MAX_SKILL_LINES = 500
MAX_DESCRIPTION_CHARS = 1024
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
PLACEHOLDER_RE = re.compile(r"\b(TODO|FIXME|XXX|TBD)\b|LOREM IPSUM", re.IGNORECASE)
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)")
README_FILES = ("README.md", "README.zh-CN.md")
SHIPPED_TEXT_SUFFIXES = (".md", ".py", ".sh")


def parse_frontmatter(text: str) -> List[str]:
    """Return the frontmatter lines, or an empty list when absent/malformed."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return []
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            return lines[1:idx]
    return []


def check_skill(skill_path: Path, errors: List[str]) -> None:
    text = skill_path.read_text(encoding="utf-8")
    lines = text.splitlines()

    if len(lines) > MAX_SKILL_LINES:
        errors.append(
            f"SKILL.md has {len(lines)} lines (limit {MAX_SKILL_LINES})"
        )

    frontmatter = parse_frontmatter(text)
    if not frontmatter:
        errors.append("SKILL.md is missing a '---' delimited frontmatter block")
    else:
        fields = {}
        for raw in frontmatter:
            if not raw.strip() or raw.lstrip().startswith("#"):
                continue
            if ":" not in raw:
                errors.append(f"SKILL.md frontmatter line is not 'key: value': {raw!r}")
                continue
            key, value = raw.split(":", 1)
            fields[key.strip()] = value.strip()
        for key in REQUIRED_FRONTMATTER_FIELDS:
            if not fields.get(key):
                errors.append(f"SKILL.md frontmatter is missing required field '{key}'")
        name = fields.get("name", "")
        if name and not NAME_RE.match(name):
            errors.append(
                f"SKILL.md frontmatter name '{name}' must be lowercase kebab-case"
            )
        description = fields.get("description", "")
        if len(description) > MAX_DESCRIPTION_CHARS:
            errors.append(
                f"SKILL.md description is {len(description)} chars "
                f"(limit {MAX_DESCRIPTION_CHARS})"
            )

    for lineno, line in enumerate(lines, start=1):
        if "\u2014" in line or "\u2013" in line:
            errors.append(f"SKILL.md:{lineno} contains an em-dash or en-dash")


def check_placeholders(root: Path, errors: List[str]) -> None:
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix not in SHIPPED_TEXT_SUFFIXES:
            continue
        if path.name == Path(__file__).name:
            continue
        rel = path.relative_to(root)
        if any(part.startswith(".") for part in rel.parts):
            continue
        for lineno, line in enumerate(
            path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1
        ):
            if PLACEHOLDER_RE.search(line):
                errors.append(f"{rel}:{lineno} contains an unresolved placeholder marker")


def check_links(root: Path, errors: List[str]) -> None:
    for readme_name in README_FILES:
        readme = root / readme_name
        if not readme.exists():
            continue
        for lineno, line in enumerate(readme.read_text(encoding="utf-8").splitlines(), start=1):
            for target in LINK_RE.findall(line):
                if target.startswith(("http://", "https://", "mailto:", "#")):
                    continue
                rel_target = target.split("#", 1)[0]
                if not rel_target:
                    continue
                resolved = (root / rel_target).resolve()
                if not resolved.exists():
                    errors.append(f"{readme_name}:{lineno} links to missing path '{target}'")


def check_example_map(root: Path, errors: List[str]) -> None:
    index_path = root / "examples" / "taskpulse-service" / ".claude" / "repo-map" / "index.json"
    if not index_path.exists():
        errors.append("example repo map is missing index.json")
        return
    try:
        data = json.loads(index_path.read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"example index.json does not parse: {exc}")
        return
    for key in ("schema_version", "last_built_commit", "topics", "modules"):
        if key not in data:
            errors.append(f"example index.json is missing required key '{key}'")


PLUGIN_NAME_RE = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$")


def check_plugin_manifests(root: Path, errors: List[str]) -> None:
    """Validate the Claude Code marketplace and plugin manifests.

    Catches schema-breaking edits (bad name format, non-semver version, missing
    required fields, paths that escape the plugin root) before they reach a user
    running `/plugin marketplace add`.
    """
    plugin_dir = root / ".claude-plugin"
    marketplace_path = plugin_dir / "marketplace.json"
    plugin_path = plugin_dir / "plugin.json"

    def load(path: Path) -> dict:
        if not path.exists():
            errors.append(f"missing plugin manifest: {path.relative_to(root)}")
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append(f"{path.relative_to(root)} does not parse: {exc}")
            return {}
        if not isinstance(data, dict):
            errors.append(f"{path.relative_to(root)} must contain a JSON object")
            return {}
        return data

    marketplace = load(marketplace_path)
    plugin = load(plugin_path)

    if marketplace:
        name = marketplace.get("name", "")
        if not name:
            errors.append("marketplace.json is missing required field 'name'")
        elif not PLUGIN_NAME_RE.match(name):
            errors.append(f"marketplace.json name '{name}' must be lowercase kebab-case")
        if not marketplace.get("owner"):
            errors.append("marketplace.json is missing required field 'owner'")
        plugins = marketplace.get("plugins")
        if not isinstance(plugins, list) or not plugins:
            errors.append("marketplace.json must list at least one plugin in 'plugins'")
            plugins = []
        listed = set()
        for entry in plugins:
            if not isinstance(entry, dict):
                errors.append("marketplace.json has a non-object entry in 'plugins'")
                continue
            entry_name = entry.get("name", "")
            if not entry_name:
                errors.append("marketplace.json plugin entry is missing 'name'")
            elif not PLUGIN_NAME_RE.match(entry_name):
                errors.append(
                    f"marketplace.json plugin name '{entry_name}' must be lowercase kebab-case"
                )
            else:
                listed.add(entry_name)
            if not entry.get("description"):
                errors.append(
                    f"marketplace.json plugin '{entry_name}' is missing 'description'"
                )
            source = entry.get("source")
            if not source:
                errors.append(f"marketplace.json plugin '{entry_name}' is missing 'source'")
            elif isinstance(source, str):
                if not source.startswith("./"):
                    errors.append(
                        f"marketplace.json plugin '{entry_name}' source '{source}' "
                        "must be a relative path starting with './'"
                    )
                elif not (root / source).resolve().exists():
                    errors.append(
                        f"marketplace.json plugin '{entry_name}' source '{source}' does not exist"
                    )
            elif not isinstance(source, dict):
                errors.append(
                    f"marketplace.json plugin '{entry_name}' source must be a string or object"
                )

        if plugin:
            plugin_name = plugin.get("name", "")
            if plugin_name and listed and plugin_name not in listed:
                errors.append(
                    f"plugin.json name '{plugin_name}' is not listed in marketplace.json"
                )

    if plugin:
        name = plugin.get("name", "")
        if not name:
            errors.append("plugin.json is missing required field 'name'")
        elif not PLUGIN_NAME_RE.match(name):
            errors.append(f"plugin.json name '{name}' must be lowercase kebab-case")
        version = plugin.get("version", "")
        if not version:
            errors.append("plugin.json is missing required field 'version'")
        elif not SEMVER_RE.match(version):
            errors.append(f"plugin.json version '{version}' must be MAJOR.MINOR.PATCH")
        if not plugin.get("description"):
            errors.append("plugin.json is missing required field 'description'")
        if not plugin.get("author"):
            errors.append("plugin.json is missing required field 'author'")
        if not plugin.get("license"):
            errors.append("plugin.json is missing required field 'license'")

        icon = plugin_dir / "icon.png"
        if not icon.exists():
            errors.append(".claude-plugin/icon.png is missing (square PNG required)")

        changelog = root / "CHANGELOG.md"
        if version and changelog.exists():
            if f"[{version}]" not in changelog.read_text(encoding="utf-8"):
                errors.append(
                    f"plugin.json version {version} has no matching [ {version} ] CHANGELOG entry"
                )


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    errors: List[str] = []

    skill_path = root / "SKILL.md"
    if not skill_path.exists():
        print("error: SKILL.md not found", file=sys.stderr)
        return 1

    check_skill(skill_path, errors)
    check_placeholders(root, errors)
    check_links(root, errors)
    check_example_map(root, errors)
    check_plugin_manifests(root, errors)

    if errors:
        print("skill validation failed:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    print("skill validation passed: frontmatter, links, placeholders, and example map are clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
