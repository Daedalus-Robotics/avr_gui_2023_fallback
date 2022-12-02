import datetime
import json
import time

import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets

from avrgui.lib import utils
from avrgui.lib.graphics_label import GraphicsLabel
from avrgui.tabs.base import BaseTabWidget

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
    def __init__(self, parent: QtWidgets.QWidget) -> None:
        super().__init__(parent)

        self.setWindowTitle("HUD")

        self.zed_pane: ZEDCameraPane | None = None
        self.thermal_pane: ThermalCameraPane | None = None
        self.water_pane: WaterDropPane | None = None
        self.gimbal_pane: GimbalPane | None = None

    def build(self) -> None:
        layout = QtWidgets.QGridLayout()
        self.setLayout(layout)

        camera_groupbox = QtWidgets.QGroupBox("Camera")
        camera_groupbox.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding, QtWidgets.QSizePolicy.Expanding)
        camera_layout = QtWidgets.QVBoxLayout()
        camera_groupbox.setLayout(camera_layout)
        camera_groupbox.setFixedWidth(500)

        self.zed_pane = ZEDCameraPane(self)
        camera_layout.addWidget(self.zed_pane)
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

        layout.addWidget(control_groupbox, 0, 1)

    def process_message(self, topic: str, payload: str) -> None:
        self.water_pane.process_message(topic, payload)
        self.gimbal_pane.process_message(topic, payload)

    def clear(self) -> None:
        pass


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
        self.view.setFixedWidth(300)
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
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)

        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)

        thermal_groupbox = QtWidgets.QGroupBox("Thermal")
        thermal_groupbox.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        # zed_groupbox.setMaximumWidth()
        thermal_layout = QtWidgets.QVBoxLayout()
        thermal_groupbox.setLayout(thermal_layout)

        self.view = GraphicsLabel((1, 1))
        self.view.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.view.sizePolicy().setHeightForWidth(True)
        self.view.setPixmap(QtGui.QPixmap("assets/blank_square.png"))
        self.view.setFixedWidth(300)
        thermal_layout.addWidget(self.view)

        layout.addWidget(thermal_groupbox)

        self.update_frame.connect(self.view.setPixmap)


class WaterDropPane(QtWidgets.QWidget):
    move_dropper = QtCore.Signal(int)

    def __init__(self, parent: QtWidgets.QWidget) -> None:
        super().__init__(parent)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.MinimumExpanding)
        self.setFixedHeight(175)

        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)
        layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)

        water_drop_groupbox = QtWidgets.QGroupBox("Water Drop")
        water_drop_groupbox.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.MinimumExpanding)
        water_drop_layout = QtWidgets.QFormLayout()
        water_drop_groupbox.setLayout(water_drop_layout)
        water_drop_groupbox.setMinimumWidth(100)

        self.percent = QtWidgets.QProgressBar()
        self.percent.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.percent.setMinimumWidth(300)
        water_drop_layout.addRow("Position:", self.percent)

        self.auto_state_label = QtWidgets.QLabel(
                self.format_auto_state(0)
        )
        self.locked_tag_label = QtWidgets.QLabel(
                COLORED_NONE_TEXT
        )
        self.countdown_label = QtWidgets.QLabel(
                COLORED_NONE_TEXT
        )
        self.tags_label = QtWidgets.QLabel(
                f"{COLORED_NONE_TEXT} (Updated at {self.get_formatted_time()})"
        )
        water_drop_layout.addRow("Autonomy State:", self.auto_state_label)
        water_drop_layout.addRow("Locked Tag:", self.locked_tag_label)
        water_drop_layout.addRow("Countdown:", self.countdown_label)
        water_drop_layout.addRow("Visible Tags:", self.tags_label)

        layout.addWidget(water_drop_groupbox)

        self.move_dropper.connect(self.percent.setValue)

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
        return f"<span style='color:{TIME_COLOR};'>{tag_ids}</span>"

    @staticmethod
    def get_formatted_time() -> str:
        t = datetime.datetime.now().strftime("%I:%M:%S")
        # noinspection SpellCheckingInspection
        return f"<span style='color:{TIME_COLOR};'>{t}</span>"


class GimbalPane(QtWidgets.QWidget):
    def __init__(self, parent: QtWidgets.QWidget) -> None:
        super().__init__(parent)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)

        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)

        gimbal_groupbox = QtWidgets.QGroupBox("Gimbal")
        gimbal_groupbox.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.MinimumExpanding)
        gimbal_layout = QtWidgets.QGridLayout()
        gimbal_groupbox.setLayout(gimbal_layout)
        gimbal_groupbox.setMinimumWidth(100)

        self.yaw_dial = QtWidgets.QDial()
        self.yaw_dial.setWrapping(True)
        self.yaw_dial.setRange(-100, 100)
        self.yaw_dial.setValue(0)
        self.yaw_dial.setMaximumWidth(300)
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
