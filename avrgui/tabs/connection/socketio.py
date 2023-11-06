import multiprocessing
from typing import Any, Tuple

import socketio
from multiprocessing import Process, Queue
from threading import Thread
from PySide6 import QtCore, QtGui, QtWidgets
from loguru import logger

from ...lib.color import wrap_text
from ...lib.config import config
from ...lib.enums import ConnectionState
from ...lib.toast import Toast
from ...lib.widgets import IntLineEdit


class SocketIOWorkaround:

    def __init__(self, signal: QtCore.SignalInstance, wanted_state) -> None:

        self.connection_state = signal
        self.running = True
        self.wanted_state = wanted_state

        self.emit_queue: multiprocessing.Queue[Tuple] = Queue()
        self.on_queue: multiprocessing.Queue[Tuple] = Queue()

        self.pipe_endpoint: multiprocessing.Process | None = None

    def _on_startup(self, host: int, port: int):
        self.client = socketio.Client()
        self.client.on("disconnect", self.on_disconnect)

        # do nothing on empty string
        if not host:
            return

        print(f"Connecting to SocketIO server at {host}:{port}")
        self.connection_state.emit(ConnectionState.connecting)

        try:
            # try to connect to MQTT server
            # noinspection HttpUrlsUsage
            self.client.connect(f"http://{host}:{port}", transports=['websocket'])

            # emit success
            print("Connected to SocketIO server")
            self.connection_state.emit(ConnectionState.connected)
            self.wanted_state = True

        except Exception:
            print("Connection failed to SocketIO server")
            self.connection_state.emit(ConnectionState.failure)

        while self.running:
            if not self.emit_queue.empty():
                event, data = self.emit_queue.get()
                self.client.emit(event, data)
            if not self.on_queue.empty():
                event, data = self.on_queue.get()
                self.client.on(event, data)

        self.client.disconnect()

    def emit(self, event: str, data: Any) -> None:
        """
        Emit an event to the server.
        """

        print(event, data)
        self.emit_queue.put((event, data))

    def login(self, host, port) -> None:
        """
        Connect the SocketIO client to the server. This method cannot be named "connect"
        as this conflicts with the connect methods of the Signals
        """
        self.pipe_endpoint = Thread(target=self._on_startup, daemon=True, args=[host, port])
        self.pipe_endpoint.start()

    def on_disconnect(self) -> None:
        """
        Callback when the SocketIO client disconnects
        """
        logger.debug("Disconnected from SocketIO server")
        self.connection_state.emit(ConnectionState.disconnected)
        if self.wanted_state is True:
            Toast.get().send_message.emit("Lost connection to mqtt broker!", 3.0)

    def logout(self) -> None:
        """
        Disconnect the SocketIO client to the server.
        """
        self.wanted_state = False
        logger.info("Disconnecting from SocketIO server")
        self.connection_state.emit(ConnectionState.disconnecting)

        self.client.disconnect()

        logger.info("Disconnected from SocketIO server")
        self.connection_state.emit(ConnectionState.disconnected)


class SocketIOClient(QtCore.QObject):
    connection_state: QtCore.SignalInstance = QtCore.Signal(object)  # type: ignore

    def __init__(self) -> None:
        super().__init__()

        self.wanted_state = False
        self.client = SocketIOWorkaround(signal=self.connection_state, wanted_state=self.wanted_state)

    def login(self, host, port) -> None:
        """
        Connect the SocketIO client to the server. This method cannot be named "connect"
        as this conflicts with the connect methods of the Signals
        """
        # do nothing on empty string

        logger.info(f"Connecting to SocketIO server at {host}:{port}")
        self.connection_state.emit(ConnectionState.connecting)

        try:
            self.client.login(host=host, port=port)

            # save settings
            config.mqtt_host = host
            config.mqtt_port = port

            # emit success
            logger.success("Connected to SocketIO server")
            self.connection_state.emit(ConnectionState.connected)
            self.wanted_state = True

        except Exception:
            logger.exception("Connection failed to SocketIO server")
            self.connection_state.emit(ConnectionState.failure)
    # def testty(self, event: str, data: Any):
    #     print(event, data)
    #     self.client.emit(event, data)

    def logout(self):
        self.client.running = False


