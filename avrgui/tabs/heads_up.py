import datetime
import json
import os.path
import time
from threading import Thread
from typing import Any, TextIO

import colour
import numpy as np
import roslibpy
import roslibpy.actionlib
from PySide6 import QtCore, QtGui, QtWidgets
from loguru import logger

from .vmc_telemetry import ZEDPositionStatus
from ..lib import utils
from ..lib.action import Action
from ..lib.controller.pythondualsense import Dualsense, BrightnessLevel
from ..lib.graphics_label import GraphicsLabel
from .base import BaseTabWidget
from .connection.rosbridge import RosBridgeClient
from ..lib.toast import Toast
from ..lib.utils import constrain

RED_COLOR = "red"
LIGHT_BLUE_COLOR = "#0091ff"
YELLOW_COLOR = "#ffb800"
GREEN_COLOR = "#1bc700"
TIME_COLOR = "#3f8c96"
COLORED_UNKNOWN_TEXT = "<span style='color:orange;'>Unknown</span>"
COLORED_NONE_TEXT = "<span style='color:orange;'>None</span>"
STATE_LOOKUP = {
    "inactive": 0,
    "searching": 1,
    "locked": 2
}


class HeadsUpDisplayWidget(BaseTabWidget):
    def __init__(self, parent: QtWidgets.QWidget, client: RosBridgeClient, controller) -> None:
        super().__init__(parent, client)
        self.controller = controller

        self.setWindowTitle("HUD")

        self.zed_pane: ZEDCameraPane | None = None
        self.thermal_pane: ThermalCameraPane | None = None
        self.water_pane: WaterDropPane | None = None
        self.gimbal_pane: GimbalPane | None = None
        self.telemetry_pane: TelemetryPane | None = None

    def build(self) -> None:
        layout = QtWidgets.QGridLayout()
        self.setLayout(layout)

        camera_groupbox = QtWidgets.QGroupBox("Camera")
        camera_groupbox.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding, QtWidgets.QSizePolicy.Expanding)
        camera_layout = QtWidgets.QVBoxLayout()
        camera_groupbox.setLayout(camera_layout)
        camera_groupbox.setFixedWidth(500)

        # self.zed_pane = ZEDCameraPane(self)
        # camera_layout.addWidget(self.zed_pane)
        self.thermal_pane = ThermalCameraPane(self)
        camera_layout.addWidget(self.thermal_pane)

        layout.addWidget(camera_groupbox, 0, 0)

        control_groupbox = QtWidgets.QGroupBox("Control")
        control_groupbox.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        control_layout = QtWidgets.QVBoxLayout()
        control_groupbox.setLayout(control_layout)

        self.water_pane = WaterDropPane(self, self.controller)
        control_layout.addWidget(self.water_pane)

        # self.gimbal_pane = GimbalPane(self)
        # control_layout.addWidget(self.gimbal_pane)

        self.telemetry_pane = TelemetryPane(self)
        control_layout.addWidget(self.telemetry_pane)

        layout.addWidget(control_groupbox, 0, 1)

    def process_message(self, topic: str, payload: str) -> None:
        self.water_pane.process_message(topic, payload)
        self.gimbal_pane.process_message(topic, payload)

    def clear(self) -> None:
        pass

    def setup_ros(self, client: roslibpy.Ros) -> None:
        super().setup_ros(client)

        self.water_pane.setup_ros(client)


class ZEDCameraPane(QtWidgets.QWidget):
    toggle_connection = QtCore.Signal()
    update_frame = QtCore.Signal(QtGui.QPixmap)

    def __init__(self, parent: QtWidgets.QWidget) -> None:
        super().__init__(parent)
        self.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding, QtWidgets.QSizePolicy.MinimumExpanding)

        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)

        zed_groupbox = QtWidgets.QGroupBox("ZED")
        zed_groupbox.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding, QtWidgets.QSizePolicy.MinimumExpanding)
        # zed_groupbox.setMaximumWidth()
        zed_layout = QtWidgets.QVBoxLayout()
        zed_groupbox.setLayout(zed_layout)

        self.view = GraphicsLabel((16, 9))
        self.view.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.MinimumExpanding)
        self.view.sizePolicy().setHeightForWidth(True)
        self.view.setPixmap(QtGui.QPixmap("assets/blank720.png"))
        self.view.setFixedWidth(200)
        zed_layout.addWidget(self.view)

        connection_button = QtWidgets.QPushButton("Toggle Connection")
        connection_button.clicked.connect(self.toggle_connection)
        zed_layout.addWidget(connection_button)

        # layout.addWidget(zed_groupbox)

        self.update_frame.connect(self.view.setPixmap)


