---
name: repo-onboarding
description: Build and maintain a persistent, commit-tracked structural map of any codebase in .claude/repo-map/ and answer codebase questions using verified file:line evidence. Use when the user asks how something works in this codebase, where to make a change, for an architecture overview, or when onboarding to an unfamiliar repo.
---

# repo-onboarding

Give the agent an accurate, persistent mental map of any codebase stored under `.claude/repo-map/` (`architecture.md`, `modules.md`, `entry-points.md`, `conventions.md`, and `index.json`), updating incrementally via Git commit diffs and grounding every architectural or code-level answer in verified `file:line` references.

## When to Use

- Use when onboarding to an unfamiliar repository or when the user asks for an architecture overview, tour, or module breakdown.
- Use when the user asks "how does X work here?", "where is Y implemented?", or "what calls Z?".
- Use when the user asks "where do I change Y?" or "how do I add a new route, command, job, or test?" so changes follow the repository's real conventions.
- Use when `.claude/repo-map/` already exists and needs an incremental refresh after new commits before answering structural questions.

## Steps

### Step 1: Check Existing Map State and Git Freshness

Determine whether `.claude/repo-map/index.json` exists and whether its recorded commit matches the current Git `HEAD`.

1. Run the incremental diff checker from the skill directory against the target repository root:

```bash
./scripts/diff-check.sh --from-index <repo-root>
```

2. Branch based on the reported `STATUS`:

- **`FULL_SCAN_NEEDED` or `NO_GIT_REPO`**: Proceed to **Step 2 (Full Structural Scan)** to build `.claude/repo-map/` from scratch.
- **`UP_TO_DATE`**: Skip rescanning and proceed directly to **Step 5 (Answer Questions Using the Map and Source Files)**.
- **`UP_TO_DATE_WITH_UNCOMMITTED_CHANGES`**: Use the existing map for routing, but note the dirty files listed under `UNCOMMITTED WORKING TREE CHANGES` and always read those files directly from disk before making claims about them.
- **`INCREMENTAL_UPDATE_NEEDED`**: Proceed to **Step 4 (Incremental Diff-Driven Update)** to rescan only the affected directories and patch the map files in place.

### Step 2: Run the Language-Agnostic Structural Discovery Pass

When creating the map for the first time (or after a history rewrite), collect raw structural evidence before writing any map files. Do not hardcode assumptions for a single language. Follow this strict discovery priority order:

1. **Directory and file topology**: Inspect how directories, packages, and filenames partition domain logic, interfaces, tests, and configuration.
2. **Manifest files**: Parse present manifests (`package.json`, `go.mod`, `pyproject.toml`, `requirements.txt`, `Cargo.toml`, `composer.json`, `Gemfile`, `pom.xml`, `build.gradle`, `Makefile`, `Dockerfile`) to extract declared dependencies, binary targets, and runnable scripts.
3. **Pattern-based convention discovery**: Use ripgrep (`rg -n`) or the bundled discovery helper to locate concrete `file:line` examples of error handling, logging, test organization, import ordering, and configuration loading.
4. **Entry-point detection**: Check standard entry locations (`main.*`, `cmd/*/main.go`, `src/index.*`, `src/main.*`, `manage.py`, `app.py`, `server.*`, CLI definitions, API routers, and job schedulers) alongside manifest-declared `scripts` or `bin` entries.

Run the bundled discovery script to gather these raw findings in a single pass:

```bash
./scripts/scan.sh <repo-root> --format markdown
```

For machine-parsable symbol, manifest, and topic-routing data, run:

```bash
./scripts/scan.sh <repo-root> --format json
```

Treat `scripts/scan.sh` as a discovery helper, not a replacement for reading code. Open and read the primary entry points, core domain modules, and configuration files surfaced by the scan so your synthesized map reflects real control flow rather than filename guesses.

### Step 3: Synthesize the Persistent Map in `.claude/repo-map/`

Create `.claude/repo-map/` inside the target repository and write five coordinated files. Every claim in the markdown files must cite real file paths or `file:line` locations verified in the repository.

#### 1. `.claude/repo-map/architecture.md`

Document the high-level system shape so an engineer or agent can grasp how the components fit together in under two minutes:

- **System Purpose and Runtime Stack**: Primary language(s), framework(s), runtime version, and external backing services declared in manifests.
- **Major Components**: Each core subsystem, its root directory, and its single-sentence responsibility.
- **Component Connections and Data Flow**: Trace how a typical request, command, or job enters the system, traverses middleware/services/domain layers, interacts with storage or external APIs, and returns a result, citing concrete `file:line` handoff points.
- **Cross-Cutting Concerns**: Authentication, configuration loading, database/session lifecycle, and background processing.

#### 2. `.claude/repo-map/modules.md`

Provide a per-directory/module reference table and breakdown covering every logical module in the repository:

- **Module Path**: Directory or package path (for example, `src/auth/`, `internal/billing/`, `pkg/storage/`).
- **Purpose**: What domain or technical responsibility the module owns and what it intentionally excludes.
- **Key Files and Symbols**: The 2 to 5 most important files in the module with `file:line` references to primary classes, structs, or functions.
- **Inbound and Outbound Dependencies**: Which internal modules depend on this module (inbound) and which internal modules or external packages this module imports (outbound).

#### 3. `.claude/repo-map/entry-points.md`

List every place where execution starts so the agent knows where to trace runtime behavior:

- **Application Bootstraps and Binaries**: Main functions, server startups, and WSGI/ASGI/HTTP listeners with a one-line description and exact `file:line` reference.
- **API Routes and Controllers**: HTTP, GraphQL, gRPC, or WebSocket route registration points with HTTP method/path patterns and `file:line` references.
- **CLI Commands and Scripts**: CLI subcommands, management commands, and manifest `scripts`/`Makefile` targets with `file:line` references.
- **Background Workers and Scheduled Jobs**: Queue consumers, cron definitions, and event listeners with `file:line` references.

