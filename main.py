import sys

from PyQt6.QtWidgets import QApplication

from core.storage import init_db
from ui.main_window import MainWindow


def main():
    init_db()
    app = QApplication(sys.argv)
    app.setApplicationName("ContextForge")
    app.setStyle("Fusion")

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
    app.setStyleSheet(DARK_STYLESHEET)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