class ThermalCameraPane(QtWidgets.QWidget):
    update_frame = QtCore.Signal(np.ndarray)

    def __init__(self, parent: QtWidgets.QWidget) -> None:
        super().__init__(parent)

        # canvas size
        self.width_ = 300
        self.height_ = self.width_

        # pixels within canvas
        self.pixels_x = 32
        self.pixels_y = self.pixels_x

        self.pixel_width = self.width_ / self.pixels_x
        self.pixel_height = self.height_ / self.pixels_y

        # low range of the sensor (this will be blue on the screen)
        self.MINTEMP = 20.0

        # high range of the sensor (this will be red on the screen)
        self.MAXTEMP = 32.0

        # last lowest temp from camera
        self.last_lowest_temp = 999.0

        # how many color values we can have
        self.COLORDEPTH = 1024

        # how many pixels the camera is
        self.camera_x = 8
        self.camera_y = self.camera_x
        self.camera_total = self.camera_x * self.camera_y

        self.colors = [
            (int(c.red * 255), int(c.green * 255), int(c.blue * 255))
            for c in list(
                colour.Color("indigo").range_to(colour.Color("red"), self.COLORDEPTH)
            )
        ]

        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)

        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)

        thermal_groupbox = QtWidgets.QGroupBox("Thermal")
        thermal_groupbox.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        # zed_groupbox.setMaximumWidth()
        thermal_layout = QtWidgets.QVBoxLayout()
        thermal_groupbox.setLayout(thermal_layout)

        # self.view = GraphicsLabel((1, 1))
        # self.view.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        # self.view.sizePolicy().setHeightForWidth(True)
        # self.view.setPixmap(QtGui.QPixmap("assets/blank_square.png"))
        # self.view.setMinimumSize(200, 200)
        self.canvas = QtWidgets.QGraphicsScene()
        self.view = QtWidgets.QGraphicsView(self.canvas)
        self.view.setGeometry(0, 0, 400, 400)
        thermal_layout.addWidget(self.view)

        layout.addWidget(thermal_groupbox)

        self.update_frame.connect(self.update_frame_callback)

    def update_frame_callback(self, frame: np.ndarray) -> None:
        pen = QtGui.QPen(QtCore.Qt.PenStyle.NoPen)
        self.canvas.clear()

        for ix, row in enumerate(frame):
            for jx, pixel in enumerate(row):
                brush = QtGui.QBrush(
                    QtGui.QColor(
                        *self.colors[int(constrain(pixel, 0, self.COLORDEPTH - 1))]
                    )
                )
                self.canvas.addRect(
                    self.pixel_width * jx,
                    self.pixel_height * ix,
                    self.pixel_width,
                    self.pixel_height,
                    pen,
                    brush,
                )


