import datetime
import json
import time
from threading import Thread
from typing import Any

import colour
import numpy as np
import roslibpy
import roslibpy.actionlib
from PySide6 import QtCore, QtGui, QtWidgets
from loguru import logger

from ..lib import utils
from ..lib.action import Action
from ..lib.graphics_label import GraphicsLabel
from .base import BaseTabWidget
from .connection.rosbridge import RosBridgeClient
from ..lib.utils import constrain

RED_COLOR = "red"
LIGHT_BLUE_COLOR = "#0091ff"
GREEN_COLOR = "#1bc700"
TIME_COLOR = "#3f8c96"
COLORED_NONE_TEXT = "<span style='color:orange;'>None</span>"
STATE_LOOKUP = {
    "inactive": 0,
    "searching": 1,
    "locked": 2
}


class HeadsUpDisplayWidget(BaseTabWidget):
    def __init__(self, parent: QtWidgets.QWidget, client: RosBridgeClient) -> None:
        super().__init__(parent, client)

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

        self.zed_pane = ZEDCameraPane(self)
        # camera_layout.addWidget(self.zed_pane)
        self.thermal_pane = ThermalCameraPane(self)
        camera_layout.addWidget(self.thermal_pane)

        layout.addWidget(camera_groupbox, 0, 0)

        control_groupbox = QtWidgets.QGroupBox("Control")
        control_groupbox.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        control_layout = QtWidgets.QVBoxLayout()
        control_groupbox.setLayout(control_layout)

        self.water_pane = WaterDropPane(self)
        control_layout.addWidget(self.water_pane)

        self.gimbal_pane = GimbalPane(self)
        control_layout.addWidget(self.gimbal_pane)

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

        layout.addWidget(zed_groupbox)

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

    def __init__(self, parent: QtWidgets.QWidget) -> None:
        super().__init__(parent)
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
        self.trigger_button.clicked.connect(self.trigger_bdu_full)
        water_drop_layout.addWidget(self.trigger_button)

        # self.atag_enable_checkbox = QtWidgets.QCheckBox("Enable Apriltags")
        #
        # self.atag_enable_checkbox.stateChanged.connect(
        #     self.auton_blink_trigger
        # )
        # water_drop_layout.addRow("Enable:", self.atag_enable_checkbox)
        #
        # self.atag_enable_drop_checkbox = QtWidgets.QCheckBox("Enable Apriltags For Drop")
        #
        # self.atag_enable_drop_checkbox.stateChanged.connect(
        #     self.auton_drop_trigger
        # )
        # water_drop_layout.addRow("Enable Drop:", self.atag_enable_drop_checkbox)

        self.atag_radio_button = QtWidgets.QRadioButton()
        self.atag_radio_button.setText('Blink')

        self.atag_drop_radio_button = QtWidgets.QRadioButton()
        self.atag_drop_radio_button.setText('Drop')

        self.atag_cancel_button = QtWidgets.QPushButton(QtGui.QIcon.fromTheme('process-stop'))

        radio_button_widget = QtWidgets.QWidget()
        radio_button_layout = QtWidgets.QGridLayout()
        radio_button_widget.setLayout(radio_button_layout)

        radio_button_layout.addWidget(self.atag_radio_button, 0, 0)
        radio_button_layout.addWidget(self.atag_radio_button, 0, 1)
        radio_button_layout.addWidget(self.atag_cancel_button, 0, 2)

        water_drop_layout.addRow('Autonomy: ', radio_button_widget)

        self.tags_label = QtWidgets.QLabel(
            f"{COLORED_NONE_TEXT}"
        )
        water_drop_layout.addRow("Visible Tags:", self.tags_label)

        layout.addWidget(water_drop_groupbox)

        self.auto_done.connect(self.stop_auton_drop)

        self.bdu_full_trigger = None
        self.bdu_trigger = None
        self.bdu_reset = None

        self.current_mode = 0

    def set_auton_drop_mode(self, mode: int) -> None:
        if self.atag_cancel_button is not None:
            self.atag_cancel_button.setEnabled(mode != 0)

        if mode != self.current_mode:
            if mode > 0:
                if self.auton_drop_client.running:
                    self.auton_drop_client.cancel()
                self.auton_drop_client.send_goal({'should_drop': mode == 2})
            else:
                self.auton_drop_client.cancel()

        self.current_mode = mode

    def auton_feedback_callback(self, msg: dict[str, Any]) -> None:
        apriltag_id = msg.get('apriltag_id', None)

        if self.current_mode == 1:
            logger.info(f'Blinking for tag: {apriltag_id}')
        else:
            logger.info(f'Dropping for tag: {apriltag_id}')

    def auton_drop_finished(self, _: dict[str, Any]) -> None:
        self.stop_auton_drop()

    def stop_auton_drop(self) -> None:
        self.set_auton_drop_mode(0)
        self.atag_radio_button.setChecked(False)
        self.atag_cancel_button.setChecked(False)

    def trigger_bdu_full(self) -> None:
        self.stop_auton_drop()
        self.bdu_full_trigger.call(
            roslibpy.ServiceRequest(),
            callback=lambda msg: logger.debug(
                'Bdu trigger result: ' + msg.get('message', '')
            )
        )

    def trigger_bdu(self) -> None:
        self.stop_auton_drop()
        self.bdu_trigger.call(
            roslibpy.ServiceRequest(),
            callback=lambda msg: logger.debug(
                'Bdu trigger m result: ' + msg.get('message', '')
            )
        )

    def reset_bdu(self) -> None:
        self.stop_auton_drop()
        self.bdu_reset.call(
            roslibpy.ServiceRequest(),
            callback=lambda msg: logger.debug(
                'Bdu reset m result: ' + msg.get('message', '')
            )
        )

    def setup_ros(self, client: roslibpy.Ros) -> None:
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

        def dummy(a=None, b=None):
            pass

        def auto_drop(msg):
            self.tags_label.setText(self.format_visible_tags(str([d['id'] for d in msg['detections']])))
            if len(msg['detections']) > 0:
                if self.enabled_atag_drop:
                    print(f"Dropping for tag: {msg['detections'][0]}")
                    self.blink_t.call(
                        roslibpy.ServiceRequest({'mode': 1, 'argument': 3, 'color': {'r': 252, 'g': 190, 'b': 3}}),
                        callback=dummy
                    )

                    def do_drop():
                        time.sleep(1)
                        self.bdu_full_trigger.call(
                            roslibpy.ServiceRequest(),
                            callback=dummy
                        )

                    Thread(
                        target=do_drop,
                        daemon=True
                    ).start()


                elif self.enabled_atag:
                    print(f"Blinking for tag: {msg['detections'][0]}")
                    self.blink_t.call(
                        roslibpy.ServiceRequest({'mode': 1, 'argument': 3, 'color': {'r': 252, 'g': 190, 'b': 3}}),
                        callback=dummy
                    )

                self.enabled_atag_drop = False
                self.enabled_atag = False

                self.auto_done.emit()

    def process_message(self, topic: str, payload: str) -> None:
        if topic == "avr/autonomy/water_drop_state":
            state_str = "inactive"
            try:
                payload = json.loads(payload)
                state_str = payload.get("state", state_str)
            except json.JSONDecodeError:
                pass
            state_str = state_str.strip().lower()
            state = STATE_LOOKUP.get(state_str, 0)
            self.auto_state_label.setText(
                    self.format_auto_state(state)
            )

        elif topic == "avr/autonomy/water_drop_locked":
            locked_tag = None
            try:
                payload = json.loads(payload)
                locked_tag = payload.get("tag", locked_tag)
            except json.JSONDecodeError:
                pass
            self.locked_tag_label.setText(
                    self.format_locked_tag(locked_tag)
            )
        elif topic == "avr/autonomy/water_drop_countdown":
            time_until_drop = None
            try:
                payload = json.loads(payload)
                time_until_drop = payload.get("time", time_until_drop)
            except json.JSONDecodeError:
                pass
            self.countdown_label.setText(
                    self.format_countdown(time_until_drop)
            )
        elif topic == "avr/apriltags/visible":
            tags = []
            tag_ids = ""
            try:
                payload = json.loads(payload)
                tags = payload.get("tags", [])
            except json.JSONDecodeError:
                pass
            for tag in tags:
                tag_id = tag.get("id", None)
                if tag_id is not None:
                    print(type(tag_id))
                    print(tag_id)
                    tag_ids += str(tag_id)
                    tag_ids += ", "
            if len(tags) > 0:
                tag_ids = tag_ids[:-2]
            self.tags_label.setText(
                    f"{self.format_visible_tags(tag_ids)} (Updated at {self.get_formatted_time()})"
            )

    def update_dropping_tag(self, tag_id: int) -> None:
        self.client.publish(
            "avr/autonomy/set_drop_tag",
            json.dumps(
                {
                    "id": tag_id
                }
            ),
            qos=2
        )

    @staticmethod
    def format_auto_state(state: int) -> str:
        color = RED_COLOR
        text = "Inactive"
        if state == 1:
            color = LIGHT_BLUE_COLOR
            text = "Searching"
        elif state == 2:
            color = GREEN_COLOR
            text = "Locked"
        return f"<span style='color:{color};'>{text}</span>"

    @staticmethod
    def format_locked_tag(tag_id: int | None) -> str:
        if tag_id is None:
            return COLORED_NONE_TEXT
        else:
            return f"<span style='color:{GREEN_COLOR};'>{tag_id}</span>"

    @staticmethod
    def format_countdown(countdown: int | None) -> str:
        if countdown is None:
            return COLORED_NONE_TEXT
        if countdown < 1:
            return f"<span style='color:{GREEN_COLOR};'>Dropping</span>"
        else:
            color = f"{RED_COLOR}" if countdown <= 1 else f"{GREEN_COLOR}"
            return f"<span style='color:{color};'>{countdown} seconds</span>"

    @staticmethod
    def format_visible_tags(tag_ids: str) -> str:
        if len(tag_ids) < 1:
            return COLORED_NONE_TEXT
        return f"<span style='color:{LIGHT_BLUE_COLOR};'>{tag_ids}</span>"

    @staticmethod
    def get_formatted_time() -> str:
        t = datetime.datetime.now().strftime("%I:%M:%S")
        # noinspection SpellCheckingInspection
        return f"<span style='color:{TIME_COLOR};'>{t}</span>"


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

    def process_message(self, topic: str, payload: str) -> None:
        if topic == "avr/gimbal/response_pos":
            x = 0
            y = 0
            try:
                payload = json.loads(payload)
                x = utils.constrain(payload.get("x", 50), 0, 180)
                y = utils.constrain(payload.get("y", 50), 0, 180)
                x = utils.map(x, 0, 180, -50, 50)
                y = utils.map(y, 0, 180, 50, -50)
            except json.JSONDecodeError:
                pass
            self.yaw_dial.setValue(x)
            self.pitch_bar.setValue(y)


