from __future__ import annotations

import json
from enum import Enum
from typing import Callable, Any

import colour
import roslibpy
from PySide6 import QtCore, QtWidgets, QtGui
from bell.avr.mqtt.payloads import (
    AvrFcmAttitudeEulerPayload,
    AvrFcmBatteryPayload,
    AvrFcmGpsInfoPayload,
    AvrFcmLocationGlobalPayload,
    AvrFcmLocationLocalPayload,
    AvrFcmStatusPayload,
)

from .base import BaseTabWidget
from .connection.rosbridge import RosBridgeClient
from ..lib.color import smear_color, wrap_text
from ..lib.toast import Toast
from ..lib.widgets import DisplayLineEdit, StatusLabel

BATTERY_COLORS: list[colour.Color] = colour.Color("green").range_to(colour.Color("red"), 101)
COLORED_UNKNOWN_TEXT = "<span style='color:orange;'>Unknown</span>"
UNKNOWN_TEXT = "Unknown"
RED_COLOR = "red"
LIGHT_BLUE_COLOR = "#0091ff"
YELLOW_COLOR = "#ffb800"
GREEN_COLOR = "#1bc700"

NAV_STATE_PREFIX_LENGTH = len('NAVIGATION_STATE_')

LOW_BATTERY_VOLTAGE = 15.8
FAULT_BATTERY_VOLTAGE = 14.8


class PX4VehicleCommand(Enum):
    VEHICLE_CMD_PREFLIGHT_REBOOT_SHUTDOWN = 246
    VEHICLE_CMD_SET_GPS_GLOBAL_ORIGIN = 100000


class PX4VehicleStatusNavState(Enum):
    NAVIGATION_STATE_MANUAL = 0  # Manual mode
    NAVIGATION_STATE_ALTCTL = 1  # Altitude control mode
    NAVIGATION_STATE_POSCTL = 2  # Position control mode
    NAVIGATION_STATE_AUTO_MISSION = 3  # Auto mission mode
    NAVIGATION_STATE_AUTO_LOITER = 4  # Auto loiter mode
    NAVIGATION_STATE_AUTO_RTL = 5  # Auto return to launch mode
    NAVIGATION_STATE_UNUSED3 = 8  # Free slot
    NAVIGATION_STATE_UNUSED = 9  # Free slot
    NAVIGATION_STATE_ACRO = 10  # Acro mode
    NAVIGATION_STATE_UNUSED1 = 11  # Free slot
    NAVIGATION_STATE_DESCEND = 12  # Descend mode (no position control)
    NAVIGATION_STATE_TERMINATION = 13  # Termination mode
    NAVIGATION_STATE_OFFBOARD = 14
    NAVIGATION_STATE_STAB = 15  # Stabilized mode
    NAVIGATION_STATE_UNUSED2 = 16  # Free slot
    NAVIGATION_STATE_AUTO_TAKEOFF = 17  # Takeoff
    NAVIGATION_STATE_AUTO_LAND = 18  # Land
    NAVIGATION_STATE_AUTO_FOLLOW_TARGET = 19  # Auto Follow
    NAVIGATION_STATE_AUTO_PRECLAND = 20  # Precision land with landing target
    NAVIGATION_STATE_ORBIT = 21  # Orbit in a circle
    NAVIGATION_STATE_AUTO_VTOL_TAKEOFF = 22  # Takeoff, transition, establish loiter
    NAVIGATION_STATE_EXTERNAL1 = 23
    NAVIGATION_STATE_EXTERNAL2 = 24
    NAVIGATION_STATE_EXTERNAL3 = 25
    NAVIGATION_STATE_EXTERNAL4 = 26
    NAVIGATION_STATE_EXTERNAL5 = 27
    NAVIGATION_STATE_EXTERNAL6 = 28
    NAVIGATION_STATE_EXTERNAL7 = 29
    NAVIGATION_STATE_EXTERNAL8 = 30
    NAVIGATION_STATE_MAX = 31


class ZEDPositionStatus(Enum):
    SEARCHING = 0
    OK = 1
    OFF = 2
    FPS_TOO_LOW = 3
    SEARCHING_FLOOR_PLANE = 3


