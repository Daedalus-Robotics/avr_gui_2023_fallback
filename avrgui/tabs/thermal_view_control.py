import math
import time
from enum import Enum, auto
from typing import Optional

import colour
import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets
from bell.avr.mqtt.payloads import (
    AvrPcmFireLaserPayload,
    AvrPcmSetLaserOffPayload,
    AvrPcmSetLaserOnPayload,
    AvrPcmSetServoAbsPayload,
    AvrPcmSetServoPctPayload,
)

from .base import BaseTabWidget
from ..lib import stream
from ..lib.graphics_label import GraphicsLabel


def map_value(
        x: float, in_min: float, in_max: float, out_min: float, out_max: float
) -> float:
    return (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min


class Direction(Enum):
    Left = auto()
    Right = auto()
    Up = auto()
    Down = auto()


class ThermalView(QtWidgets.QWidget):
    def __init__(self, parent: QtWidgets.QWidget) -> None:
        super().__init__(parent)

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
        # i'm not fully sure what this does
        self.grid_x, self.grid_y = np.mgrid[
                                   0: self.camera_x - 1: self.camera_total / 2j,
                                   0: self.camera_y - 1: self.camera_total / 2j,
                                   ]

        # create avaiable colors
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

    def set_calibrted_temp_range(self) -> None:
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
        self.view.setPixmap(stream.convert_cv_qt(frame, (self.view.width(), self.view.height())))


class JoystickWidget(BaseTabWidget):
    def __init__(self, parent: QtWidgets.QWidget) -> None:
        super().__init__(parent)

        self.setFixedSize(300, 300)

        self.movingOffset = QtCore.QPointF(0, 0)

        self.grabCenter = False
        self.__maxDistance = 100

        self.last_time = 0

        self.current_y = 0
        self.current_x = 0

        self.servoxmin = 0
        self.servoymin = 0
        self.servoxmax = 100
        self.servoymax = 100

        # servo declarations
        self.SERVO_ABS_MAX = 2500
        self.SERVO_ABS_MIN = 500

    def process_message(self, topic: str, payload: str) -> None:
        pass

    def _center(self) -> QtCore.QPointF:
        """
        Return the center of the widget.
        """
        return QtCore.QPointF(self.width() / 2, self.height() / 2)

    def move_gimbal(self, x_servo_percent: int, y_servo_percent: int) -> None:
        self.send_message(
                "avr/pcm/set_servo_pct",
                AvrPcmSetServoPctPayload(servo = 2, percent = x_servo_percent),
        )
        self.send_message(
                "avr/pcm/set_servo_pct",
                AvrPcmSetServoPctPayload(servo = 3, percent = y_servo_percent),
        )

    def move_gimbal_absolute(self, x_servo_abs: int, y_servo_abs: int) -> None:
        self.send_message(
                "avr/pcm/set_servo_abs",
                AvrPcmSetServoAbsPayload(servo = 2, absolute = x_servo_abs),
        )
        self.send_message(
                "avr/pcm/set_servo_abs",
                AvrPcmSetServoAbsPayload(servo = 3, absolute = y_servo_abs),
        )

    def update_servos(self) -> None:
        """
        Update the servos on joystick movement.
        """
        ms = int(round(time.time() * 1000))
        timesince = ms - self.last_time
        if timesince < 50:
            return
        self.last_time = ms

        y_reversed = 100 - self.current_y

        x_servo_percent = round(map_value(self.current_x, 0, 200, 0, 100))
        y_servo_percent = round(map_value(y_reversed, 0, 200, 0, 100))

        if x_servo_percent < self.servoxmin:
            return
        if y_servo_percent < self.servoymin:
            return
        if x_servo_percent > self.servoxmax:
            return
        if y_servo_percent > self.servoymax:
            return

        self.move_gimbal(x_servo_percent, y_servo_percent)

        # y_reversed = 225 - self.current_y
        # # side to side  270 left, 360 right
        #
        # x_servo_abs = round(
        #         map_value(
        #                 self.current_x + 25, 225, 25, self.SERVO_ABS_MIN, self.SERVO_ABS_MAX
        #         )
        # )
        # y_servo_abs = round(
        #         map_value(y_reversed, 225, 25, self.SERVO_ABS_MIN, self.SERVO_ABS_MAX)
        # )
        #
        # self.move_gimbal_absolute(x_servo_abs, y_servo_abs)

    def _center_ellipse(self) -> QtCore.QRectF:
        # sourcery skip: assign-if-exp
        if self.grabCenter:
            center = self.movingOffset
        else:
            center = self._center()

        return QtCore.QRectF(-20, -20, 40, 40).translated(center)

    def _bound_joystick(self, point: QtCore.QPoint) -> QtCore.QPoint:
        """
        If the joystick is leaving the widget, bound it to the edge of the widget.
        """
        if point.x() > (self._center().x() + self.__maxDistance):
            point.setX(int(self._center().x() + self.__maxDistance))
        elif point.x() < (self._center().x() - self.__maxDistance):
            point.setX(int(self._center().x() - self.__maxDistance))

        if point.y() > (self._center().y() + self.__maxDistance):
            point.setY(int(self._center().y() + self.__maxDistance))
        elif point.y() < (self._center().y() - self.__maxDistance):
            point.setY(int(self._center().y() - self.__maxDistance))
        return point

    def joystick_direction(self) -> Optional[tuple[Direction, float]]:
        """
        Retrieve the direction the joystick is moving
        """
        if not self.grabCenter:
            return None

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

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        painter = QtGui.QPainter(self)
        bounds = QtCore.QRectF(
                -self.__maxDistance,
                -self.__maxDistance,
                self.__maxDistance * 2,
                self.__maxDistance * 2,
        ).translated(self._center())

        # painter.drawEllipse(bounds)
        painter.drawRect(bounds)
        painter.setBrush(QtCore.Qt.GlobalColor.black)

        painter.drawEllipse(self._center_ellipse())

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> QtGui.QMouseEvent:
        """
        On a mouse press, check if we've clicked on the center of the joystick.
        """
        self.grabCenter = self._center_ellipse().contains(event.pos())
        return event

    def mouseReleaseEvent(self, event: QtCore.QEvent) -> None:
        # self.grabCenter = False
        # self.movingOffset = QtCore.QPointF(0, 0)
        self.update()

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:
        if self.grabCenter:
            self.movingOffset = self._bound_joystick(event.pos())
            self.update()

        self.current_x = self.movingOffset.x() - self._center().x() + self.__maxDistance
        self.current_y = self.movingOffset.y() - self._center().y() + self.__maxDistance
        self.update_servos()

    def center_gimbal(self) -> None:
        self.move_gimbal(50, 50)


class ThermalViewControlWidget(BaseTabWidget):
    def __init__(self, parent: QtWidgets.QWidget) -> None:
        super().__init__(parent)

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

        self.viewer = ThermalView(self)
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

        self.joystick = JoystickWidget(self)
        sub_joystick_layout.addWidget(self.joystick)

        center_gimbal_button = QtWidgets.QPushButton("Center Gimbal")
        joystick_layout.addWidget(center_gimbal_button)

        fire_laser_button = QtWidgets.QPushButton("Laser Fire")
        joystick_layout.addWidget(fire_laser_button)

        laser_on_button = QtWidgets.QPushButton("Laser On")
        joystick_layout.addWidget(laser_on_button)

        laser_off_button = QtWidgets.QPushButton("Laser Off")
        joystick_layout.addWidget(laser_off_button)

        layout.addWidget(joystick_groupbox)

        # connect signals
        self.joystick.emit_message.connect(self.emit_message.emit)

        # center_gimbal_button.clicked.connect(
        #         lambda: self.joystick.grabCenter()
        # )

        fire_laser_button.clicked.connect(
                lambda: self.send_message("avr/pcm/fire_laser", AvrPcmFireLaserPayload())
        )

        center_gimbal_button.clicked.connect(
                lambda: self.joystick.center_gimbal()
        )

        laser_on_button.clicked.connect(
                lambda: self.send_message("avr/pcm/set_laser_on", AvrPcmSetLaserOnPayload())
        )

        laser_off_button.clicked.connect(
                lambda: self.send_message("avr/pcm/set_laser_off", AvrPcmSetLaserOffPayload())
        )

        # don't allow us to shrink below size hint
        self.setMinimumSize(self.sizeHint())

    def process_message(self, topic: str, payload: str) -> None:
        pass

    def process_message_bytes(self, topic: str, payload: bytes) -> None:
        """
        Process an incoming message and update the appropriate component
        """
        # discard topics we don't recognize
        if topic != "avr/thermal/reading":
            return

        success, frame = stream.decode_frame_uncompressed(payload)
        if success:
            self.viewer.update_canvas(frame)

    def clear(self) -> None:
        # self.viewer.canvas.clear()
        pass
