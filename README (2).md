# ContextForge

A desktop application that analyses your codebase and generates optimised context files for AI coding agents. Instead of starting every session with a blank-slate AI, ContextForge reads your project structure, git history, and dependencies — then writes a tight, task-specific rules file so your AI agent knows exactly what it is working with before it writes a single line.

Supports Cursor (`.cursorrules`), Windsurf (`.windsurfrules`), and Google Antigravity (`.antigravity/context.md`).

Runs as a standalone `.exe` — no Python installation required on the target machine.

---

## The problem this solves

When you use Windsurf, Cursor, or Antigravity, the AI agent has no memory of your project between sessions. You burn credits re-explaining context, the agent makes changes that break unrelated files, and you spend sessions correcting mistakes instead of shipping features.

ContextForge solves this by:
1. Analysing your repo before each session
2. Generating a rules file that tells the agent exactly what exists, what patterns to follow, and what not to break
3. Learning from your ratings over time — sessions that went well inform future context generation

---

## Project structure

```
contextforge/
├── core/
│   ├── __init__.py
│   ├── analyzer.py       # File tree, stack detection, git history reader
│   ├── generator.py      # Gemini API call — generates the rules content
│   ├── adapters.py       # Writes output to the correct file per IDE
│   └── storage.py        # SQLite — persists sessions and ratings
├── ui/
│   ├── __init__.py
│   ├── main_window.py    # QMainWindow — root window and layout
│   ├── pages/
│   │   ├── __init__.py
│   │   ├── generate_page.py   # Generate tab
│   │   ├── rate_page.py       # Rate tab
│   │   └── improve_page.py    # Improve tab
│   └── widgets/
│       ├── __init__.py
│       └── rules_viewer.py    # Reusable read-only text panel
├── assets/
│   └── icon.ico               # App icon for the .exe
├── main.py                    # Entry point — launches the Qt app
├── build.bat                  # One-click PyInstaller build script
└── pyproject.toml
```

---

## Tech stack

- **Python 3.10+**
- **PyQt6** — desktop GUI framework
- **pathspec** — `.gitignore`-aware file tree traversal
- **google-generativeai** — Gemini API for rules generation (free tier at aistudio.google.com)
- **SQLite** (stdlib) — local session storage
- **PyInstaller** — packages everything into a single `.exe`

---

## Dependencies

`pyproject.toml`:

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "contextforge"
version = "0.1.0"
description = "Generates optimised AI context files for Cursor, Windsurf, and Antigravity"
readme = "README.md"
requires-python = ">=3.10"
dependencies = [
    "PyQt6>=6.6.0",
    "pathspec>=0.12.0",
    "google-generativeai>=0.5.0",
    "pyinstaller>=6.0.0",
]

[project.scripts]
contextforge = "main:main"
```

---

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `GEMINI_API_KEY` | Yes | Free at [aistudio.google.com](https://aistudio.google.com) |

The app reads this from the system environment on launch. If it is not set, the app shows an inline error message in the Generate tab rather than crashing.

---

## Core module specifications

These five modules contain all business logic. They have zero Qt imports — they are pure Python and completely separate from the UI.

---

### `core/analyzer.py`

**Purpose:** Reads a project directory and returns a `ProjectContext` dataclass.

**`ProjectContext` dataclass:**
```python
@dataclass
class ProjectContext:
    root: str
    file_tree: list[str]
    stack: dict                   # { "language": str, "manifest": str|None, "deps": list[str] }
    git_log: list[dict]           # [{ "hash", "author", "date", "message" }]
    recent_changed_files: list[str]
    existing_rules: str | None
