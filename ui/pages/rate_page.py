import subprocess

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFileDialog,
)

from core.storage import get_project_sessions, rate_last_session


class RatePage(QWidget):
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

        # Session label
        self.session_label = QLabel("")
        layout.addWidget(self.session_label)

        # Rating buttons
        rating_layout = QHBoxLayout()
        self.good_btn = QPushButton("✓  Good session")
        self.good_btn.setStyleSheet("background-color: #a6e3a1; color: #1e1e2e;")
        self.bad_btn = QPushButton("✗  Bad session")
        self.bad_btn.setStyleSheet("background-color: #f38ba8; color: #1e1e2e;")
        rating_layout.addWidget(self.good_btn)
        rating_layout.addWidget(self.bad_btn)
        layout.addLayout(rating_layout)

        # Feedback label
        self.feedback_label = QLabel("")
        self.feedback_label.setObjectName("label_hint")
        layout.addWidget(self.feedback_label)

        layout.addStretch()
        self.setLayout(layout)

    def _setup_connections(self):
        browse_btn.clicked.connect(self._browse_folder)
        self.path_input.textChanged.connect(self._update_session_label)
        self.good_btn.clicked.connect(lambda: self._rate(1))
        self.bad_btn.clicked.connect(lambda: self._rate(0))

    def _browse_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Select Project Folder")
        if path:
            self.path_input.setText(path)

    def _update_session_label(self):
        path = self.path_input.text().strip()
        if not path:
            self.session_label.setText("")
            return

        sessions = get_project_sessions(path)
        # Find last unrated session
        unrated = [s for s in sessions if s.get("rating") is None]
        if unrated:
            session = unrated[0]
            ide = session.get("ide", "unknown")
            timestamp = session.get("timestamp", "")
            task = session.get("task_description", "unknown task")
            self.session_label.setText(f"Last session: {task} ({ide}) — {timestamp}")
        else:
            self.session_label.setText("No unrated sessions found")

    def _rate(self, rating):
        path = self.path_input.text().strip()
        if not path:
            self.feedback_label.setText("Please enter a project path")
            return

        # Get current git hash
        git_hash_after = ""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=path,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                git_hash_after = result.stdout.strip()
        except Exception:
            pass

        updated = rate_last_session(path, rating, git_hash_after)
        if updated:
            rating_text = "Good" if rating == 1 else "Bad"
            self.feedback_label.setText(f"Rated as {rating_text} session")
            self._update_session_label()
        else:
            self.feedback_label.setText("No unrated session found to rate")
