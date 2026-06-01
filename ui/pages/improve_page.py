import subprocess

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFileDialog, QPlainTextEdit,
)

from core.analyzer import analyse
from core.adapters import write_rules, IDE_CONFIG
from core.generator import generate
from core.storage import save_session, get_patterns
from ui.widgets.rules_viewer import RulesViewer


class ImproveWorker(QThread):
    finished = pyqtSignal(str, str)  # (rules_content, output_path)
    error = pyqtSignal(str)  # error message

    def __init__(self, project_path, task, ide, keywords):
        super().__init__()
        self.project_path = project_path
        self.task = task
        self.ide = ide
        self.keywords = keywords

    def run(self):
        try:
            # Get git hash before
            git_hash_before = ""
            try:
                result = subprocess.run(
                    ["git", "rev-parse", "HEAD"],
                    cwd=self.project_path,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode == 0:
                    git_hash_before = result.stdout.strip()
            except Exception:
                pass

            # Analyse
            ctx = analyse(self.project_path)

            # Enrich task with learned patterns
            enriched_task = self.task
            if self.keywords:
                enriched_task += "\n\nLearned: successful tasks involved " + ", ".join(self.keywords[:5])

            # Generate
            ide_display = IDE_CONFIG.get(self.ide.lower(), {}).get("display", "Cursor")
            rules = generate(ctx, enriched_task, ide_display)

            # Write
            output_path = write_rules(
                self.project_path,
                self.ide,
                rules,
                self.task,
                ctx.stack["language"]
            )

            # Save session
            save_session(
                self.project_path,
                self.task,
                self.ide,
                ctx.stack["language"],
                {
                    "file_tree": ctx.file_tree,
                    "stack": ctx.stack,
                    "git_log": ctx.git_log,
                },
                rules,
                git_hash_before,
            )

            self.finished.emit(rules, output_path)
        except EnvironmentError as e:
            self.error.emit(str(e))
        except Exception as e:
            self.error.emit(f"Error: {str(e)}")


class ImprovePage(QWidget):
    def __init__(self):
        super().__init__()
        self._patterns = None
        self._setup_ui()
        self._setup_connections()

    def _setup_ui(self):
        layout = QVBoxLayout()

        # Project folder
        layout.addWidget(QLabel("Project folder"))
        path_layout = QHBoxLayout()
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("Path to your project...")
        self.browse_btn = QPushButton("Browse")
        path_layout.addWidget(self.path_input)
        path_layout.addWidget(self.browse_btn)
        layout.addLayout(path_layout)

        # Load patterns button
        self.load_btn = QPushButton("Load patterns")
        layout.addWidget(self.load_btn)

        # Patterns label
        self.patterns_label = QLabel("")
        self.patterns_label.setObjectName("label_hint")
        self.patterns_label.setWordWrap(True)
        layout.addWidget(self.patterns_label)

        # Task input
        layout.addWidget(QLabel("What are you about to work on?"))
        self.task_input = QPlainTextEdit()
        self.task_input.setPlaceholderText("e.g. Add JWT authentication to the Flask API")
        self.task_input.setFixedHeight(80)
        layout.addWidget(self.task_input)

        # Regenerate button
        self.improve_btn = QPushButton("Regenerate with learned patterns")
        self.improve_btn.setEnabled(False)
        layout.addWidget(self.improve_btn)

        # Rules viewer
        self.rules_viewer = RulesViewer()
        self.rules_viewer.hide()
        layout.addWidget(self.rules_viewer)

        layout.addStretch()
        self.setLayout(layout)

    def _setup_connections(self):
        self.browse_btn.clicked.connect(self._browse_folder)
        self.load_btn.clicked.connect(self._load_patterns)
        self.improve_btn.clicked.connect(self._regenerate)

    def _browse_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Select Project Folder")
        if path:
            self.path_input.setText(path)

    def _load_patterns(self):
        path = self.path_input.text().strip()
        if not path:
            self.patterns_label.setText("Please enter a project path")
            return

        patterns = get_patterns(path)
        if not patterns:
            self.patterns_label.setText("Not enough data yet — need 3+ rated sessions")
            self._patterns = None
            self.improve_btn.setEnabled(False)
            return

        self._patterns = patterns
        total = patterns["total_sessions"]
        good = patterns["good_sessions"]
        bad = patterns["bad_sessions"]
        keywords = patterns.get("common_good_task_keywords", [])

        self.patterns_label.setText(
            f"Sessions: {total} total · {good} good · {bad} bad\n"
            f"Keywords from successful sessions: {', '.join(keywords)}"
        )
        self.improve_btn.setEnabled(True)

    def _regenerate(self):
        path = self.path_input.text().strip()
        task = self.task_input.toPlainText().strip()

        if not path:
            self.patterns_label.setText("Please enter a project path")
            return

        if not task:
            self.patterns_label.setText("Please describe what you're working on")
            return

        if not self._patterns:
            self.patterns_label.setText("Please load patterns first")
            return

        # Use detected IDE or default to Cursor
        from core.adapters import detect_ide
        ide = detect_ide(path) or "cursor"
        keywords = self._patterns.get("common_good_task_keywords", [])

        self.improve_btn.setEnabled(False)
        self.rules_viewer.hide()

        self.worker = ImproveWorker(path, task, ide, keywords)
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self._on_error)
        self.worker.start()

    def _on_finished(self, rules, output_path):
        self.improve_btn.setEnabled(True)
        self.patterns_label.setText(f"Rules written to: {output_path}")
        self.rules_viewer.set_content(rules)
        self.rules_viewer.show()

    def _on_error(self, error_msg):
        self.improve_btn.setEnabled(True)
        self.patterns_label.setText(error_msg)
