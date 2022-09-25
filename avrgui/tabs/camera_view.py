from PySide6 import QtWidgets, QtCore, QtGui

from avrgui.tabs.base import BaseTabWidget


class CameraViewWidget(BaseTabWidget):

    def __init__(self, parent: QtWidgets.QWidget) -> None:
        super().__init__(parent)

        self.setWindowTitle("Camera View")

        self.view_size = (480, 270)
        self.view_pixels_size = (1280, 720)
        self.view_pixels_total = self.view_pixels_size[0] * self.view_pixels_size[1]

        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)

        self.canvas = QtWidgets.QGraphicsScene()
        self.view = QtWidgets.QGraphicsView(self.canvas)
        self.view.setGeometry(0, 0, self.view_size[0], self.view_size[1])
        layout.addWidget(self.view)

        self.setFixedSize(QtCore.QSize(self.view_size[0] + 50, self.view_size[1] + 50))

    def build(self) -> None:
        layout = QtWidgets.QGridLayout()
        self.setLayout(layout)

        viewer_groupbox = QtWidgets.QGroupBox("Viewer")
        viewer_layout = QtWidgets.QVBoxLayout()
        viewer_groupbox.setLayout(viewer_layout)

        hello = QtWidgets.QLabel("hello world")
        viewer_layout.addWidget(hello)

        layout.addWidget(viewer_groupbox)

    def process_message(self, topic: str, payload: str) -> None:
        pass

    def clear(self) -> None:
        pass
