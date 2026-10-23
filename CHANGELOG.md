# Changelog

All notable changes to `repo-onboarding` are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-10-23

### Added

- **`SKILL.md`**: Complete Claude Skill definition and imperative workflow for initial structural mapping, incremental Git diff updates, and `file:line`-grounded codebase Q&A.
- **`scripts/scan.py` & `scripts/scan.sh`**: Zero-dependency, language-agnostic discovery helper supporting directory topology analysis, manifest parsing (`package.json`, `pyproject.toml`, `requirements.txt`, `go.mod`, `Cargo.toml`, `Makefile`), entry-point detection, and `file:line` convention sampling, plus `--paths` for partial directory rescans.
- **`scripts/diff-check.sh`**: Commit hash comparison script that reads `last_built_commit` from `.claude/repo-map/index.json`, compares against `HEAD` and working tree status, and outputs `git diff <last-hash>..HEAD --stat` alongside affected modules.
- **`examples/taskpulse-service/`**: End-to-end worked example containing all five generated `.claude/repo-map/` files (`architecture.md`, `modules.md`, `entry-points.md`, `conventions.md`, `index.json`), incremental diff output (`incremental-diff-output.txt`), and a grounded Q&A walkthrough (`sample-qa-walkthrough.md`).
- **Repository Documentation**: Added `README.md`, `LICENSE` (Apache 2.0), `CONTRIBUTING.md`, and `.gitignore`.
