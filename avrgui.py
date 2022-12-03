import argparse
import json
import os.path
import sys

from PySide6 import QtCore, QtGui, QtWidgets
from loguru import logger
from playsound import playsound

from avrgui.lib.controller.controller import Controller
from avrgui.lib.enums import ConnectionState
from avrgui.lib.qt_icon import set_icon
from avrgui.lib.toast import Toast
from avrgui.lib.water_drop_popup import WaterDropPopup
# from avrgui.tabs.autonomy import AutonomyWidget
from avrgui.tabs.camera_view import CameraViewWidget
from avrgui.tabs.connection.main import MainConnectionWidget
from avrgui.tabs.heads_up import HeadsUpDisplayWidget
from avrgui.tabs.moving_map import MovingMapWidget
from avrgui.tabs.mqtt_debug import MQTTDebugWidget
# from avrgui.tabs.mqtt_logger import MQTTLoggerWidget
from avrgui.tabs.pcc_tester import PCCTesterWidget
from avrgui.tabs.thermal_view_control import ThermalViewControlWidget
# from avrgui.tabs.vmc_control import VMCControlWidget
from avrgui.tabs.vmc_telemetry import VMCTelemetryWidget
from avrgui.tabs.water_drop import WaterDropWidget

controller = Controller()


class TabBar(QtWidgets.QTabBar):
    """
    Custom QTabBar for a QTabWidget to allow the tabs to be popped in/out
    from an external window.
    """

    pop_out: QtCore.SignalInstance = QtCore.Signal(int)  # type: ignore

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.tabBarDoubleClicked.connect(self.pop_out)  # type: ignore

    def contextMenuEvent(self, event: QtGui.QContextMenuEvent) -> None:
        menu = QtWidgets.QMenu(self)

        # needs to be done before the menu is popped up, otherwise the QEvent will expire
        selected_item = self.tabAt(event.pos())

        pop_out_action = QtGui.QAction("Pop Out", self)
        pop_out_action.triggered.connect(lambda: self.pop_out.emit(selected_item))  # type: ignore
        menu.addAction(pop_out_action)

        menu.popup(QtGui.QCursor.pos())


