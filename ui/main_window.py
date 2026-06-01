from PyQt6.QtWidgets import QMainWindow, QTabWidget, QWidget, QVBoxLayout

from ui.pages.generate_page import GeneratePage
from ui.pages.rate_page import RatePage
from ui.pages.improve_page import ImprovePage


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ContextForge")
        self.setMinimumSize(800, 560)

        # Create tab widget
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # Add pages
        self.generate_page = GeneratePage()
        self.rate_page = RatePage()
        self.improve_page = ImprovePage()

        self.tabs.addTab(self.generate_page, "Generate")
        self.tabs.addTab(self.rate_page, "Rate")
        self.tabs.addTab(self.improve_page, "Improve")

        # Status bar
        self.statusBar().showMessage("Ready")
