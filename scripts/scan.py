#!/usr/bin/env python3
"""
repo-onboarding: Language-agnostic structural discovery helper (scan.py).

Performs a fast, zero-dependency structural discovery pass on a repository (or
a subset of directories during incremental updates) and emits raw, structured
findings (JSON or human-readable report) with exact file:line citations for the
agent to synthesize into `.claude/repo-map/`:
  - architecture.md
  - modules.md
  - entry-points.md
  - conventions.md
  - index.json

Design philosophy:
  This script is intentionally a thin discovery helper, NOT a black box that
  writes the markdown maps itself. It collects verifiable evidence (directory
  topology, manifest declarations, entry-point candidates with line numbers,
  and concrete file:line convention samples) so the agent can synthesize
  high-signal documentation grounded in actual code.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

IGNORE_DIRS: Set[str] = {
    ".git",
    ".hg",
    ".svn",
    ".claude",
    "node_modules",
    "vendor",
    "bower_components",
    "target",
    "dist",
    "build",
    "out",
    ".next",
    ".nuxt",
    ".svelte-kit",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    "coverage",
    ".nyc_output",
    ".idea",
    ".vscode",
    ".terraform",
    ".gradle",
    "Pods",
}

IGNORE_EXTENSIONS: Set[str] = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".svg", ".bmp",
    ".mp3", ".mp4", ".wav", ".avi", ".mov", ".mkv",
    ".zip", ".tar", ".gz", ".tgz", ".bz2", ".xz", ".7z", ".rar",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".pyc", ".pyo", ".pyd", ".so", ".dll", ".dylib", ".exe", ".bin", ".o", ".a",
    ".class", ".jar", ".war", ".ear",
    ".woff", ".woff2", ".ttf", ".eot", ".otf",
    ".db", ".sqlite", ".sqlite3", ".lock", ".min.js", ".min.css", ".map",
}

LANGUAGE_BY_EXT: Dict[str, str] = {
    ".py": "Python",
    ".js": "JavaScript",
    ".mjs": "JavaScript",
    ".cjs": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript (React)",
    ".jsx": "JavaScript (React)",
    ".go": "Go",
    ".rs": "Rust",
    ".java": "Java",
    ".kt": "Kotlin",
    ".rb": "Ruby",
    ".php": "PHP",
    ".cs": "C#",
    ".c": "C",
    ".h": "C/C++ Header",
    ".cpp": "C++",
    ".cc": "C++",
    ".hpp": "C++ Header",
    ".swift": "Swift",
    ".scala": "Scala",
    ".ex": "Elixir",
    ".exs": "Elixir",
    ".sh": "Shell",
    ".bash": "Shell",
    ".zsh": "Shell",
    ".sql": "SQL",
    ".graphql": "GraphQL",
    ".proto": "Protocol Buffers",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".toml": "TOML",
    ".json": "JSON",
    ".md": "Markdown",
}

MANIFEST_FILES: Set[str] = {
    "package.json",
    "go.mod",
    "pyproject.toml",
    "requirements.txt",
    "setup.py",
    "Pipfile",
    "Cargo.toml",
    "composer.json",
    "Gemfile",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "Makefile",
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
}

ENTRYPOINT_FILENAME_PATTERNS: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"^(main|index|app|server|cli|manage|wsgi|asgi)\.(py|js|ts|tsx|go|rs|rb|php|java|kt)$"), "Standard entry file"),
    (re.compile(r"^cmd/.+/main\.go$"), "Go command binary entrypoint"),
    (re.compile(r"^src/(main|index|app|server|cli)\.(py|js|ts|tsx|rs|go|rb)$"), "Source root entry file"),
    (re.compile(r"^src/bin/.+\.rs$"), "Rust binary target"),
    (re.compile(r"^bin/.+$"), "Executable script in bin/"),
    (re.compile(r"(routes|router|urls|controllers|endpoints|views|handlers)\.(py|js|ts|go|rb|php)$"), "Route / handler definition file"),
    (re.compile(r"(tasks|jobs|worker|cron|scheduler|consumers)\.(py|js|ts|go|rb)$"), "Background job / worker definition"),
]

CODE_ENTRYPOINT_PATTERNS: List[Tuple[str, re.Pattern]] = [
    ("Python __main__ guard", re.compile(r'^\s*if\s+__name__\s*==\s*[\'"]__main__[\'"]\s*:')),
    ("Go/Rust/C/Java main()", re.compile(r'^\s*(func\s+main\s*\(| pub\s+fn\s+main\s*\(|fn\s+main\s*\(|public\s+static\s+void\s+main\s*\()')),
    ("CLI parser / command registration", re.compile(r'(argparse\.ArgumentParser|click\.(command|group)|typer\.Typer|cobra\.Command|Commander|yargs|\.command\s*\()')),
    ("HTTP server / app initialization", re.compile(r'(FastAPI\s*\(|Flask\s*\(|express\s*\(|http\.ListenAndServe|gin\.(Default|New)| echo\.New\s*\(| NestFactory\.create|createServer\s*\()')),
    ("HTTP route registration", re.compile(r'(@(app|router|bp|api)\.(get|post|put|delete|patch|route)\s*\(|(app|router)\.(get|post|put|delete|patch|use)\s*\(|http\.HandleFunc\s*\(|path\s*\(\s*[\'"][^\'"]+[\'"])')),
    ("Job scheduler / worker registration", re.compile(r'(@(celery|app|scheduler)\.(task|scheduled_job|job)|cron\.schedule\s*\(|setInterval\s*\(|Queue\s*\()')),
]

CONVENTION_PROBES: Dict[str, List[Tuple[str, re.Pattern]]] = {
    "error_handling": [
        ("Custom error/exception class", re.compile(r'^\s*(class\s+\w*(Error|Exception)\b|type\s+\w*Error\s+struct|enum\s+\w*Error\b)')),
        ("Try / catch / except block", re.compile(r'^\s*(try\s*[:{]|except\s+\w+|catch\s*\()')),
        ("Go explicit error check / wrapping", re.compile(r'(if\s+err\s*!=\s*nil|fmt\.Errorf\([^)]*%w|errors\.(New|Is|As|Wrap))')),
        ("Rust Result / ? propagation / map_err", re.compile(r'(\.map_err\s*\(|anyhow!|bail!|thiserror)')),
        ("HTTP error / middleware handler", re.compile(r'(HTTPException|status\s*\(\s*[45]\d\d\s*\)|res\.status\([45]\d\d\)|abort\([45]\d\d\))')),
    ],
    "logging": [
        ("Logger initialization", re.compile(r'(logging\.getLogger|structlog\.get_logger|winston\.createLogger|pino\s*\(|slog\.(New|Default)|zap\.(New|L\b)|tracing::| LoggerFactory\.getLogger)')),
        ("Structured / leveled log call", re.compile(r'\b(logger|log|slog|tracing)\.(debug|info|warn|warning|error|critical|fatal|Info|Error|Warn|Debug)\s*\(')),
    ],
    "testing": [
        ("Test function / suite definition", re.compile(r'^\s*(def\s+test_\w+|async\s+def\s+test_\w+|func\s+Test\w+\s*\(|#\[(tokio::)?test\]|\b(describe|it|test)\s*\(\s*[\'"`])')),
        ("Fixture / mock / setup pattern", re.compile(r'(@pytest\.fixture|beforeEach\s*\(|afterEach\s*\(|unittest\.mock|jest\.mock|vi\.mock|gomock)')),
    ],
    "imports_and_modules": [
        ("Module import / export statement", re.compile(r'^\s*(from\s+[\w.]+\s+import\s+|import\s+[\w.{*\s,]+\s+from\s+[\'"`]|const\s+\w+\s*=\s*require\(|use\s+[\w:]+;|package\s+\w+)')),
    ],
    "configuration_and_env": [
        ("Environment variable access", re.compile(r'(os\.(environ|getenv)|process\.env\.\w+|os\.Getenv\(|std::env::var|dotenv|BaseSettings)')),
    ],
}


def run_git_cmd(repo_root: Path, args: List[str]) -> Optional[str]:
    """Run a git command safely and return stripped stdout, or None on failure."""
    try:
        res = subprocess.run(
            ["git", "-C", str(repo_root)] + args,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if res.returncode == 0:
            return res.stdout.strip()
        return None
    except Exception:
        return None


def get_git_metadata(repo_root: Path) -> Dict[str, Any]:
    """Retrieve current HEAD commit, branch, and working-tree status."""
    head_hash = run_git_cmd(repo_root, ["rev-parse", "HEAD"])
    short_hash = run_git_cmd(repo_root, ["rev-parse", "--short", "HEAD"])
    branch = run_git_cmd(repo_root, ["rev-parse", "--abbrev-ref", "HEAD"])
    status_porcelain = run_git_cmd(repo_root, ["status", "--porcelain"])
    dirty_files = [
        line[3:].strip()
        for line in (status_porcelain.splitlines() if status_porcelain else [])
        if line.strip()
    ]
    return {
        "is_git_repo": head_hash is not None,
        "head_commit": head_hash or "UNCOMMITTED",
        "short_commit": short_hash or "UNCOMMITTED",
        "branch": branch or "unknown",
        "is_dirty": len(dirty_files) > 0,
        "dirty_file_count": len(dirty_files),
        "dirty_files_sample": dirty_files[:20],
    }


def is_ignored_path(rel_parts: Tuple[str, ...]) -> bool:
    for part in rel_parts:
        if part in IGNORE_DIRS or (part.startswith(".") and part not in {".github", ".env.example"}):
            return True
    return False


def is_test_file(rel_path: str) -> bool:
    name = os.path.basename(rel_path).lower()
    parts = [p.lower() for p in Path(rel_path).parts]
    if any(p in {"test", "tests", "__tests__", "spec", "specs", "e2e"} for p in parts):
        return True
    if (
        name.startswith("test_")
        or name.endswith("_test.py")
        or name.endswith("_test.go")
        or name.endswith(".test.js")
        or name.endswith(".test.ts")
        or name.endswith(".test.tsx")
        or name.endswith(".spec.js")
        or name.endswith(".spec.ts")
        or name.endswith(".spec.tsx")
        or name.endswith("_spec.rb")
    ):
        return True
    return False


def walk_repository(
    repo_root: Path, target_subpaths: Optional[List[str]] = None
) -> List[Path]:
    """Return sorted list of relative file paths under repo_root (or target_subpaths)."""
    collected: List[Path] = []
    roots_to_walk: List[Path] = []
    if target_subpaths:
        for sp in target_subpaths:
            candidate = (repo_root / sp).resolve()
            if candidate.exists():
                roots_to_walk.append(candidate)
    else:
        roots_to_walk.append(repo_root)

    seen: Set[Path] = set()
    for start_path in roots_to_walk:
        if start_path.is_file():
            rel = start_path.relative_to(repo_root)
            if not is_ignored_path(rel.parts) and rel not in seen:
                seen.add(rel)
                collected.append(rel)
            continue

        for root, dirs, files in os.walk(start_path):
            rel_root = Path(root).relative_to(repo_root)
            dirs[:] = sorted(
                d
                for d in dirs
                if d not in IGNORE_DIRS
                and not (d.startswith(".") and d not in {".github"})
            )
            if rel_root != Path(".") and is_ignored_path(rel_root.parts):
                continue
            for fname in sorted(files):
                rel_file = rel_root / fname if rel_root != Path(".") else Path(fname)
                if rel_file in seen:
                    continue
                if any( str(rel_file).endswith(ext) for ext in IGNORE_EXTENSIONS ):
                    continue
                seen.add(rel_file)
                collected.append(rel_file)

    return sorted(collected)


def parse_package_json(path: Path, rel_path: str) -> Dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception as exc:
        return {"file": rel_path, "type": "npm/node (package.json)", "error": str(exc)}

    deps = list((data.get("dependencies") or {}).keys())
    dev_deps = list((data.get("devDependencies") or {}).keys())
    scripts = data.get("scripts") or {}
    entry_fields: Dict[str, Any] = {}
    for k in ("main", "module", "types", "bin", "exports"):
        if k in data:
            entry_fields[k] = data[k]

    return {
        "file": rel_path,
        "type": "npm/node (package.json)",
        "name": data.get("name"),
        "version": data.get("version"),
        "description": data.get("description"),
        "entry_fields": entry_fields,
        "scripts": scripts,
        "dependencies": deps[:40],
        "dev_dependencies": dev_deps[:30],
    }


def parse_pyproject_toml(path: Path, rel_path: str) -> Dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="replace")
    name_match = re.search(r'^\s*name\s*=\s*[\'"]([^\'"]+)[\'"]', text, re.M)
    desc_match = re.search(r'^\s*description\s*=\s*[\'"]([^\'"]+)[\'"]', text, re.M)
    scripts: Dict[str, str] = {}
    in_scripts = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            sec = stripped[1:-1].strip()
            in_scripts = sec in {
                "project.scripts",
                "tool.poetry.scripts",
                "project.gui-scripts",
            }
            continue
        if in_scripts and "=" in stripped and not stripped.startswith("#"):
            k, v = stripped.split("=", 1)
            scripts[k.strip()] = v.strip().strip("\"'")

    deps: List[str] = []
    dep_block = re.search(r"dependencies\s*=\s*\[(.*?)\]", text, re.S)
    if dep_block:
        for item in re.findall(r'[\'"]([^\'"]+)[\'"]', dep_block.group(1)):
            deps.append(item)

    return {
        "file": rel_path,
        "type": "Python (pyproject.toml)",
        "name": name_match.group(1) if name_match else None,
        "description": desc_match.group(1) if desc_match else None,
        "scripts": scripts,
        "dependencies": deps[:40],
    }


def parse_requirements_txt(path: Path, rel_path: str) -> Dict[str, Any]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    deps = []
    for line in lines:
        s = line.strip()
        if s and not s.startswith("#") and not s.startswith("-"):
            deps.append(s)
    return {
        "file": rel_path,
        "type": "Python (requirements.txt)",
        "dependencies": deps[:50],
    }


def parse_go_mod(path: Path, rel_path: str) -> Dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="replace")
    mod_match = re.search(r"^\s*module\s+(\S+)", text, re.M)
    go_ver = re.search(r"^\s*go\s+(\S+)", text, re.M)
    deps: List[str] = []
    for line in text.splitlines():
        s = line.strip()
        if s and not s.startswith(("module ", "go ", "require", ")", "//", "replace", "exclude")):
            parts = s.split()
            if len(parts) >= 2 and "/" in parts[0]:
                deps.append(f"{parts[0]} {parts[1]}")
    return {
        "file": rel_path,
        "type": "Go (go.mod)",
        "module": mod_match.group(1) if mod_match else None,
        "go_version": go_ver.group(1) if go_ver else None,
        "dependencies": deps[:40],
    }


def parse_cargo_toml(path: Path, rel_path: str) -> Dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="replace")
    name_match = re.search(r'^\s*name\s*=\s*[\'"]([^\'"]+)[\'"]', text, re.M)
    bins = re.findall(r"\[\[bin\]\].*?name\s*=\s*[\'\"]([^\'\"]+)[\'\"]", text, re.S)
    deps: List[str] = []
    in_deps = False
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("[") and s.endswith("]"):
            in_deps = s[1:-1].strip() in {"dependencies", "dev-dependencies", "workspace.dependencies"}
            continue
        if in_deps and "=" in s and not s.startswith("#"):
            deps.append(s.split("=", 1)[0].strip())
    return {
        "file": rel_path,
        "type": "Rust (Cargo.toml)",
        "name": name_match.group(1) if name_match else None,
        "bins": bins,
        "dependencies": deps[:40],
    }


def parse_Makefile(path: Path, rel_path: str) -> Dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="replace")
    targets: List[Dict[str, Any]] = []
    for idx, line in enumerate(text.splitlines(), start=1):
        m = re.match(r"^([a-zA-Z0-9_-]+)\s*:(?!=)", line)
        if m and not m.group(1).startswith("."):
            targets.append({"target": m.group(1), "line": idx})
    return {
        "file": rel_path,
        "type": "Makefile",
        "targets": targets[:30],
    }


def parse_manifests(repo_root: Path, rel_files: List[Path]) -> List[Dict[str, Any]]:
    manifests: List[Dict[str, Any]] = []
    for rel in rel_files:
        fname = rel.name
        if fname not in MANIFEST_FILES:
            continue
        full = repo_root / rel
        rel_str = str(rel)
        if fname == "package.json":
            manifests.append(parse_package_json(full, rel_str))
        elif fname == "pyproject.toml":
            manifests.append(parse_pyproject_toml(full, rel_str))
        elif fname == "requirements.txt":
            manifests.append(parse_requirements_txt(full, rel_str))
        elif fname == "go.mod":
            manifests.append(parse_go_mod(full, rel_str))
        elif fname == "Cargo.toml":
            manifests.append(parse_cargo_toml(full, rel_str))
        elif fname == "Makefile":
            manifests.append(parse_Makefile(full, rel_str))
        else:
            manifests.append({"file": rel_str, "type": fname})
    return manifests


def extract_file_summary_and_symbols(
    full_path: Path, rel_str: str
) -> Dict[str, Any]:
    """Read a source file to extract top docstring/comment, key symbols, imports, and line count."""
    try:
        text = full_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return {"file": rel_str, "line_count": 0, "symbols": [], "imports": []}

    lines = text.splitlines()
    line_count = len(lines)
    symbols: List[Dict[str, Any]] = []
    imports: List[str] = []
    doc_hint: Optional[str] = None

    # Check first 20 lines for module docstring or leading comment
    for line in lines[:20]:
        s = line.strip()
        if not s or s.startswith("#!"):
            continue
        if s.startswith(('"""', "'''", "//", "/*", "#")):
            cleaned = s.strip("\"'/*# ").strip()
            if len(cleaned) > 8:
                doc_hint = cleaned[:140]
                break

    sym_patterns = [
        ("class", re.compile(r"^\s*(?:export\s+)?(?:abstract\s+)?class\s+([A-Za-z_]\w*)")),
        ("function", re.compile(r"^\s*(?:export\s+)?(?:async\s+)?(?:def|function|fn| pub\s+fn|func)\s+([A-Za-z_]\w*)")),
        ("struct/interface", re.compile(r"^\s*(?:export\s+)?(?:type|interface|struct|enum)\s+([A-Za-z_]\w*)")),
    ]
    import_re = re.compile(
        r"^\s*(?:from\s+([\w.]+)\s+import|import\s+([\w.]+)|import\s+.*?\s+from\s+['\"]([^'\"]+)['\"]|const\s+.*?=\s*require\(['\"]([^'\"]+)['\"]\)|use\s+([\w:]+))"
    )

    for idx, line in enumerate(lines, start=1):
        if len(symbols) < 15:
            for kind, pat in sym_patterns:
                m = pat.match(line)
                if m:
                    symbols.append({"name": m.group(1), "kind": kind, "line": idx})
                    break
        if len(imports) < 20:
            im = import_re.match(line)
            if im:
                target = next((g for g in im.groups() if g), None)
                if target and target not in imports:
                    imports.append(target)

    return {
        "file": rel_str,
        "line_count": line_count,
        "doc_hint": doc_hint,
        "symbols": symbols,
        "imports": imports,
    }


