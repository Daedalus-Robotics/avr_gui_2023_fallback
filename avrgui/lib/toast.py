from PySide6.QtCore import Qt
from PySide6 import QtCore, QtGui, QtWidgets

HEIGHT = 40
BOTTOM_OFFSET = 50
ALPHA = 180
DEFAULT_TIMEOUT = 2.0


class Toast(QtWidgets.QWidget):
    _instance = None
    send_message = QtCore.Signal(str, float)

    @classmethod
    def get(cls, parent: QtWidgets.QWidget = None) -> "Toast":
        if cls._instance is None:
            cls._instance = Toast(parent)
        return cls._instance

    def __init__(self, parent: QtWidgets.QWidget):
        super().__init__(parent)

        layout = QtWidgets.QVBoxLayout()
        self.text = QtWidgets.QLabel()
        layout.addWidget(self.text)
        self.setLayout(layout)

        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(lambda: self.setVisible(False))

        self.send_message.connect(self.show_message)

        self.setVisible(False)

    def window_resize_event(self, event: QtGui.QResizeEvent) -> None:
        self.refresh_size(event.size())

    def refresh_size(self, size):
        window_height = size.height()
        window_width = size.width()

        width = 250
        x = (window_width // 2) - (width // 2)
        y = window_height - (HEIGHT // 2) - BOTTOM_OFFSET

        self.setGeometry(x, y, width, HEIGHT)

    def paintEvent(self, ev):
        painter = QtGui.QPainter(self)
        if not painter.isActive():
            painter.begin(self)

        pen = QtGui.QPen(Qt.GlobalColor.black, 10)
        painter.setPen(pen)

        path = QtGui.QPainterPath()
        path.addRoundedRect(self.rect(), 12.0, 12.0)

        color = QtGui.QColor(0, 0, 0, ALPHA)
        painter.fillPath(path, color)
        painter.end()

    def show_message(self, text: str, timeout: float = DEFAULT_TIMEOUT):
        self.setVisible(True)
        self.text.setText(text)
        if self.timer.isActive():
            self.timer.stop()
        self.timer.start(int(timeout * 1000))
