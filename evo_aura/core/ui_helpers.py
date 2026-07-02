"""Shared lightweight UI helpers for the modular EvoAura app."""

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QPainter, QLinearGradient, QColor
from PyQt6.QtWidgets import (
    QFrame, QLabel, QPushButton, QLineEdit, QVBoxLayout, QWidget,
    QStyledItemDelegate, QStyle,
)

from core.theme import C


def F(sz=13, bold=False, mono=False) -> QFont:
    font = QFont("Courier New" if mono else "Segoe UI", sz)
    if bold:
        font.setWeight(QFont.Weight.Bold)
    return font


def L(text, size=13, bold=False, color=None):
    label = QLabel(text)
    label.setFont(F(size, bold))
    label.setStyleSheet(
        f"color:{color or C['text']}; background:transparent; border:none;")
    return label


def gap(h=8):
    widget = QWidget()
    widget.setFixedHeight(h)
    widget.setStyleSheet("background:transparent;")
    return widget


def hline():
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setStyleSheet(f"color:{C['border']};background:{C['border']};")
    line.setFixedHeight(1)
    return line


def card_style(radius=14):
    return (
        f"background:{C['bg_white']};border:1px solid {C['border']};"
        f"border-radius:{radius}px;"
    )


class Toast(QLabel):
    _P = {
        "success": (C["success"], "✓"),
        "error": (C["accent"], "✕"),
        "warn": (C["warning"], "!"),
        "info": (C["blue"], "i"),
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hide()

    def show_msg(self, message, kind="info", ms=2600):
        color, icon = self._P.get(kind, self._P["info"])
        self.setText(f"{icon}  {message}")
        self.setStyleSheet(
            f"background:{C['bg_white']};color:{C['text']};"
            f"border:1px solid {color};border-radius:10px;"
            "padding:9px 14px;font-weight:700;"
        )
        self.adjustSize()
        if self.parent():
            self.move(
                max(12, self.parent().width() - self.width() - 24),
                max(12, self.parent().height() - self.height() - 24),
            )
        self.show()
        QTimer.singleShot(ms, self.hide)


class SI(QWidget):
    returnPressed = pyqtSignal()

    def __init__(self, label="", icon="", ph="", pw=False, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        if label:
            layout.addWidget(L(label, 11, False, C["text2"]))
        self.edit = QLineEdit()
        self.edit.setPlaceholderText(ph)
        if pw:
            self.edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.edit.returnPressed.connect(self.returnPressed)
        self.edit.setStyleSheet(
            f"QLineEdit{{background:{C['input_bg']};border:1px solid {C['border']};"
            "border-radius:10px;padding:10px 12px;}}"
            f"QLineEdit:focus{{border:2px solid {C['accent']};}}"
        )
        layout.addWidget(self.edit)

    def text(self):
        return self.edit.text()

    def setText(self, value):
        self.edit.setText(value)

    def clear(self):
        self.edit.clear()


class GB(QPushButton):
    def __init__(self, text="", kind="primary", parent=None):
        super().__init__(text, parent)
        self.kind = kind
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(40)
        self.setStyleSheet(
            f"QPushButton{{background:{C['accent']};color:white;border:none;"
            "border-radius:10px;padding:9px 16px;font-weight:700;}}"
            f"QPushButton:hover{{background:{C['accent_dark']};}}"
        )


class LV(QWidget):
    """Lightweight compatibility base for auth/page imports."""


class ComboDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        option.state &= ~QStyle.StateFlag.State_HasFocus
        super().paint(painter, option, index)


def apply_combo_delegate(combo):
    combo.setItemDelegate(ComboDelegate(combo))


NO_ARROW = (
    "QDoubleSpinBox,QSpinBox{"
    f"background:{C['input_bg']}; border:2px solid {C['border']};"
    f"border-radius:9px; padding:8px 10px; color:{C['text']};"
    "font-size:13px;}"
    "QDoubleSpinBox::up-button,QDoubleSpinBox::down-button,"
    "QSpinBox::up-button,QSpinBox::down-button{width:0;border:none;}"
)

# Compatibility aliases used by older page code while the split continues.
_NO_ARROW = NO_ARROW
_apply_combo_delegate = apply_combo_delegate