def scan_entrypoints_and_conventions(
    repo_root: Path, rel_files: List[Path]
) -> Tuple[List[Dict[str, Any]], Dict[str, List[Dict[str, Any]]], Dict[str, Any]]:
    entrypoints: List[Dict[str, Any]] = []
    conventions: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    naming_stats = {
        "snake_case_files": 0,
        "kebab_case_files": 0,
        "camel_or_pascal_files": 0,
        "test_files": [],
    }

    for rel in rel_files:
        rel_str = str(rel)
        stem = rel.stem
        if "_" in stem and stem == stem.lower():
            naming_stats["snake_case_files"] += 1
        elif "-" in stem and stem == stem.lower():
            naming_stats["kebab_case_files"] += 1
        elif any(c.isupper() for c in stem):
            naming_stats["camel_or_pascal_files"] += 1

        if is_test_file(rel_str):
            if len(naming_stats["test_files"]) < 25:
                naming_stats["test_files"].append(rel_str)

        # Check filename-based entrypoint candidates
        file_ep_reason = None
        for pat, reason in ENTRYPOINT_FILENAME_PATTERNS:
            if pat.search(rel_str) or pat.search(rel.name):
                file_ep_reason = reason
                break

        ext = rel.suffix.lower()
        if ext not in LANGUAGE_BY_EXT and not file_ep_reason:
            continue

        full_path = repo_root / rel
        try:
            lines = full_path.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception:
            continue

        matched_ep_in_file = False
        for idx, line in enumerate(lines, start=1):
            for ep_kind, ep_pat in CODE_ENTRYPOINT_PATTERNS:
                if ep_pat.search(line):
                    entrypoints.append({
                        "file": rel_str,
                        "line": idx,
                        "ref": f"{rel_str}:{idx}",
                        "kind": ep_kind,
                        "snippet": line.strip()[:120],
                    })
                    matched_ep_in_file = True
                    break

            for category, probes in CONVENTION_PROBES.items():
                if len(conventions[category]) >= 18:
                    continue
                for label, probe_pat in probes:
                    if probe_pat.search(line):
                        conventions[category].append({
                            "pattern": label,
                            "file": rel_str,
                            "line": idx,
                            "ref": f"{rel_str}:{idx}",
                            "snippet": line.strip()[:120],
                        })
                        break

        if file_ep_reason and not matched_ep_in_file:
            entrypoints.append({
                "file": rel_str,
                "line": 1,
                "ref": f"{rel_str}:1",
                "kind": file_ep_reason,
                "snippet": lines[0].strip()[:120] if lines else "(empty file)",
            })

    return entrypoints, dict(conventions), naming_stats


