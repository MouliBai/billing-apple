"""Application-wide, user-friendly behavior for editable value controls."""

from PyQt6.QtCore import QEvent, QObject, QTimer
from PyQt6.QtWidgets import (
    QApplication,
    QAbstractSpinBox,
    QComboBox,
    QDoubleSpinBox,
    QLineEdit,
    QSpinBox,
)


class InputBehaviorGuard(QObject):
    """Prevent accidental wheel edits and make numeric entry feel natural."""

    @staticmethod
    def _spin_for(widget):
        if isinstance(widget, (QSpinBox, QDoubleSpinBox)):
            return widget
        if isinstance(widget, QLineEdit):
            parent = widget.parentWidget()
            if isinstance(parent, (QSpinBox, QDoubleSpinBox)):
                return parent
        return None

    @staticmethod
    def _value_control_for(widget):
        if isinstance(widget, (QComboBox, QAbstractSpinBox)):
            return widget
        if isinstance(widget, QLineEdit):
            parent = widget.parentWidget()
            if isinstance(parent, (QComboBox, QAbstractSpinBox)):
                return parent
        return None

    @staticmethod
    def _prepare_spin(spin):
        if spin.minimum() == 0:
            spin.setSpecialValueText("")
            line_edit = spin.lineEdit()
            if line_edit and not line_edit.placeholderText():
                line_edit.setPlaceholderText("Enter value")
        spin.setKeyboardTracking(False)
        spin.setAccelerated(False)

    def eventFilter(self, watched, event):
        event_type = event.type()
        control = self._value_control_for(watched)

        if event_type == QEvent.Type.Wheel and control is not None:
            event.accept()
            return True

        spin = self._spin_for(watched)
        if spin is not None and event_type in (
            QEvent.Type.Show,
            QEvent.Type.Polish,
            QEvent.Type.FocusIn,
        ):
            self._prepare_spin(spin)

        if event_type == QEvent.Type.FocusIn and isinstance(watched, QLineEdit):
            parent = watched.parentWidget()
            if isinstance(parent, (QSpinBox, QDoubleSpinBox)) or (
                isinstance(parent, QComboBox) and parent.isEditable()
            ):
                QTimer.singleShot(0, watched.selectAll)

        return super().eventFilter(watched, event)


def ensure_global_input_guard():
    app = QApplication.instance()
    if app is None:
        return None
    guard = getattr(app, "_evo_input_behavior_guard", None)
    if guard is None:
        guard = InputBehaviorGuard(app)
        app.installEventFilter(guard)
        app._evo_input_behavior_guard = guard
    return guard

