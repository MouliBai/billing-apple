from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget


class PlaceholderPage(QWidget):
    def __init__(self, title="Page", parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        label = QLabel(f"{title}\n\nThis section is ready for the next build step.")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("font-size:18px;font-weight:700;color:#6E6E73;")
        layout.addWidget(label)