def summarize_modules(
    repo_root: Path, rel_files: List[Path]
) -> Tuple[List[Dict[str, Any]], Dict[str, List[str]]]:
    """Group files by logical module/directory and build a candidate topic->files index."""
    dir_groups: Dict[str, List[Path]] = defaultdict(list)
    for rel in rel_files:
        parts = rel.parts
        if len(parts) == 1:
            dir_key = "."
        elif len(parts) >= 3 and parts[0] in {"src", "lib", "pkg", "internal", "cmd", "app", "packages", "apps"}:
            dir_key = f"{parts[0]}/{parts[1]}"
        else:
            dir_key = parts[0]
        dir_groups[dir_key].append(rel)

    modules_summary: List[Dict[str, Any]] = []
    topic_index: Dict[str, List[str]] = defaultdict(list)

    for mod_key in sorted(dir_groups.keys()):
        files = dir_groups[mod_key]
        lang_counts: Counter = Counter()
        key_files_info: List[Dict[str, Any]] = []
        internal_imports: Set[str] = set()

        for f in files:
            ext = f.suffix.lower()
            if ext in LANGUAGE_BY_EXT:
                lang_counts[LANGUAGE_BY_EXT[ext]] += 1
            if len(key_files_info) < 10 and ext in LANGUAGE_BY_EXT:
                info = extract_file_summary_and_symbols(repo_root / f, str(f))
                key_files_info.append(info)
                for imp in info["imports"]:
                    internal_imports.add(imp)

        modules_summary.append({
            "module": mod_key,
            "file_count": len(files),
            "languages": dict(lang_counts),
            "files": [str(f) for f in files[:30]],
            "key_files": key_files_info,
            "observed_imports": sorted(internal_imports)[:25],
        })

        topic_name = mod_key if mod_key != "." else "root"
        topic_index[topic_name] = [str(f) for f in files]

    return modules_summary, dict(topic_index)


