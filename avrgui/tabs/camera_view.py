from PySide6 import QtWidgets, QtCore, QtGui

from avrgui.lib.graphics_view import GraphicsView
from avrgui.tabs.base import BaseTabWidget

ENDPOINT = ""
DEFAULT_CAMERA = {
    "resolution": "0x0",
    "fov": 0,
    "model": "Unknown",
    "topic": None
}
CAMERAS = {
    "CSI Camera": {
        "resolution": "3840x2160",
        "fov": 160,
        "model": "SeeedStudio IMX219-160",
        "topic": ""
    },
    "Stereoscopic Camera Right": {
        "resolution": "4416x1242",
        "fov": 90,
        "model": "Zed Mini",
        "topic": ""
    },
    "Stereoscopic Camera Left": {
        "resolution": "4416x1242",
        "fov": 90,
        "model": "Zed Mini",
        "topic": ""
    },
    "Stereoscopic Camera Depth": {
        "resolution": "?",
        "fov": 100,
        "model": "Zed Mini",
        "topic": ""
    }
}


class CameraViewWidget(BaseTabWidget):

    def __init__(self, parent: QtWidgets.QWidget) -> None:
        super().__init__(parent)

        self.streaming_camera = None
        self.is_streaming = False
        self.streaming_button = None
        self.camera_picker = None
        self.resolution_text = None
        self.fov_text = None
        self.streaming_text = None
        self.model_text = None
        self.view = None
        self.canvas = None

        self.setWindowTitle("Camera View")

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
        # viewer_groupbox.setFixedWidth(self.view_size[0] + 50)

        self.canvas = QtWidgets.QGraphicsScene()
        self.view = GraphicsView(self.canvas)
        self.view.setGeometry(0, 0, self.view_size[0], self.view_size[1])
        # viewer_groupbox.setMaximumSize(self.view_size[0], self.view_size[1])
        # self.view.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.MinimumExpanding)
        # self.view.sizePolicy().setHeightForWidth(True)

        viewer_layout.addWidget(self.view)

        layout.addWidget(viewer_groupbox, 0, 0)

        # Options

        options_groupbox = QtWidgets.QGroupBox("Options")
        options_layout = QtWidgets.QFormLayout()
        options_groupbox.setLayout(options_layout)
        options_groupbox.setFixedWidth(250)
        options_groupbox.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Expanding)

        spacer = QtWidgets.QSpacerItem(0, 5)
        options_layout.addItem(spacer)

        self.camera_picker = QtWidgets.QComboBox()
        for camera in CAMERAS:
            self.camera_picker.addItem(camera)
        self.camera_picker.currentTextChanged.connect(self.camera_selected)
        options_layout.addRow("Camera", self.camera_picker)

        self.streaming_button = QtWidgets.QPushButton("Start Streaming")
        self.streaming_button.clicked.connect(self.streaming_button_pressed)
        options_layout.addWidget(self.streaming_button)

        layout.addWidget(options_groupbox, 0, 1)

        # Information

        info_groupbox = QtWidgets.QGroupBox("Information")
        info_layout = QtWidgets.QGridLayout()
        info_groupbox.setLayout(info_layout)
        info_groupbox.setFixedHeight(150)
        info_groupbox.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)

        self.resolution_text = QtWidgets.QLabel("Resolution: None")
        info_layout.addWidget(self.resolution_text, 0, 0)

        self.fov_text = QtWidgets.QLabel("FOV: None")
        info_layout.addWidget(self.fov_text, 1, 0)

        self.model_text = QtWidgets.QLabel("Model: None")
        info_layout.addWidget(self.model_text, 0, 1)

        self.streaming_text = QtWidgets.QLabel("Streaming: False")
        info_layout.addWidget(self.streaming_text, 1, 1)

        layout.addWidget(info_groupbox, 1, 0, 1, 0)

        self.set_camera_info(self.camera_picker.currentText())

    def camera_selected(self, name):
        print(name)
        self.set_camera_info(name)
        if self.is_streaming:
            self.set_streaming(name)

    def set_camera_info(self, name):
        camera = CAMERAS.get(name, DEFAULT_CAMERA)
        resolution = camera.get("resolution", DEFAULT_CAMERA["resolution"])
        fov = camera.get("fov", DEFAULT_CAMERA["fov"])
        model = camera.get("model", DEFAULT_CAMERA["model"])

        self.resolution_text.setText(f"Resolution: { resolution }")
        self.fov_text.setText(f"FOV: { fov }º")
        self.model_text.setText(f"Model: { model }")

    def streaming_button_pressed(self):
        if self.is_streaming:
            self.set_streaming(None)
        else:
            self.set_streaming(self.camera_picker.currentText())

    def set_streaming(self, name: str = None):
        if name is not None:
            if self.is_streaming:
                self.set_streaming(None)
            self.is_streaming = True
            self.streaming_camera = name
            self.streaming_button.setText("Stop Streaming")
            # Start Streaming
        else:
            # Stop Streaming
            self.streaming_button.setText("Start Streaming")
            self.is_streaming = False
            self.streaming_camera = None
        self.streaming_text.setText("Streaming: " + str(self.is_streaming))

    def process_message(self, topic: str, payload: str) -> None:
        pass

    def clear(self) -> None:
        pass
