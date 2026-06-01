import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pathspec


ALWAYS_IGNORE = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", "env",
    "dist", "build", ".next", ".nuxt", "coverage", ".pytest_cache",
    ".mypy_cache", ".ruff_cache",
}


@dataclass
class ProjectContext:
    root: str
    file_tree: list[str]
    stack: dict  # { "language": str, "manifest": str|None, "deps": list[str] }
    git_log: list[dict]  # [{ "hash", "author", "date", "message" }]
    recent_changed_files: list[str]
    existing_rules: str | None


def build_file_tree(root: Path, max_files: int = 200) -> list[str]:
    """Build a file tree respecting .gitignore patterns."""
    gitignore_path = root / ".gitignore"
    spec = None
    if gitignore_path.exists():
        with open(gitignore_path, "r", encoding="utf-8") as f:
            spec = pathspec.PathSpec.from_lines("gitwildmatch", f.readlines())

    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        # Prune directories in-place
        dirnames[:] = [
            d for d in dirnames
            if d not in ALWAYS_IGNORE and
            (spec is None or not spec.match_file(os.path.join(dirpath, d)))
        ]

        for filename in filenames:
            full_path = os.path.join(dirpath, filename)
            rel_path = os.path.relpath(full_path, root)
            if spec is None or not spec.match_file(rel_path):
                files.append(rel_path.replace("\\", "/"))

    return sorted(files)[:max_files]


def detect_stack(root: Path, file_tree: list[str]) -> dict:
    """Detect the tech stack from manifest files and file extensions."""
    manifest_files = {
        "package.json": "javascript",
        "requirements.txt": "python",
        "pyproject.toml": "python",
        "Cargo.toml": "rust",
        "go.mod": "go",
    }

    manifest = None
    language = None
    deps = []

    for filename, lang in manifest_files.items():
        manifest_path = root / filename
        if manifest_path.exists():
            manifest = filename
            language = lang
            break

    if manifest == "package.json":
        import json
        with open(root / manifest, "r", encoding="utf-8") as f:
            data = json.load(f)
            deps = list(data.get("dependencies", {}).keys()) + list(data.get("devDependencies", {}).keys())
        # Check for TypeScript
        if any(f.endswith((".ts", ".tsx")) for f in file_tree):
            language = "typescript"

    elif manifest == "requirements.txt":
        with open(root / manifest, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    pkg = line.split("==")[0].split(">=")[0].split("<=")[0].strip()
                    if pkg:
                        deps.append(pkg)

    elif manifest == "pyproject.toml":
        with open(root / manifest, "r", encoding="utf-8") as f:
            in_deps = False
            for line in f:
                line = line.strip()
                if line.startswith("[dependencies]"):
                    in_deps = True
                elif line.startswith("["):
                    in_deps = False
                elif in_deps and line and not line.startswith("#"):
                    pkg = line.split("=")[0].strip()
                    if pkg:
                        deps.append(pkg)

    # Fallback: detect from file extensions
    if not language:
        ext_counts = {}
        for f in file_tree:
            ext = f.split(".")[-1] if "." in f else ""
            ext_counts[ext] = ext_counts.get(ext, 0) + 1
        if ext_counts:
            dominant = max(ext_counts, key=ext_counts.get)
            lang_map = {
                "py": "python",
                "js": "javascript",
                "ts": "typescript",
                "tsx": "typescript",
                "jsx": "javascript",
                "go": "go",
                "rs": "rust",
                "java": "java",
                "kt": "kotlin",
                "cs": "csharp",
            }
            language = lang_map.get(dominant, dominant)

    return {
        "language": language or "unknown",
        "manifest": manifest,
        "deps": deps,
    }


def read_git_log(root: Path, max_commits: int = 20) -> list[dict]:
    """Read git log history."""
    try:
        result = subprocess.run(
            ["git", "log", f"--max-count={max_commits}", "--pretty=format:%H|%an|%ad|%s", "--date=short"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return []

        commits = []
        for line in result.stdout.strip().split("\n"):
            if line:
                parts = line.split("|", 3)
                if len(parts) == 4:
                    commits.append({
                        "hash": parts[0],
                        "author": parts[1],
                        "date": parts[2],
                        "message": parts[3],
                    })
        return commits
    except Exception:
        return []


def read_recent_changed_files(root: Path, max_files: int = 15) -> list[str]:
    """Read recently changed files from git diff."""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD~5", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return []

        files = [f.strip().replace("\\", "/") for f in result.stdout.strip().split("\n") if f.strip()]
        return files[:max_files]
    except Exception:
        return []


def find_existing_rules(root: Path) -> str | None:
    """Find existing rules file in the project."""
    rule_files = [
        ".cursorrules",
        ".windsurfrules",
        "CLAUDE.md",
        ".context.md",
    ]
    for filename in rule_files:
        path = root / filename
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
    return None


def analyse(project_path: str) -> ProjectContext:
    """Analyze a project and return context."""
    root = Path(project_path)
    if not root.exists() or not root.is_dir():
        raise ValueError(f"Path does not exist or is not a directory: {project_path}")

    file_tree = build_file_tree(root)
    stack = detect_stack(root, file_tree)
    git_log = read_git_log(root)
    recent_changed_files = read_recent_changed_files(root)
    existing_rules = find_existing_rules(root)

    return ProjectContext(
        root=str(root),
        file_tree=file_tree,
        stack=stack,
        git_log=git_log,
        recent_changed_files=recent_changed_files,
        existing_rules=existing_rules,
    )
