# Worked Example: `repo-onboarding` on the `taskpulse` Service

This walkthrough demonstrates `repo-onboarding` across its full lifecycle on `taskpulse` (a Python webhook queue service with an HTTP API, SQLite storage layer, CLI, and background worker):

1. **First Invocation**: Full structural scan and synthesis of `.claude/repo-map/`.
2. **Subsequent Invocation (Unchanged HEAD)**: Instant validation via `scripts/diff-check.sh`.
3. **Subsequent Invocation (After New Commit)**: Incremental `git diff --stat` detection and surgical rescanning of only affected modules (`src/api` and `src/storage`).
4. **Grounded Q&A Exchange**: Answering `"How does X work here?"`, `"Where do I change Y?"`, and handling uncommitted working-tree changes by routing through `index.json` and reading the underlying source files.

## Part 1: Initial Scan & Incremental Update Lifecycle

### 1. First Invocation (`FULL_SCAN_NEEDED`)

When invoked in `taskpulse` for the first time at commit `474926e`, the skill checks `.claude/repo-map/index.json`:

```text
$ ./scripts/diff-check.sh --from-index /path/to/taskpulse
STATUS: FULL_SCAN_NEEDED
REASON: .claude/repo-map/index.json does not exist yet.
CURRENT_HEAD: 474926e43d1be1e144298853d7305ea25f4b2cd6
```

It then runs `./scripts/scan.sh /path/to/taskpulse --format markdown`, inspects the primary files, and writes `.claude/repo-map/{architecture.md,modules.md,entry-points.md,conventions.md,index.json}`.

### 2. Second Invocation on Unchanged Repo (`UP_TO_DATE`)

```text
$ ./scripts/diff-check.sh --from-index /path/to/taskpulse
STATUS: UP_TO_DATE
LAST_BUILT_COMMIT: 474926e43d1be1e144298853d7305ea25f4b2cd6
CURRENT_HEAD: 474926e43d1be1e144298853d7305ea25f4b2cd6
DIRTY_WORKING_TREE: false
```

No rescan is needed; the agent immediately uses `.claude/repo-map/index.json` to route questions.

### 3. Third Invocation After Commit `e2a4eb2` (`INCREMENTAL_UPDATE_NEEDED`)

After a developer commits task cancellation support (`e2a4eb2`), `diff-check.sh` detects the commit delta and isolates the two affected modules:

```text
$ ./scripts/diff-check.sh --from-index /path/to/taskpulse
STATUS: INCREMENTAL_UPDATE_NEEDED
LAST_BUILT_COMMIT: 474926e43d1be1e144298853d7305ea25f4b2cd6
CURRENT_HEAD: e2a4eb25e5ecb1f799bb9fdddfaa5995c66fdf93
DIRTY_WORKING_TREE: false

=== DIFF STAT (474926e43d1be1e144298853d7305ea25f4b2cd6..e2a4eb25e5ecb1f799bb9fdddfaa5995c66fdf93) ===
 src/api/routes.py         |  6 ++++++
 src/storage/repository.py | 13 +++++++++++++
 2 files changed, 19 insertions(+)

=== CHANGED FILES (474926e43d1be1e144298853d7305ea25f4b2cd6..e2a4eb25e5ecb1f799bb9fdddfaa5995c66fdf93) ===
M	src/api/routes.py
M	src/storage/repository.py

=== AFFECTED MODULES / DIRECTORIES ===
src/api
src/storage
```

The agent rescans only those two directories (`./scripts/scan.sh /path/to/taskpulse --paths src/api src/storage`), reads the diff in `src/api/routes.py` and `src/storage/repository.py`, patches the `TaskRepository.cancel_task` (`src/storage/repository.py:109`) and `TaskRouter.handle_delete_task` (`src/api/routes.py:45`) entries into the map files, and updates `last_built_commit` in `index.json` to `e2a4eb25e5ecb1f799bb9fdddfaa5995c66fdf93`.

## Part 2: Sample Q&A Exchange

### Q1: "How does webhook delivery failure and dead-lettering work here?"

**Agent Routing & Verification Steps**:
1. Consult `.claude/repo-map/index.json` -> topic `"worker_dispatch_and_retries"` maps to `["src/workers/dispatcher.py", "src/storage/repository.py", "src/config.py"]`.
2. Read `src/workers/dispatcher.py`, `src/storage/repository.py`, and `src/config.py` directly to verify exact control flow and line numbers.

**Grounded Answer**:

Webhook delivery failures are handled across the worker dispatch loop (`src/workers/dispatcher.py`) and the SQLite repository (`src/storage/repository.py`):

