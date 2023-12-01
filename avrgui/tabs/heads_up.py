import datetime
import json
import math
import os.path
import time
from threading import Thread
from typing import Any, TextIO, List

import colour
import numpy as np
import roslibpy
import roslibpy.actionlib
import scipy
from PySide6 import QtCore, QtGui, QtWidgets
from loguru import logger
from qmaterialwidgets import (OutlinedCardWidget, ElevatedCardWidget, InfoBarIcon, FilledPushButton,
                              RadioButton, TonalToolButton, FluentIcon, InputChip, MaterialStyleSheet, SwitchButton)

from .vmc_telemetry import ZEDPositionStatus
from ..lib.action import Action
from ..lib.controller.pythondualsense import Dualsense, BrightnessLevel
from ..lib.graphics_label import GraphicsLabel
from .base import BaseTabWidget
from .connection.rosbridge import RosBridgeClient
from ..lib.toast import Toast
from ..lib.utils import constrain, map_value

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
        super().__init__(parent, client, 'heads_up_display')
        self.controller = controller

        self.setWindowTitle("HUD")

        self.camera_groupbox = None

        self.zed_pane: ZEDCameraPane | None = None
        self.thermal_pane: ThermalCameraPane | None = None
        self.water_pane: WaterDropPane | None = None
        self.gimbal_pane: GimbalPane | None = None
        self.telemetry_pane: TelemetryPane | None = None

    def build(self) -> None:
        layout = QtWidgets.QGridLayout()
        self.setLayout(layout)

        self.camera_groupbox = ElevatedCardWidget()
        self.camera_groupbox.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding, QtWidgets.QSizePolicy.Expanding)
        camera_layout = QtWidgets.QGridLayout()
        self.camera_groupbox.setLayout(camera_layout)
        self.camera_groupbox.setFixedWidth(self.width() // 3)

        # self.zed_pane = ZEDCameraPane(self)
        # camera_layout.addWidget(self.zed_pane)
        self.thermal_pane = ThermalCameraPane(self)
        camera_layout.addWidget(self.thermal_pane, 0, 0, QtCore.Qt.AlignmentFlag.AlignHCenter)

        # camera_layout.addWidget(QtWidgets.QWidget(), 1, 0, QtCore.Qt.AlignmentFlag.AlignHCenter)

        layout.addWidget(self.camera_groupbox, 0, 0)

        control_groupbox = ElevatedCardWidget()
        control_groupbox.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        control_layout = QtWidgets.QVBoxLayout()
        control_groupbox.setLayout(control_layout)

        control_layout.setSpacing(100)

        self.water_pane = WaterDropPane(self, self.controller)
        control_layout.addWidget(self.water_pane)

        self.laser_pane = LaserPane(self)
        control_layout.addWidget(self.laser_pane)

        # self.gimbal_pane = GimbalPane(self)
        # control_layout.addWidget(self.gimbal_pane)

        self.telemetry_pane = TelemetryPane(self)
        control_layout.addWidget(self.telemetry_pane)

        layout.addWidget(control_groupbox, 0, 1)

    def clear(self) -> None:
        pass

    def setup_ros(self, client: roslibpy.Ros) -> None:
        super().setup_ros(client)

        self.thermal_pane.setup_ros(client)
        self.water_pane.setup_ros(client)
        self.laser_pane.setup_ros(client)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.camera_groupbox.setFixedWidth((self.width() // 5) * 2)


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


class ThermalCameraPane(OutlinedCardWidget):
    update_frame = QtCore.Signal(np.ndarray)

    def __init__(self, parent: QtWidgets.QWidget) -> None:
        super().__init__(parent)

        self.thermal_raw: roslibpy.Topic | None = None

        # canvas size
        self.width_ = 300
        self.height_ = self.width_

        # pixels within canvas
        self.pixels_x = 32
        self.pixels_y = self.pixels_x

        self.pixel_width = self.width_ / self.pixels_x
        self.pixel_height = self.height_ / self.pixels_y

        # low range of the sensor (this will be blue on the screen)
        self.MIN_TEMP = 20.0

        # high range of the sensor (this will be red on the screen)
        self.MAX_TEMP = 32.0

        # last lowest temp from camera
        self.last_lowest_temp = 999.0

        # how many color values we can have
        self.COLOR_DEPTH = 1024

        # how many pixels the camera is
        self.camera_x = 8
        self.camera_y = self.camera_x
        self.camera_total = self.camera_x * self.camera_y

        # create list of x/y points
        self.points = [
            (math.floor(ix / self.camera_x), (ix % self.camera_y))
            for ix in range(self.camera_total)
        ]
        # I'm not fully sure what this does
        self.grid_x, self.grid_y = np.mgrid[
                                   0: self.camera_x - 1: self.camera_total / 2j,
                                   0: self.camera_y - 1: self.camera_total / 2j,
                                   ]

        # create available colors
        self.colors = [
            (int(c.red * 255), int(c.green * 255), int(c.blue * 255))
            for c in list(
                colour.Color("indigo").range_to(colour.Color("red"), self.COLOR_DEPTH)
            )
        ]

        # create canvas
        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)

        self.canvas = QtWidgets.QGraphicsScene()
        self.view = QtWidgets.QGraphicsView(self.canvas)
        self.view.setGeometry(0, 0, self.width_, self.height_)
        # self.view = GraphicsLabel((1, 1))
        # self.view.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.MinimumExpanding)
        # self.view.sizePolicy().setHeightForWidth(True)
        # self.view.setPixmap(QtGui.QPixmap("assets/blank_square.png"))

        layout.addWidget(self.view)

        # need a bit of padding for the edges of the canvas
        self.setFixedSize(self.width_ + 50, self.height_ + 50)

        self.update_frame.connect(self.update_canvas_2)

    def set_temp_range(self, min_temp: float, max_temp: float) -> None:
        self.MIN_TEMP = min_temp
        self.MAX_TEMP = max_temp

    def set_calibrated_temp_range(self) -> None:
        self.MIN_TEMP = self.last_lowest_temp + 0.0
        self.MAX_TEMP = self.last_lowest_temp + 15.0

    def check_size(self, height, width) -> None:
        if not height == self.pixels_y or not width == self.pixels_x:
            self.pixels_y = height
            self.pixels_x = width

            self.pixel_width = self.width_ / self.pixels_x
            self.pixel_height = self.height_ / self.pixels_y

    def update_canvas(self, pixels: List[float]) -> None:
        float_pixels = [
            map_value(p, self.MIN_TEMP, self.MAX_TEMP, 0, self.COLOR_DEPTH - 1)
            for p in pixels
        ]

        float_pixels_matrix = np.reshape(float_pixels, (self.camera_x, self.camera_y))
        rotated_float_pixels = np.rot90(np.rot90(float_pixels_matrix))
        rotated_float_pixels = rotated_float_pixels.flatten()

        bicubic = scipy.interpolate.griddata(
            self.points,
            rotated_float_pixels,
            (self.grid_x, self.grid_y),
            method="cubic",
        )

        self.update_frame.emit(bicubic)

    def update_canvas_2(self, frame: np.ndarray):
        pen = QtGui.QPen(QtCore.Qt.PenStyle.NoPen)
        self.canvas.clear()

        for ix, row in enumerate(frame):
            for jx, pixel in enumerate(row):
                brush = QtGui.QBrush(
                    QtGui.QColor(
                        *self.colors[int(constrain(pixel, 0, self.COLOR_DEPTH - 1))]
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

    def setup_ros(self, client: roslibpy.Ros) -> None:
        self.thermal_raw = roslibpy.Topic(
            client,
            '/thermal/raw',
            'avr_pcc_2023_interfaces/msg/ThermalFrame'
        )

        self.thermal_raw.subscribe(lambda msg: self.update_canvas(msg['data']))


class WaterDropPane(OutlinedCardWidget):
    move_dropper = QtCore.Signal(int)
    auto_done = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QWidget, controller: Dualsense) -> None:
        super().__init__(parent)
        self.controller = controller
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)

        self.enabled_atag = False
        self.enabled_atag_drop = False

        self.atag_goal: roslibpy.actionlib.Goal | None = None
        self.atag_drop_goal: roslibpy.actionlib.Goal | None = None

        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)
        layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignVCenter)

        self.title = QtWidgets.QLabel('Water Drop')
        font = self.font()
        font.setPixelSize(15)
        self.title.setFont(font)
        self.title.setAlignment(QtCore.Qt.AlignmentFlag.AlignHCenter | QtCore.Qt.AlignmentFlag.AlignTop)
        self.title.setFixedHeight(25)
        layout.addWidget(self.title, QtCore.Qt.AlignmentFlag.AlignHCenter)

        water_drop_groupbox = QtWidgets.QWidget()
        water_drop_groupbox.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.MinimumExpanding)
        water_drop_layout = QtWidgets.QGridLayout()
        water_drop_layout.setVerticalSpacing(20)
        water_drop_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        y = 0
        water_drop_groupbox.setLayout(water_drop_layout)
        water_drop_groupbox.setMinimumWidth(100)

        self.trigger_button = FilledPushButton("Trigger", self)
        self.trigger_button.clicked.connect(self.trigger_bdu)
        self.trigger_button.setMinimumWidth(350)
        water_drop_layout.addWidget(self.trigger_button, y, 0, 1, 2, QtCore.Qt.AlignmentFlag.AlignHCenter)
        y += 1

        self.full_trigger_button = FilledPushButton("Full Trigger", self)
        self.full_trigger_button.clicked.connect(self.trigger_bdu_full)
        self.full_trigger_button.setMinimumWidth(350)
        water_drop_layout.addWidget(self.full_trigger_button, y, 0, 1, 2, QtCore.Qt.AlignmentFlag.AlignHCenter)
        y += 1

        self.auton_radio_group = QtWidgets.QButtonGroup(self)

        self.atag_radio_button = RadioButton(self)
        self.auton_radio_group.addButton(self.atag_radio_button, 1)
        self.atag_radio_button.setText('Blink')
        self.atag_radio_button.pressed.connect(
            lambda: self.set_auton_drop_mode(1)
        )

        self.atag_drop_radio_button = RadioButton(self)
        self.auton_radio_group.addButton(self.atag_drop_radio_button, 2)
        self.atag_drop_radio_button.setText('Drop')
        self.atag_drop_radio_button.pressed.connect(
            lambda: self.set_auton_drop_mode(2)
        )

        self.atag_cancel_button = TonalToolButton(FluentIcon.CLOSE, self)
        self.atag_cancel_button.setEnabled(False)
        self.atag_cancel_button.clicked.connect(self.stop_auton_drop)

        radio_button_widget = QtWidgets.QWidget()
        radio_button_layout = QtWidgets.QGridLayout()
        radio_button_widget.setLayout(radio_button_layout)

        radio_button_layout.addWidget(QtWidgets.QLabel('Autonomy: '), 0, 0)
        radio_button_layout.addWidget(self.atag_radio_button, 0, 1)
        radio_button_layout.addWidget(self.atag_drop_radio_button, 0, 2)
        radio_button_layout.addWidget(self.atag_cancel_button, 0, 3)

        water_drop_layout.addWidget(radio_button_widget, y, 0, 1, 2, QtCore.Qt.AlignmentFlag.AlignHCenter)
        y += 1

        self.tags_label = QtWidgets.QLabel(
            f"{COLORED_NONE_TEXT}"
        )
        water_drop_layout.addWidget(QtWidgets.QLabel("Visible Tags:"), y, 0, QtCore.Qt.AlignmentFlag.AlignRight)
        water_drop_layout.addWidget(self.tags_label, y, 1, QtCore.Qt.AlignmentFlag.AlignLeft)
        y += 1

        self.full_drops_label = QtWidgets.QLabel(
            f"{self.format_use_full_drops(False)}",
            self
        )
        water_drop_layout.addWidget(QtWidgets.QLabel("Using full drops:"), y, 0, QtCore.Qt.AlignmentFlag.AlignRight)
        water_drop_layout.addWidget(self.full_drops_label, y, 1, QtCore.Qt.AlignmentFlag.AlignLeft)
        y += 1

        logging_layout = QtWidgets.QGridLayout()
        self.logging_switch = SwitchButton(self)
        self.logging_switch.checkedChanged.connect(
            lambda state: self.start_log_file() if state else self.close_log_file()
        )
        logging_layout.addWidget(QtWidgets.QLabel("Enable Logging:"), 0, 0, QtCore.Qt.AlignmentFlag.AlignRight)
        logging_layout.addWidget(self.logging_switch, 0, 1, QtCore.Qt.AlignmentFlag.AlignLeft)
        water_drop_layout.addLayout(logging_layout, y, 0, 1, 2, QtCore.Qt.AlignmentFlag.AlignHCenter)

        layout.addWidget(water_drop_groupbox)

        self.auto_done.connect(self.stop_auton_drop)

        self.detections_subscriber: roslibpy.Topic | None = None
        self.bdu_full_trigger: roslibpy.Service | None = None
        self.bdu_trigger: roslibpy.Service | None = None
        self.bdu_reset: roslibpy.Service | None = None
        self.auton_use_full_drop_client: roslibpy.Service | None = None
        self.auton_drop_client: Action | None = None

        self.current_mode = 0

        self.use_full_drops = False

        if not os.path.isdir('log'):
            os.mkdir('log')

        self.log_file: TextIO | None = None
        self.log_start_time: float = 0

        self.controller.touchpad.led_color = (255, 0, 0)
        self.controller.mic_button.led_state = False
        self.controller.mic_button.led_pulsating = True
        self.controller.mic_button.led_brightness = BrightnessLevel.HIGH

    def toggle_use_full_drops(self) -> None:
        self.use_full_drops = not self.use_full_drops
        self.full_drops_label.setText(self.format_use_full_drops(self.use_full_drops))
        if self.auton_use_full_drop_client is not None:
            self.auton_use_full_drop_client.call(
                roslibpy.ServiceRequest({'data': self.use_full_drops}),
                callback=lambda msg: print(f'Use full drops response: {msg}')
            )

    def start_log_file(self) -> None:
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
        if self.log_file is not None:
            self.log_to_file(
                f'Closed file at {round(time.time())} (Ran for {round(time.time() - self.log_start_time)}s)'
            )
            self.log_file.close()
            Toast.get().show_message('Log', f'Saved log to: {self.log_file.name}', InfoBarIcon.SUCCESS, 4)
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
                    self.auton_drop_client.send_goal({'should_drop': mode == 2})
                else:
                    self.auton_drop_client.cancel()

            self.current_mode = mode
        else:
            self.uncheck_radio_buttons()

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

    def uncheck_radio_buttons(self) -> None:
        self.auton_radio_group.setExclusive(False)
        self.atag_radio_button.setChecked(False)
        self.atag_drop_radio_button.setChecked(False)
        self.auton_radio_group.setExclusive(True)

    def stop_auton_drop(self) -> None:
        self.set_auton_drop_mode(0)
        self.uncheck_radio_buttons()
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
        self.auton_use_full_drop_client = roslibpy.Service(
            client,
            '/auton_drop/use_full_drop',
            'std_srvs/srv/SetBool'
        )

        self.auton_drop_client = Action(
            client,
            0,
            self.auton_feedback_callback,
            self.auton_drop_finished
        )

        self.auton_use_full_drop_client.call(
            roslibpy.ServiceRequest({'data': self.use_full_drops}),
            callback=lambda msg: print(f'Use full drops response: {msg}')
        )

    def show_log_countdown(self) -> None:
        for countdown in range(5, 0, -1):
            Toast.get().send_message.emit(
                'Log', f'Log timer starting in {countdown} seconds...', InfoBarIcon.INFORMATION, 0.9
            )
            time.sleep(1)
            if self.log_file is None:
                return
        Toast.get().send_message.emit('Log', f'Log timer started', InfoBarIcon.INFORMATION, 2)

    @staticmethod
    def format_use_full_drops(use_full_drops: bool) -> str:
        if use_full_drops:
            return f"<a style='color:{GREEN_COLOR};'>True</a>"
        else:
            return f"<a style='color:{YELLOW_COLOR};'>False</a>"

    @staticmethod
    def format_visible_tags(tags: list[int]) -> str:
        if len(tags) < 1:
            return COLORED_NONE_TEXT
        text = ''
        for tag_id in tags:
            text += f"{tag_id},"
        text = text[:-1]
        return f"<a style='color:{GREEN_COLOR};'>{text}</a>"


