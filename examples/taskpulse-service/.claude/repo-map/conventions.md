# Codebase Conventions & Patterns: `taskpulse`

> **Last Built Commit**: `e2a4eb25e5ecb1f799bb9fdddfaa5995c66fdf93` (`main`)
> Every pattern below is inferred from actual code and backed by concrete `file:line` citations.

## 1. Error Handling Style

- **Domain Exception Hierarchy with Embedded HTTP Status Codes**: All application errors inherit from `TaskPulseError` (`src/core/errors.py:6-14`), which stores machine-readable `code` (`str`), `message` (`str`), HTTP `status_code` (`int`), and an optional `details` dictionary.
  - Evidence 1: `AuthenticationError` subclasses `TaskPulseError` and sets `code="AUTH_FAILED"` and `status_code=401` (`src/core/errors.py:17-21`).
  - Evidence 2: `InvalidTaskStateError` subclasses `TaskPulseError` and sets `code="INVALID_TASK_STATE"`, `status_code=409`, and `details={"task_id": task_id, "current_state": current_state}` (`src/core/errors.py:36-45`).
- **Worker Transport Fault Isolation**: While API and storage methods raise `TaskPulseError` subclasses directly (`src/storage/repository.py:70`, `src/storage/repository.py:83`), the background worker catches transport exceptions in `dispatch_single_task` so a failing webhook never crashes the worker batch loop.
  - Evidence 1: `src/workers/dispatcher.py:19-27` wraps `sender(record.target_url, record.payload)` in `try ... except Exception as exc:`, logs the transport error, and delegates to `repo.record_failure(...)`.

## 2. Test Structure & Location

- **Centralized Pytest Suite with In-Memory SQLite Fixtures**: Tests live under `tests/` in `test_*.py` files (`tests/test_taskpulse.py:1`) and use `@pytest.fixture` to wire `Settings`, `TaskRepository(":memory:")`, and `TaskRouter` without touching disk.
  - Evidence 1: `tests/test_taskpulse.py:12-17` defines `@pytest.fixture def app_context()` returning `(settings, repo, router)` backed by `TaskRepository(":memory:")`.
  - Evidence 2: `tests/test_taskpulse.py:33-38` uses `with pytest.raises(AuthenticationError) as exc_info:` and asserts both `exc_info.value.status_code == 401` and `exc_info.value.code == "AUTH_FAILED"`.

## 3. Naming Conventions

- **Modules & Functions (`snake_case`)**: All Python files (`repository.py`, `dispatcher.py`), functions (`load_settings`, `verify_api_token`, `run_worker_once`), and methods use `snake_case`. Route handlers on `TaskRouter` follow the prefix pattern `handle_<verb>_<resource>`.
  - Evidence 1: `src/api/routes.py:21` (`def handle_post_tasks`), `src/api/routes.py:32` (`def handle_get_task`), and `src/api/routes.py:45` (`def handle_delete_task`).
- **Classes & Dataclasses (`PascalCase`)**: Domain records, repositories, routers, and exceptions use `PascalCase`.
  - Evidence 1: `@dataclass(frozen=True) class Settings` (`src/config.py:8-9`) and `@dataclass class TaskRecord` (`src/storage/repository.py:16-17`).
- **Task Status Constants (`UPPER_SNAKE_CASE` strings)**: Task lifecycle states in SQLite are stored as uppercase string literals: `'PENDING'`, `'DELIVERED'`, `'DEAD_LETTER'`, and `'CANCELLED'`.
  - Evidence 1: `src/storage/repository.py:60` (`'PENDING'`), `src/storage/repository.py:86` (`'DELIVERED'`), `src/storage/repository.py:96` (`'DEAD_LETTER'`), and `src/storage/repository.py:115` (`'CANCELLED'`).

## 4. Import Ordering & Module Boundaries

- **Two-Group Absolute Imports (`stdlib` then `src.*`)**: Files group standard library imports alphabetically at the top, separated by a single blank line from absolute `from src.<module> import ...` statements. Relative imports (`from . import ...`) are never used.
  - Evidence 1: `src/storage/repository.py:3-11` imports `json`, `sqlite3`, `uuid`, `dataclasses`, `datetime`, and `typing` first, followed by a blank line and `from src.core.errors import InvalidTaskStateError, TaskNotFoundError` and `from src.core.logger import get_logger`.
  - Evidence 2: `src/api/routes.py:3-9` imports `from typing import Any, Dict`, followed by a blank line and absolute imports from `src.api.auth`, `src.config`, `src.core.errors`, `src.core.logger`, and `src.storage.repository`.

## 5. Logging & Observability Approach

- **Hierarchical Module Loggers with `structured_fields` Extra Dict**: Every module initializes a module-level logger via `logger = get_logger("taskpulse.<submodule>")` (`src/core/logger.py:26`) and passes structured key-value metadata through `extra={"structured_fields": {...}}` so `StructuredFormatter` (`src/core/logger.py:10-23`) merges them into the top-level JSON log object.
  - Evidence 1: `src/storage/repository.py:13` initializes `logger = get_logger("taskpulse.storage")` and logs task creation at `src/storage/repository.py:65`: `logger.info("Enqueued new task", extra={"structured_fields": {"task_id": task_id, "topic": topic}})`.
  - Evidence 2: `src/workers/dispatcher.py:9` initializes `logger = get_logger("taskpulse.workers.dispatcher")` and logs delivery failure at `src/workers/dispatcher.py:26`: `logger.error("Webhook transport error", extra={"structured_fields": {"task_id": record.task_id, "error": str(exc)}})`.