class WaterDropPane(QtWidgets.QWidget):
    move_dropper = QtCore.Signal(int)
    auto_done = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QWidget, controller: Dualsense) -> None:
        super().__init__(parent)
        self.controller = controller
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.MinimumExpanding)

        self.enabled_atag = False
        self.enabled_atag_drop = False

        self.atag_goal: roslibpy.actionlib.Goal | None = None
        self.atag_drop_goal: roslibpy.actionlib.Goal | None = None

        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)
        layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)

        water_drop_groupbox = QtWidgets.QGroupBox("Water Drop")
        water_drop_groupbox.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.MinimumExpanding)
        water_drop_layout = QtWidgets.QFormLayout()
        water_drop_groupbox.setLayout(water_drop_layout)
        water_drop_groupbox.setMinimumWidth(100)

        self.trigger_button = QtWidgets.QPushButton("Trigger")
        self.trigger_button.clicked.connect(self.trigger_bdu)
        water_drop_layout.addWidget(self.trigger_button)

        self.full_trigger_button = QtWidgets.QPushButton("Full Trigger")
        self.full_trigger_button.clicked.connect(self.trigger_bdu_full)
        water_drop_layout.addWidget(self.full_trigger_button)

        self.auton_radio_group = QtWidgets.QButtonGroup()

        self.atag_radio_button = QtWidgets.QRadioButton()
        self.auton_radio_group.addButton(self.atag_radio_button, 1)
        self.atag_radio_button.setText('Blink')
        self.atag_radio_button.pressed.connect(
            lambda: self.set_auton_drop_mode(1)
        )

        self.atag_drop_radio_button = QtWidgets.QRadioButton()
        self.auton_radio_group.addButton(self.atag_drop_radio_button, 2)
        self.atag_drop_radio_button.setText('Drop')
        self.atag_drop_radio_button.pressed.connect(
            lambda: self.set_auton_drop_mode(2)
        )

        self.atag_cancel_button = QtWidgets.QPushButton('X')
        self.atag_cancel_button.setEnabled(False)
        self.atag_cancel_button.clicked.connect(self.stop_auton_drop)

        radio_button_widget = QtWidgets.QWidget()
        radio_button_layout = QtWidgets.QGridLayout()
        radio_button_widget.setLayout(radio_button_layout)

        radio_button_layout.addWidget(self.atag_radio_button, 0, 0)
        radio_button_layout.addWidget(self.atag_drop_radio_button, 0, 1)
        radio_button_layout.addWidget(self.atag_cancel_button, 0, 2)

        water_drop_layout.addRow('Autonomy: ', radio_button_widget)

        self.tags_label = QtWidgets.QLabel(
            f"{COLORED_NONE_TEXT}"
        )
        water_drop_layout.addRow("Visible Tags:", self.tags_label)

        self.open_log_button = QtWidgets.QPushButton("Open log")
        self.open_log_button.clicked.connect(self.start_log_file)
        water_drop_layout.addWidget(self.open_log_button)

        self.close_log_button = QtWidgets.QPushButton("Close log")
        self.close_log_button.clicked.connect(self.close_log_file)
        self.close_log_button.setEnabled(False)
        water_drop_layout.addWidget(self.close_log_button)

        layout.addWidget(water_drop_groupbox)

        self.auto_done.connect(self.stop_auton_drop)

        self.detections_subscriber: roslibpy.Topic | None = None
        self.bdu_full_trigger: roslibpy.Service | None = None
        self.bdu_trigger: roslibpy.Service | None = None
        self.bdu_reset: roslibpy.Service | None = None
        self.auton_drop_client: Action | None = None

        self.current_mode = 0

        if not os.path.isdir('log'):
            os.mkdir('log')

        self.log_file: TextIO | None = None
        self.log_start_time: float = 0

        self.controller.touchpad.led_color = (255, 0, 0)
        self.controller.mic_button.led_state = False
        self.controller.mic_button.led_pulsating = True
        self.controller.mic_button.led_brightness = BrightnessLevel.HIGH

    def start_log_file(self) -> None:
        self.open_log_button.setEnabled(False)
        self.close_log_button.setEnabled(True)
        if self.log_file is None:
            self.log_file = open(f'log/{datetime.datetime.utcnow().isoformat()}.log', 'w')
            self.log_start_time = time.time() + 5
            self.log_to_file(f'Started log at {round(self.log_start_time)}')
            self.controller.mic_button.led_state = True
            Thread(target=self.show_log_countdown, daemon=True).start()

    def log_to_file(self, text: str) -> None:
        if self.log_file is not None:
            self.log_file.write(f'{round(time.time() - self.log_start_time)}: {text}\n')
            self.log_file.flush()

    def close_log_file(self) -> None:
        self.open_log_button.setEnabled(True)
        self.close_log_button.setEnabled(False)
        if self.log_file is not None:
            self.log_to_file(f'Closed file at {round(time.time())} (Ran for {round(time.time() - self.log_start_time)}s)')
            self.log_file.close()
            Toast.get().show_message(f'Saved log to: {self.log_file.name}', 4)
            self.log_file = None
            self.controller.mic_button.led_state = False

    def detections_callback(self, msg: dict[str, Any]) -> None:
        detections = msg.get('detections', [])
        tags = [detection.get('id', '?') for detection in detections]
        self.tags_label.setText(self.format_visible_tags(tags))

    def enable_drop(self) -> None:
        self.atag_drop_radio_button.setChecked(True)
        self.set_auton_drop_mode(2)

    def enable_blink(self) -> None:
        self.atag_radio_button.setChecked(True)
        self.set_auton_drop_mode(1)

    def set_auton_drop_mode(self, mode: int) -> None:
        if self.auton_drop_client is not None:
            if self.atag_cancel_button is not None:
                self.atag_cancel_button.setEnabled(mode != 0)

            if mode != self.current_mode:
                if mode != 0:
                    if self.current_mode != 0:
                        self.auton_drop_client.cancel()
                    self.controller.touchpad.led_color = (255, 150, 0) if mode == 2 else (0, 255, 0)
                    print(self.controller.touchpad.led_color)
                    self.auton_drop_client.send_goal({'should_drop': mode == 2})
                else:
                    self.auton_drop_client.cancel()

            self.current_mode = mode

    def auton_feedback_callback(self, msg: dict[str, Any]) -> None:
        apriltag_id = msg.get('_apriltag_id', None)

        if self.current_mode == 1:
            msg = f'Blinking for tag: {apriltag_id}'
        else:
            msg = f'Dropping for tag: {apriltag_id}'

        logger.info(msg)
        self.log_to_file(msg)

    def auton_drop_finished(self, _: dict[str, Any]) -> None:
        self.log_to_file(f'Finished auton drop')
        self.stop_auton_drop()

    def stop_auton_drop(self) -> None:
        self.set_auton_drop_mode(0)
        self.auton_radio_group.setExclusive(False)
        self.atag_radio_button.setChecked(False)
        self.atag_drop_radio_button.setChecked(False)
        self.auton_radio_group.setExclusive(True)
        self.controller.touchpad.led_color = (255, 0, 0)

    def trigger_bdu_full(self) -> None:
        if self.bdu_full_trigger is not None:
            self.stop_auton_drop()
            self.bdu_full_trigger.call(
                roslibpy.ServiceRequest(),
                callback=lambda msg: logger.debug(
                    'Bdu trigger result: ' + msg.get('message', '')
                )
            )
            self.log_to_file(f'Full manual drop triggered')

    def trigger_bdu(self) -> None:
        if self.bdu_trigger is not None:
            self.stop_auton_drop()
            self.bdu_trigger.call(
                roslibpy.ServiceRequest(),
                callback=lambda msg: logger.debug(
                    'Bdu trigger m result: ' + msg.get('message', '')
                )
            )
            self.log_to_file(f'Stage manual drop triggered')

    def reset_bdu(self) -> None:
        if self.bdu_reset is not None:
            self.stop_auton_drop()
            self.bdu_reset.call(
                roslibpy.ServiceRequest(),
                callback=lambda msg: logger.debug(
                    'Bdu reset m result: ' + msg.get('message', '')
                )
            )
            self.log_to_file(f'Reset BDU')

    def setup_ros(self, client: roslibpy.Ros) -> None:
        self.detections_subscriber = roslibpy.Topic(
            client,
            '/detections',
            'apriltag_msgs/msg/AprilTagDetectionArray'
        )
        self.detections_subscriber.subscribe(self.detections_callback)

        self.bdu_full_trigger = roslibpy.Service(
            client,
            '/bdu/full_trigger',
            'std_srvs/srv/Trigger'
        )
        self.bdu_trigger = roslibpy.Service(
            client,
            '/bdu/trigger',
            'std_srvs/srv/Trigger'
        )
        self.bdu_reset = roslibpy.Service(
            client,
            '/bdu/reset',
            'std_srvs/srv/Trigger'
        )

        self.auton_drop_client = Action(
            client,
            0,
            self.auton_feedback_callback,
            self.auton_drop_finished
        )

    @staticmethod
    def show_log_countdown() -> None:
        for countdown in range(5, 0, -1):
            Toast.get().send_message.emit(f'Log timer starting in {countdown} seconds...', 1.5)
            time.sleep(1)
        Toast.get().send_message.emit(f'Log timer started', 2)

    @staticmethod
    def format_visible_tags(tags: list[int]) -> str:
        if len(tags) < 1:
            return COLORED_NONE_TEXT
        text = ''
        for tag_id in tags:
            text += f"{tag_id},"
        text = text[:-1]
        return f"<a style='color:{GREEN_COLOR};'>{text}</a>"


