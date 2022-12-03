from typing import Any

import paho.mqtt.client as mqtt
from PySide6 import QtCore, QtGui, QtWidgets
from loguru import logger

from ...lib.color import wrap_text
from ...lib.config import config
from ...lib.enums import ConnectionState
from ...lib.toast import Toast
from ...lib.widgets import IntLineEdit

DEFAULT_QOS = 1


class MQTTClient(QtCore.QObject):
    # This class MUST inherit from QObject in order for the signals to work

    # This class works with a QSigna based architecture, as the MQTT client
    # runs in a separate thread. The callbacks from the MQTT client run in the same
    # thread as the client and thus those cannot update the GUI, as only the
    # thread that started the GUI is allowed to update it. Thus, set up the
    # MQTT client in a separate class with signals that are emitted and connected to
    # so the data gets passed back to the GUI thread.

    # Once the Signal objects are created, they transform into SignalInstance objects
    connection_state: QtCore.SignalInstance = QtCore.Signal(object)  # type: ignore
    message: QtCore.SignalInstance = QtCore.Signal(str, str)  # type: ignore
    message_bytes: QtCore.SignalInstance = QtCore.Signal(str, bytes)

    def __init__(self) -> None:
        super().__init__()

        self.client = mqtt.Client()
        self.client.max_inflight_messages_set(10)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect

        self.wanted_state = False

    def on_connect(self, client: mqtt.Client, userdata: Any, flags: dict, rc: int) -> None:
        """
        Callback when the MQTT client connects
        """
        # subscribe to all topics
        logger.debug("Subscribing to all topics")
        client.subscribe("#", DEFAULT_QOS)

    def on_message(self, client: mqtt.Client, userdata: Any, msg: mqtt.MQTTMessage) -> None:
        """
        Callback for every MQTT message
        """
        if "avr/raw" in msg.topic:
            self.message_bytes.emit(msg.topic, msg.payload)
        else:
            try:
                self.message.emit(msg.topic, msg.payload.decode("utf-8"))
            except UnicodeDecodeError:
                pass

    def on_disconnect(self, client: mqtt.Client, userdata: Any, rc: int) -> None:
        """
        Callback when the MQTT client disconnects
        """
        logger.debug("Disconnected from MQTT server")
        self.connection_state.emit(ConnectionState.disconnected)
        if self.wanted_state is True:
            Toast.get().send_message.emit("Lost connection to mqtt broker!", 3.0)
            self.message.emit("avr/gui/sound/critical", {})

    def login(self, host: str, port: int) -> None:
        """
        Connect the MQTT client to the server. This method cannot be named "connect"
        as this conflicts with the connect methods of the Signals
        """
        # do nothing on empty sring
        if not host:
            return

        logger.info(f"Connecting to MQTT server at {host}:{port}")
        self.connection_state.emit(ConnectionState.connecting)

        try:
            # try to connect to MQTT server
            self.client.connect(host=host, port=port, keepalive=60)
            self.client.loop_start()

            # save settings
            config.mqtt_host = host
            config.mqtt_port = port

            # emit success
            logger.success("Connected to MQTT server")
            self.connection_state.emit(ConnectionState.connected)
            self.wanted_state = True

        except Exception:
            logger.exception("Connection failed to MQTT server")
            self.connection_state.emit(ConnectionState.failure)

    def logout(self) -> None:
        """
        Disconnect the MQTT client to the server.
        """
        self.wanted_state = False
        logger.info("Disconnecting from MQTT server")
        self.connection_state.emit(ConnectionState.disconnecting)

        self.client.disconnect()
        self.client.loop_stop()

        logger.info("Disconnected from MQTT server")
        self.connection_state.emit(ConnectionState.disconnected)

    def publish(self, topic: str, payload: Any, qos: int = DEFAULT_QOS, retain: bool = False) -> None:
        """
        Publish an MQTT message. Proxy function to the underlying client
        """
        if not topic:
            return

        logger.debug(f"Publishing message {topic}: {payload}")
        self.client.publish(topic, payload, qos, retain)


class MQTTConnectionWidget(QtWidgets.QWidget):
    connection_state: QtCore.SignalInstance = QtCore.Signal(object)  # type: ignore
    current_host: str = ""

    def __init__(self, parent: QtWidgets.QWidget) -> None:
        super().__init__(parent)

        self.mqtt_menu_state = None
        self.mqtt_menu_connect = None
        self.mqtt_menu = None
        self.disconnect_button = None
        self.connect_button = None
        self.state_label = None
        self.port_line_edit = None
        self.hostname_line_edit = None
        self.mqtt_client = MQTTClient()
        self.mqtt_client.connection_state.connect(self.set_connected_state)

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
                lambda: self.mqtt_client.login(
                        self.hostname_line_edit.text(), int(self.port_line_edit.text())
                )
        )
        self.disconnect_button.clicked.connect(self.mqtt_client.logout)  # type: ignore

        self.mqtt_menu = QtWidgets.QMenu("MQTT")

        self.mqtt_menu_connect = QtGui.QAction("Connect")

        def mqtt_menu_connect_triggered() -> None:
            if self.mqtt_client.connection_state == ConnectionState.connected:
                self.mqtt_client.logout()
                self.mqtt_menu_connect.setChecked(False)
            else:
                try:
                    port = int(self.port_line_edit.text())
                except ValueError:
                    return
                self.mqtt_client.login(self.hostname_line_edit.text(), port)
                self.mqtt_menu_connect.setChecked(True)

        self.mqtt_menu_connect.triggered.connect(mqtt_menu_connect_triggered)
        self.mqtt_menu_connect.setCheckable(True)
        self.mqtt_menu.addAction(self.mqtt_menu_connect)

        self.mqtt_menu_state = QtGui.QAction("Disconnected")
        self.mqtt_menu_state.setEnabled(False)
        self.mqtt_menu.addAction(self.mqtt_menu_state)

        def mqtt_menu_state(state: ConnectionState) -> None:
            if state == ConnectionState.connected:
                self.mqtt_menu_connect.setChecked(True)
                self.mqtt_menu_state.setText("Connected")
            elif state == ConnectionState.disconnected:
                self.mqtt_menu_connect.setChecked(False)
                self.mqtt_menu_state.setText("Disconnected")
            elif state == ConnectionState.connecting:
                self.mqtt_menu_connect.setChecked(True)
                self.mqtt_menu_state.setText("Connecting")
            elif state == ConnectionState.disconnecting:
                self.mqtt_menu_connect.setChecked(False)
                self.mqtt_menu_state.setText("Disconnecting")

        self.mqtt_client.connection_state.connect(mqtt_menu_state)

    def set_connected_state(self, connection_state: ConnectionState) -> None:
        """
        Set the connected state of the MQTT connection widget elements.
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