def build_report(
    repo_root: Path, target_subpaths: Optional[List[str]] = None
) -> Dict[str, Any]:
    git_meta = get_git_metadata(repo_root)
    rel_files = walk_repository(repo_root, target_subpaths)

    lang_breakdown: Counter = Counter()
    for rel in rel_files:
        ext = rel.suffix.lower()
        if ext in LANGUAGE_BY_EXT:
            lang_breakdown[LANGUAGE_BY_EXT[ext]] += 1

    manifests = parse_manifests(repo_root, rel_files)
    entrypoints, conventions, naming_stats = scan_entrypoints_and_conventions(
        repo_root, rel_files
    )
    modules_summary, candidate_index = summarize_modules(repo_root, rel_files)

    return {
        "repo_root": str(repo_root),
        "scanned_subpaths": target_subpaths or ["."],
        "git": git_meta,
        "total_files_scanned": len(rel_files),
        "languages": dict(lang_breakdown.most_common()),
        "manifests": manifests,
        "modules": modules_summary,
        "entrypoints": entrypoints[:60],
        "conventions": conventions,
        "naming_and_tests": naming_stats,
        "candidate_topic_index": candidate_index,
    }


def format_markdown_report(report: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append("# Repository Structural Discovery Report")
    lines.append("")
    git = report["git"]
    lines.append("## 1. Git & Repository Metadata")
    lines.append(f"- **Repo Root**: `{report['repo_root']}`")
    lines.append(f"- **Current HEAD**: `{git['head_commit']}` (`{git['short_commit']}` on branch `{git['branch']}`)")
    lines.append(f"- **Working Tree Dirty**: `{git['is_dirty']}` ({git['dirty_file_count']} uncommitted/modified files)")
    lines.append(f"- **Total Files Scanned**: {report['total_files_scanned']}")
    langs = ", ".join(f"{k} ({v})" for k, v in report["languages"].items()) or "None detected"
    lines.append(f"- **Language Breakdown**: {langs}")
    lines.append("")

    lines.append("## 2. Manifests & Declared Scripts/Dependencies")
    if not report["manifests"]:
        lines.append("- No standard manifest files detected.")
    for m in report["manifests"]:
        lines.append(f"### `{m['file']}` ({m.get('type')})")
        if m.get("name"):
            lines.append(f"- **Package Name**: `{m['name']}`")
        if m.get("module"):
            lines.append(f"- **Go Module**: `{m['module']}`")
        if m.get("entry_fields"):
            lines.append(f"- **Entry Fields**: `{json.dumps(m['entry_fields'])}`")
        if m.get("scripts"):
            lines.append(f"- **Declared Scripts**: `{json.dumps(m['scripts'])}`")
        if m.get("targets"):
            t_str = ", ".join(f"`{t['target']}` (line {t['line']})" for t in m["targets"])
            lines.append(f"- **Make Targets**: {t_str}")
        if m.get("dependencies"):
            lines.append(f"- **Dependencies**: {', '.join(f'`{d}`' for d in m['dependencies'][:20])}")
    lines.append("")

    lines.append("## 3. Modules & Directory Topology")
    for mod in report["modules"]:
        lines.append(f"### Module `{mod['module']}` ({mod['file_count']} files)")
        if mod["observed_imports"]:
            lines.append(f"- **Observed Imports**: {', '.join(f'`{i}`' for i in mod['observed_imports'][:12])}")
        for kf in mod["key_files"]:
            sym_str = ", ".join(f"`{s['name']}` ({s['kind']} @ L{s['line']})" for s in kf["symbols"][:8])
            hint = f" — _{kf['doc_hint']}_" if kf.get("doc_hint") else ""
            lines.append(f"  - `{kf['file']}` ({kf['line_count']} lines){hint}")
            if sym_str:
                lines.append(f"    - Symbols: {sym_str}")
    lines.append("")

    lines.append("## 4. Detected Entry Points (`file:line`)")
    if not report["entrypoints"]:
        lines.append("- No explicit entry-point signatures matched.")
    for ep in report["entrypoints"]:
        lines.append(f"- `{ep['ref']}` [{ep['kind']}]: `{ep['snippet']}`")
    lines.append("")

    lines.append("## 5. Convention Evidence Samples (`file:line`)")
    ns = report["naming_and_tests"]
    lines.append(
        f"- **File Naming Counts**: snake_case={ns['snake_case_files']}, "
        f"kebab-case={ns['kebab_case_files']}, camel/PascalCase={ns['camel_or_pascal_files']}"
    )
    if ns["test_files"]:
        lines.append(f"- **Detected Test Files**: {', '.join(f'`{tf}`' for tf in ns['test_files'][:15])}")
    for cat, items in report["conventions"].items():
        lines.append(f"### Category: `{cat}`")
        for item in items[:10]:
            lines.append(f"- `{item['ref']}` ({item['pattern']}): `{item['snippet']}`")
    lines.append("")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run language-agnostic structural discovery for repo-onboarding."
    )
    parser.add_argument(
        "repo_dir",
        nargs="?",
        default=".",
        help="Path to the target repository root (default: current directory).",
    )
    parser.add_argument(
        "--paths",
        nargs="*",
        default=None,
        help="Optional list of relative directory/file paths for incremental rescanning.",
    )
    parser.add_argument(
        "--format",
        choices=["markdown", "json"],
        default="markdown",
        help="Output format: 'markdown' (default) or 'json'.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional file path to write discovery output.",
    )

    args = parser.parse_args()
    repo_root = Path(args.repo_dir).resolve()
    if not repo_root.exists() or not repo_root.is_dir():
        print(f"Error: target directory does not exist: {repo_root}", file=sys.stderr)
        return 1

    report = build_report(repo_root, args.paths)
    rendered = (
        json.dumps(report, indent=2)
        if args.format == "json"
        else format_markdown_report(report)
    )

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)

    return 0


if __name__ == "__main__":
    sys.exit(main())
