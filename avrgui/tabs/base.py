from __future__ import annotations

import roslibpy
from PySide6 import QtCore, QtGui, QtWidgets
from loguru import logger

from .connection.rosbridge import RosBridgeClient
from ..lib.qt_icon import set_icon


class BaseTabWidget(QtWidgets.QWidget):
    pop_in: QtCore.SignalInstance = QtCore.Signal(object)

    def __init__(self, parent: QtWidgets.QWidget, ros_client: RosBridgeClient | None) -> None:
        super().__init__(parent)

        self.client: roslibpy.Ros | None = None

        if ros_client is not None:
            ros_client.ros_connection.connect(self.setup_ros)
            logger.debug(f"Set up signal for {self.__class__.__name__}")
        else:
            logger.warning(f"Didn\'t set up signal for {self.__class__.__name__}")
        set_icon(self)

    def setup_ros(self, client: roslibpy.Ros) -> None:
        self.client = client

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        self.pop_in.emit(self)
        return super().closeEvent(event)