```

**`ALWAYS_IGNORE` set:**
```python
ALWAYS_IGNORE = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", "env",
    "dist", "build", ".next", ".nuxt", "coverage", ".pytest_cache",
    ".mypy_cache", ".ruff_cache",
}
```

**`build_file_tree(root: Path, max_files: int = 200) -> list[str]`**
- Load `.gitignore` using `pathspec.PathSpec.from_lines("gitwildmatch", patterns)`
- Walk with `os.walk`, pruning `dirnames` in-place: `dirnames[:] = [d for d in dirnames if d not in ALWAYS_IGNORE and not spec.match_file(...)]`
- Return sorted list of relative paths, capped at `max_files`

**`detect_stack(root: Path, file_tree: list[str]) -> dict`**
- Check manifest files in this order: `package.json`, `requirements.txt`, `pyproject.toml`, `Cargo.toml`, `go.mod`
- For `package.json`: parse JSON, merge `dependencies` + `devDependencies`, detect TypeScript if any `.ts`/`.tsx` in `file_tree`
- For `requirements.txt`: split each non-comment line on `==` and `>=` to extract package name
- For `pyproject.toml`: scan lines for the `dependencies` section, read until the next `[` header
- Fallback: count file extensions, map the dominant one to a language name
- Always return `{ "language": str, "manifest": str|None, "deps": list[str] }`

**`read_git_log(root: Path, max_commits: int = 20) -> list[dict]`**
- Run: `git log --max-count=N --pretty=format:"%H|%an|%ad|%s" --date=short`
- Use `subprocess.run(..., cwd=root, capture_output=True, text=True, timeout=10)`
- Split each output line on `|` with `maxsplit=3`, return list of dicts
- Return `[]` on any failure — git is optional

**`read_recent_changed_files(root: Path, max_files: int = 15) -> list[str]`**
- Run: `git diff --name-only HEAD~5 HEAD`
- Return `[]` on failure (new repos with fewer than 5 commits will fail)

**`find_existing_rules(root: Path) -> str | None`**
- Check in order: `.cursorrules`, `.windsurfrules`, `CLAUDE.md`, `.context.md`
- Return content of first found, or `None`

**`analyse(project_path: str) -> ProjectContext`**
- Calls all functions above, returns a `ProjectContext`
- Raises `ValueError` if path does not exist or is not a directory

---

### `core/generator.py`

**Purpose:** Calls Gemini API with the project context and task, returns the rules string.

**Setup:**
```python
import google.generativeai as genai
import os

def _get_model():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "GEMINI_API_KEY is not set. Get a free key at aistudio.google.com"
        )
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        system_instruction=SYSTEM_PROMPT
    )
```

**`SYSTEM_PROMPT` string:**
```
You are ContextForge, an expert at writing precise AI agent context files.
Your output is always terse, specific, and actionable.
You never write generic advice. Every line must reference something specific about the project given to you.
You write as if you are a senior engineer on the team briefing a new AI agent before a task.
```

**`_build_prompt(ctx: ProjectContext, task: str, ide: str) -> str`**

Build this string dynamically:
```
Analyse this project and generate a {ide} rules file for the task described below.

## Project overview
- Language: {ctx.stack["language"]}
- Manifest: {ctx.stack["manifest"] or "none"}
- Key dependencies: {", ".join(ctx.stack["deps"][:20]) or "none detected"}

## File structure
{chr(10).join(ctx.file_tree[:60])}
{"... and N more files" if len > 60}

## Recent git commits
{each commit as "  [date] message", max 8}

## Recently changed files
{chr(10).join(ctx.recent_changed_files) or "  None"}

{if ctx.existing_rules: "## Existing rules (improve on these)\n" + ctx.existing_rules[:1500]}

## Task the developer is about to do
{task}

---

Generate a {ide} rules file that:
1. Gives the AI agent ONLY the context it needs for this specific task — no generic advice
2. Lists the most relevant files it should read first before making changes
3. Calls out known patterns in this codebase the agent should follow (naming, structure, error handling)
4. Flags potential conflict zones — files likely to be affected that the agent must not break
5. States the tech stack constraints clearly (versions, frameworks, patterns already in use)
6. Is under 400 words — tight context beats verbose context

