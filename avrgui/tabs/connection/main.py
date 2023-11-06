from PySide6 import QtWidgets

from ..base import BaseTabWidget
from .socketio import SocketIOConnectionWidget


class MainConnectionWidget(BaseTabWidget):
    """
    This manages connections to all the external services
    """

    def __init__(self, parent: QtWidgets.QWidget) -> None:
        super().__init__(parent)

        self.controller_connect_button = None
        self.setWindowTitle("Connections")

    def build(self) -> None:
        """
        Build the GUI layout
        """
        layout = QtWidgets.QVBoxLayout(self)
        self.setLayout(layout)

        socketio_groupbox = QtWidgets.QGroupBox("SocketIO")
        socketio_layout = QtWidgets.QVBoxLayout()
        socketio_groupbox.setLayout(socketio_layout)

        self.socketio_connection_widget = SocketIOConnectionWidget(self)
        self.socketio_connection_widget.build()
        socketio_layout.addWidget(self.socketio_connection_widget)

        socketio_groupbox.setSizePolicy(
                QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed
        )
        layout.addWidget(socketio_groupbox)

        self.controller_connect_button = QtWidgets.QPushButton("Connect DualSense Controller")
        layout.addWidget(self.controller_connect_button)
