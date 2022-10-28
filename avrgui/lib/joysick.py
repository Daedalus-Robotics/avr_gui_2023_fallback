from enum import Enum
from typing import Any

from PySide6.QtCore import QLineF, QPointF, QRectF
from PySide6.QtGui import QPainter, Qt
from PySide6.QtWidgets import QWidget


class Direction(Enum):
    Left = 0
    Right = 1
    Up = 2
    Down = 3


class Joystick(QWidget):
    def __init__(self, parent = None) -> None:
        super(Joystick, self).__init__(parent)
        self.setMinimumSize(100, 100)
        self.movingOffset = QPointF(0, 0)
        self.grabCenter = False
        self.__maxDistance = 50

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        bounds = QRectF(
                -self.__maxDistance,
                -self.__maxDistance,
                self.__maxDistance * 2,
                self.__maxDistance * 2
        ).translated(self._center())
        painter.drawEllipse(bounds)
        painter.setBrush(Qt.GlobalColor.black)
        painter.drawEllipse(self._center_ellipse())

    def _center_ellipse(self) -> QRectF:
        if self.grabCenter:
            return QRectF(-20, -20, 40, 40).translated(self.movingOffset)
        return QRectF(-20, -20, 40, 40).translated(self._center())

    def _center(self) -> QPointF:
        return QPointF(self.width() / 2, self.height() / 2)

    def _bound_joystick(self, point) -> QPointF:
        limit_line = QLineF(self._center(), point)
        if limit_line.length() > self.__maxDistance:
            limit_line.setLength(self.__maxDistance)
        return limit_line.p2()

    def joystick_direction(self) -> tuple[Direction, float]:
        if not self.grabCenter:
            return 0
        norm_vector = QLineF(self._center(), self.movingOffset)
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
        return super().mousePressEvent(ev)

    def mouseReleaseEvent(self, event) -> Any:
        self.grabCenter = False
        self.movingOffset = QPointF(0, 0)
        self.update()

    def mouseMoveEvent(self, event) -> Any:
        if self.grabCenter:
            self.movingOffset = self._bound_joystick(event.pos())
            self.update()
        print(self.joystick_direction())