Do NOT include generic best practices. Output ONLY the rules file content. No preamble, no markdown fences.
```

**`generate(ctx: ProjectContext, task: str, ide: str = "Cursor") -> str`**
- Call `_get_model()`, then `model.generate_content(_build_prompt(ctx, task, ide))`
- Return `response.text.strip()`
- Let `EnvironmentError` propagate to the UI layer — do not catch it here

---

### `core/adapters.py`

**Purpose:** Writes the rules string to the correct filename for each IDE.

```python
IDE_CONFIG = {
    "cursor":      { "filename": ".cursorrules",            "display": "Cursor" },
    "windsurf":    { "filename": ".windsurfrules",          "display": "Windsurf" },
    "antigravity": { "filename": ".antigravity/context.md", "display": "Antigravity" },
}
```

**`write_rules(project_root, ide, content, task="", language="") -> str`**
- Resolve path, call `mkdir(parents=True, exist_ok=True)` on parent
- For Antigravity only, prepend:
  ```
  # Project context
  > Auto-generated by ContextForge
  > Task: {task}
  > Language: {language}

  ```
- Write file, return absolute path string

**`detect_ide(project_root: str) -> str | None`**
- Check for marker paths in this order:
  - `cursor`: `.cursorrules` or `.cursor/` directory
  - `windsurf`: `.windsurfrules` or `.windsurf/` directory
  - `antigravity`: `.antigravity/` directory
- Return the matching ide key, or `None`

---

### `core/storage.py`

**Purpose:** SQLite persistence at `~/.contextforge/sessions.db`.

**Schema:**
```sql
CREATE TABLE IF NOT EXISTS sessions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    project_path        TEXT NOT NULL,
    task_description    TEXT NOT NULL,
    ide                 TEXT NOT NULL,
    language            TEXT,
    context_snapshot    TEXT,
    generated_rules     TEXT,
    git_hash_before     TEXT,
    git_hash_after      TEXT,
    rating              INTEGER,
    timestamp           TEXT NOT NULL
)
```

**Functions:**

`init_db() -> None` — creates DB and table if missing. Call on every app launch.

`save_session(project_path, task, ide, language, context_snapshot: dict, generated_rules, git_hash_before) -> int` — inserts row, returns new `id`.

`rate_last_session(project_path, rating: int, git_hash_after) -> bool` — updates most recent unrated session for this project. Returns `True` if updated.

`get_project_sessions(project_path) -> list` — all rated sessions, newest first.

`get_patterns(project_path) -> dict` — requires 3+ rated sessions. Returns:
```python
{
    "total_sessions": int,
    "good_sessions": int,
    "bad_sessions": int,
    "common_good_task_keywords": list[str],  # top 10 words (>4 chars) from good tasks
    "ide_scores": { ide_key: { "good": int, "bad": int } }
}
```
Returns `{}` if fewer than 3 rated sessions exist.

---

## UI module specifications

The UI is a `QMainWindow` with a `QTabWidget` containing three tabs: Generate, Rate, Improve.

All long-running operations (analyse + API call) run in a `QThread` worker to keep the UI responsive. Never call `analyse()` or `generate()` on the main thread.

---

### `main.py`

Entry point:

```python
import sys
from PyQt6.QtWidgets import QApplication
from core.storage import init_db
from ui.main_window import MainWindow

