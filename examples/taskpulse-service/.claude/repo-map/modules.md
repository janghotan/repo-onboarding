# Module Reference: `taskpulse`

> **Last Built Commit**: `e2a4eb25e5ecb1f799bb9fdddfaa5995c66fdf93` (`main`)

## Module Summary Table

| Module | Files | Primary Purpose | Inbound Dependents | Outbound Dependencies |
| :--- | :--- | :--- | :--- | :--- |
| `.` (root) | 2 | Package metadata, script entry declarations, and developer Makefile targets. | CI / Developer CLI | `fastapi`, `uvicorn`, `pydantic`, `httpx` |
| `src` | 4 | Application bootstrap (`main.py`), environment config (`config.py`), and admin CLI (`cli.py`). | `pyproject.toml` scripts, `tests` | `src/api`, `src/core`, `src/storage` |
| `src/api` | 3 | Header token authentication and HTTP route handlers for task lifecycle operations. | `src/main.py`, `tests` | `src/config`, `src/core`, `src/storage` |
| `src/core` | 3 | Domain exception classes with HTTP status mapping and structured JSON logging. | `src`, `src/api`, `src/storage`, `src/workers`, `tests` | Python stdlib (`logging`, `json`, `datetime`) |
| `src/storage` | 2 | SQLite `tasks` schema management, CRUD queries, and state transition guards. | `src/main.py`, `src/cli.py`, `src/api`, `src/workers`, `tests` | `src/core`, Python stdlib (`sqlite3`, `uuid`) |
| `src/workers` | 2 | Background polling loop and outbound webhook delivery/retry orchestration. | `pyproject.toml` (`taskpulse-worker`), `tests` | `src/config`, `src/core`, `src/storage` |
| `tests` | 1 | Pytest unit and integration test suite covering API, auth, and worker dead-lettering. | Developer / CI (`make test`) | `src/api`, `src/config`, `src/core`, `src/storage`, `src/workers` |

## Detailed Module Breakdown

### 1. Root Module (`.`)

- **Purpose**: Declares Python build metadata, runtime dependencies, console script entry points, and developer shortcut targets.
- **Key Files**:
  - `pyproject.toml:1-21` — Declares package `taskpulse` (`0.4.0`), dependencies (`pyproject.toml:10-15`), and `[project.scripts]` (`pyproject.toml:17-20`).
  - `Makefile:1-11` — Defines `run` (`Makefile:1`), `worker` (`Makefile:4`), `test` (`Makefile:7`), and `lint` (`Makefile:10`).

### 2. `src` (Bootstrap, Configuration & CLI)

- **Purpose**: Houses top-level application wiring, environment variable parsing, and the command-line administrative tool. Does not contain SQL queries or HTTP route logic directly.
- **Key Files**:
  - `src/config.py:8-28` — Defines `@dataclass(frozen=True) class Settings` (`src/config.py:8`) and `load_settings()` (`src/config.py:18`).
  - `src/main.py:11-26` — Defines `create_app(db_path)` (`src/main.py:11`) and `run_server()` (`src/main.py:19`).
  - `src/cli.py:12-44` — Defines `build_parser()` (`src/cli.py:12`) and `main(argv)` (`src/cli.py:26`) supporting `enqueue` and `inspect`.
- **Dependencies**:
  - **Inbound**: Invoked by console scripts in `pyproject.toml:18-19` and tests in `tests/test_taskpulse.py:6`.
  - **Outbound**: Imports `src.api.routes`, `src.core.logger`, and `src.storage.repository`.

### 3. `src/api` (HTTP API & Authentication)

- **Purpose**: Enforces API token authentication and translates HTTP request payloads into `TaskRepository` calls.
- **Key Files**:
  - `src/api/auth.py:12-16` — `verify_api_token(provided_token, settings)` validates `X-TaskPulse-Token` and raises `AuthenticationError` on mismatch.
  - `src/api/routes.py:14-49` — `TaskRouter` class exposing `handle_post_tasks` (`src/api/routes.py:21`), `handle_get_task` (`src/api/routes.py:32`), and `handle_delete_task` (`src/api/routes.py:45`).
- **Dependencies**:
  - **Inbound**: Instantiated by `create_app` in `src/main.py:16` and tested in `tests/test_taskpulse.py:16`.
  - **Outbound**: Imports `src.config.Settings`, `src.core.errors`, `src.core.logger`, and `src.storage.repository.TaskRepository`.

### 4. `src/core` (Errors & Structured Logging)

- **Purpose**: Zero-dependency internal foundation providing structured exceptions and JSON log formatting across all layers.
- **Key Files**:
  - `src/core/errors.py:6-45` — `TaskPulseError` base class (`src/core/errors.py:6`) and subclasses `AuthenticationError` (`src/core/errors.py:17`, HTTP 401), `TaskNotFoundError` (`src/core/errors.py:24`, HTTP 404), and `InvalidTaskStateError` (`src/core/errors.py:36`, HTTP 409).
  - `src/core/logger.py:10-34` — `StructuredFormatter` (`src/core/logger.py:10`) and `get_logger(name)` (`src/core/logger.py:26`).
- **Dependencies**:
  - **Inbound**: Imported by every runtime package (`src`, `src/api`, `src/storage`, `src/workers`).
  - **Outbound**: Python standard library only.

### 5. `src/storage` (SQLite Persistence)

- **Purpose**: Encapsulates all SQLite connection setup, schema creation, row serialization, and task state transitions.
- **Key Files**:
  - `src/storage/repository.py:17-25` — `TaskRecord` dataclass representing a row in the `tasks` table.
  - `src/storage/repository.py:28-133` — `TaskRepository` implementing `_init_schema` (`L37`), `enqueue_task` (`L54`), `get_task` (`L68`), `fetch_pending_batch` (`L74`), `mark_delivered` (`L81`), `record_failure` (`L93`), and `cancel_task` (`L109`).
- **Dependencies**:
  - **Inbound**: Used by `src/api/routes.py`, `src/workers/dispatcher.py`, `src/cli.py`, `src/main.py`, and `tests/test_taskpulse.py`.
  - **Outbound**: Imports `src.core.errors` and `src.core.logger`.

### 6. `src/workers` (Webhook Dispatcher)

- **Purpose**: Polls pending tasks from `TaskRepository` and executes outbound webhook HTTP calls, routing delivery outcomes back to storage.
- **Key Files**:
  - `src/workers/dispatcher.py:12-27` — `dispatch_single_task(record, repo, settings, sender)` handles single-task delivery and exception recovery.
  - `src/workers/dispatcher.py:30-39` — `run_worker_once(repo, settings, sender)` processes a batch of up to 10 pending tasks.
  - `src/workers/dispatcher.py:42-47` — `run_worker_loop()` initializes settings and repository for continuous worker execution.

### 7. `tests` (Verification Suite)

- **Purpose**: Validates end-to-end API route behavior, token authentication failures, and worker dead-letter transitions against an in-memory SQLite database (`:memory:`).
- **Key Files**:
  - `tests/test_taskpulse.py:12-48` — Defines `app_context` fixture (`L12`) and 3 test functions (`L20`, `L33`, `L41`).
