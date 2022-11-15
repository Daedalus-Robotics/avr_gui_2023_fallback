import json
import math
import time
from enum import Enum, auto
from typing import Any

import colour
import cv2
import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets
from bell.avr.mqtt.payloads import (
    AvrPcmFireLaserPayload,
    AvrPcmSetLaserOffPayload,
    AvrPcmSetLaserOnPayload
)

from .base import BaseTabWidget
from .connection.zmq import ZMQClient
from ..lib import stream
from ..lib.graphics_label import GraphicsLabel


def map_value(
        x: float, in_min: float, in_max: float, out_min: float, out_max: float
) -> float:
    return (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min


def deadzone(value: float | int, min_value: float | int) -> float | int:
    number_type = type(value)
    if min_value <= value <= -min_value:
        return number_type(0)
    else:
        return value


class Direction(Enum):
    Left = auto()
    Right = auto()
    Up = auto()
    Down = auto()


class ThermalView(QtWidgets.QWidget):
    def __init__(self, parent: QtWidgets.QWidget, zmq_client: ZMQClient) -> None:
        super().__init__(parent)

        self.zmq_client = zmq_client

        # canvas size
        self.width_ = 300
        self.height_ = self.width_

        # pixels within canvas
        self.pixels_x = 8
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
                    colour.Color("indigo").range_to(colour.Color("red"), self.COLORDEPTH)
            )
        ]

        # create canvas
        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)

        # self.canvas = QtWidgets.QGraphicsScene()
        # self.view = QtWidgets.QGraphicsView(self.canvas)
        # self.view.setGeometry(0, 0, self.width_, self.height_)
        self.view = GraphicsLabel((1, 1))
        self.view.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.MinimumExpanding)
        self.view.sizePolicy().setHeightForWidth(True)
        self.view.setPixmap(QtGui.QPixmap("assets/blank_square.png"))

        layout.addWidget(self.view)

        # need a bit of padding for the edges of the canvas
        self.setFixedSize(self.width_ + 50, self.height_ + 50)

    def set_temp_range(self, mintemp: float, maxtemp: float) -> None:
        self.MINTEMP = mintemp
        self.MAXTEMP = maxtemp

    def set_calibrated_temp_range(self) -> None:
        self.MINTEMP = self.last_lowest_temp + 0.0
        self.MAXTEMP = self.last_lowest_temp + 15.0

    def check_size(self, height, width) -> None:
        if not height == self.pixels_y or not width == self.pixels_x:
            self.pixels_y = height
            self.pixels_x = width

            self.pixel_width = self.width_ / self.pixels_x
            self.pixel_height = self.height_ / self.pixels_y

    def update_canvas(self, frame: np.ndarray) -> None:
        # float_pixels = [
        #     map_value(p, self.MINTEMP, self.MAXTEMP, 0, self.COLORDEPTH - 1)
        #     for p in pixels
        # ]

        # bicubic = scipy.interpolate.griddata(
        #         self.points, float_pixels, (self.grid_x, self.grid_y), method = "cubic"
        # )
        # print(frame.shape)
        # print(frame)
        # self.check_size(frame.shape[0], frame.shape[1])

        # pen = QtGui.QPen(QtCore.Qt.NoPen)
        # self.canvas.clear()
        #
        # y = 0
        # for row in frame:
        #     x = 0
        #     for pixel in row:
        #         x += 1
        #         brush = QtGui.QBrush(QtGui.QColor(pixel[2], pixel[1], pixel[0], 255))
        #         self.canvas.addRect(
        #                 self.pixel_width * x,
        #                 self.pixel_height * y,
        #                 self.pixel_width,
        #                 self.pixel_height,
        #                 pen,
        #                 brush
        #         )
        #     y += 1
        # cv2.imwrite("hello.png", frame)
        self.view.setPixmap(stream.convert_cv_qt(frame, (self.view.width(), self.view.height())))


