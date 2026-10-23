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

    if errors:
        print("skill validation failed:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    print("skill validation passed: frontmatter, links, placeholders, and example map are clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
