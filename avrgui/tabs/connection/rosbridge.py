from typing import Any
import roslibpy
from PySide6 import QtCore, QtGui, QtWidgets
from loguru import logger

from ...lib.color import wrap_text
from ...lib.config import config
from ...lib.enums import ConnectionState
from ...lib.toast import Toast
from ...lib.widgets import IntLineEdit


class RosBridgeClient(QtCore.QObject):
    connection_state: QtCore.SignalInstance = QtCore.Signal(object)
    ros_connection: QtCore.SignalInstance = QtCore.Signal(object)

    def __init__(self, ) -> None:
        super().__init__()

        self.client: roslibpy.Ros | None = None
        self.wanted_state = False

    def on_disconnect(self) -> None:
        """
        Callback when the SocketIO client disconnects
        """
        logger.debug("Disconnected from SocketIO server")
        self.connection_state.emit(ConnectionState.disconnected)
        if self.wanted_state is True:
            Toast.get().send_message.emit("Lost connection to ROS bridge!", 3.0)

    def login(self, host: str, port: int) -> None:
        """
        Connect the SocketIO client to the server. This method cannot be named "connect"
        as this conflicts with the connect methods of the Signals
        """
        # do nothing on empty string
        if not host:
            return

        logger.info(f"Connecting to SocketIO server at {host}:{port}")
        self.connection_state.emit(ConnectionState.connecting)

        try:
            # try to connect to ROSBridge server
            self.client = roslibpy.Ros(host=host, port=port)
            self.client.run()

            self.client.on("closing", self.on_disconnect)

            # save settings
            config.ros_client_host = host
            config.ros_client_port = port

            # emit success
            self.client.on_ready(self._connected)

        except Exception as e:
            print(e)
            logger.exception("Connection failed to SocketIO server")
            self.connection_state.emit(ConnectionState.failure)

    def _connected(self):
        logger.success(f"Connected to SocketIO server {self.client.is_connected}")
        self.connection_state.emit(ConnectionState.connected)
        self.ros_connection.emit(self.client)
        self.wanted_state = True

    def logout(self) -> None:
        """
        Disconnect the SocketIO client to the server.
        """
        self.wanted_state = False
        logger.info("Disconnecting from SocketIO server")
        self.connection_state.emit(ConnectionState.disconnecting)

        self.client.terminate()

        logger.info("Disconnected from SocketIO server")
        self.connection_state.emit(ConnectionState.disconnected)


class RosConnectionWidget(QtWidgets.QWidget):
    connection_state: QtCore.SignalInstance = QtCore.Signal(object)
    current_host: str = ""

    def __init__(self, parent: QtWidgets.QWidget) -> None:
        super().__init__(parent)

        self.ros_client_menu_state = None
        self.ros_client_menu_connect = None
        self.ros_client_menu = None
        self.disconnect_button = None
        self.connect_button = None
        self.state_label = None
        self.port_line_edit = None
        self.hostname_line_edit = None
        self.ros_client = RosBridgeClient()
        self.ros_client.connection_state.connect(self.set_connected_state)

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

        self.hostname_line_edit.setText(config.ros_client_host)
        self.port_line_edit.setText(str(config.ros_client_port))

        # set up connections
        self.hostname_line_edit.returnPressed.connect(self.connect_button.click)
        self.port_line_edit.returnPressed.connect(self.connect_button.click)
        self.connect_button.clicked.connect(  # type: ignore
            lambda: self.ros_client.login(
                self.hostname_line_edit.text(), int(self.port_line_edit.text())
            )
        )
        self.disconnect_button.clicked.connect(self.ros_client.logout)  # type: ignore

        self.ros_client_menu = QtWidgets.QMenu("ROS Bridge ")

        self.ros_client_menu_connect = QtGui.QAction("Connect")

        def ros_client_menu_connect_triggered() -> None:
            if self.ros_client.connection_state == ConnectionState.connected:
                self.ros_client.logout()
                self.ros_client_menu_connect.setChecked(False)
            else:
                try:
                    port = int(self.port_line_edit.text())
                except ValueError:
                    return
                self.ros_client.login(self.hostname_line_edit.text(), port)
                self.ros_client_menu_connect.setChecked(True)

        self.ros_client_menu_connect.triggered.connect(ros_client_menu_connect_triggered)
        self.ros_client_menu_connect.setCheckable(True)
        self.ros_client_menu.addAction(self.ros_client_menu_connect)

        self.ros_client_menu_state = QtGui.QAction("Disconnected")
        self.ros_client_menu_state.setEnabled(False)
        self.ros_client_menu.addAction(self.ros_client_menu_state)

        def ros_client_menu_state(state: ConnectionState) -> None:
            if state == ConnectionState.connected:
                self.ros_client_menu_connect.setChecked(True)
                self.ros_client_menu_state.setText("Connected")
            elif state == ConnectionState.disconnected:
                self.ros_client_menu_connect.setChecked(False)
                self.ros_client_menu_state.setText("Disconnected")
            elif state == ConnectionState.connecting:
                self.ros_client_menu_connect.setChecked(True)
                self.ros_client_menu_state.setText("Connecting")
            elif state == ConnectionState.disconnecting:
                self.ros_client_menu_connect.setChecked(False)
                self.ros_client_menu_state.setText("Disconnecting")

        self.ros_client.connection_state.connect(ros_client_menu_state)

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
