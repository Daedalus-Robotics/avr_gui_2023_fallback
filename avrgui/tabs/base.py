from __future__ import annotations

import json
from typing import Any

from PySide6 import QtCore, QtGui, QtWidgets

from .connection.mqtt import DEFAULT_QOS
from ..lib.qt_icon import set_icon


class BaseTabWidget(QtWidgets.QWidget):
    pop_in: QtCore.SignalInstance = QtCore.Signal(object)  # type: ignore
    emit_message: QtCore.SignalInstance = QtCore.Signal(str, Any, int, bool)  # type: ignore

    def __init__(self, parent: QtWidgets.QWidget) -> None:
        super().__init__(parent)
        set_icon(self)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        self.pop_in.emit(self)
        return super().closeEvent(event)

    def send_message(self, topic: str, payload: Any, qos: int = DEFAULT_QOS, retain: bool = False) -> None:
        """
        Emit a Qt Signal for a message to be sent to the MQTT broker.
        """
        if not isinstance(payload, (str, bytes)):
            try:
                payload = json.dumps(payload)
            except ValueError:
                pass

        self.emit_message.emit(topic, payload, qos, retain)

    def process_message(self, topic: str, payload: str) -> None:
        """
        Process an incoming message from the MQTT broker.
        """
        raise NotImplementedError()