class SocketIOConnectionWidget(QtWidgets.QWidget):
    connection_state: QtCore.SignalInstance = QtCore.Signal(object)  # type: ignore
    current_host: str = ""

    def __init__(self, parent: QtWidgets.QWidget) -> None:
        super().__init__(parent)

        self.socketio_menu_state = None
        self.socketio_menu_connect = None
        self.socketio_menu = None
        self.disconnect_button = None
        self.connect_button = None
        self.state_label = None
        self.port_line_edit = None
        self.hostname_line_edit = None
        self.socketio_client = SocketIOClient()
        self.socketio_client.connection_state.connect(self.set_connected_state)

    def build(self) -> None:
        """
        Build the GUI layout
        """
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
        self.set_connected_state(ConnectionState.disconnected)

        self.hostname_line_edit.setText(config.mqtt_host)
        self.port_line_edit.setText(str(config.mqtt_port))

        # set up connections
        self.hostname_line_edit.returnPressed.connect(self.connect_button.click)
        self.port_line_edit.returnPressed.connect(self.connect_button.click)
        self.connect_button.clicked.connect(  # type: ignore
            lambda: self.socketio_client.login(
                self.hostname_line_edit.text(), int(self.port_line_edit.text())
            )
        )
        self.disconnect_button.clicked.connect(self.socketio_client.logout)  # type: ignore

        self.socketio_menu = QtWidgets.QMenu("SocketIO")

        self.socketio_menu_connect = QtGui.QAction("Connect")

        def mqtt_menu_connect_triggered() -> None:
            if self.socketio_client.connection_state == ConnectionState.connected:
                self.socketio_client.logout()
                self.socketio_menu_connect.setChecked(False)
            else:
                try:
                    port = int(self.port_line_edit.text())
                except ValueError:
                    return
                self.socketio_client.login(self.hostname_line_edit.text(), port)
                self.socketio_menu_connect.setChecked(True)

        self.socketio_menu_connect.triggered.connect(mqtt_menu_connect_triggered)
        self.socketio_menu_connect.setCheckable(True)
        self.socketio_menu.addAction(self.socketio_menu_connect)

        self.socketio_menu_state = QtGui.QAction("Disconnected")
        self.socketio_menu_state.setEnabled(False)
        self.socketio_menu.addAction(self.socketio_menu_state)

        def socketio_menu_state(state: ConnectionState) -> None:
            if state == ConnectionState.connected:
                self.socketio_menu_connect.setChecked(True)
                self.socketio_menu_state.setText("Connected")
            elif state == ConnectionState.disconnected:
                self.socketio_menu_connect.setChecked(False)
                self.socketio_menu_state.setText("Disconnected")
            elif state == ConnectionState.connecting:
                self.socketio_menu_connect.setChecked(True)
                self.socketio_menu_state.setText("Connecting")
            elif state == ConnectionState.disconnecting:
                self.socketio_menu_connect.setChecked(False)
                self.socketio_menu_state.setText("Disconnecting")

        self.socketio_client.connection_state.connect(socketio_menu_state)

    def set_connected_state(self, connection_state: ConnectionState) -> None:
        """
        Set the connected state of the SocketIO connection widget elements.
        """
        color_lookup = {
            ConnectionState.connected: "Green",
            ConnectionState.connecting: "DarkGoldenRod",
            ConnectionState.disconnecting: "DarkGoldenRod",
            ConnectionState.disconnected: "Red",
            ConnectionState.failure: "Red",
        }

        connected = connection_state == ConnectionState.connected
        disconnected = connection_state in [
            ConnectionState.failure,
            ConnectionState.disconnected,
        ]

        self.state_label.setText(
            f"State: {wrap_text(connection_state.name.title(), color_lookup[connection_state])}"
        )

        self.disconnect_button.setEnabled(connected)
        self.connect_button.setDisabled(connected)

        self.hostname_line_edit.setReadOnly(not disconnected)
        self.port_line_edit.setReadOnly(not disconnected)

        self.connection_state.emit(connection_state)
        QtGui.QGuiApplication.processEvents()

        self._set_current_host(self.hostname_line_edit.text())

    @classmethod
    def _set_current_host(cls, host: str) -> None:
        cls.current_host = host
