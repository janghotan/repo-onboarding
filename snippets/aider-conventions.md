# Codebase onboarding (repo-onboarding)

A `repo-onboarding` skill is available at `CLONE_PATH/SKILL.md`.

When asked to onboard to this codebase, give an architecture overview, explain how
something works here, or say where to make a change, read `CLONE_PATH/SKILL.md` first and
follow its process:

1. Run `CLONE_PATH/scripts/diff-check.sh --from-index .` to see whether a map already exists
   at `.claude/repo-map/` and whether it is stale.
2. On a first run, run `CLONE_PATH/scripts/scan.sh . --format markdown` and synthesize
   `.claude/repo-map/{architecture.md,modules.md,entry-points.md,conventions.md,index.json}`
   as SKILL.md describes.
3. On later runs, re-scan only the directories reported under
   `AFFECTED MODULES / DIRECTORIES` and patch the affected map sections in place.
4. Read the actual source files before making any code-level claim, and cite exact
   `file:line` references.

Aider does not auto-load files by convention. Load this file explicitly with
`aider --read CONVENTIONS.md`, or make it permanent by adding to `.aider.conf.yml`:

```yaml
read: [CONVENTIONS.md]
```
