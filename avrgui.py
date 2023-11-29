import argparse
import json
import os.path
import sys
import time
from threading import Thread

from PySide6 import QtCore, QtGui, QtWidgets
from loguru import logger

from avrgui.lib.controller.pythondualsense import Dualsense, TriggerMode, find_devices, BrightnessLevel
from avrgui.lib.enums import ConnectionState
from avrgui.lib.qt_icon import set_icon
from avrgui.lib.toast import Toast
from avrgui.lib.water_drop_popup import WaterDropPopup
from avrgui.tabs.connection.main import MainConnectionWidget
from avrgui.tabs.heads_up import HeadsUpDisplayWidget
from avrgui.tabs.thermal_view_control import ThermalViewControlWidget
from avrgui.tabs.vmc_telemetry import VMCTelemetryWidget
from avrgui.tabs.water_drop import WaterDropWidget

controller = Dualsense()
was_connected = False

tabs_unlocked = False


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
    controller_rb = QtCore.Signal()
    controller_lt = QtCore.Signal()
    controller_rt = QtCore.Signal(bool)
    controller_dpad_left = QtCore.Signal()
    controller_dpad_right = QtCore.Signal()
    controller_options = QtCore.Signal()
    controller_share = QtCore.Signal()
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
        self.main_connection_widget: MainConnectionWidget | None = None
        self.pcc_tester_widget = None
        self.mqtt_debug_widget = None
        self.vmc_telemetry_widget = None
        self.vmc_control_widget = None
        self.thermal_view_control_widget = None
        self.camera_view_widget = None
        self.water_drop_widget = None
        self.moving_map_widget = None
        self.heads_up_widget: HeadsUpDisplayWidget | None = None

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

        self.main_connection_widget.ros_client_connection_widget.connection_state.connect(
            self.set_mqtt_connected_state
        )

        self.menu_bar.addMenu(self.main_connection_widget.ros_client_connection_widget.ros_client_menu)

        self.controller_share.connect(
            self.main_connection_widget.ros_client_connection_widget.connect_slot
        )

        # def toast_mqtt(topic, message) -> None:
        #     if topic == "avr/gui/toast":
        #         try:
        #             message = json.loads(message)
        #             text = message.get("text", "")
        #             timeout = message.get("timeout", 1)
        #             self.toast.show_message(text, timeout)
        #         except json.JSONDecodeError:
        #             pass

        # self.main_connection_widget.socketio_connection_widget.socketio_client.client.message.connect(
        #         toast_mqtt
        # )

        ros_client = self.main_connection_widget.ros_client_connection_widget.ros_client

        def shift_left() -> None:
            if tabs_unlocked:
                index = (self.tabs.tab_bar.currentIndex() - 1) % self.tabs.tab_bar.count()
                self.tabs.tab_bar.setCurrentIndex(index)

        self.controller_dpad_left.connect(shift_left)

        def shift_right() -> None:
            if tabs_unlocked:
                index = (self.tabs.tab_bar.currentIndex() + 1) % self.tabs.tab_bar.count()
                self.tabs.tab_bar.setCurrentIndex(index)

        self.controller_dpad_right.connect(shift_right)

        # vmc telemetry widget

        self.vmc_telemetry_widget = VMCTelemetryWidget(self, ros_client, controller)
        self.vmc_telemetry_widget.build()
        self.vmc_telemetry_widget.pop_in.connect(self.tabs.pop_in)
        self.tabs.addTab(
            self.vmc_telemetry_widget, self.vmc_telemetry_widget.windowTitle()
        )

        # if controller is not None:
        #     def set_mic_led(state: bool):
        #         controller.mic_button.led_state = state
        #
        #     self.vmc_telemetry_widget.armed_state.connect(
        #             set_mic_led
        #     )

        self.controller_ps.connect(
            self.vmc_telemetry_widget.main_shutdown_callback
        )

        # thermal view widget

        self.thermal_view_control_widget = ThermalViewControlWidget(self, ros_client)
        self.thermal_view_control_widget.build()
        self.thermal_view_control_widget.pop_in.connect(self.tabs.pop_in)
        self.tabs.addTab(
            self.thermal_view_control_widget,
            self.thermal_view_control_widget.windowTitle(),
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

        self.controller_r_press.connect(
            self.thermal_view_control_widget.on_controller_r3
        )

        # camera view widget

        # self.camera_view_widget = CameraViewWidget(self)
        # self.camera_view_widget.client = self.main_connection_widget.socketio_connection_widget.socketio_client.client
        # self.camera_view_widget.build()
        # self.camera_view_widget.pop_in.connect(self.tabs.pop_in)
        # self.tabs.addTab(
        #         self.camera_view_widget,
        #         self.camera_view_widget.windowTitle(),
        # )
        # 
        # self.main_connection_widget.socketio_connection_widget.connection_state.connect(
        #         self.camera_view_widget.mqtt_connection_state
        # )
        # 
        # self.menu_bar.addMenu(self.camera_view_widget.video_menu)

        # water drop widget

        self.water_drop_widget = WaterDropWidget(self, ros_client)
        self.water_drop_widget.build()
        self.water_drop_widget.pop_in.connect(self.tabs.pop_in)
        self.tabs.addTab(
            self.water_drop_widget,
            self.water_drop_widget.windowTitle(),
        )
        # self.controller_touchBtn.connect(
        #         lambda: self.main_connection_widget.ros_client_connection_widget.ros_client.client.publish(
        #                 "avr/autonomy/kill",
        #                 ""
        #         )
        # )
        # self.controller_lb.connect(
        #         lambda: self.main_connection_widget.ros_client_connection_widget.ros_client.client.publish(
        #                 "avr/autonomy/set_auto_water_drop",
        #                 json.dumps({
        #                     "enabled": True
        #                 })
        #         )
        # )

        # moving map widget

        # self.moving_map_widget = MovingMapWidget(self)
        # self.moving_map_widget.build()
        # self.moving_map_widget.pop_in.connect(self.tabs.pop_in)
        # self.tabs.addTab(self.moving_map_widget, self.moving_map_widget.windowTitle())

        # autonomy widget

        # self.autonomy_widget = AutonomyWidget(self)
        # self.autonomy_widget.build()
        # self.autonomy_widget.pop_in.connect(self.tabs.pop_in)
        # self.tabs.addTab(self.autonomy_widget, self.autonomy_widget.windowTitle())

        # heads up display widget

        self.heads_up_widget = HeadsUpDisplayWidget(self, ros_client, controller)
        self.heads_up_widget.build()
        self.heads_up_widget.pop_in.connect(self.tabs.pop_in)
        self.tabs.addTab(
            self.heads_up_widget,
            self.heads_up_widget.windowTitle(),
        )
        # self.heads_up_widget.zed_pane.toggle_connection.connect(
        #     lambda: self.camera_view_widget.change_streaming.emit(
        #         not self.camera_view_widget.is_connected
        #     )
        # )

        self.vmc_telemetry_widget.formatted_battery_signal.connect(
            self.heads_up_widget.telemetry_pane.formatted_battery_signal.emit
        )
        self.vmc_telemetry_widget.formatted_armed_signal.connect(
            self.heads_up_widget.telemetry_pane.formatted_armed_signal.emit
        )
        self.vmc_telemetry_widget.formatted_mode_signal.connect(
            self.heads_up_widget.telemetry_pane.formatted_mode_signal.emit
        )
        self.vmc_telemetry_widget.pose_state_signal.connect(
            self.heads_up_widget.telemetry_pane.pose_state_signal.emit
        )

        self.controller_triangle.connect(
            lambda v: self.heads_up_widget.water_pane.enable_drop() if v else None
        )
        self.controller_circle.connect(
            lambda v: self.heads_up_widget.water_pane.enable_blink() if v else None
        )
        self.controller_cross.connect(
            lambda v: self.heads_up_widget.water_pane.reset_bdu() if v else None
        )
        self.controller_touchBtn.connect(
            self.heads_up_widget.water_pane.stop_auton_drop
        )
        self.controller_mic.connect(
            lambda: self.heads_up_widget.water_pane.start_log_file()
            if self.heads_up_widget.water_pane.log_file is None else
            self.heads_up_widget.water_pane.close_log_file()
        )
        # self.camera_view_widget.update_frame.connect(
        #         self.heads_up_widget.zed_pane.update_frame.emit
        # )
        self.thermal_view_control_widget.viewer.update_frame.connect(
            self.heads_up_widget.thermal_pane.update_frame.emit
        )
        self.controller_lt.connect(
            self.heads_up_widget.water_pane.trigger_bdu_full
        )
        self.controller_lb.connect(
            self.heads_up_widget.water_pane.trigger_bdu
        )

        self.controller_options.connect(
            self.heads_up_widget.water_pane.toggle_use_full_drops
        )

        # set initial state
        self.set_mqtt_connected_state(ConnectionState.DISCONNECTED)
        self.set_serial_connected_state(ConnectionState.DISCONNECTED)

        controller.right_trigger.trigger_mode = TriggerMode.NO_RESISTANCE
        controller.right_trigger.trigger_section = (75, 120)
        controller.right_trigger.trigger_force = 255

        controller.left_trigger.trigger_mode = TriggerMode.NO_RESISTANCE
        controller.left_trigger.trigger_section = (75, 120)
        controller.left_trigger.trigger_force = 255

        controller.player_led.brightness = BrightnessLevel.HIGH
        controller.player_led.player_num = 0

    def set_mqtt_connected_state(self, connection_state: ConnectionState) -> None:
        global tabs_unlocked
        self.mqtt_connected = connection_state == ConnectionState.CONNECTED

        # list of widgets that are mqtt connected
        widgets = [
            # self.mqtt_debug_widget,
            # self.mqtt_logger_widget,
            self.vmc_telemetry_widget,
            self.vmc_control_widget,
            self.thermal_view_control_widget,
            # self.camera_view_widget,
            self.water_drop_widget,
            # self.moving_map_widget,
            # self.autonomy_widget,
            self.heads_up_widget,
        ]

        tabs_unlocked = self.mqtt_connected
        # disable/enable widgets
        for widget in widgets:
            idx = self.tabs.indexOf(widget)
            self.tabs.setTabEnabled(idx, self.mqtt_connected)
            if not self.mqtt_connected:
                self.tabs.setTabToolTip(idx, "SocketIO not connected")
            else:
                self.tabs.setTabToolTip(idx, "")

        # clear widgets to a starting state
        if not self.mqtt_connected:
            self.vmc_telemetry_widget.clear()
            self.thermal_view_control_widget.clear()
            # self.camera_view_widget.clear()
            self.water_drop_widget.clear()
            # self.moving_map_widget.clear()
            self.heads_up_widget.clear()

    def set_serial_connected_state(self, connection_state: ConnectionState) -> None:
        self.serial_connected = connection_state == ConnectionState.CONNECTED

        # deal with pcc tester
        idx = self.tabs.indexOf(self.pcc_tester_widget)
        self.tabs.tab_bar.setTabVisible(idx, self.serial_connected)
        self.tabs.setTabEnabled(idx, self.serial_connected)
        if not self.serial_connected:

            # self.pcc_tester_widget.reset_all()
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
            self.main_connection_widget.ros_client_connection_widget.ros_client.logout()
        self.heads_up_widget.water_pane.close_log_file()

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
        controller.right_bumper.on_press.register(w.controller_rb.emit)
        controller.left_trigger.on_press.register(w.controller_lt.emit)
        controller.right_trigger.on_state.register(w.controller_rt.emit)
        controller.dpad.left.on_press.register(w.controller_dpad_left.emit)
        controller.dpad.right.on_press.register(w.controller_dpad_right.emit)
        controller.ps.on_press.register(w.controller_ps.emit)
        controller.left_stick.on_move.register(w.controller_l.emit)
        controller.right_stick.on_move.register(w.controller_r.emit)
        controller.touchpad.on_press.register(w.controller_touchBtn.emit)
        controller.dpad.on_direction.register(w.controller_dpad.emit)
        controller.left_stick.on_press.register(w.controller_l_press.emit)
        controller.right_stick.on_press.register(w.controller_r_press.emit)
        controller.mic_button.on_press.register(w.controller_mic.emit)
        controller.options.on_press.register(w.controller_options.emit)
        controller.share.on_press.register(w.controller_share.emit)

    w.build()

    # if controller is not None:
    #     def set_player_led(state: ConnectionState) -> None:
    #         if state == ConnectionState.connected:
    #             controller.player_led.player_num = 3
    #         elif state == ConnectionState.connecting:
    #             controller.player_led.raw = 10
    #         elif state == ConnectionState.disconnecting:
    #             controller.player_led.raw = 31
    #         else:
    #             controller.player_led.player_num = 0
    #
    #     w.main_connection_widget.ros_client_connection_widget.connection_state.connect(set_player_led)

    d = QtWidgets.QMenu(w)
    # socketio_action = QtGui.QAction("SocketIO Disconnected")
    # socketio_action.triggered.connect(w.main_connection_widget.ros_client_connection_widget.ros_client.logout)
    # socketio_action.setEnabled(False)
    # w.main_connection_widget.ros_client_connection_widget.connection_state.connect(
    #     lambda state: socketio_action.setEnabled(state == ConnectionState.connected)
    # )
    # w.main_connection_widget.ros_client_connection_widget.connection_state.connect(
    #     lambda state: socketio_action.setText(
    #         "Disconnect SocketIO" if state == ConnectionState.connected else "SocketIO Disconnected"
    #     )
    # )
    # d.addAction(socketio_action)

    # kill_action = QtGui.QAction("Kill Motors")
    # kill_action.triggered.connect(
    #         lambda: w.main_connection_widget.socketio_connection_widget.socketio_client.client.publish(
    #                 "avr/kill", "", qos=2
    #         )
    # )
    # kill_action.setEnabled(False)
    # w.main_connection_widget.socketio_connection_widget.connection_state.connect(
    #         lambda state: kill_action.setEnabled(
    #                 True if state == ConnectionState.connected else False
    #         )
    # )
    # d.addAction(kill_action)

    # controller_action = QtGui.QAction("Connect Controller")
    # w.main_connection_widget.controller_connect_button.clicked.connect(
    #     lambda: controller.open()
    # )
    # w.main_connection_widget.controller_connect_button.clicked.connect(
    #     lambda: controller.force_update()
    # )
    # d.addAction(controller_action)

    # w.main_connection_widget.socketio_connection_widget.connection_state.connect(
    #         lambda state: w.main_connection_widget.socketio_connection_widget.socketio_client.client.publish(
    #                 "avr/status/request_update", "", qos=2
    #         ) if state == ConnectionState.connected else None
    # )

    w.show()
    splash.finish(w)

    def set_controller_outputs() -> None:
        global was_connected
        connected = False
        exists = w.main_connection_widget.ros_client_connection_widget.ros_client.client is not None
        if exists:
            connected = w.main_connection_widget.ros_client_connection_widget.ros_client.client.is_connected
        if connected:
            controller.right_trigger.trigger_mode = TriggerMode.SECTION
            controller.left_trigger.trigger_mode = TriggerMode.SECTION
            controller.player_led.player_num = 3
        else:
            controller.right_trigger.trigger_mode = TriggerMode.NO_RESISTANCE
            controller.left_trigger.trigger_mode = TriggerMode.NO_RESISTANCE
            controller.player_led.player_num = 0

        was_connected = connected

    def alert_buzz() -> None:
        controller.right_rumble.value = 255
        controller.left_rumble.value = 255
        time.sleep(0.1)
        controller.right_rumble.value = 0
        controller.left_rumble.value = 0
        time.sleep(0.1)
        controller.right_rumble.value = 255
        controller.left_rumble.value = 255
        time.sleep(0.1)
        controller.right_rumble.value = 0
        controller.left_rumble.value = 0

    def connection_callback(connection_state: ConnectionState) -> None:
        set_controller_outputs()
        if connection_state == ConnectionState.CONNECTED:
            Thread(target=alert_buzz, daemon=True).start()
        elif connection_state == ConnectionState.FAILURE:
            Toast.get().show_message('Failed to connect to rosbridge', 1)

    w.main_connection_widget.ros_client_connection_widget.connection_state.connect(connection_callback)

    def reconnect_controller() -> None:
        while True:
            set_controller_outputs()
            if not controller.is_open:
                if len(find_devices()) > 0:
                    controller.open()
                    if controller.is_open:
                        logger.info("Controller Auto-Connected")
                        controller.force_update()
                        controller.right_rumble.value = 255
                        controller.left_rumble.value = 255
                        time.sleep(0.25)
                        controller.right_rumble.value = 0
                        controller.left_rumble.value = 0
                else:
                    time.sleep(1)
            else:
                time.sleep(5)

    Thread(target=reconnect_controller, daemon=True).start()

    # run
    sys.exit(app.exec())


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
