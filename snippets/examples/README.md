# Example instruction snippets (unverified)

These files are optional reference material for wiring `repo-onboarding` into specific AI
coding tools. They are **not** guaranteed-current syntax.

Each tool's instructions-file convention changes between versions, and these examples were
not independently verified against official documentation at release time. Treat them as
starting points to check, not as copy-paste-and-trust instructions.

The supported approach is the generic one in the main README: point your agent at this
repository and ask it to read `SKILL.md` and wire it into its own skill or instructions
system, or add one line to your project's persistent instructions file telling the agent to
read `<path>/SKILL.md` before onboarding-style tasks.

| File | Roughly targets |
| --- | --- |
| `AGENTS.md.example` | The cross-tool `AGENTS.md` convention |
| `cursor-repo-onboarding.mdc` | Cursor project rules |
| `windsurf-repo-onboarding.md` | Windsurf / Devin Desktop workspace rules |
| `copilot-instructions.md` | GitHub Copilot repository instructions |
| `aider-conventions.md` | Aider conventions file |
| `opencode.json.example` | OpenCode `instructions` config |

Replace `CLONE_PATH` with the absolute path where you cloned this repository.
