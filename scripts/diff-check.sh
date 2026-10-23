#!/usr/bin/env bash
# repo-onboarding: Incremental commit diff checker (diff-check.sh)
#
# Compares the stored last-built commit hash (either passed directly or read
# from .claude/repo-map/index.json) against the current git HEAD and working
# tree state, then outputs:
#   - Status: UP_TO_DATE | INCREMENTAL_UPDATE_NEEDED | FULL_SCAN_NEEDED | DIRTY_WORKING_TREE
#   - Stored commit hash vs current HEAD commit hash
#   - `git diff <last-hash>..HEAD --stat`
#   - `git diff <last-hash>..HEAD --name-status`
#   - Affected top-level directories/modules to pass to `scan.sh --paths ...`
#
# Usage:
#   ./scripts/diff-check.sh [last_built_hash] [repo_dir]
#   ./scripts/diff-check.sh --from-index [repo_dir]

set -euo pipefail

ARG1="${1:-}"
ARG2="${2:-}"

if [ "${ARG1}" = "--from-index" ] || [ -z "${ARG1}" ]; then
  REPO_DIR="${ARG2:-.}"
  LAST_HASH=""
else
  LAST_HASH="${ARG1}"
  REPO_DIR="${ARG2:-.}"
fi

cd "${REPO_DIR}"

MAP_DIR=".claude/repo-map"
INDEX_FILE="${MAP_DIR}/index.json"

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "STATUS: NO_GIT_REPO"
  echo "REASON: Target directory is not a Git repository; perform a full structural scan."
  exit 0
fi

CURRENT_HEAD="$(git rev-parse HEAD 2>/dev/null || echo "UNCOMMITTED")"

# If LAST_HASH was not explicitly provided, attempt to extract it from .claude/repo-map/index.json
if [ -z "${LAST_HASH}" ]; then
  if [ ! -f "${INDEX_FILE}" ]; then
    echo "STATUS: FULL_SCAN_NEEDED"
    echo "REASON: ${INDEX_FILE} does not exist yet."
    echo "CURRENT_HEAD: ${CURRENT_HEAD}"
    exit 0
  fi

  if command -v python3 >/dev/null 2>&1; then
    LAST_HASH="$(python3 -c '
import json, sys
try:
    data = json.load(open(sys.argv[1], encoding="utf-8"))
    print(data.get("last_built_commit") or data.get("commit_hash") or "")
except Exception:
    print("")
' "${INDEX_FILE}")"
  else
    LAST_HASH="$(grep -Eo '"(last_built_commit|commit_hash)"\s*:\s*"[^"]+"' "${INDEX_FILE}" | head -n1 | sed -E 's/.*"([^"]+)"$/\1/' || true)"
  fi
fi

if [ -z "${LAST_HASH}" ]; then
  echo "STATUS: FULL_SCAN_NEEDED"
  echo "REASON: No last_built_commit found in ${INDEX_FILE}."
  echo "CURRENT_HEAD: ${CURRENT_HEAD}"
  exit 0
fi

if ! git cat-file -e "${LAST_HASH}^{commit}" 2>/dev/null; then
  echo "STATUS: FULL_SCAN_NEEDED"
  echo "REASON: Stored commit ${LAST_HASH} is not present in git history (e.g. after rebase/force-push)."
  echo "LAST_BUILT_COMMIT: ${LAST_HASH}"
  echo "CURRENT_HEAD: ${CURRENT_HEAD}"
  exit 0
fi

FULL_LAST_HASH="$(git rev-parse "${LAST_HASH}")"
DIRTY_STATUS="$(git status --porcelain)"

if [ "${FULL_LAST_HASH}" = "${CURRENT_HEAD}" ]; then
  if [ -z "${DIRTY_STATUS}" ]; then
    echo "STATUS: UP_TO_DATE"
    echo "LAST_BUILT_COMMIT: ${FULL_LAST_HASH}"
    echo "CURRENT_HEAD: ${CURRENT_HEAD}"
    echo "DIRTY_WORKING_TREE: false"
    exit 0
  else
    echo "STATUS: UP_TO_DATE_WITH_UNCOMMITTED_CHANGES"
    echo "LAST_BUILT_COMMIT: ${FULL_LAST_HASH}"
    echo "CURRENT_HEAD: ${CURRENT_HEAD}"
    echo "DIRTY_WORKING_TREE: true"
    echo ""
    echo "=== UNCOMMITTED WORKING TREE CHANGES ==="
    git status --short
    exit 0
  fi
fi

echo "STATUS: INCREMENTAL_UPDATE_NEEDED"
echo "LAST_BUILT_COMMIT: ${FULL_LAST_HASH}"
echo "CURRENT_HEAD: ${CURRENT_HEAD}"
if [ -n "${DIRTY_STATUS}" ]; then
  echo "DIRTY_WORKING_TREE: true"
else
  echo "DIRTY_WORKING_TREE: false"
fi

echo ""
echo "=== DIFF STAT (${FULL_LAST_HASH}..${CURRENT_HEAD}) ==="
git diff "${FULL_LAST_HASH}..${CURRENT_HEAD}" --stat

echo ""
echo "=== CHANGED FILES (${FULL_LAST_HASH}..${CURRENT_HEAD}) ==="
git diff "${FULL_LAST_HASH}..${CURRENT_HEAD}" --name-status

echo ""
echo "=== AFFECTED MODULES / DIRECTORIES ==="
git diff "${FULL_LAST_HASH}..${CURRENT_HEAD}" --name-only | awk -F'/' '
  NF == 1 { print "." }
  NF >= 3 && ($1 == "src" || $1 == "lib" || $1 == "pkg" || $1 == "internal" || $1 == "cmd" || $1 == "app" || $1 == "packages" || $1 == "apps") { print $1 "/" $2; next }
  NF >= 2 { print $1 }
' | sort -u

if [ -n "${DIRTY_STATUS}" ]; then
  echo ""
  echo "=== UNCOMMITTED WORKING TREE CHANGES ==="
  git status --short
fi