#### 4. `.claude/repo-map/conventions.md`

Document inferred, real codebase patterns so any future code modification looks native to the repository. Never assert a convention without backing it by 1 to 2 concrete `file:line` examples pulled from actual code:

- **Error Handling Style**: How errors are defined, wrapped, propagated, and translated into API/CLI responses (cite 1 to 2 `file:line` examples).
- **Test Structure and Location**: Where unit/integration tests live, naming conventions (`test_*.py`, `*.test.ts`, `*_test.go`), fixture/mocking patterns, and how tests are invoked (cite 1 to 2 `file:line` examples).
- **Naming Conventions**: File naming (`snake_case`, `kebab-case`, `PascalCase`), symbol naming for classes/functions/constants, and interface/type prefixes (cite 1 to 2 `file:line` examples).
- **Import Ordering and Module Boundaries**: Relative vs. absolute/alias imports, grouping order (standard library, third-party, internal), and layer boundary rules (cite 1 to 2 `file:line` examples).
- **Logging and Observability Approach**: Logger initialization, structured vs. formatted logging fields, and log levels used in practice (cite 1 to 2 `file:line` examples).

#### 5. `.claude/repo-map/index.json`

Write a valid, compact JSON routing map that records the current Git `HEAD` hash and maps domain topics, features, and module names to relevant file paths:

```json
{
  "schema_version": "1.0",
  "repo_name": "example-repo",
  "last_built_commit": "4b825dc642cb6eb9a060e54bf8d69288fbee4904",
  "last_built_branch": "main",
  "generated_at": "2026-10-23T10:00:00Z",
  "topics": {
    "authentication": ["src/auth/service.py", "src/middleware/auth.py"],
    "routing": ["src/api/routes.py", "src/app.py"],
    "database": ["src/db/connection.py", "src/db/models.py"],
    "cli": ["src/cli.py"],
    "testing": ["tests/conftest.py", "tests/test_api.py"]
  },
  "modules": {
    "src/api": {
      "summary": "HTTP route handlers and request validation",
      "key_files": ["src/api/routes.py", "src/api/schemas.py"],
      "depends_on": ["src/auth", "src/services"]
    }
  }
}
```

Verify that `.claude/repo-map/index.json` parses cleanly with `python3 -m json.tool .claude/repo-map/index.json`.

### Step 4: Incremental Diff-Driven Update (Subsequent Invocations)

When `scripts/diff-check.sh --from-index <repo-root>` reports `STATUS: INCREMENTAL_UPDATE_NEEDED`:

1. Inspect the `DIFF STAT`, `CHANGED FILES`, and `AFFECTED MODULES / DIRECTORIES` sections emitted by `scripts/diff-check.sh`.
2. Re-scan only the affected directories rather than regenerating the entire repository map from scratch:

```bash
./scripts/scan.sh <repo-root> --paths <affected-dir-1> <affected-dir-2>
```

3. Read the modified or newly added files in those directories to understand what changed (new routes, renamed symbols, updated dependencies, or shifted line numbers).
4. Patch only the affected sections in `architecture.md`, `modules.md`, `entry-points.md`, and `conventions.md`, updating any shifted `file:line` references in the touched files.
5. Update `topics`, `modules`, and `last_built_commit` (to the new `CURRENT_HEAD` hash) in `.claude/repo-map/index.json`.

### Step 5: Answer Codebase Questions ("How does X work?", "Where do I change Y?")

Follow this grounding protocol whenever answering a question about the repository:

1. **Route via `index.json` first**: Read `.claude/repo-map/index.json` (and relevant sections of `architecture.md`, `modules.md`, `entry-points.md`, or `conventions.md`) to identify the candidate files for the user's topic without scanning the whole repo.
2. **Read the actual source files before answering**: Always open and inspect the candidate source files directly. The map is a routing aid and high-level summary, never the sole authority for a code-level claim.
3. **Reconcile staleness in favor of live code**: If a source file disagrees with the map (for example, due to uncommitted working-tree edits or line drift), trust the actual source file, cite its current `file:line` numbers, and flag or patch the stale map section immediately.
4. **Fall back to direct exploration for unmapped topics**: If a question asks about a brand-new, uncommitted, or niche symbol not covered in `index.json`, run targeted search (`rg -n` / `grep -rn` / file globbing) and read the matching files directly rather than guessing or saying "I don't know."
5. **Cite concrete `file:line` references**: Every explanation of how a feature works or checklist of where to make a change must include exact `file:line` citations and point out the relevant patterns from `conventions.md` (such as how to handle errors, write tests, and register routes) so changes stay consistent.

## Gotchas

- **Never answer from the map alone**: Summarized markdown can miss subtle conditionals or recent uncommitted edits. Always verify against the underlying source files before stating how a function behaves or where to edit.
- **Never assert conventions without `file:line` proof**: Generic advice like "use standard Python logging" is unhelpful if the repo actually uses a custom structured logger wrapper at `src/core/logger.py:18`. Every entry in `conventions.md` requires 1 to 2 real `file:line` examples.
- **Keep incremental updates surgical**: When `last_built_commit` differs from `HEAD` by only a few files, do not rewrite untouched module descriptions in `modules.md` or `conventions.md`. Patch only the sections impacted by `git diff <last-hash>..HEAD --stat`.
- **Handle repositories without ripgrep (`rg`)**: If `rg` is not installed in the environment, use `./scripts/scan.sh` (which uses Python 3 standard library) or `grep -rnE` so discovery remains zero-dependency.
