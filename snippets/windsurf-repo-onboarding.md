---
trigger: model_decision
description: Codebase onboarding with the repo-onboarding skill; use for architecture overviews, how-does-X-work answers, and where-to-change guidance grounded in real file reads.
---

# Codebase onboarding (repo-onboarding)

A `repo-onboarding` skill is available at `CLONE_PATH/SKILL.md`.

When asked to onboard to this codebase, explain its architecture, answer "how does X work
here", or say where to change Y, read `CLONE_PATH/SKILL.md` and follow its process:

- Run `CLONE_PATH/scripts/diff-check.sh --from-index .` first to check for an existing,
  fresh map at `.claude/repo-map/`.
- Build the map with `CLONE_PATH/scripts/scan.sh . --format markdown` on a first run, or
  re-scan only the affected directories when the checker reports
  `INCREMENTAL_UPDATE_NEEDED`.
- Read the actual source files before claiming how anything works, and cite exact
  `file:line` references.

Save this file as `.devin/rules/repo-onboarding.md` (preferred) or
`.windsurf/rules/repo-onboarding.md` (legacy fallback). Use `trigger: always_on` in the
frontmatter instead if you want it loaded on every message. Windsurf and Devin Desktop also
read a root-level `AGENTS.md` with no frontmatter at all, which is always on.