class JoystickWidget(BaseTabWidget):
    def __init__(self, parent: QtWidgets.QWidget, controller_checkbox: QtWidgets.QCheckBox, zmq_client: ZMQClient) -> None:
        super().__init__(parent)

        self.zmq_client = zmq_client

        self.controller_checkbox = controller_checkbox
        self.setFixedSize(300, 300)

        self.movingOffset = QtCore.QPointF(0, 0)

        self.grabCenter = False
        self.controller_enabled = False
        self.relative_movement = False
        self.__maxDistance = 100

        self.last_time = 0

        self.current_y = 0
        self.current_x = 0

        self.servo_x_min = 0
        self.servo_y_min = 0
        self.servo_x_max = 100
        self.servo_y_max = 100

        # servo declarations
        self.SERVO_ABS_MAX = 2500
        self.SERVO_ABS_MIN = 500

    def process_message(self, topic: str, payload: str) -> None:
        pass

    def move_gimbal(self, x_servo: int, y_servo: int) -> None:
        # self.send_message(
        #         "avr/pcm/set_servo_pct",
        #         AvrPcmSetServoPctPayload(servo = 2, percent = x_servo_percent),
        # )
        # self.send_message(
        #         "avr/pcm/set_servo_pct",
        #         AvrPcmSetServoPctPayload(servo = 3, percent = y_servo_percent),
        # )
        # self.send_message(
        #         "avr/gimbal/pos",
        #         {
        #             "x": x_servo,
        #             "y": y_servo
        #         }
        # )
        self.zmq_client.zmq_publish(
                "gimbal_pos",
                {
                    "x": x_servo,
                    "y": y_servo
                }
        )

    def update_servos(self) -> None:
        """
        Update the servos on joystick movement.
        """
        ss = time.time()
        timesince = ss - self.last_time
        if timesince >= 0.1:
            if not self.relative_movement:
                # y_reversed = 100 - self.current_y
                y_reversed = self.current_y

                x_servo_pos = round(map_value(self.current_x, 0, 200, 0, 180))
                y_servo_pos = round(map_value(y_reversed, 0, 200, 0, 180))

                if not 0 <= x_servo_pos <= 180:
                    return
                if not 0 <= y_servo_pos <= 180:
                    return

                self.move_gimbal(x_servo_pos, y_servo_pos)
            else:
                ms = int(round(time.time() * 1000))
                timesince = ms - self.last_time
                if timesince < 100:
                    return
                self.last_time = ms

                x = deadzone(map_value(self.current_x, 0, 200, -100, 100), 10)
                y = deadzone(map_value(self.current_y, 0, 200, -100, 100), 10)

                x = int(map_value(x, -100, 100, -20, 20))
                y = int(map_value(y, -100, 100, -10, 10))
                # self.send_message("avr/gimbal/move", json.dumps({"x": x, "y": y}))
                self.zmq_client.zmq_publish(
                        "gimbal_move",
                        {
                            "x": x,
                            "y": y
                        }
                )
            self.last_time = ss

    def paintEvent(self, event) -> None:
        painter = QtGui.QPainter(self)
        bounds = QtCore.QRectF(
                -self.__maxDistance,
                -self.__maxDistance,
                self.__maxDistance * 2,
                self.__maxDistance * 2
        ).translated(self._center())
        painter.drawEllipse(bounds)
        painter.setBrush(QtCore.Qt.GlobalColor.black)
        painter.drawEllipse(self._center_ellipse())

    def _center_ellipse(self) -> QtCore.QRectF:
        if self.grabCenter or self.controller_enabled:
            return QtCore.QRectF(-20, -20, 40, 40).translated(self.movingOffset)
        return QtCore.QRectF(-20, -20, 40, 40).translated(self._center())

    def _center(self) -> QtCore.QPointF:
        return QtCore.QPointF(self.width() / 2, self.height() / 2)

    def _bound_joystick(self, point) -> QtCore.QPointF:
        limit_line = QtCore.QLineF(self._center(), point)
        if limit_line.length() > self.__maxDistance:
            limit_line.setLength(self.__maxDistance)
        return limit_line.p2()

    def joystick_direction(self) -> tuple[Direction, float] | int:
        if not self.grabCenter and not self.controller_enabled:
            return 0
        norm_vector = QtCore.QLineF(self._center(), self.movingOffset)
        current_distance = norm_vector.length()
        angle = norm_vector.angle()

        distance = min(current_distance / self.__maxDistance, 1.0)
        if 45 <= angle < 135:
            return Direction.Up, distance
        elif 135 <= angle < 225:
            return Direction.Left, distance
        elif 225 <= angle < 315:
            return Direction.Down, distance
        return Direction.Right, distance

    def mousePressEvent(self, ev) -> Any:
        self.grabCenter = self._center_ellipse().contains(ev.pos())
        if self.grabCenter:
            self.controller_checkbox.setChecked(False)
            self.controller_enabled = False
        return super().mousePressEvent(ev)

    def mouseReleaseEvent(self, event) -> Any:
        self.grabCenter = False
        self.movingOffset = QtCore.QPointF(0, 0)
        self.update()
        if not self.relative_movement:
            self.center_gimbal()

    def mouseMoveEvent(self, event) -> Any:
        if self.grabCenter or self.controller_enabled:
            self.movingOffset = self._bound_joystick(event.pos())
            self.update()

        self.current_x = self.movingOffset.x() - self._center().x() + self.__maxDistance
        self.current_y = self.movingOffset.y() - self._center().y() + self.__maxDistance
        self.update_servos()

    def center_gimbal(self) -> None:
        self.send_message("avr/gimbal/center", "")

    def set_pos(self, x: float, y: float) -> None:
        if self.controller_enabled:
            self.movingOffset = self._bound_joystick(
                    QtCore.QPoint(
                            int(
                                    x + self._center().x() - self.__maxDistance
                            ),
                            int(
                                    y + self._center().y() - self.__maxDistance
                            )
                    )
            )
            self.update()

            self.current_x = self.movingOffset.x() - self._center().x() + self.__maxDistance
            self.current_y = self.movingOffset.y() - self._center().y() + self.__maxDistance
            self.update_servos()