class TelemetryPane(QtWidgets.QWidget):
    update_battery = QtCore.Signal(float)
    update_armed = QtCore.Signal(str)
    update_mode = QtCore.Signal(str)

    def __init__(self, parent: QtWidgets.QWidget) -> None:
        super(TelemetryPane, self).__init__(parent)

        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)

        telemetry_groupbox = QtWidgets.QGroupBox("Telemetry")
        telemetry_groupbox.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Policy.Minimum)
        telemetry_layout = QtWidgets.QFormLayout()
        telemetry_groupbox.setLayout(telemetry_layout)
        # telemetry_groupbox.setMinimumWidth(100)

        self.battery_label = QtWidgets.QLabel(COLORED_NONE_TEXT)
        self.armed_label = QtWidgets.QLabel(COLORED_NONE_TEXT)
        self.mode_label = QtWidgets.QLabel(COLORED_NONE_TEXT)
        telemetry_layout.addRow("Battery:", self.battery_label)
        telemetry_layout.addRow("Armed:", self.armed_label)
        telemetry_layout.addRow("Flight Mode:", self.mode_label)

        layout.addWidget(telemetry_groupbox)

        self.update_battery.connect(
                lambda voltage: self.battery_label.setText(
                        f"<span style='color:{LIGHT_BLUE_COLOR if voltage > 14 else RED_COLOR};'>{voltage} Volts</span>"
                )
        )
        self.update_armed.connect(
                self.armed_label.setText
        )
        self.update_mode.connect(
                lambda text: self.mode_label.setText(
                        f"<span style='color:{GREEN_COLOR};'>{text}</span>"
                )
        )
