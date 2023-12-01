import sys
import time
from threading import Thread

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtWidgets import QApplication
from easing_functions import ExponentialEaseInOut
from qmaterialwidgets import (MaterialWindow, SplashScreen as MaterialSplashScreen,
                              Theme, setTheme, FluentIcon, MaterialTitleBar, MaterialIconBase, palette, NavigationRail,
                              InfoBarIcon)

from loguru import logger

from avrgui.lib.controller.pythondualsense import Dualsense, TriggerMode, find_devices, BrightnessLevel
from avrgui.lib.enums import ConnectionState
from avrgui.lib.toast import Toast
from avrgui.tabs.connection.main import MainConnectionWidget
from avrgui.tabs.heads_up import HeadsUpDisplayWidget
from avrgui.tabs.vmc_telemetry import VMCTelemetryWidget

controller = Dualsense()
was_connected = False

QApplication.setHighDpiScaleFactorRoundingPolicy(QtCore.Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)


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


class MainWindow(MaterialWindow):
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
    controller_dpad_up = QtCore.Signal()
    controller_dpad_down = QtCore.Signal()
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

        self.setWindowIcon(QtGui.QIcon('assets/logo.png'))
        self.setWindowTitle('Daedalus AVR GUI')

        self.ros_connected = False

        self.is_fullscreen = True

    def build(self) -> None:
        """
        Build the GUI layout
        """
        self.toast = Toast.get(self)
        self.menu_bar = QtWidgets.QMenuBar()

        # add tabs

        # connection widget

        self.main_connection_widget = MainConnectionWidget(self)
        self.main_connection_widget.build()
        self.addSubInterface(self.main_connection_widget, FluentIcon.CONNECT, 'Connection')

        self.main_connection_widget.ros_client_connection_widget.connection_state.connect(
            self.set_ros_connected_state
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

        # vmc telemetry widget

        self.vmc_telemetry_widget = VMCTelemetryWidget(self, ros_client, controller)
        self.vmc_telemetry_widget.build()
        self.addSubInterface(self.vmc_telemetry_widget, FluentIcon.DEVELOPER_TOOLS, 'Telemetry')

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

        # self.thermal_view_control_widget = ThermalViewControlWidget(self, ros_client)
        # self.thermal_view_control_widget.build()
        # self.addSubInterface(self.thermal_view_control_widget, FluentIcon.CAMERA, 'Thermal')
        #
        # self.controller_r.connect(
        #     self.thermal_view_control_widget.on_controller_r
        # )
        #
        # self.controller_rt.connect(
        #     self.thermal_view_control_widget.on_controller_rt
        # )
        #
        # self.controller_rb.connect(
        #     self.thermal_view_control_widget.on_controller_rb
        # )
        #
        # self.controller_r_press.connect(
        #     self.thermal_view_control_widget.on_controller_r3
        # )

        # camera view widget

        # self.camera_view_widget = CameraViewWidget(self)
        # self.camera_view_widget.client = self.main_connection_widget.socketio_connection_widget.socketio_client.client
        # self.camera_view_widget.build()
        # 
        # self.main_connection_widget.socketio_connection_widget.connection_state.connect(
        #         self.camera_view_widget.mqtt_connection_state
        # )
        # 
        # self.menu_bar.addMenu(self.camera_view_widget.video_menu)

        # water drop widget

        # self.water_drop_widget = WaterDropWidget(self, ros_client)
        # self.water_drop_widget.build()
        # self.addSubInterface(self.water_drop_widget, FluentIcon.ARROW_DOWN, 'Water Drop')
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

        # autonomy widget

        # self.autonomy_widget = AutonomyWidget(self)
        # self.autonomy_widget.build()

        # heads up display widget

        self.heads_up_widget = HeadsUpDisplayWidget(self, ros_client, controller)
        self.heads_up_widget.build()
        self.addSubInterface(self.heads_up_widget, FluentIcon.FULL_SCREEN, 'HUD')
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
            lambda: self.heads_up_widget.water_pane.logging_switch.setChecked(
                not self.heads_up_widget.water_pane.logging_switch.isChecked()
            )
        )
        self.controller_rb.connect(
            self.heads_up_widget.laser_pane.fire
        )
        self.controller_rt.connect(
            lambda state: self.heads_up_widget.laser_pane.loop_switch.setChecked(state)
            if self.heads_up_widget.laser_pane.laser_set_loop_client is not None or not state else None
        )
        # self.camera_view_widget.update_frame.connect(
        #         self.heads_up_widget.zed_pane.update_frame.emit
        # )
        # self.thermal_view_control_widget.viewer.update_frame.connect(
        #     self.heads_up_widget.thermal_pane.update_frame.emit
        # )
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
        self.set_ros_connected_state(ConnectionState.DISCONNECTED)

        routes = ['main_connection', 'vmc_telemetry', 'heads_up_display']

        def get_selected_route() -> int:
            for route, item in self.navigationInterface.items.items():
                if item.isSelected:
                    return routes.index(route)

        def shift_up() -> None:
            index = (get_selected_route() - 1) % len(routes)
            self.stackedWidget.setCurrentIndex(index)
            self.navigationInterface.setCurrentItem(routes[index])

        self.controller_dpad_up.connect(shift_up)

        def shift_down() -> None:
            index = (get_selected_route() + 1) % len(routes)
            self.stackedWidget.setCurrentIndex(index)
            self.navigationInterface.setCurrentItem(routes[index])

        self.controller_dpad_down.connect(shift_down)

        controller.right_trigger.trigger_mode = TriggerMode.NO_RESISTANCE
        controller.right_trigger.trigger_section = (75, 120)
        controller.right_trigger.trigger_force = 255

        controller.left_trigger.trigger_mode = TriggerMode.NO_RESISTANCE
        controller.left_trigger.trigger_section = (75, 120)
        controller.left_trigger.trigger_force = 255

        controller.player_led.brightness = BrightnessLevel.HIGH
        controller.player_led.player_num = 0

    def set_ros_connected_state(self, connection_state: ConnectionState) -> None:
        self.ros_connected = connection_state == ConnectionState.CONNECTED

        # clear widgets to a starting state
        if not self.ros_connected:
            self.vmc_telemetry_widget.clear()
            # self.thermal_view_control_widget.clear()
            # self.camera_view_widget.clear()
            # self.water_drop_widget.clear()
            # self.moving_map_widget.clear()
            self.heads_up_widget.clear()

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        title_bar: MaterialTitleBar = w.titleBar
        title_bar.setFixedWidth(event.size().width())

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        """
        Override close event to close all connections.
        """
        if self.ros_connected:
            self.main_connection_widget.ros_client_connection_widget.ros_client.logout()
        self.heads_up_widget.water_pane.close_log_file()

        controller.close()

        event.accept()

    def toggle_fullscreen(self) -> None:
        self.is_fullscreen = not self.is_fullscreen
        if self.is_fullscreen:
            self.showFullScreen()
        else:
            self.showNormal()
        self.titleBar.maxBtn.setMaxState(self.is_fullscreen)


