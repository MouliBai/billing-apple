import sys

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QColor, QPalette

from core.app_shell import MainWindow, C
from core.app_branding import apply_app_icon
from core.input_behavior import ensure_global_input_guard


def main():
    app = QApplication(sys.argv)
    ensure_global_input_guard()
    apply_app_icon()
    app.setStyle("Fusion")

    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window, QColor(C["bg_white"]))
    pal.setColor(QPalette.ColorRole.WindowText, QColor(C["text"]))
    pal.setColor(QPalette.ColorRole.Base, QColor(C["input_bg"]))
    pal.setColor(QPalette.ColorRole.AlternateBase, QColor(C["bg_light"]))
    pal.setColor(QPalette.ColorRole.Text, QColor(C["text"]))
    pal.setColor(QPalette.ColorRole.Button, QColor(C["bg_light"]))
    pal.setColor(QPalette.ColorRole.ButtonText, QColor(C["text"]))
    pal.setColor(QPalette.ColorRole.Highlight, QColor(C["accent"]))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    app.setPalette(pal)

    win = MainWindow()
    win.show()
    win.showMaximized()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

