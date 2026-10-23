# System Architecture: `taskpulse`

> **Last Built Commit**: `e2a4eb25e5ecb1f799bb9fdddfaa5995c66fdf93` (`main`)

## 1. System Purpose & Runtime Stack

`taskpulse` is a webhook-driven task queue and HTTP API service that accepts outbound webhook jobs over a token-authenticated REST API or CLI, persists them in SQLite, and asynchronously dispatches them via a polling worker with automatic retry and dead-letter state transitions.

- **Language & Runtime**: Python `>=3.11` (`pyproject.toml:9`)
- **Declared Dependencies**: `fastapi>=0.110.0`, `uvicorn>=0.29.0`, `pydantic>=2.6.0`, `httpx>=0.27.0` (`pyproject.toml:10-15`)
- **Storage Engine**: Embedded SQLite accessed via Python's standard library `sqlite3` (`src/storage/repository.py:4`)

## 2. Major Components

| Component | Directory / Path | Responsibility |
| :--- | :--- | :--- |
| **Application Bootstrap & Config** | `src/main.py`, `src/config.py` | Loads runtime environment variables into an immutable `Settings` dataclass (`src/config.py:8-28`) and wires `TaskRepository` into `TaskRouter` (`src/main.py:11-16`). |
| **HTTP API & Auth Layer** | `src/api/` | Authenticates incoming requests via the `X-TaskPulse-Token` header (`src/api/auth.py:12-16`) and exposes route handlers on `TaskRouter` (`src/api/routes.py:14-49`). |
| **Administrative CLI** | `src/cli.py` | Provides `taskpulse-cli enqueue` and `taskpulse-cli inspect` subcommands backed directly by `TaskRepository` (`src/cli.py:12-40`). |
| **SQLite Persistence Layer** | `src/storage/` | Owns the `tasks` SQLite table schema and enforces state transitions (`PENDING` -> `DELIVERED`, `DEAD_LETTER`, or `CANCELLED`) (`src/storage/repository.py:28-120`). |
| **Background Webhook Worker** | `src/workers/` | Polls `PENDING` tasks in FIFO order (`created_at ASC`) and dispatches HTTP payloads, recording delivery or failure (`src/workers/dispatcher.py:12-48`). |
| **Core Primitives** | `src/core/` | Defines the `TaskPulseError` exception hierarchy (`src/core/errors.py:6-45`) and single-line JSON structured logging (`src/core/logger.py:10-34`). |

## 3. Component Connections & Data Flow

### Flow A: Task Submission (`POST /v1/tasks` or `taskpulse-cli enqueue`)

1. **Entry & Auth**: An HTTP caller invokes `TaskRouter.handle_post_tasks` (`src/api/routes.py:21`), which calls `verify_api_token` (`src/api/auth.py:12`) to compare the `X-TaskPulse-Token` header against `Settings.api_secret_token` (`src/config.py:12`). Unauthorized requests raise `AuthenticationError` (`status_code=401`, `src/core/errors.py:17-21`).
2. **Validation**: `handle_post_tasks` validates that `topic` and `target_url` are non-empty, raising `TaskPulseError("VALIDATION_ERROR", ..., status_code=422)` otherwise (`src/api/routes.py:26-27`).
3. **Persistence**: `TaskRepository.enqueue_task` (`src/storage/repository.py:54-66`) generates a `tsk_<12-hex>` identifier (`src/storage/repository.py:56`), inserts a row with `status = 'PENDING'` and `attempts = 0`, commits the transaction, and logs an `"Enqueued new task"` event (`src/storage/repository.py:65`).

### Flow B: Asynchronous Webhook Dispatch (`taskpulse-worker`)

1. **Batch Polling**: `run_worker_loop` (`src/workers/dispatcher.py:42`) invokes `run_worker_once` (`src/workers/dispatcher.py:30`), which queries up to 10 `PENDING` tasks ordered by `created_at ASC` via `TaskRepository.fetch_pending_batch` (`src/storage/repository.py:74-79`).
2. **Outbound Delivery**: For each `TaskRecord`, `dispatch_single_task` (`src/workers/dispatcher.py:12-27`) invokes the HTTP `sender(record.target_url, record.payload)`.
3. **State Transition**:
   - **2xx Response**: Calls `TaskRepository.mark_delivered` (`src/storage/repository.py:81-91`), verifying the task is in `PENDING` or `RETRYING` state before setting `status = 'DELIVERED'` and incrementing `attempts`.
   - **Non-2xx Response or Exception**: Calls `TaskRepository.record_failure` (`src/storage/repository.py:93-107`), incrementing `attempts` and transitioning `status` to `'DEAD_LETTER'` once `attempts >= settings.max_attempts` (default `3`, `src/config.py:27`), or keeping it `'PENDING'` for retry.

### Flow C: Task Cancellation (`DELETE /v1/tasks/{task_id}`)

1. **Entry & Auth**: `TaskRouter.handle_delete_task` (`src/api/routes.py:45-49`) verifies the API token and delegates to `TaskRepository.cancel_task(task_id)`.
2. **State Guard**: `TaskRepository.cancel_task` (`src/storage/repository.py:109-120`) loads the task and enforces `record.status == "PENDING"`; if the task is already `DELIVERED`, `DEAD_LETTER`, or `CANCELLED`, it raises `InvalidTaskStateError` (`status_code=409`, `src/core/errors.py:36-45`).

## 4. Cross-Cutting Concerns

- **Configuration**: All environment variables (`TASKPULSE_ENV`, `TASKPULSE_DB_URL`, `TASKPULSE_SECRET_TOKEN`, `TASKPULSE_POLL_SECONDS`, `TASKPULSE_WEBHOOK_TIMEOUT`, `TASKPULSE_MAX_ATTEMPTS`) are read exclusively in `load_settings()` (`src/config.py:18-28`).
- **Observability**: Every module acquires a logger via `get_logger(name)` (`src/core/logger.py:26-34`), emitting UTC-timestamped JSON lines with contextual fields passed via `extra={"structured_fields": {...}}`.