def main():
    init_db()
    app = QApplication(sys.argv)
    app.setApplicationName("ContextForge")
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
```

---

### `ui/main_window.py`

**Class: `MainWindow(QMainWindow)`**

- Window title: `"ContextForge"`
- Minimum size: `800 x 560`
- Central widget: `QTabWidget` with three tabs added in order:
  1. `GeneratePage` — label `"Generate"`
  2. `RatePage` — label `"Rate"`
  3. `ImprovePage` — label `"Improve"`
- Status bar: `self.statusBar().showMessage("Ready")` on init

Apply this stylesheet to `QApplication` for a clean dark theme:
```python
DARK_STYLESHEET = """
QMainWindow, QWidget {
    background-color: #1e1e2e;
    color: #cdd6f4;
    font-family: 'Segoe UI', sans-serif;
    font-size: 13px;
}
QTabWidget::pane {
    border: 1px solid #313244;
    border-radius: 6px;
}
QTabBar::tab {
    background: #181825;
    color: #a6adc8;
    padding: 8px 20px;
    border-radius: 4px;
    margin-right: 2px;
}
QTabBar::tab:selected {
    background: #313244;
    color: #cdd6f4;
}
QLineEdit, QTextEdit, QPlainTextEdit {
    background-color: #181825;
    border: 1px solid #313244;
    border-radius: 6px;
    padding: 6px;
    color: #cdd6f4;
}
QPushButton {
    background-color: #89b4fa;
    color: #1e1e2e;
    border: none;
    border-radius: 6px;
    padding: 8px 18px;
    font-weight: bold;
}
QPushButton:hover { background-color: #b4d0ff; }
QPushButton:disabled { background-color: #45475a; color: #6c7086; }
QComboBox {
    background-color: #181825;
    border: 1px solid #313244;
    border-radius: 6px;
    padding: 6px;
    color: #cdd6f4;
}
QLabel { color: #cdd6f4; }
QLabel#label_hint { color: #6c7086; font-size: 11px; }
"""
```

Apply with `app.setStyleSheet(DARK_STYLESHEET)` in `main.py` before `window.show()`.

---

### `ui/pages/generate_page.py`

**Class: `GeneratePage(QWidget)`**

**Layout (top to bottom, use `QVBoxLayout`):**

1. `QLabel("Project folder")` + `QHBoxLayout` containing:
   - `QLineEdit` — `self.path_input`, placeholder `"Path to your project..."`
   - `QPushButton("Browse")` — opens `QFileDialog.getExistingDirectory`, sets `path_input` text

2. `QLabel("Target IDE")` + `QComboBox` — `self.ide_combo`
   - Items: `"Auto-detect"`, `"Cursor"`, `"Windsurf"`, `"Antigravity"`
   - On path input change: call `detect_ide(path)` and update combo selection if detected

3. `QLabel("What are you about to work on?")` + `QPlainTextEdit` — `self.task_input`
   - Placeholder: `"e.g. Add JWT authentication to the Flask API"`
   - Fixed height: 80px

4. `QPushButton("Generate rules file")` — `self.generate_btn`
   - On click: validate inputs, disable button, start `GenerateWorker` thread

5. `QLabel("")` — `self.status_label`, used for inline status/error messages
   - objectName: `"label_hint"`

6. `RulesViewer` widget — `self.rules_viewer` (see widgets spec)
   - Hidden initially, shown after successful generation

**`GenerateWorker(QThread)`** — defined in this file:
```python
class GenerateWorker(QThread):
    finished = pyqtSignal(str, str)   # (rules_content, output_path)
    error    = pyqtSignal(str)        # error message string

    def __init__(self, project_path, task, ide):
        ...

    def run(self):
        # 1. analyse(project_path)
        # 2. generate(ctx, task, ide_display_name)
        # 3. write_rules(...)
        # 4. save_session(...)
        # emit finished or error
```

On `finished`: update `status_label` with the output path, show `rules_viewer` with the content, re-enable button.
On `error`: show error message in `status_label` in red (`color: #f38ba8`), re-enable button.

---

### `ui/pages/rate_page.py`

**Class: `RatePage(QWidget)`**

**Layout:**

1. `QLabel("Project folder")` + path input row (same Browse pattern as GeneratePage) — `self.path_input`

2. `QLabel` — `self.session_label`
   - Shows the last unrated session for the entered path if one exists
   - Format: `"Last session: {task_description} ({ide}) — {timestamp}"`
   - Update this whenever `path_input` text changes (query `get_project_sessions` and filter `rating IS NULL`)

3. `QHBoxLayout` with two buttons side by side:
   - `QPushButton("✓  Good session")` — green background `#a6e3a1`, text `#1e1e2e`
   - `QPushButton("✗  Bad session")` — red background `#f38ba8`, text `#1e1e2e`

4. `QLabel("")` — `self.feedback_label` for confirmation messages

On good/bad click:
- Get current git HEAD via subprocess
- Call `rate_last_session(path, 1 or 0, git_hash)`
- Show confirmation in `feedback_label`
- Refresh `session_label` (should now show no unrated session)

---

### `ui/pages/improve_page.py`

**Class: `ImprovePage(QWidget)`**

**Layout:**

1. Path input row — same Browse pattern

2. `QPushButton("Load patterns")` — `self.load_btn`
   - On click: call `get_patterns(path)`, display result in `self.patterns_label`
   - If `{}` returned: show `"Not enough data yet — need 3+ rated sessions"`
   - If patterns found: show summary:
     ```
     Sessions: {total} total · {good} good · {bad} bad
     Keywords from successful sessions: {keywords joined by ", "}
     ```

3. `QLabel` — `self.patterns_label`

4. `QLabel("What are you about to work on?")` + `QPlainTextEdit` — `self.task_input`, 80px tall

5. `QPushButton("Regenerate with learned patterns")` — `self.improve_btn`
   - Disabled until patterns have been loaded and show data
   - On click: same worker pattern as GeneratePage, but passes enriched task string:
     `enriched = task + "\n\nLearned: successful tasks involved " + ", ".join(keywords[:5])`

