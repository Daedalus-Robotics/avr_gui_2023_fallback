import json
from typing import Any

import zmq
from PySide6 import QtCore, QtGui, QtWidgets
from loguru import logger

from ...lib.color import wrap_text
from ...lib.config import config
from ...lib.toast import Toast
from ...lib.widgets import IntLineEdit


class ZMQClient(QtCore.QObject):
    connection_state: QtCore.SignalInstance = QtCore.Signal(bool)

    def __init__(self) -> None:
        super().__init__()

        self.context = zmq.Context()
        self.pub_socket = self.context.socket(zmq.PUB)

    def zmq_publish(self, topic: str, message: str | bytes | dict | list | None):
        if isinstance(message, (dict | list)):
            message = json.dumps(message)
        self.pub_socket.send_string(f"{topic} {message}")

    def zmq_connect(self, host: str, port: int = 5580) -> None:
        self.pub_socket.connect(f"tcp://{host}:{port}")
        self.connection_state.emit(True)

    def zmq_disconnect(self, host: str, port: int = 5580) -> None:
        self.pub_socket.disconnect(f"tcp://{host}:{port}")
        self.connection_state.emit(False)


class ZMQConnectionWidget(QtWidgets.QWidget):
    def __init__(self, parent: QtWidgets.QWidget) -> None:
        super().__init__(parent)

        self.disconnect_button = None
        self.connect_button = None
        self.state_label = None
        self.port_line_edit = None
        self.hostname_line_edit = None

        self.zmq_client = ZMQClient()

        self.current_host = ""
        self.current_port = 0

    def publish(self, topic: str, message: str | bytes | dict | list | None):
        self.zmq_client.zmq_publish(topic, message)

    def build(self) -> None:
        """
        Build the GUI layout
        """
        self.zmq_client.connection_state.connect(self.set_connected_state)

        layout = QtWidgets.QVBoxLayout(self)
        self.setLayout(layout)

        # lay out the host label and line edit
        host_layout = QtWidgets.QFormLayout()

        self.hostname_line_edit = QtWidgets.QLineEdit()
        host_layout.addRow(QtWidgets.QLabel("Host:"), self.hostname_line_edit)

        self.port_line_edit = IntLineEdit()
        host_layout.addRow(QtWidgets.QLabel("Port:"), self.port_line_edit)

        layout.addLayout(host_layout)

        # lay out the bottom connection state and buttons
        bottom_layout = QtWidgets.QHBoxLayout()
        self.state_label = QtWidgets.QLabel()
        bottom_layout.addWidget(self.state_label)

        button_layout = QtWidgets.QHBoxLayout()
        self.connect_button = QtWidgets.QPushButton("Connect")
        button_layout.addWidget(self.connect_button)

        self.disconnect_button = QtWidgets.QPushButton("Disconnect")
        button_layout.addWidget(self.disconnect_button)

        bottom_layout.addLayout(button_layout)

        layout.addLayout(bottom_layout)

        # set starting state
        self.set_connected_state(False)

        self.hostname_line_edit.setText(config.mqtt_host)
        self.port_line_edit.setText(str(5580))

        # set up connections
        self.hostname_line_edit.returnPressed.connect(self.connect_button.click)
        self.connect_button.clicked.connect(
                lambda: self.zmq_connect()
        )
        self.disconnect_button.clicked.connect(
                lambda: self.zmq_client.zmq_disconnect(
                        self.current_host,
                        self.current_port
                )
        )

    def zmq_connect(self) -> None:
        self.current_host = self.hostname_line_edit.text()
        self.current_port = int(self.port_line_edit.text())
        self.zmq_client.zmq_connect(
                self.current_host,
                self.current_port
        )

    def set_connected_state(self, connected: bool) -> None:
        """
        Set the connected state of the MQTT connection widget elements.
        """
        label, color = ("Connected", "Green") if connected else ("Disconnected", "Red")

        self.state_label.setText(
                f"State: {wrap_text(label, color)}"
        )

        self.disconnect_button.setEnabled(connected)
        self.connect_button.setDisabled(connected)

        self.hostname_line_edit.setReadOnly(connected)
        self.port_line_edit.setReadOnly(connected)

        QtGui.QGuiApplication.processEvents()
