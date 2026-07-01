from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget


class DashboardPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        label = QLabel("Dashboard\n\nPyQt6 dashboard page placeholder for the modular EvoAura structure.")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("font-size:18px;font-weight:800;color:#1D1D1F;")
        layout.addWidget(label)