class GimbalPane(QtWidgets.QWidget):
    def __init__(self, parent: QtWidgets.QWidget) -> None:
        super().__init__(parent)
        self.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding, QtWidgets.QSizePolicy.MinimumExpanding)

        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)

        gimbal_groupbox = QtWidgets.QGroupBox("Gimbal")
        gimbal_groupbox.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding, QtWidgets.QSizePolicy.MinimumExpanding)
        gimbal_layout = QtWidgets.QGridLayout()
        gimbal_groupbox.setLayout(gimbal_layout)
        gimbal_groupbox.setMinimumWidth(100)

        self.yaw_dial = QtWidgets.QDial()
        self.yaw_dial.setWrapping(True)
        self.yaw_dial.setRange(-100, 100)
        self.yaw_dial.setValue(0)
        self.yaw_dial.setMaximumWidth(200)
        self.yaw_dial.setStyleSheet("border: 4px solid white ; border-radius: 82px;")
        self.yaw_dial.setDisabled(True)
        gimbal_layout.addWidget(self.yaw_dial, 0, 0, 0, 1)

        self.pitch_bar = QtWidgets.QProgressBar()
        self.pitch_bar.setOrientation(QtCore.Qt.Orientation.Vertical)
        self.pitch_bar.setRange(-50, 50)
        self.pitch_bar.setValue(0)
        self.pitch_bar.setMinimumWidth(10)
        self.pitch_bar.setContentsMargins(0, 0, 50, 0)
        gimbal_layout.addWidget(self.pitch_bar, 0, 2, 0, 1)

        layout.addWidget(gimbal_groupbox)


