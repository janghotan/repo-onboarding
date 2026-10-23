#!/usr/bin/env bash
# repo-onboarding: Thin shell entrypoint for structural discovery (scan.sh)
# Delegates to scripts/scan.py when python3 is available, or runs a fast POSIX/ripgrep fallback.
#
# Usage:
#   ./scripts/scan.sh [repo_dir] [--format markdown|json] [--paths dir1 dir2 ...]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if command -v python3 >/dev/null 2>&1 && [ -f "${SCRIPT_DIR}/scan.py" ]; then
  exec python3 "${SCRIPT_DIR}/scan.py" "$@"
fi

# Fallback when python3 is unavailable: pure shell + git/rg/grep structural discovery
TARGET_DIR="${1:-.}"
cd "${TARGET_DIR}"

echo "# Repository Structural Discovery Report (Shell Fallback)"
echo ""
echo "## 1. Git & Repository Metadata"
echo "- **Repo Root**: \`$(pwd)\`"
if git rev-parse HEAD >/dev/null 2>&1; then
  echo "- **Current HEAD**: \`$(git rev-parse HEAD)\` (\`$(git rev-parse --short HEAD)\` on branch \`$(git rev-parse --abbrev-ref HEAD)\`)"
else
  echo "- **Current HEAD**: \`UNCOMMITTED\`"
fi
echo ""

echo "## 2. Directory & File Tree"
find . -maxdepth 3 \
  -not -path '*/.git*' \
  -not -path '*/node_modules*' \
  -not -path '*/.venv*' \
  -not -path '*/__pycache__*' \
  -not -path '*/dist*' \
  -not -path '*/build*' \
  | sort
echo ""

echo "## 3. Manifest Files Detected"
find . -maxdepth 3 \( \
  -name "package.json" -o -name "pyproject.toml" -o -name "requirements.txt" \
  -o -name "go.mod" -o -name "Cargo.toml" -o -name "composer.json" \
  -o -name "Gemfile" -o -name "pom.xml" -o -name "Makefile" \
\) -not -path '*/node_modules*' | sort
