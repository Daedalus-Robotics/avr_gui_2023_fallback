import contextlib
import os
from typing import Optional

from PySide6 import QtGui, QtWidgets, QtCore
from qmaterialwidgets import FilledLineEdit


class IntLineEdit(FilledLineEdit):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.setValidator(QtGui.QIntValidator(0, 1000000, self))


class DoubleLineEdit(QtWidgets.QLineEdit):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.setValidator(QtGui.QDoubleValidator(0.0, 100.0, 2, self))


class DisplayLineEdit(FilledLineEdit):
    def __init__(self, parent: Optional[QtWidgets.QWidget] = None,
                 round_digits: Optional[int] = 4) -> None:
        super().__init__()

        self.round_digits = round_digits

        self.setReadOnly(True)
        self.setEnabled(False)

        font = self.font()
        font.setPixelSize(12)
        self.setFont(font)
        # self.setStyleSheet("background-color: rgb(220, 220, 220)")
        self.setMaximumWidth(120)

    def setText(self, arg__1: str) -> None:
        # round incoming float values
        if self.round_digits is not None:
            with contextlib.suppress(ValueError):
                arg__1 = str(round(float(arg__1), self.round_digits))

        return super().setText(arg__1)


class StatusLabel(QtWidgets.QWidget):
    # Combination of 2 QLabels to add a status icon
    def __init__(self, text: str):
        super().__init__()

        size = 25

        self.green_pixmap = QtGui.QPixmap("assets/img/green.png").scaledToWidth(size)
        self.red_pixmap = QtGui.QPixmap("assets/img/red.png").scaledToWidth(size)

        # create a horizontal layout
        layout = QtWidgets.QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

        # create a label for the icon
        self.icon = QtWidgets.QLabel()
        self.icon.setFixedSize(QtCore.QSize(size, size))
        layout.addWidget(self.icon)
        self.set_health(False)

        # add text label
        layout.addWidget(QtWidgets.QLabel(text))

    def set_health(self, healthy: bool) -> None:
        """
        Set the health state of the status label
        """
        self.icon.setPixmap(self.green_pixmap if healthy else self.red_pixmap)
