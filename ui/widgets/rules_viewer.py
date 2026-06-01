from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QPlainTextEdit
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt


class RulesViewer(QWidget):
    def __init__(self):
        super().__init__()
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout()

        # Header
        header_layout = QHBoxLayout()
        title_label = QLabel("Generated rules")
        title_label.setStyleSheet("font-weight: bold;")
        header_layout.addWidget(title_label)
        header_layout.addStretch()

        # Copy button
        copy_btn = QPushButton("Copy")
        copy_btn.clicked.connect(self._copy_to_clipboard)
        header_layout.addWidget(copy_btn)

        layout.addLayout(header_layout)

        # Text area
        self.text_area = QPlainTextEdit()
        self.text_area.setReadOnly(True)
        font = QFont("Consolas", 10)
        if not font.exactMatch():
            font = QFont("Courier New", 10)
        self.text_area.setFont(font)
        self.text_area.setMinimumHeight(200)
        layout.addWidget(self.text_area)

        self.setLayout(layout)

    def _copy_to_clipboard(self):
        from PyQt6.QtWidgets import QApplication
        QApplication.clipboard().setText(self.text_area.toPlainText())

    def set_content(self, text: str):
        self.text_area.setPlainText(text)
