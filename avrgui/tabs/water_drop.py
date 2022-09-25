from PySide6 import QtWidgets

from avrgui.lib.graphics_view import GraphicsView
from avrgui.tabs.base import BaseTabWidget


class WaterDropWidget(BaseTabWidget):
    def __init__(self, parent: QtWidgets.QWidget) -> None:
        super().__init__(parent)

        self.canvas = None
        self.view = None

        self.setWindowTitle("Water Drop")

        self.view_size = (640, 360)
        self.view_pixels_size = (1280, 720)
        self.view_pixels_total = self.view_pixels_size[0] * self.view_pixels_size[1]

    def build(self) -> None:
        layout = QtWidgets.QGridLayout()
        self.setLayout(layout)

        # Viewer

        viewer_groupbox = QtWidgets.QGroupBox("Viewer")
        viewer_layout = QtWidgets.QVBoxLayout()
        viewer_groupbox.setLayout(viewer_layout)

        self.canvas = QtWidgets.QGraphicsScene()
        self.view = GraphicsView(self.canvas)
        self.view.setGeometry(0, 0, self.view_size[0], self.view_size[1])

        viewer_layout.addWidget(self.view)

        layout.addWidget(viewer_groupbox, 0, 0)

        # Controls

        controls_groupbox = QtWidgets.QGroupBox("Controls")
        controls_layout = QtWidgets.QFormLayout()
        controls_groupbox.setLayout(controls_layout)
        controls_groupbox.setFixedWidth(350)
        controls_groupbox.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Expanding)

        layout.addWidget(controls_groupbox, 0, 1, 0, 1)  # These cords don't make any sense to me, but they work

        # Loading

        loading_groupbox = QtWidgets.QGroupBox("Loading")
        loading_layout = QtWidgets.QGridLayout()
        loading_groupbox.setLayout(loading_layout)
        loading_groupbox.setFixedHeight(150)
        loading_groupbox.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)

        layout.addWidget(loading_groupbox, 1, 0)

    def process_message(self, topic: str, payload: str) -> None:
        pass

    def clear(self) -> None:
        pass
