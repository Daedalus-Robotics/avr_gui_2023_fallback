import time

from PySide6 import QtCore, QtWidgets

from avrgui.lib.graphics_view import GraphicsView
from avrgui.tabs.base import BaseTabWidget
import socketio


def map_value(
        x: float, in_min: float, in_max: float, out_min: float, out_max: float
) -> float:
    return (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min


class WaterDropWidget(BaseTabWidget):
    update_position = QtCore.Signal(int)

    def __init__(self, parent: QtWidgets.QWidget) -> None:
        super().__init__(parent)

        self.last_time = 0
        # self.position_slider: QtWidgets.QSlider | None = None
        self.trigger_button: QtWidgets.QPushButton | None = None
        self.controller_enabled_checkbox = None
        self.controller_enabled = False
        self.canvas = None
        self.view = None

        self.selected_tag = 0

        self.is_streaming = False

        self.setWindowTitle("Water Drop")

        self.view_size = (640, 360)
        self.view_pixels_size = (1280, 720)
        self.view_pixels_total = self.view_pixels_size[0] * self.view_pixels_size[1]
        self.last_closed = True

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

        # self.position_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        # # self.position_slider.setTickPosition(QtWidgets.QSlider.TickPosition.TicksBothSides)
        # self.position_slider.setRange(0, 100)
        # self.position_slider.setFixedWidth(250)
        # self.position_slider.sliderMoved.connect(
        #         self.set_bpu_slider
        # )
        # controls_layout.addWidget(self.position_slider)

        self.trigger_button = QtWidgets.QPushButton("Trigger")
        self.trigger_button.clicked.connect(self.trigger_bpu)
        controls_layout.addWidget(self.trigger_button)

        self.controller_enabled_checkbox = QtWidgets.QCheckBox("Enable Controller")
        self.controller_enabled_checkbox.stateChanged.connect(
                self.set_controller
        )
        controls_layout.addWidget(self.controller_enabled_checkbox)

        layout.addWidget(controls_groupbox, 0, 1, 0, 1)  # These cords don't make any sense to me, but they work

        # Loading

        loading_groupbox = QtWidgets.QGroupBox("Loading")
        loading_layout = QtWidgets.QGridLayout()
        loading_groupbox.setLayout(loading_layout)
        loading_groupbox.setFixedHeight(150)
        loading_groupbox.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)

        layout.addWidget(loading_groupbox, 1, 0)

    def set_controller(self, state: bool) -> None:
        self.controller_enabled = state
        # self.position_slider.setEnabled(not state)

    def process_message(self, topic: str, payload: str) -> None:
        pass

    def clear(self) -> None:
        pass

    def trigger_bpu(self) -> None:
        self.client.emit("/bdu/trigger", {})
