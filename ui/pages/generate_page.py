import subprocess

from PyQt6.QtCore import QThread, pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QPlainTextEdit, QFileDialog,
)

from core.analyzer import analyse
from core.adapters import detect_ide, write_rules, IDE_CONFIG
from core.generator import generate, EnvironmentError
from core.storage import save_session
from ui.widgets.rules_viewer import RulesViewer


class GenerateWorker(QThread):
    finished = pyqtSignal(str, str)  # (rules_content, output_path)
    error = pyqtSignal(str)  # error message

    def __init__(self, project_path, task, ide):
        super().__init__()
        self.project_path = project_path
        self.task = task
        self.ide = ide

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

            # Generate
            ide_display = IDE_CONFIG.get(self.ide.lower(), {}).get("display", "Cursor")
            rules = generate(ctx, self.task, ide_display)

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


class GeneratePage(QWidget):
    def __init__(self):
        super().__init__()
        self._setup_ui()
        self._setup_connections()

    def _setup_ui(self):
        layout = QVBoxLayout()

        # Project folder
        layout.addWidget(QLabel("Project folder"))
        path_layout = QHBoxLayout()
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("Path to your project...")
        browse_btn = QPushButton("Browse")
        path_layout.addWidget(self.path_input)
        path_layout.addWidget(browse_btn)
        layout.addLayout(path_layout)

        # Target IDE
        layout.addWidget(QLabel("Target IDE"))
        self.ide_combo = QComboBox()
        self.ide_combo.addItem("Auto-detect")
        self.ide_combo.addItem("Cursor")
        self.ide_combo.addItem("Windsurf")
        self.ide_combo.addItem("Antigravity")
        layout.addWidget(self.ide_combo)

        # Task input
        layout.addWidget(QLabel("What are you about to work on?"))
        self.task_input = QPlainTextEdit()
        self.task_input.setPlaceholderText("e.g. Add JWT authentication to the Flask API")
        self.task_input.setFixedHeight(80)
        layout.addWidget(self.task_input)

        # Generate button
        self.generate_btn = QPushButton("Generate rules file")
        layout.addWidget(self.generate_btn)

        # Status label
        self.status_label = QLabel("")
        self.status_label.setObjectName("label_hint")
        layout.addWidget(self.status_label)

        # Rules viewer
        self.rules_viewer = RulesViewer()
        self.rules_viewer.hide()
        layout.addWidget(self.rules_viewer)

        layout.addStretch()
        self.setLayout(layout)

    def _setup_connections(self):
        browse_btn.clicked.connect(self._browse_folder)
        self.generate_btn.clicked.connect(self._generate)

        # Debounce IDE detection
        self._debounce_timer = QTimer()
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.timeout.connect(self._detect_ide)
        self.path_input.textChanged.connect(self._debounce_timer.start)

    def _browse_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Select Project Folder")
        if path:
            self.path_input.setText(path)

    def _detect_ide(self):
        path = self.path_input.text()
        if path:
            detected = detect_ide(path)
            if detected:
                index = self.ide_combo.findText(detected.capitalize())
                if index >= 0:
                    self.ide_combo.setCurrentIndex(index)

    def _generate(self):
        path = self.path_input.text().strip()
        task = self.task_input.toPlainText().strip()
        ide = self.ide_combo.currentText().lower()

        if not path:
            self.status_label.setText("Please enter a project path")
            self.status_label.setStyleSheet("color: #f38ba8")
            return

        if not task:
            self.status_label.setText("Please describe what you're working on")
            self.status_label.setStyleSheet("color: #f38ba8")
            return

        if ide == "auto-detect":
            detected = detect_ide(path)
            if not detected:
                self.status_label.setText("Could not auto-detect IDE. Please select one manually.")
                self.status_label.setStyleSheet("color: #f38ba8")
                return
            ide = detected

        self.generate_btn.setEnabled(False)
        self.status_label.setText("Generating...")
        self.status_label.setStyleSheet("color: #cdd6f4")
        self.rules_viewer.hide()

        self.worker = GenerateWorker(path, task, ide)
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self._on_error)
        self.worker.start()

    def _on_finished(self, rules, output_path):
        self.generate_btn.setEnabled(True)
        self.status_label.setText(f"Rules written to: {output_path}")
        self.status_label.setStyleSheet("color: #a6e3a1")
        self.rules_viewer.set_content(rules)
        self.rules_viewer.show()

    def _on_error(self, error_msg):
        self.generate_btn.setEnabled(True)
        self.status_label.setText(error_msg)
        self.status_label.setStyleSheet("color: #f38ba8")
