# Changelog

All notable changes to `repo-onboarding` are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.1] - 2026-10-23

Simplified the cross-agent documentation. The previous release published precise per-tool
syntax (Cursor `.mdc` frontmatter, Windsurf rule paths, OpenCode config keys, Copilot
`applyTo`, Aider config) that was fragile and could go stale silently.

### Changed

- **`README.md` / `README.zh-CN.md`**: The "other AI coding agents" section is now short and generic. It tells you to point the agent at this repository and ask it to read `SKILL.md`, with one line in a project instructions file as the manual fallback. The per-agent subsections and their syntax claims are gone.
- **`README.md` / `README.zh-CN.md`**: The plugin install section leads with the two-command flow that is actually tested; the one-step `--marketplace` form is mentioned without a version claim.

### Moved

- **`snippets/*` to `snippets/examples/`**: The old snippet files are kept as optional reference only, behind a `snippets/examples/README.md` disclaimer that they are unverified and may not match current tool syntax. Nothing links to them as instructions to follow.

## [0.3.0] - 2026-10-23

Documents how to use the skill from AI coding agents other than Claude Code, with
copy-pasteable snippets per agent.

### Added

- **`snippets/AGENTS.md.example`**: Ready-made `AGENTS.md` block for the cross-tool convention read by OpenAI Codex, Cursor, Windsurf / Devin Desktop, GitHub Copilot agents, and OpenCode.
- **`snippets/cursor-repo-onboarding.mdc`**: Cursor project rule with `description` and `alwaysApply` frontmatter (`.cursor/rules/*.mdc`).
- **`snippets/windsurf-repo-onboarding.md`**: Windsurf / Devin Desktop workspace rule with `trigger` frontmatter (`.devin/rules/` or `.windsurf/rules/`).
- **`snippets/copilot-instructions.md`**: GitHub Copilot repository instruction block (`.github/copilot-instructions.md`).
- **`snippets/aider-conventions.md`**: Aider conventions file plus the `.aider.conf.yml` `read:` entry that makes it permanent.
- **`snippets/opencode.json.example`**: OpenCode `instructions` config pointing at `SKILL.md`.
- **`README.md` / `README.zh-CN.md`**: New "Using repo-onboarding with other AI coding agents" section covering each verified convention, the plugin-marketplace-less reality, and the manual paste fallback that works with any file-reading agent.

## [0.2.0] - 2026-10-23

Installable straight from Claude Code's plugin system, with the standalone skill drop-in
unchanged.

### Added

- **`.claude-plugin/marketplace.json`**: Declares this repository as its own plugin marketplace containing one plugin, `repo-onboarding`, so `/plugin marketplace add janghotan/repo-onboarding` works.
- **`.claude-plugin/plugin.json`**: Plugin manifest (name, version, description, author, license, keywords) for `/plugin install repo-onboarding@repo-onboarding`. The skill itself is picked up from the repository root by default discovery, so `SKILL.md` and `scripts/` are served unchanged.
- **`.claude-plugin/icon.png`**: 512x512 plugin listing icon.
- **Manifest validation**: `scripts/validate.py` now checks both manifests (kebab-case names, semver version, required fields, plugin listed by the marketplace, relative `./` source paths that exist, icon presence, and a matching CHANGELOG entry), and CI runs `claude plugin validate .` on every push.

### Changed

- **`README.md` / `README.zh-CN.md`**: New "Install via the Claude Code plugin marketplace" section with the one-step and two-step commands; the manual `.claude/skills/` clone instructions remain as the alternative.

## [0.1.0] - 2026-10-23

First public release. A Claude Skill that builds a persistent, commit-tracked map of any
codebase and answers architecture and change-location questions with verified `file:line`
evidence.

### Added

- **`SKILL.md`**: Complete Claude Skill definition and imperative workflow for initial structural mapping, incremental Git diff updates, and `file:line`-grounded codebase Q&A.
- **`scripts/scan.py` & `scripts/scan.sh`**: Zero-dependency, language-agnostic discovery helper supporting directory topology analysis, manifest parsing (`package.json`, `pyproject.toml`, `requirements.txt`, `go.mod`, `Cargo.toml`, `Makefile`), entry-point detection, and `file:line` convention sampling, plus `--paths` for partial directory rescans.
- **`scripts/diff-check.sh`**: Commit hash comparison script that reads `last_built_commit` from `.claude/repo-map/index.json`, compares against `HEAD` and working tree status, and outputs `git diff <last-hash>..HEAD --stat` alongside affected modules.
- **`scripts/validate.py`**: Zero-dependency self-validation script checking `SKILL.md` frontmatter and line budget, unresolved placeholder markers, relative README link targets, and the example `index.json` schema.
- **`examples/taskpulse-service/`**: End-to-end worked example containing all five generated `.claude/repo-map/` files (`architecture.md`, `modules.md`, `entry-points.md`, `conventions.md`, `index.json`), incremental diff output (`incremental-diff-output.txt`), and a grounded Q&A walkthrough (`sample-qa-walkthrough.md`).
- **GitHub Actions CI (`.github/workflows/ci.yml`)**: Runs on every push and pull request, validating the skill, linting the Python scripts with `ruff`, linting the shell scripts with `shellcheck`, exercising `scan.sh` and `diff-check.sh` against the `examples/taskpulse-service` fixture and this repository, and verifying the two READMEs link to each other.
- **Repository Documentation**: `README.md`, `README.zh-CN.md`, `LICENSE` (Apache 2.0), `CONTRIBUTING.md`, and `.gitignore`.
- **`assets/`**: Hand-authored SVG architecture diagrams and social-preview banners in English and Simplified Chinese, each with an opaque white background for the diagrams, plus 1280x640 PNG exports of the banners.

### Changed

- **`README.md`**: Added a language switcher, an embedded architecture diagram in the how-it-works section, and a development section mirroring the CI checks.

### Fixed

- Removed an unused `shutil` import in `scripts/scan.py` flagged by `ruff`.
