# Contributing to `repo-onboarding`

Thank you for helping improve `repo-onboarding`! This project gives AI coding agents a fast, zero-dependency, evidence-grounded mental map of any software repository.

## Core Design Principles

1. **Zero External Dependencies**: Discovery scripts (`scripts/scan.py`, `scripts/scan.sh`, `scripts/diff-check.sh`) must run using only standard POSIX tools, `git`, and the Python 3 standard library. Do not add third-party PyPI or npm packages.
2. **Thin Discovery, Agent Synthesis**: `scripts/scan.py` gathers structural evidence (`file:line` candidates, manifest metadata, and convention probes), while the agent synthesizes the markdown files in `.claude/repo-map/`. Do not turn `scan.py` into a rigid template generator that writes `.claude/repo-map/*.md` directly.
3. **Language Agnosticism**: New manifest parsers or convention regexes should degrade gracefully on polyglot or unfamiliar repositories.
4. **Skill Authoring Standards**: Any edits to `SKILL.md` must keep the file under 500 lines, use imperative steps, include a blank line before every list, and avoid em-dashes or en-dashes.

## Development Workflow

1. Fork and clone the repository.
2. Test `scripts/scan.sh` and `scripts/diff-check.sh` against both a clean repository and a repository with multiple commits:
   ```bash
   ./scripts/scan.sh . --format markdown
   ./scripts/scan.sh . --format json | python3 -m json.tool > /dev/null
   ./scripts/diff-check.sh --from-index examples/taskpulse-service
   ```
3. Verify `SKILL.md` formatting and frontmatter rules before opening a pull request.

## Pull Request Checklist

- [ ] Scripts execute cleanly with `bash` and `python3` without external dependencies.
- [ ] New manifest or entry-point patterns include `file:line` evidence in discovery output.
- [ ] `SKILL.md` remains under 500 lines and follows the Claude Skill frontmatter specification.
- [ ] Changes are documented in `CHANGELOG.md`.
