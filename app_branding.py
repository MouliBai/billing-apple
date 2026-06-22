"""Shared EvoAura title-bar icon handling for PyQt6."""

import os

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication


def apply_app_icon(window=None):
    path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "icons", "logo.png"
    )
    if not os.path.isfile(path):
        return QIcon()
    icon = QIcon(path)
    app = QApplication.instance()
    if app is not None:
        app.setWindowIcon(icon)
    if window is not None:
        window.setWindowIcon(icon)
    return icon
