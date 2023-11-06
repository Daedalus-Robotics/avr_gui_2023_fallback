from __future__ import annotations

import socketio
from PySide6 import QtCore, QtGui, QtWidgets
from ..lib.qt_icon import set_icon


class BaseTabWidget(QtWidgets.QWidget):
    pop_in: QtCore.SignalInstance = QtCore.Signal(object)

    def __init__(self, parent: QtWidgets.QWidget) -> None:
        super().__init__(parent)

        self.client: socketio.Client | None = None
        set_icon(self)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        self.pop_in.emit(self)
        return super().closeEvent(event)