class TabWidget(QtWidgets.QTabWidget):
    """
    Custom QTabWidget that allows the tab to be popped in/out from an external window.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.tab_bar = TabBar(self)
        self.setTabBar(self.tab_bar)
        self.setMovable(True)

        self.tab_bar.pop_out.connect(self.pop_out)

    def pop_out(self, index: int) -> None:
        """
        Pop a tab out into a new window.
        """
        tab = self.widget(index)
        logger.debug(f"Pop out requested on tab {index}, {tab}")

        # don't allow user to pop out last tab
        visible = [i for i in range(self.count()) if self.isTabVisible(i)]
        logger.debug(f"Visible tabs: {visible}")
        if len(visible) <= 1:
            logger.warning("Not popping out last visible tab")
            return

        # don't allow user to pop out the last enabled, visible tab
        enabled_visible = [i for i in visible if self.isTabEnabled(i)]
        logger.debug(f"Enabled visible tabs: {enabled_visible}")
        if len(enabled_visible) <= 1 and index in enabled_visible:
            logger.warning("Not popping out last visible enabled tab")
            return

        self.setTabVisible(index, False)
        tab.setWindowFlags(QtCore.Qt.Window)  # type: ignore
        tab.show()

    def pop_in(self, widget: QtWidgets.QWidget) -> None:
        """
        Pop a tab out into a new window.
        """
        index = self.indexOf(widget)
        logger.debug(f"Popping in tab {index}, {widget}")

        widget.setWindowFlags(QtCore.Qt.Widget)  # type: ignore
        self.setTabVisible(index, True)


class MainWindow(QtWidgets.QWidget):
    """
    This is the main application class.
    """

    controller_circle = QtCore.Signal(bool)
    controller_cross = QtCore.Signal(bool)
    controller_triangle = QtCore.Signal(bool)
    controller_square = QtCore.Signal(bool)
    controller_lb = QtCore.Signal()
    controller_rb = QtCore.Signal(bool)
    controller_lt = QtCore.Signal(int)
    controller_rt = QtCore.Signal()
    controller_ps = QtCore.Signal()
    controller_l = QtCore.Signal(tuple)
    controller_r = QtCore.Signal(tuple)
    controller_touchBtn = QtCore.Signal()
    controller_dpad = QtCore.Signal(int)
    controller_l_press = QtCore.Signal()
    controller_r_press = QtCore.Signal()
    controller_mic = QtCore.Signal()

    def __init__(self) -> None:
        super().__init__()

        self.water_drop_popup = None
        self.menu_bar = None
        self.toast: Toast | None = None
        self.tabs = None
        self.main_connection_widget = None
        self.pcc_tester_widget = None
        self.mqtt_debug_widget = None
        self.vmc_telemetry_widget = None
        self.vmc_control_widget = None
        self.thermal_view_control_widget = None
        self.camera_view_widget = None
        self.water_drop_widget = None
        self.moving_map_widget = None
        # self.autonomy_widget = None
        self.heads_up_widget = None

        set_icon(self)
        self.setWindowTitle("AVR GUI")

        self.mqtt_connected = False
        self.serial_connected = False

    def build(self) -> None:
        """
        Build the GUI layout
        """
        self.toast = Toast.get(self)
        self.water_drop_popup = WaterDropPopup(self)
        self.menu_bar = QtWidgets.QMenuBar()

        layout = QtWidgets.QVBoxLayout(self)
        self.setLayout(layout)

        self.tabs = TabWidget(self)
        layout.addWidget(self.tabs)

        # add tabs

        # connection widget

        self.main_connection_widget = MainConnectionWidget(self)
        self.main_connection_widget.build()
        self.main_connection_widget.pop_in.connect(self.tabs.pop_in)
        self.tabs.addTab(
                self.main_connection_widget, self.main_connection_widget.windowTitle()
        )

        self.main_connection_widget.mqtt_connection_widget.connection_state.connect(
                self.set_mqtt_connected_state
        )
        self.main_connection_widget.serial_connection_widget.connection_state.connect(
                self.set_serial_connected_state
        )

        self.menu_bar.addMenu(self.main_connection_widget.mqtt_connection_widget.mqtt_menu)

        def toast_mqtt(topic, message) -> None:
            if topic == "avr/gui/toast":
                try:
                    message = json.loads(message)
                    text = message.get("text", "")
                    timeout = message.get("timeout", 1)
                    self.toast.show_message(text, timeout)
                except json.JSONDecodeError:
                    pass

        self.main_connection_widget.mqtt_connection_widget.mqtt_client.message.connect(
                toast_mqtt
        )

        # pcc tester widget

        self.pcc_tester_widget = PCCTesterWidget(
                self, self.main_connection_widget.serial_connection_widget.serial_client
        )
        self.pcc_tester_widget.build()
        self.pcc_tester_widget.pop_in.connect(self.tabs.pop_in)
        self.tabs.addTab(self.pcc_tester_widget, self.pcc_tester_widget.windowTitle())

        # mqtt debug widget

        self.mqtt_debug_widget = MQTTDebugWidget(self)
        self.mqtt_debug_widget.build()
        self.mqtt_debug_widget.pop_in.connect(self.tabs.pop_in)
        self.tabs.addTab(self.mqtt_debug_widget, self.mqtt_debug_widget.windowTitle())

        self.main_connection_widget.mqtt_connection_widget.mqtt_client.message.connect(
                self.mqtt_debug_widget.process_message
        )
        self.mqtt_debug_widget.emit_message.connect(
                self.main_connection_widget.mqtt_connection_widget.mqtt_client.publish
        )
        # self.main_connection_widget.zmq_connection_widget.zmq_client.connection_state.connect(
        #         self.mqtt_debug_widget.zmq_send_button.setEnabled
        # )
        self.mqtt_debug_widget.zmq_send_button.setEnabled(True)
        self.mqtt_debug_widget.send_zmq.connect(
                lambda message: self.main_connection_widget.zmq_connection_widget.publish(message[0], message[1])
        )

        # mqtt logger widget

        # self.mqtt_logger_widget = MQTTLoggerWidget(self)
        # self.mqtt_logger_widget.build()
        # self.mqtt_logger_widget.pop_in.connect(self.tabs.pop_in)
        # self.tabs.addTab(self.mqtt_logger_widget, self.mqtt_logger_widget.windowTitle())
        #
        # self.main_connection_widget.mqtt_connection_widget.mqtt_client.message.connect(
        #         self.mqtt_logger_widget.process_message
        # )

        # vmc telemetry widget

        self.vmc_telemetry_widget = VMCTelemetryWidget(self, controller)
        self.vmc_telemetry_widget.build()
        self.vmc_telemetry_widget.pop_in.connect(self.tabs.pop_in)
        self.tabs.addTab(
                self.vmc_telemetry_widget, self.vmc_telemetry_widget.windowTitle()
        )

        self.main_connection_widget.mqtt_connection_widget.mqtt_client.message.connect(
                self.vmc_telemetry_widget.process_message
        )

        self.vmc_telemetry_widget.emit_message.connect(
                self.main_connection_widget.mqtt_connection_widget.mqtt_client.publish
        )

        if controller is not None:
            def set_mic_led(state: bool):
                controller.mic_button.led_state = state

            self.vmc_telemetry_widget.armed_state.connect(
                    set_mic_led
            )

        self.controller_ps.connect(
                lambda: self.vmc_telemetry_widget.restart_service(
                        None,
                        True,
                        """This will shutdown the vehicle management computer.
                        This means that you have to unplug it and re plug it to restart it again.""",
                        lambda: self.vmc_telemetry_widget.send_message("avr/shutdown", "", qos=2)
                )
        )

        self.controller_mic.connect(
                lambda: self.vmc_telemetry_widget.toggle_arm()
        )

        # vmc control widget

        # self.vmc_control_widget = VMCControlWidget(self)
        # self.vmc_control_widget.build()
        # self.vmc_control_widget.pop_in.connect(self.tabs.pop_in)
        # self.tabs.addTab(self.vmc_control_widget, self.vmc_control_widget.windowTitle())
        #
        # self.vmc_control_widget.emit_message.connect(
        #         self.main_connection_widget.mqtt_connection_widget.mqtt_client.publish
        # )

        # thermal view widget

        self.thermal_view_control_widget = ThermalViewControlWidget(
                self,
                self.main_connection_widget.zmq_connection_widget.zmq_client
        )
        self.thermal_view_control_widget.build()
        self.thermal_view_control_widget.pop_in.connect(self.tabs.pop_in)
        self.tabs.addTab(
                self.thermal_view_control_widget,
                self.thermal_view_control_widget.windowTitle(),
        )

        self.main_connection_widget.mqtt_connection_widget.mqtt_client.message_bytes.connect(
                self.thermal_view_control_widget.process_message_bytes
        )

        self.thermal_view_control_widget.emit_message.connect(
                self.main_connection_widget.mqtt_connection_widget.mqtt_client.publish
        )

        self.controller_r.connect(
                self.thermal_view_control_widget.on_controller_r
        )

        self.controller_rt.connect(
                self.thermal_view_control_widget.on_controller_rt
        )

        self.controller_rb.connect(
                self.thermal_view_control_widget.on_controller_rb
        )

        self.controller_circle.connect(
                self.thermal_view_control_widget.on_controller_circle
        )

        self.controller_r_press.connect(
                self.thermal_view_control_widget.on_controller_r3
        )

        # camera view widget

        self.camera_view_widget = CameraViewWidget(self)
        self.camera_view_widget.build()
        self.camera_view_widget.pop_in.connect(self.tabs.pop_in)
        self.tabs.addTab(
                self.camera_view_widget,
                self.camera_view_widget.windowTitle(),
        )

        self.main_connection_widget.mqtt_connection_widget.mqtt_client.message.connect(
                self.camera_view_widget.process_message
        )

        self.camera_view_widget.emit_message.connect(
                self.main_connection_widget.mqtt_connection_widget.mqtt_client.publish
        )

        self.main_connection_widget.mqtt_connection_widget.connection_state.connect(
                self.camera_view_widget.mqtt_connection_state
        )

        self.menu_bar.addMenu(self.camera_view_widget.video_menu)

        # water drop widget

        self.water_drop_widget = WaterDropWidget(
                self,
                self.main_connection_widget.zmq_connection_widget.zmq_client
        )
        self.water_drop_widget.build()
        self.water_drop_widget.pop_in.connect(self.tabs.pop_in)
        self.tabs.addTab(
                self.water_drop_widget,
                self.water_drop_widget.windowTitle(),
        )

        self.main_connection_widget.mqtt_connection_widget.mqtt_client.message.connect(
                self.water_drop_widget.process_message
        )

        self.water_drop_widget.emit_message.connect(
                self.main_connection_widget.mqtt_connection_widget.mqtt_client.publish
        )

        self.controller_lt.connect(
                self.water_drop_widget.set_bpu
        )
        self.controller_touchBtn.connect(
                lambda: self.main_connection_widget.mqtt_connection_widget.mqtt_client.publish(
                        "avr/autonomy/kill",
                        ""
                )
        )
        self.controller_lb.connect(
                lambda: self.main_connection_widget.mqtt_connection_widget.mqtt_client.publish(
                        "avr/autonomy/set_auto_water_drop",
                        json.dumps({
                            "enabled": True
                        })
                )
        )

        # moving map widget

        self.moving_map_widget = MovingMapWidget(self)
        self.moving_map_widget.build()
        self.moving_map_widget.pop_in.connect(self.tabs.pop_in)
        self.tabs.addTab(self.moving_map_widget, self.moving_map_widget.windowTitle())

        self.main_connection_widget.mqtt_connection_widget.mqtt_client.message.connect(
                self.moving_map_widget.process_message
        )

        # autonomy widget

        # self.autonomy_widget = AutonomyWidget(self)
        # self.autonomy_widget.build()
        # self.autonomy_widget.pop_in.connect(self.tabs.pop_in)
        # self.tabs.addTab(self.autonomy_widget, self.autonomy_widget.windowTitle())
        #
        # self.autonomy_widget.emit_message.connect(
        #         self.main_connection_widget.mqtt_connection_widget.mqtt_client.publish
        # )

        # heads up display widget

        self.heads_up_widget = HeadsUpDisplayWidget(
                self.main_connection_widget.mqtt_connection_widget.mqtt_client,
                self
        )
        self.heads_up_widget.build()
        self.heads_up_widget.pop_in.connect(self.tabs.pop_in)
        self.tabs.addTab(
                self.heads_up_widget,
                self.heads_up_widget.windowTitle(),
        )
        self.main_connection_widget.mqtt_connection_widget.mqtt_client.message.connect(
                self.heads_up_widget.process_message
        )
        self.heads_up_widget.emit_message.connect(
                self.main_connection_widget.mqtt_connection_widget.mqtt_client.publish
        )
        self.heads_up_widget.zed_pane.toggle_connection.connect(
                lambda: self.camera_view_widget.change_streaming.emit(
                        not self.camera_view_widget.is_connected
                )
        )
        self.camera_view_widget.update_frame.connect(
                self.heads_up_widget.zed_pane.update_frame.emit
        )
        self.thermal_view_control_widget.viewer.update_frame.connect(
                self.heads_up_widget.thermal_pane.update_frame.emit
        )
        self.water_drop_widget.update_position.connect(
                self.heads_up_widget.water_pane.move_dropper.emit
        )
        self.vmc_telemetry_widget.voltage_update.connect(
                self.heads_up_widget.telemetry_pane.update_battery.emit
        )
        self.vmc_telemetry_widget.armed_update.connect(
                self.heads_up_widget.telemetry_pane.update_armed.emit
        )
        self.vmc_telemetry_widget.mode_update.connect(
                self.heads_up_widget.telemetry_pane.update_mode.emit
        )

        # set initial state
        self.set_mqtt_connected_state(ConnectionState.disconnected)
        self.set_serial_connected_state(ConnectionState.disconnected)

    def set_mqtt_connected_state(self, connection_state: ConnectionState) -> None:
        self.mqtt_connected = connection_state == ConnectionState.connected

        # list of widgets that are mqtt connected
        widgets = [
            self.mqtt_debug_widget,
            # self.mqtt_logger_widget,
            self.vmc_telemetry_widget,
            self.vmc_control_widget,
            self.thermal_view_control_widget,
            self.camera_view_widget,
            self.water_drop_widget,
            self.moving_map_widget,
            # self.autonomy_widget,
            self.heads_up_widget,
        ]

        # disable/enable widgets
        for widget in widgets:
            idx = self.tabs.indexOf(widget)
            self.tabs.setTabEnabled(idx, self.mqtt_connected)
            if not self.mqtt_connected:
                self.tabs.setTabToolTip(idx, "MQTT not connected")
            else:
                self.tabs.setTabToolTip(idx, "")

        # clear widgets to a starting state
        if not self.mqtt_connected:
            self.mqtt_debug_widget.clear()
            # self.mqtt_logger_widget.clear()
            self.vmc_telemetry_widget.clear()
            self.thermal_view_control_widget.clear()
            self.camera_view_widget.clear()
            self.water_drop_widget.clear()
            self.moving_map_widget.clear()
            self.heads_up_widget.clear()

    def set_serial_connected_state(self, connection_state: ConnectionState) -> None:
        self.serial_connected = connection_state == ConnectionState.connected

        # deal with pcc tester
        idx = self.tabs.indexOf(self.pcc_tester_widget)
        self.tabs.tab_bar.setTabVisible(idx, self.serial_connected)
        self.tabs.setTabEnabled(idx, self.serial_connected)
        if not self.serial_connected:
            self.pcc_tester_widget.reset_all()
            self.tabs.setTabToolTip(idx, "Serial not connected")
        else:
            self.tabs.setTabToolTip(idx, "")

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        self.toast.window_resize_event(event)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        """
        Override close event to close all connections.
        """
        if self.mqtt_connected:
            self.main_connection_widget.mqtt_connection_widget.mqtt_client.logout()

        if self.serial_connected:
            self.main_connection_widget.serial_connection_widget.serial_client.logout()

        event.accept()

        controller.close()


w: MainWindow | None = None


def main() -> None:
    global w
    # create Qt Application instance
    app = QtWidgets.QApplication()
    pixmap = QtGui.QPixmap("assets/splash.png")
    splash = QtWidgets.QSplashScreen(pixmap)
    splash.show()
    app.processEvents()

    app.setWindowIcon(QtGui.QIcon("assets/icon.png"))
    app.setApplicationName("Team Daedalus AVR Gui")
    app.setApplicationDisplayName("Team Daedalus AVR Gui")

    # create the main window
    w = MainWindow()

    if controller is not None:
        controller.circle.on_state.register(w.controller_circle.emit)
        controller.cross.on_state.register(w.controller_cross.emit)
        controller.triangle.on_state.register(w.controller_triangle.emit)
        controller.square.on_state.register(w.controller_square.emit)
        controller.left_bumper.on_press.register(w.controller_lb.emit)
        controller.right_bumper.on_state.register(w.controller_rb.emit)
        controller.left_trigger.on_pos.register(w.controller_lt.emit)
        controller.right_trigger.on_press.register(w.controller_rt.emit)
        controller.ps.on_press.register(w.controller_ps.emit)
        controller.left_stick.on_move.register(w.controller_l.emit)
        controller.right_stick.on_move.register(w.controller_r.emit)
        controller.touchpad.on_press.register(w.controller_touchBtn.emit)
        controller.dpad.on_direction.register(w.controller_dpad.emit)
        controller.left_stick.on_press.register(w.controller_l_press.emit)
        controller.right_stick.on_press.register(w.controller_r_press.emit)
        controller.mic_button.on_press.register(w.controller_mic.emit)

    w.build()

    if controller is not None:
        def set_player_led(state: ConnectionState) -> None:
            if state == ConnectionState.connected:
                controller.player_led.player_num = 3
            elif state == ConnectionState.connecting:
                controller.player_led.raw = 10
            elif state == ConnectionState.disconnecting:
                controller.player_led.raw = 31
            else:
                controller.player_led.player_num = 0

        w.main_connection_widget.mqtt_connection_widget.connection_state.connect(set_player_led)

    d = QtWidgets.QMenu(w)
    mqtt_action = QtGui.QAction("MQTT Disconnected")
    mqtt_action.triggered.connect(w.main_connection_widget.mqtt_connection_widget.mqtt_client.logout)
    mqtt_action.setEnabled(False)
    w.main_connection_widget.mqtt_connection_widget.connection_state.connect(
            lambda state: mqtt_action.setEnabled(state == ConnectionState.connected)
    )
    w.main_connection_widget.mqtt_connection_widget.connection_state.connect(
            lambda state: mqtt_action.setText(
                    "Disconnect MQTT" if state == ConnectionState.connected else "MQTT Disconnected"
            )
    )
    d.addAction(mqtt_action)

    kill_action = QtGui.QAction("Kill Motors")
    kill_action.triggered.connect(
            lambda: w.main_connection_widget.mqtt_connection_widget.mqtt_client.publish(
                    "avr/kill", "", qos=2
            )
    )
    kill_action.setEnabled(False)
    w.main_connection_widget.mqtt_connection_widget.connection_state.connect(
            lambda state: kill_action.setEnabled(
                    True if state == ConnectionState.connected else False
            )
    )
    d.addAction(kill_action)

    controller_action = QtGui.QAction("Connect Controller")
    w.main_connection_widget.controller_connect_button.clicked.connect(
            lambda: controller.open()
    )
    d.addAction(controller_action)

    w.main_connection_widget.mqtt_connection_widget.connection_state.connect(
            lambda state: w.main_connection_widget.mqtt_connection_widget.mqtt_client.publish(
                    "avr/status/request_update", "", qos=2
            ) if state == ConnectionState.connected else None
    )

    w.main_connection_widget.mqtt_connection_widget.mqtt_client.message.connect(on_message)

    w.show()
    splash.finish(w)

    # run
    sys.exit(app.exec())


def on_message(topic: str, payload: str | dict) -> None:
    if "avr/gui/sound/" in topic:
        filename = topic[len("avr/gui/sound/"):]
        if os.path.isfile(f"assets/sound/{filename}.wav"):
            playsound(f"assets/sound/{filename}.wav", block=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
            "--test-bundle",
            action="store_true",
            help="Immediately exit the application with exit code 0, to test bundling",
    )
    args = parser.parse_args()

    if args.test_bundle:
        sys.exit(0)

    main()