class ThermalViewControlWidget(BaseTabWidget):
    def __init__(self, parent: QtWidgets.QWidget, zmq_client: ZMQClient) -> None:
        super().__init__(parent)

        self.zmq_client = zmq_client

        self.relative_checkbox = None
        self.auto_checkbox = None
        self.last_fire = 0
        self.joystick = None
        self.viewer = None
        self.streaming_checkbox = None
        self.setWindowTitle("Thermal View/Control")

    def build(self) -> None:
        """
        Build the GUI layout
        """
        layout = QtWidgets.QHBoxLayout(self)
        self.setLayout(layout)

        # viewer
        viewer_groupbox = QtWidgets.QGroupBox("Viewer")
        viewer_layout = QtWidgets.QVBoxLayout()
        viewer_groupbox.setLayout(viewer_layout)

        self.viewer = ThermalView(self, self.zmq_client)
        viewer_layout.addWidget(self.viewer)

        # set temp range

        # lay out the host label and line edit
        below_image_layout = QtWidgets.QFormLayout()

        # self.streaming_checkbox = QtWidgets.QCheckBox("Enable Thermal Camera Streaming")
        # self.streaming_checkbox.toggled.connect(self.set_streaming)
        # below_image_layout.addRow(self.streaming_checkbox)

        viewer_layout.addLayout(below_image_layout)

        layout.addWidget(viewer_groupbox)

        # joystick
        joystick_groupbox = QtWidgets.QGroupBox("Joystick")
        joystick_layout = QtWidgets.QVBoxLayout()
        joystick_groupbox.setLayout(joystick_layout)

        sub_joystick_layout = QtWidgets.QHBoxLayout()
        joystick_layout.addLayout(sub_joystick_layout)

        controller_enable_checkbox = QtWidgets.QCheckBox("Enable Controller")

        self.joystick = JoystickWidget(self, controller_enable_checkbox, self.zmq_client)
        sub_joystick_layout.addWidget(self.joystick)

        controller_enable_checkbox.stateChanged.connect(
                lambda state: self.set_controller(state > 0)
        )
        joystick_layout.addWidget(controller_enable_checkbox)

        self.relative_checkbox = QtWidgets.QCheckBox("Relative Movement")
        self.relative_checkbox.stateChanged.connect(
                lambda state: self.set_rel(state > 0)
        )
        joystick_layout.addWidget(self.relative_checkbox)

        self.auto_checkbox = QtWidgets.QCheckBox("Enable Auto Aim")
        self.auto_checkbox.stateChanged.connect(
                lambda state: self.set_auto(state > 0)
        )
        joystick_layout.addWidget(self.auto_checkbox)

        center_gimbal_button = QtWidgets.QPushButton("Center Gimbal")
        joystick_layout.addWidget(center_gimbal_button)

        fire_laser_button = QtWidgets.QPushButton("Laser Fire")
        joystick_layout.addWidget(fire_laser_button)

        laser_on_button = QtWidgets.QPushButton("Laser On")
        joystick_layout.addWidget(laser_on_button)

        laser_off_button = QtWidgets.QPushButton("Laser Off")
        joystick_layout.addWidget(laser_off_button)

        kill_button = QtWidgets.QPushButton("Kill")
        joystick_layout.addWidget(kill_button)

        layout.addWidget(joystick_groupbox)

        # connect signals
        self.joystick.emit_message.connect(self.emit_message.emit)

        center_gimbal_button.clicked.connect(
                lambda: self.joystick.center_gimbal()
        )

        fire_laser_button.clicked.connect(
                lambda: self.send_message("avr/pcm/fire_laser", AvrPcmFireLaserPayload())
        )

        laser_on_button.clicked.connect(
                lambda: self.send_message("avr/pcm/set_laser_on", AvrPcmSetLaserOnPayload())
        )

        laser_off_button.clicked.connect(
                lambda: self.send_message("avr/pcm/set_laser_off", AvrPcmSetLaserOffPayload())
        )

        kill_button.clicked.connect(
                lambda: self.kill()
        )

        # don't allow us to shrink below size hint
        self.setMinimumSize(self.sizeHint())

    def set_controller(self, enabled: bool) -> None:
        self.joystick.controller_enabled = enabled

    def set_auto(self, enabled: bool) -> None:
        # self.send_message("avr/gimbal/auto_aim", json.dumps({"enabled": enabled}))
        self.zmq_client.zmq_publish("gimbal_auto", {"enabled": enabled})

    def set_rel(self, state: bool) -> None:
        self.joystick.relative_movement = state

    def process_message(self, topic: str, payload: str) -> None:
        pass

    def process_message_bytes(self, topic: str, payload: bytes) -> None:
        """
        Process an incoming message and update the appropriate component
        """
        # discard topics we don't recognize
        if topic != "avr/raw/thermal/reading":
            return

        success, frame = stream.decode_frame(payload)
        if success:
            self.viewer.update_canvas(frame)

    def on_controller_r(self, pos: tuple[float, float]) -> None:
        x = deadzone(pos[0], 20)
        y = deadzone(pos[1], 20)
        self.joystick.set_pos(
                map_value(x, -130, 130, 0, 200),
                map_value(y, -130, 130, 0, 200)
        )

    def on_controller_rt(self) -> None:
        ms = int(round(time.time() * 1000))
        timesince = ms - self.last_fire
        if timesince < 100:
            return
        self.last_fire = ms

        # self.send_message("avr/pcm/fire_laser", AvrPcmFireLaserPayload())
        self.zmq_client.zmq_publish("gimbal_fire", "")

    def on_controller_rb(self, state: bool) -> None:
        self.send_message("avr/gimbal/fire-ready", {"state": state})

    def on_controller_circle(self, state: bool) -> None:
        self.auto_checkbox.setChecked(state)

    def on_controller_r3(self) -> None:
        self.relative_checkbox.setChecked(not self.joystick.relative_movement)

    def kill(self) -> None:
        self.set_controller(False)
        self.set_rel(False)
        self.set_auto(False)
        # self.send_message("avr/gimbal/disable", "", qos = 2)
        self.zmq_client.zmq_publish("gimbal_disable", "")

    def clear(self) -> None:
        # self.viewer.canvas.clear()
        pass
