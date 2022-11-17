from PySide6.QtCore import Qt
from PySide6 import QtCore, QtGui, QtWidgets

WIDTH = 2000
HEIGHT = 1800
POS_OFFSET = ()
BOTTOM_OFFSET = 50
ALPHA = 255
DEFAULT_TIMEOUT = 2.0


class WaterDropPopup(QtWidgets.QWidget):
    _instance = None
    send_popup = QtCore.Signal(int)

    @classmethod
    def get(cls, parent: QtWidgets.QWidget = None) -> "WaterDropPopup":
        if cls._instance is None:
            cls._instance = WaterDropPopup(parent)
        return cls._instance

    def __init__(self, parent: QtWidgets.QWidget):
        super().__init__(parent)

        self.fallback_image = QtGui.QPixmap("assets/apriltags.png")
        self.images = {
            0: QtGui.QPixmap("assets/apriltags_0.png"),
            1: QtGui.QPixmap("assets/apriltags_1.png"),
            2: QtGui.QPixmap("assets/apriltags_2.png"),
            3: QtGui.QPixmap("assets/apriltags_3.png"),
            4: QtGui.QPixmap("assets/apriltags_4.png"),
            5: QtGui.QPixmap("assets/apriltags_5.png")
        }

        layout = QtWidgets.QVBoxLayout()
        self.image = QtWidgets.QLabel()
        self.image.setAlignment(Qt.AlignCenter)
        self.image.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)
        # self.image.setFixedSize(self.fallback_image.size())
        layout.addWidget(self.image)
        self.setLayout(layout)
        self.setFixedSize(self.fallback_image.size())

        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(lambda: self.setVisible(False))

        self.send_popup.connect(self.show_popup)

        self.setVisible(False)

    # def window_resize_event(self, event: QtGui.QResizeEvent) -> None:
    #     self.refresh_size(event.size())
    #
    # def refresh_size(self, size):
    #     w = self.fallback_image.size().width()
    #     h = self.fallback_image.size().height()
    #
    #     window_height = size.height()
    #     window_width = size.width()
    #
    #     x = (window_width // 2) - (w // 2) - POS_OFFSET[0]
    #     y = window_height - (h // 2) - POS_OFFSET[1]
    #
    #     self.setGeometry(x, y, w, h)
    #     self.setFixedSize(w + 5, h + 5)

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

    def show_popup(self, number: int):
        image = self.images.get(number, self.fallback_image)
        self.image.setPixmap(image)
        self.setVisible(True)
        self.timer.start(2000)