class SplashScreen(MaterialSplashScreen):
    def __init__(self, icon: str | QtGui.QIcon | MaterialIconBase, parent=None, enable_shadow=True) -> None:
        super().__init__(icon, parent, enable_shadow)
        self.opacity = 1
        self.shadowEffect.deleteLater()

    def paintEvent(self, e) -> None:
        painter = QtGui.QPainter(self)
        painter.setPen(QtCore.Qt.PenStyle.NoPen)

        # draw background
        c = 32
        painter.setBrush(QtGui.QColor(c, c, c, round(self.opacity * 255)))
        painter.drawRect(self.rect())
        painter.end()


w: MainWindow | None = None


def main() -> None:
    global w
    # create Qt Application instance
    setTheme(Theme.AUTO)
    app = QtWidgets.QApplication()
    app.setAttribute(QtCore.Qt.ApplicationAttribute.AA_DontCreateNativeWidgetSiblings)

    app.setWindowIcon(QtGui.QIcon("assets/icon.png"))
    app.setApplicationName("Daedalus AVR GUI")
    app.setApplicationDisplayName("Daedalus AVR GUI")

    # create the main window
    w = MainWindow()
    w.setMinimumSize(QtCore.QSize(900, 600))
    splash_screen = SplashScreen(QtGui.QIcon('assets/splash.png'), w)
    splash_screen.setIconSize(QtCore.QSize(220, 220))
    splash_screen.raise_()

    title_bar: MaterialTitleBar = w.titleBar
    palette.setThemeColor(QtGui.QColor(156, 67, 53))
    title_bar.setFixedWidth(w.size().width())
    title_bar.maxBtn.setMaxState(True)
    title_bar.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
    # noinspection PyUnresolvedReferences,PyProtectedMember
    title_bar.maxBtn.clicked.disconnect(title_bar._TitleBarBase__toggleMaxState)
    title_bar.maxBtn.clicked.connect(w.toggle_fullscreen)
    title_bar.maxBtn.setVisible(False)
    title_bar.minBtn.setVisible(False)
    w.showFullScreen()

    app.processEvents()

    if controller is not None:
        controller.circle.on_state.register(w.controller_circle.emit)
        controller.cross.on_state.register(w.controller_cross.emit)
        controller.triangle.on_state.register(w.controller_triangle.emit)
        controller.square.on_state.register(w.controller_square.emit)
        controller.left_bumper.on_press.register(w.controller_lb.emit)
        controller.right_bumper.on_press.register(w.controller_rb.emit)
        controller.left_trigger.on_press.register(w.controller_lt.emit)
        controller.right_trigger.on_state.register(w.controller_rt.emit)
        controller.dpad.up.on_press.register(w.controller_dpad_up.emit)
        controller.dpad.down.on_press.register(w.controller_dpad_down.emit)
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

    count = 20
    duration = 0.5

    opacity_effect = QtWidgets.QGraphicsOpacityEffect(w)
    opacity_effect.setOpacity(1)
    splash_screen.iconWidget.setGraphicsEffect(opacity_effect)
    ease = ExponentialEaseInOut(start=1, end=0, duration=count)
    index = 0
    wait_time = round(duration // (count + 1)) * 1000
    timer = QtCore.QTimer(splash_screen)
    timer.setTimerType(QtCore.Qt.TimerType.PreciseTimer)

    def splash_reveal_callback() -> None:
        nonlocal index

        opacity = ease(index)
        opacity_effect.setOpacity(opacity)
        splash_screen.opacity = opacity

        if index == count + 1:
            timer.stop()
            timer.deleteLater()
            splash_screen.finish()

        splash_screen.update()

        index += 1

    timer.timeout.connect(splash_reveal_callback)
    timer.start(wait_time)

    def connection_state_callback(connection_state: ConnectionState) -> None:
        navigation_interface: NavigationRail = w.navigationInterface
        state = connection_state == ConnectionState.CONNECTED

        for name, item in navigation_interface.items.items():
            if not name == 'main_connection':
                item.setEnabled(state)

    connection_state_callback(ConnectionState.DISCONNECTED)
    w.main_connection_widget.ros_client_connection_widget.connection_state.connect(
        connection_state_callback
    )

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
            Toast.get().show_message('Rosbridge', 'Connected successfully', InfoBarIcon.SUCCESS, 2)
            Thread(target=alert_buzz, daemon=True).start()
        elif connection_state == ConnectionState.FAILURE:
            Toast.get().show_message('Rosbridge', 'Failed to connect to rosbridge', InfoBarIcon.ERROR, 4)

    w.main_connection_widget.ros_client_connection_widget.connection_state.connect(connection_callback)

    def reconnect_controller() -> None:
        while True:
            set_controller_outputs()
            if w.main_connection_widget.controller_connect_button is not None:
                w.main_connection_widget.controller_connect_button.setEnabled(not controller.is_open)
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

    w.main_connection_widget.ros_client_connection_widget.ros_client.connection_state.emit(ConnectionState.CONNECTED)

    w.show()
    splash_screen.show()
    app.processEvents()

    # run
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