6. `RulesViewer` — `self.rules_viewer`, hidden until generation completes

Use a separate `ImproveWorker(QThread)` — same structure as `GenerateWorker`.

---

### `ui/widgets/rules_viewer.py`

**Class: `RulesViewer(QWidget)`**

A reusable panel for displaying generated rules with a copy button.

**Layout (`QVBoxLayout`):**

1. `QHBoxLayout` header row:
   - `QLabel("Generated rules")` — bold
   - Spacer
   - `QPushButton("Copy")` — on click, copy `text_area` content to clipboard via `QApplication.clipboard().setText(...)`

2. `QPlainTextEdit` — `self.text_area`
   - Read-only: `setReadOnly(True)`
   - Monospace font: `QFont("Consolas", 10)` or `"Courier New"`
   - Minimum height: 200px

**Public method:**
```python
def set_content(self, text: str) -> None:
    self.text_area.setPlainText(text)
```

---

## Build script — `build.bat`

Create this file at the project root. Running it produces `dist/ContextForge.exe`.

```bat
@echo off
echo Building ContextForge.exe...

pip install pyinstaller --quiet

pyinstaller ^
    --onefile ^
    --windowed ^
    --name "ContextForge" ^
    --icon "assets/icon.ico" ^
    --add-data "assets;assets" ^
    main.py

echo.
echo Build complete. Executable is at dist/ContextForge.exe
pause
```

Flags explained:
- `--onefile` — single `.exe`, no folder of DLLs
- `--windowed` — no console window appears behind the GUI
- `--name` — output filename
- `--icon` — taskbar and window icon
- `--add-data` — bundles the assets folder into the exe

If `assets/icon.ico` does not exist, remove the `--icon` line to avoid a build error.

---

## Important implementation notes for Windsurf

1. **Never import PyQt6 in the `core/` modules.** All Qt code lives in `ui/`. The core modules are plain Python.

2. **All blocking operations go in `QThread` workers.** Calling `analyse()` or `generate()` on the main thread will freeze the UI. Use `GenerateWorker` and `ImproveWorker`.

3. **`GEMINI_API_KEY` error handling:** If the key is missing, `generator.py` raises `EnvironmentError`. The worker's `run()` method must catch this and emit it via the `error` signal with a message like: `"GEMINI_API_KEY not set. Get a free key at aistudio.google.com"`.

4. **`init_db()` is called once in `main.py`** before the window is shown. Do not call it anywhere else.

5. **`os.walk` directory pruning must be in-place:** `dirnames[:] = [...]` — not `dirnames = [...]`.

6. **Git commands are optional.** Wrap all subprocess git calls in `try/except` and return empty lists. The tool must work on non-git projects.

7. **SQLite `row_factory = sqlite3.Row`** must be set on every connection so rows can be accessed by column name.

8. **`detect_ide()` is called live** as the user types in the path field on GeneratePage. Debounce with a 300ms `QTimer` to avoid calling it on every keystroke.

9. **The `--windowed` PyInstaller flag** suppresses the terminal. Make sure all error messages surface in the UI — nothing should print to stdout/stderr silently.

10. **Test the `.exe` on a machine without Python installed** to catch any missing hidden imports. Common ones for google-generativeai: add `--hidden-import=google.generativeai` to the PyInstaller command if the exe crashes on launch.

---

## What Windsurf should build

Recreate every module exactly as specified. The full file list:

```
contextforge/
├── core/__init__.py
├── core/analyzer.py
├── core/generator.py
├── core/adapters.py
├── core/storage.py
├── ui/__init__.py
├── ui/main_window.py
├── ui/pages/__init__.py
├── ui/pages/generate_page.py
├── ui/pages/rate_page.py
├── ui/pages/improve_page.py
├── ui/widgets/__init__.py
├── ui/widgets/rules_viewer.py
├── assets/                     (create empty folder, add icon.ico if available)
├── main.py
├── build.bat
└── pyproject.toml
```

After generating all files:
```bash
pip install -e .
set GEMINI_API_KEY=your_key_here
python main.py
```

Verify the GUI opens with three tabs and the Generate tab can browse to a project folder. Once working, run `build.bat` to produce `dist/ContextForge.exe`.