class TelemetryPane(QtWidgets.QWidget):
    formatted_battery_signal = QtCore.Signal(str, str)
    formatted_armed_signal = QtCore.Signal(str)
    formatted_mode_signal = QtCore.Signal(str)
    pose_state_signal = QtCore.Signal(object)

    def __init__(self, parent: QtWidgets.QWidget) -> None:
        super(TelemetryPane, self).__init__(parent)

        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)

        telemetry_groupbox = QtWidgets.QGroupBox("Telemetry")
        telemetry_groupbox.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Policy.Minimum)
        telemetry_layout = QtWidgets.QGridLayout()
        telemetry_groupbox.setLayout(telemetry_layout)
        # telemetry_groupbox.setMinimumWidth(100)

        # battery row
        battery_layout = QtWidgets.QHBoxLayout()

        self.battery_voltage_label = QtWidgets.QLabel(COLORED_UNKNOWN_TEXT)
        self.battery_current_label = QtWidgets.QLabel("")
        battery_layout.addWidget(self.battery_voltage_label)
        battery_layout.addWidget(self.battery_current_label)
        self.formatted_battery_signal.connect(
            lambda voltage, _: self.battery_voltage_label.setText(voltage)
        )
        self.formatted_battery_signal.connect(
            lambda _, current: self.battery_current_label.setText(current)
        )

        telemetry_layout.addWidget(QtWidgets.QLabel("Battery:"), 0, 0)
        telemetry_layout.addLayout(battery_layout, 0, 1)

        # armed row
        self.armed_label = QtWidgets.QLabel(COLORED_UNKNOWN_TEXT)
        telemetry_layout.addWidget(QtWidgets.QLabel("Armed Status:"), 1, 0)
        telemetry_layout.addWidget(self.armed_label, 1, 1)
        self.formatted_armed_signal.connect(self.armed_label.setText)

        # flight mode row
        self.mode_label = QtWidgets.QLabel(COLORED_UNKNOWN_TEXT)
        telemetry_layout.addWidget(QtWidgets.QLabel("Flight Mode:"), 2, 0)
        telemetry_layout.addWidget(self.mode_label, 2, 1)
        self.formatted_mode_signal.connect(self.mode_label.setText)

        # position tracking row
        self.pose_state_label = QtWidgets.QLabel(COLORED_UNKNOWN_TEXT)
        telemetry_layout.addWidget(QtWidgets.QLabel("Position Tracking:"), 3, 0)
        telemetry_layout.addWidget(self.pose_state_label, 3, 1)
        self.pose_state_signal.connect(
            lambda state: self.pose_state_label.setText(self.format_position_tracking(state))
        )

        layout.addWidget(telemetry_groupbox)

    @staticmethod
    def format_position_tracking(status: ZEDPositionStatus | None) -> str:
        match status:
            case ZEDPositionStatus.OK:
                return f"<a style='color:{GREEN_COLOR};'>GOOD</a>"
            case ZEDPositionStatus.SEARCHING:
                return f"<a style='color:{YELLOW_COLOR};'>SEARCHING</a>"
            case ZEDPositionStatus.SEARCHING_FLOOR_PLANE:
                return f"<a style='color:{YELLOW_COLOR};'>SEARCHING</a>"
            case None:
                return COLORED_UNKNOWN_TEXT
            case _:
                return f"<a style='color:{RED_COLOR};'>ERROR</a>"