1. **Batch Polling (`src/workers/dispatcher.py:30-39`)**: `run_worker_once()` calls `repo.fetch_pending_batch(limit=10)` (`src/storage/repository.py:74-79`), which selects up to 10 rows with `status = 'PENDING'` ordered by `created_at ASC`.
2. **Delivery & Exception Catching (`src/workers/dispatcher.py:12-27`)**: For each task, `dispatch_single_task()` calls `sender(record.target_url, record.payload)` inside a `try ... except Exception as exc:` block (`src/workers/dispatcher.py:19-27`):
   - If `200 <= status_code < 300` (`src/workers/dispatcher.py:21`), it calls `repo.mark_delivered(record.task_id)` (`src/storage/repository.py:81-91`), setting `status = 'DELIVERED'` and incrementing `attempts`.
   - If `status_code` is outside `200..299` (`src/workers/dispatcher.py:24`) or `sender` raises an exception (`src/workers/dispatcher.py:25-27`), it logs `"Webhook transport error"` (`src/workers/dispatcher.py:26`) and calls `repo.record_failure(record.task_id, max_attempts=settings.max_attempts)`.
3. **Retry vs. Dead-Letter Transition (`src/storage/repository.py:93-107`)**:
   - `TaskRepository.record_failure()` computes `next_attempts = record.attempts + 1` (`src/storage/repository.py:95`).
   - It compares `next_attempts` against `max_attempts` (configured via `TASKPULSE_MAX_ATTEMPTS`, defaulting to `3` in `src/config.py:27`):
     - When `next_attempts < max_attempts`, `next_status` stays `'PENDING'` (`src/storage/repository.py:96`), leaving the task eligible for subsequent `fetch_pending_batch()` polls.
     - When `next_attempts >= max_attempts`, `next_status` transitions to `'DEAD_LETTER'` (`src/storage/repository.py:96`), excluding it from future `fetch_pending_batch()` queries, and emits a structured warning log with `{"task_id", "attempts", "next_status"}` (`src/storage/repository.py:103-106`).

### Q2: "Where do I change the code to add a `POST /v1/tasks/{task_id}/retry` endpoint that requeues a `DEAD_LETTER` task?"

**Agent Routing & Verification Steps**:
1. Consult `.claude/repo-map/index.json` -> topics `"api_routes"`, `"task_enqueue_and_lifecycle"`, `"error_handling"`, and `"testing"`.
2. Check `.claude/repo-map/conventions.md` for state transition guards, route naming (`handle_<verb>_<resource>`), structured logging, and pytest conventions.
3. Read `src/storage/repository.py`, `src/api/routes.py`, `src/core/errors.py`, and `tests/test_taskpulse.py`.

**Grounded Answer**:

To add a `POST /v1/tasks/{task_id}/retry` endpoint that follows `taskpulse` conventions, make changes in three files:

1. **Add the storage transition method in `src/storage/repository.py` (after `cancel_task` at `src/storage/repository.py:109-120`)**:
   - Add `def retry_dead_letter_task(self, task_id: str) -> TaskRecord:`.
   - Load the existing record via `record = self.get_task(task_id)` (`src/storage/repository.py:68`), which automatically raises `TaskNotFoundError` (`status_code=404`, `src/core/errors.py:24`) if the ID is missing.
   - Enforce the state machine guard following the pattern in `mark_delivered` (`src/storage/repository.py:82-83`) and `cancel_task` (`src/storage/repository.py:111-112`):
     ```python
     if record.status != "DEAD_LETTER":
         raise InvalidTaskStateError(task_id, record.status, "retry_dead_letter_task")
     ```
   - Execute an `UPDATE tasks SET status = 'PENDING', attempts = 0, updated_at = ? WHERE task_id = ?` query, commit (`self._conn.commit()`), and emit a structured log following `src/storage/repository.py:119`:
     ```python
     logger.info("Requeued dead-letter task", extra={"structured_fields": {"task_id": task_id}})
     ```

2. **Expose the route handler in `src/api/routes.py` (after `handle_delete_task` at `src/api/routes.py:45-49`)**:
   - Follow the `handle_<verb>_<action>` naming convention on `TaskRouter` (`src/api/routes.py:14`):
     ```python
     def handle_post_task_retry(self, headers: Dict[str, str], task_id: str) -> Dict[str, Any]:
         """POST /v1/tasks/{task_id}/retry - Reset a DEAD_LETTER task back to PENDING."""
         verify_api_token(headers.get(self.settings.api_key_header), self.settings)
         record = self.repo.retry_dead_letter_task(task_id)
         return {"task_id": record.task_id, "status": record.status, "attempts": record.attempts, "updated_at": record.updated_at}
     ```
   - Calling `verify_api_token` (`src/api/auth.py:12`) first ensures unauthorized requests raise `AuthenticationError` (`401`) consistently with `handle_post_tasks` (`src/api/routes.py:23`) and `handle_get_task` (`src/api/routes.py:34`).

3. **Add unit and state-guard tests in `tests/test_taskpulse.py` (after `test_worker_dead_letters_after_max_attempts` at `tests/test_taskpulse.py:41-48`)**:
   - Reuse the `app_context` fixture (`tests/test_taskpulse.py:12-17`).
   - Add `test_retry_dead_letter_task_resets_status_and_attempts(app_context)` to verify that a task driven to `DEAD_LETTER` transitions back to `status == "PENDING"` and `attempts == 0`.
   - Add `test_retry_non_dead_letter_task_raises_invalid_state(app_context)` using `with pytest.raises(InvalidTaskStateError) as exc_info:` to confirm attempting to retry a `PENDING` task returns `status_code == 409`.