class VMCTelemetryWidget(BaseTabWidget):
    # This widget provides a minimal QGroundControl-esque interface.
    # In our case, this operates over MQTT as all the relevant data
    # is already published there.
    vehicle_state_signal = QtCore.Signal(bool, object)
    battery_state_signal = QtCore.Signal(bool, float, float)
    pose_signal = QtCore.Signal(tuple[float, float, float], tuple[float, float, float, float])
    pose_state_signal = QtCore.Signal(object)
    formatted_battery_signal = QtCore.Signal(str, str)
    formatted_armed_signal = QtCore.Signal(str)
    formatted_mode_signal = QtCore.Signal(str)

    def __init__(self, parent: QtWidgets.QWidget, client: RosBridgeClient, controller) -> None:
        super().__init__(parent, client)

        self.controller = controller

        self.last_armed = False
        self.armed = False
        self.battery_voltage_label = None
        self.battery_current_label = None
        self.armed_label = None

        self.pos_x_line_edit = None
        self.pos_y_line_edit = None
        self.pos_z_line_edit = None
        self.att_r_line_edit = None
        self.att_p_line_edit = None
        self.att_y_line_edit = None
        self.flight_mode_label = None

        self.service_map: dict[str, Callable[[bool], None]] = {}
        self.zed_tracking_status_label = None
        self.vmc_service_status_label = None
        self.fcm_status_label = None
        self.pcm_status_label = None

        self.main_shutdown_button = None
        self.main_shutdown_callback: Callable[[], None] = lambda: None

        self.battery_level = 0

        self.setWindowTitle("VMC Telemetry")

        self.pcc_restart_service: roslibpy.Service | None = None
        self.fcm_command_publisher: roslibpy.Topic | None = None
        self.fcm_status_subscriber: roslibpy.Topic | None = None
        self.fcm_battery_status_subscriber: roslibpy.Topic | None = None
        self.zed_pose_subscriber: roslibpy.Topic | None = None
        self.zed_pose_state_subscriber: roslibpy.Topic | None = None

    def build(self) -> None:
        """
        Build the GUI layout
        """
        layout = QtWidgets.QVBoxLayout(self)
        self.setLayout(layout)

        # bottom groupbox
        top_group = QtWidgets.QFrame()
        top_group.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed
        )
        top_layout = QtWidgets.QHBoxLayout()
        top_group.setLayout(top_layout)

        # fcc groupbox
        fcc_groupbox = QtWidgets.QGroupBox("FCC")
        fcc_groupbox.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed
        )
        fcc_layout = QtWidgets.QGridLayout()
        fcc_groupbox.setLayout(fcc_layout)

        # battery row
        battery_layout = QtWidgets.QHBoxLayout()

        self.battery_voltage_label = QtWidgets.QLabel(COLORED_UNKNOWN_TEXT)
        self.battery_current_label = QtWidgets.QLabel("")
        battery_layout.addWidget(self.battery_voltage_label)
        battery_layout.addWidget(self.battery_current_label)
        self.battery_state_signal.connect(
            lambda _, voltage, __: self.battery_voltage_label.setText(self.format_battery_voltage(voltage))
        )
        self.battery_state_signal.connect(
            lambda _, __, current: self.battery_voltage_label.setText(self.format_battery_current(current))
        )

        self.battery_state_signal.connect(
            lambda _, voltage, current: self.battery_state_signal.emit(
                self.format_battery_voltage(voltage),
                self.format_battery_current(current)
            )
        )

        fcc_layout.addWidget(QtWidgets.QLabel("Battery:"), 0, 0)
        fcc_layout.addLayout(battery_layout, 0, 1)

        # armed row
        self.armed_label = QtWidgets.QLabel(COLORED_UNKNOWN_TEXT)
        fcc_layout.addWidget(QtWidgets.QLabel("Armed Status:"), 1, 0)
        fcc_layout.addWidget(self.armed_label, 1, 1)
        self.vehicle_state_signal.connect(
            lambda armed, _: self.armed_label.setText(self.format_armed_text(armed))
        )

        # flight mode row
        self.flight_mode_label = QtWidgets.QLabel(COLORED_UNKNOWN_TEXT)
        fcc_layout.addWidget(QtWidgets.QLabel("Flight Mode:"), 2, 0)
        fcc_layout.addWidget(self.flight_mode_label, 2, 1)
        self.vehicle_state_signal.connect(
            lambda _, nav_state: self.flight_mode_label.setText(self.format_nav_state(nav_state))
        )

        top_layout.addWidget(fcc_groupbox)

        # pose
        pose_groupbox = QtWidgets.QGroupBox("Pose")
        pose_layout = QtWidgets.QFormLayout()
        pose_groupbox.setLayout(pose_layout)

        # xyz row
        loc_xyz_layout = QtWidgets.QHBoxLayout()

        self.pos_x_line_edit = DisplayLineEdit(UNKNOWN_TEXT)
        loc_xyz_layout.addWidget(self.pos_x_line_edit)

        self.pos_y_line_edit = DisplayLineEdit(UNKNOWN_TEXT)
        loc_xyz_layout.addWidget(self.pos_y_line_edit)

        self.pos_z_line_edit = DisplayLineEdit(UNKNOWN_TEXT)
        loc_xyz_layout.addWidget(self.pos_z_line_edit)

        pose_layout.addRow(
            QtWidgets.QLabel("Local FLU (x, y, z):"), loc_xyz_layout
        )

        # euler row
        att_rpy_layout = QtWidgets.QHBoxLayout()

        self.att_r_line_edit = DisplayLineEdit(UNKNOWN_TEXT)
        att_rpy_layout.addWidget(self.att_r_line_edit)

        self.att_p_line_edit = DisplayLineEdit(UNKNOWN_TEXT)
        att_rpy_layout.addWidget(self.att_p_line_edit)

        self.att_y_line_edit = DisplayLineEdit(UNKNOWN_TEXT)
        att_rpy_layout.addWidget(self.att_y_line_edit)

        pose_layout.addRow(QtWidgets.QLabel("Euler (r, p , y)"), att_rpy_layout)

        top_layout.addWidget(pose_groupbox)

        def update_pose(position: tuple[float, float, float],
                        _: tuple[float, float, float, float]) -> None:
            self.pos_x_line_edit.setText(position[0])
            self.pos_y_line_edit.setText(position[1])
            self.pos_z_line_edit.setText(position[2])

            # ToDo: Convert quaternion to rpy and set values

        self.pose_signal.connect(update_pose)

        layout.addWidget(top_group)

        states_groupbox = QtWidgets.QGroupBox("States")
        states_groupbox.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed
        )
        states_layout = QtWidgets.QGridLayout()
        states_groupbox.setLayout(states_layout)

        y = 0

        self.zed_tracking_status_label = StatusLabel("ZED Tracking")
        states_layout.addWidget(self.zed_tracking_status_label, y, 0)
        self.service_map["zed_tracking"] = self.zed_tracking_status_label.set_health
        self.pose_state_signal.connect(
            lambda state: self.zed_tracking_status_label.set_health(state == ZEDPositionStatus.OK)
        )

        y += 1

        self.vmc_service_status_label = StatusLabel("ROS2 Launch File")
        restart_button = QtWidgets.QPushButton("Restart")
        restart_button.clicked.connect(lambda: self.restart_service(
            lambda: None  # ToDo: Make this run 'sudo systemctl restart vmc'
        ))
        states_layout.addWidget(self.vmc_service_status_label, y, 0)
        states_layout.addWidget(restart_button, y, 1)
        self.service_map["vmc_service"] = self.vmc_service_status_label.set_health
        self.vmc_service_status_label.set_health(True)

        y += 1

        self.fcm_status_label = StatusLabel("Flight Controller")
        restart_button = QtWidgets.QPushButton("Restart")
        restart_button.clicked.connect(lambda: self.restart_service(
            self.reset_fcm,
            True,
            "Restart Flight Controller",
            "This will restart the flight controller.\nIf the drone is currently flying, it will fall."
        ))
        states_layout.addWidget(self.fcm_status_label, y, 0)
        states_layout.addWidget(restart_button, y, 1)
        self.service_map["fcc"] = self.fcm_status_label.set_health
        self.battery_state_signal.connect(lambda connected, voltage, _: self.fcm_status_label.set_health(
            connected and voltage > FAULT_BATTERY_VOLTAGE
        ))

        y += 1

        self.pcm_status_label = StatusLabel("Peripheral Controller")
        restart_button = QtWidgets.QPushButton("Restart")
        restart_button.clicked.connect(lambda: self.restart_service(
            self.reset_pcc,
            True,
            "Restart Peripheral Controller"
            "This will restart the peripheral controller.\nIt may also stop the servos from working."
        ))
        states_layout.addWidget(self.pcm_status_label, y, 0)
        states_layout.addWidget(restart_button, y, 1)
        self.service_map["pcc"] = self.pcm_status_label.set_health
        self.pcm_status_label.set_health(True)

        layout.addWidget(states_groupbox)

        self.main_shutdown_button = QtWidgets.QPushButton("Shutdown")
        self.main_shutdown_callback = lambda: self.restart_service(
            lambda: None,  # ToDo: Make this run 'sudo shutdown now'
            True,
            "Shutdown VMC",
            "This will shutdown the vehicle management computer.\nThis is not reversible!",
        )
        self.main_shutdown_button.clicked.connect(self.main_shutdown_callback)

        layout.addWidget(self.main_shutdown_button)

    def status_callback_fcm(self, msg: dict[str, Any]) -> None:
        arming_state = bool(msg['arming_state'])
        nav_state = PX4VehicleStatusNavState(msg['nav_state'])

        self.vehicle_state_signal.emit(arming_state, nav_state)

    def battery_status_callback_fcm(self, msg: dict[str, Any]) -> None:
        connected = msg['connected']
        voltage = msg['voltage_filtered_v']
        current = msg['current_filtered_a']

        self.battery_state_signal.emit(connected, voltage, current)

    def pose_callback_zed(self, msg: dict[str, Any]) -> None:
        pose = msg['pose']
        position_dict = pose['position']
        orientation_dict = pose['orientation']

        position = position_dict['x'], position_dict['y'], position_dict['z']
        orientation = orientation_dict['x'], orientation_dict['y'], orientation_dict['z'], orientation_dict['w']

        self.pose_signal.emit(position, orientation)

    def pose_state_callback_zed(self, msg: dict[str, Any]) -> None:
        status = ZEDPositionStatus(msg['status'])

        self.pose_state_signal.emit(status)

    def setup_ros(self, client: roslibpy.Ros) -> None:
        super().setup_ros(client)

        self.pcc_restart_service = roslibpy.Service(
            client,
            '/pcc/reset',
            'std_srvs/srv/Trigger'
        )

        self.fcm_command_publisher = roslibpy.Topic(
            client,
            '/fmu/in/vehicle_command',
            'px4_msgs/msg/VehicleCommand'
        )

        self.fcm_status_subscriber = roslibpy.Topic(
            client,
            '/fmu/out/vehicle_status',
            'px4_msgs/msg/VehicleStatus'
        )
        self.fcm_status_subscriber.subscribe(self.status_callback_fcm)

        self.fcm_battery_status_subscriber = roslibpy.Topic(
            client,
            '/fmu/out/battery_status',
            'px4_msgs/msg/BatteryStatus'
        )
        self.fcm_battery_status_subscriber.subscribe(self.battery_status_callback_fcm)

        self.zed_pose_subscriber = roslibpy.Topic(
            client,
            '/zed/zed_node/pose',
            'geometry_msgs/msg/PoseStamped'
        )
        self.zed_pose_subscriber.subscribe(self.pose_callback_zed)

        self.zed_pose_state_subscriber = roslibpy.Topic(
            client,
            '/zed/zed_node/pose/state',
            'zed_interfaces/msg/PosTrackStatus'
        )
        self.zed_pose_state_subscriber.subscribe(self.pose_state_callback_zed)

    def reset_pcc(self) -> None:
        self.pcc_restart_service.call(
            roslibpy.ServiceRequest(),
            lambda msg: print(f'PCC reset triggered: {msg}')
        )

    def reset_fcm(self) -> None:
        self.fcm_command_publisher.publish(
            {
                'command': PX4VehicleCommand.VEHICLE_CMD_PREFLIGHT_REBOOT_SHUTDOWN,
                'param1': float(1)
            }
        )

    def set_global_position_fcm(self, latitude: float, longitude: float, altitude: float = 0) -> None:
        self.fcm_command_publisher.publish(
            {
                'command': PX4VehicleCommand.VEHICLE_CMD_SET_GPS_GLOBAL_ORIGIN,
                'param5': latitude,
                'param6': longitude,
                'param7': altitude
            }
        )

    # ToDo: Maybe add some calibration buttons for level horizon and mag

    def clear(self) -> None:
        # status
        self.battery_voltage_label.setText(COLORED_UNKNOWN_TEXT)
        self.battery_current_label.setText('')
        self.formatted_battery_signal.emit(COLORED_UNKNOWN_TEXT, '')

        self.armed_label.setText(COLORED_UNKNOWN_TEXT)
        self.formatted_armed_signal.emit(COLORED_UNKNOWN_TEXT)

        self.flight_mode_label.setText(COLORED_UNKNOWN_TEXT)
        self.formatted_mode_signal.emit(COLORED_UNKNOWN_TEXT)

        # position
        self.pos_x_line_edit.setText(UNKNOWN_TEXT)
        self.pos_y_line_edit.setText(UNKNOWN_TEXT)
        self.pos_z_line_edit.setText(UNKNOWN_TEXT)

        self.att_r_line_edit.setText(UNKNOWN_TEXT)
        self.att_p_line_edit.setText(UNKNOWN_TEXT)
        self.att_y_line_edit.setText(UNKNOWN_TEXT)

    @staticmethod
    def restart_service(callback: Callable[[], None],
                        show_dialog: bool = False, title: str = "", message: str = "") -> None:
        do_reset = True
        if show_dialog:
            if '\n' in message:
                split = message.split('‡')
                message = ""
                num = 0
                for text in split[0:-1]:
                    message += text
                    if not num == len(split[0:-1]) - 1:
                        message += "\n"
                    num += 1
                info = split[-1]
            else:
                info = None

            dialog = QtWidgets.QMessageBox()
            dialog.setWindowTitle(title)
            dialog.setText(message)
            if info is not None:
                dialog.setInformativeText(info)
            dialog.setIcon(QtWidgets.QMessageBox.Critical)
            dialog.setStandardButtons(QtWidgets.QMessageBox.Cancel | QtWidgets.QMessageBox.Ok)
            dialog.setDefaultButton(QtWidgets.QMessageBox.Ok)
            dialog.setEscapeButton(QtWidgets.QMessageBox.Cancel)
            if dialog.exec_() != QtWidgets.QMessageBox.Ok:
                do_reset = False
        if do_reset:
            callback()

    @staticmethod
    def format_battery_voltage(voltage: float) -> str:
        if voltage <= FAULT_BATTERY_VOLTAGE:
            start = f"<a style='color:{RED_COLOR};'>"
        elif voltage <= LOW_BATTERY_VOLTAGE:
            start = f"<a style='color:{YELLOW_COLOR};'>"
        else:
            start = f"<a style='color:{GREEN_COLOR};'>"
        return f"{start}{voltage} V</a>"

    @staticmethod
    def format_battery_current(current: float) -> str:
        return f"<a style='color:{LIGHT_BLUE_COLOR};'>{current} A</a>"

    @staticmethod
    def format_armed_text(armed: bool) -> str:
        if armed:
            return f"<a style='color:{YELLOW_COLOR};'>Armed</a>"
        else:
            return f"<a style='color:{GREEN_COLOR};'>Disarmed</a>"

    @staticmethod
    def format_nav_state(nav_state: PX4VehicleStatusNavState) -> str:
        state = nav_state.name[NAV_STATE_PREFIX_LENGTH:]
        return f"<a style='color:{LIGHT_BLUE_COLOR};'>{state}</a>"