class LaserPane(OutlinedCardWidget):
    def __init__(self, parent: QtWidgets.QWidget) -> None:
        super().__init__(parent)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)

        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)
        layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignVCenter)

        self.title = QtWidgets.QLabel('Laser')
        font = self.font()
        font.setPixelSize(15)
        self.title.setFont(font)
        self.title.setAlignment(QtCore.Qt.AlignmentFlag.AlignHCenter | QtCore.Qt.AlignmentFlag.AlignTop)
        self.title.setFixedHeight(25)
        layout.addWidget(self.title, QtCore.Qt.AlignmentFlag.AlignHCenter)

        laser_groupbox = QtWidgets.QWidget()
        laser_groupbox.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.MinimumExpanding)
        laser_layout = QtWidgets.QGridLayout()
        laser_layout.setVerticalSpacing(20)
        laser_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        y = 0
        laser_groupbox.setLayout(laser_layout)
        laser_groupbox.setMinimumWidth(100)

        self.fire_button = FilledPushButton("Fire", self)
        self.fire_button.clicked.connect(self.fire)
        self.fire_button.setMinimumWidth(350)
        laser_layout.addWidget(self.fire_button, y, 0, 1, 2, QtCore.Qt.AlignmentFlag.AlignHCenter)
        y += 1

        loop_layout = QtWidgets.QGridLayout()
        self.loop_switch = SwitchButton(self)
        self.loop_switch.checkedChanged.connect(self.set_loop)
        loop_layout.addWidget(QtWidgets.QLabel("Enable Loop:"), 0, 0, QtCore.Qt.AlignmentFlag.AlignRight)
        loop_layout.addWidget(self.loop_switch, 0, 1, QtCore.Qt.AlignmentFlag.AlignLeft)
        laser_layout.addLayout(loop_layout, y, 0, 1, 2, QtCore.Qt.AlignmentFlag.AlignHCenter)

        layout.addWidget(laser_groupbox, QtCore.Qt.AlignmentFlag.AlignVCenter)

        self.laser_fire_client: roslibpy.Service | None = None
        self.laser_set_loop_client: roslibpy.Service | None = None

    def setup_ros(self, client: roslibpy.Ros) -> None:
        self.laser_fire_client = roslibpy.Service(
            client,
            '/laser/fire',
            'std_srvs/srv/Trigger'
        )
        self.laser_set_loop_client = roslibpy.Service(
            client,
            '/laser/set_loop',
            'std_srvs/srv/SetBool'
        )

    def fire(self) -> None:
        if self.laser_fire_client is not None:
            self.laser_fire_client.call(
                roslibpy.ServiceRequest(),
                lambda msg: logger.debug(f'Got response from laser fire: {msg}')
            )

    def set_loop(self, state: bool) -> None:
        if self.laser_set_loop_client is not None:
            self.laser_set_loop_client.call(
                roslibpy.ServiceRequest({'data': state}),
                lambda msg: logger.debug(f'Got response from laser set_loop: {msg}')
            )

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


class TelemetryPane(OutlinedCardWidget):
    formatted_battery_signal = QtCore.Signal(str, str)
    formatted_armed_signal = QtCore.Signal(str)
    formatted_mode_signal = QtCore.Signal(str)
    pose_state_signal = QtCore.Signal(object)

    def __init__(self, parent: QtWidgets.QWidget) -> None:
        super(TelemetryPane, self).__init__(parent)

        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)

        telemetry_groupbox = QtWidgets.QWidget()
        telemetry_groupbox.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Policy.Minimum)
        telemetry_layout = QtWidgets.QGridLayout()
        telemetry_groupbox.setLayout(telemetry_layout)

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
