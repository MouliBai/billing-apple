"""PyQt5 companion to the EvoAura application-wide input guard."""

from PyQt5.QtCore import QEvent, QObject, QTimer
from PyQt5.QtWidgets import (
    QApplication,
    QAbstractSpinBox,
    QComboBox,
    QDoubleSpinBox,
    QLineEdit,
    QSpinBox,
)


class InputBehaviorGuardQt5(QObject):
    def eventFilter(self, watched, event):
        parent = watched.parentWidget() if isinstance(watched, QLineEdit) else None
        control = watched
        if isinstance(parent, (QComboBox, QAbstractSpinBox)):
            control = parent

        if event.type() == QEvent.Wheel and isinstance(
            control, (QComboBox, QAbstractSpinBox)
        ):
            event.accept()
            return True

        spin = control if isinstance(control, (QSpinBox, QDoubleSpinBox)) else None
        if spin is not None and event.type() in (
            QEvent.Show,
            QEvent.Polish,
            QEvent.FocusIn,
        ):
            if spin.minimum() == 0:
                spin.setSpecialValueText("")
                if not spin.lineEdit().placeholderText():
                    spin.lineEdit().setPlaceholderText("Enter value")
            spin.setKeyboardTracking(False)
            spin.setAccelerated(False)

        if event.type() == QEvent.FocusIn and isinstance(watched, QLineEdit):
            if isinstance(parent, (QSpinBox, QDoubleSpinBox)) or (
                isinstance(parent, QComboBox) and parent.isEditable()
            ):
                QTimer.singleShot(0, watched.selectAll)
        return super().eventFilter(watched, event)


def ensure_global_input_guard_qt5():
    app = QApplication.instance()
    if app is None:
        return None
    guard = getattr(app, "_evo_input_behavior_guard_qt5", None)
    if guard is None:
        guard = InputBehaviorGuardQt5(app)
        app.installEventFilter(guard)
        app._evo_input_behavior_guard_qt5 = guard
    return guard
