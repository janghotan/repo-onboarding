# Execution Entry Points: `taskpulse`

> **Last Built Commit**: `e2a4eb25e5ecb1f799bb9fdddfaa5995c66fdf93` (`main`)

## 1. Application Bootstraps & Console Binaries

- `src/main.py:11` (`create_app`) — Initializes runtime `Settings`, creates `TaskRepository`, and returns a configured `TaskRouter` instance.
- `src/main.py:19` (`run_server`) — Console script entry point declared as `taskpulse-api = "src.main:run_server"` in `pyproject.toml:18` (also invoked via `python3 -m src.main` at `src/main.py:25` and `Makefile:1-2`).
- `src/workers/dispatcher.py:42` (`run_worker_loop`) — Worker process entry point declared as `taskpulse-worker = "src.workers.dispatcher:run_worker_loop"` in `pyproject.toml:20` (also invoked via `python3 -m src.workers.dispatcher` at `src/workers/dispatcher.py:50` and `Makefile:4-5`).

## 2. HTTP API Routes (`src/api/routes.py`)

All routes are methods on `TaskRouter` (`src/api/routes.py:14`) and require the `X-TaskPulse-Token` header verified by `verify_api_token` (`src/api/auth.py:12`):

- `src/api/routes.py:21` (`TaskRouter.handle_post_tasks`) — `POST /v1/tasks`: Validates `topic` and `target_url` in request body and enqueues a new `PENDING` webhook task.
- `src/api/routes.py:32` (`TaskRouter.handle_get_task`) — `GET /v1/tasks/{task_id}`: Returns task metadata, current `status`, `attempts`, and `updated_at` timestamp.
- `src/api/routes.py:45` (`TaskRouter.handle_delete_task`) — `DELETE /v1/tasks/{task_id}`: Cancels a task if its current status is `PENDING`, transitioning it to `CANCELLED`.

## 3. CLI Commands (`src/cli.py`)

Declared as `taskpulse-cli = "src.cli:main"` in `pyproject.toml:19` and runnable directly via `src/cli.py:43`:

- `src/cli.py:16` (`taskpulse-cli enqueue --topic <TOPIC> --url <URL> [--payload <JSON>]`) — Dispatched in `src/cli.py:32-35` to enqueue a task directly into `taskpulse.db` and print JSON `{"task_id", "status"}`.
- `src/cli.py:21` (`taskpulse-cli inspect <task_id>`) — Dispatched in `src/cli.py:36-39` to look up a task by ID and print JSON `{"task_id", "status", "attempts"}`.

## 4. Developer & CI Task Targets (`Makefile`)

- `Makefile:1` (`make run`) — Starts the application entrypoint (`python3 -m src.main`).
- `Makefile:4` (`make worker`) — Starts the background webhook worker (`python3 -m src.workers.dispatcher`).
- `Makefile:7` (`make test`) — Runs the test suite via `pytest -q tests/`.
- `Makefile:10` (`make lint`) — Runs static linting via `ruff check src/ tests/`.
