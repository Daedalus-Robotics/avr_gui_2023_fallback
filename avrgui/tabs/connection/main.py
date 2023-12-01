from PySide6 import QtWidgets
from qmaterialwidgets import ElevatedPushButton, TonalPushButton, OutlinedCardWidget

from ..base import BaseTabWidget
from .rosbridge import RosConnectionWidget


class MainConnectionWidget(BaseTabWidget):
    """
    This manages connections to all the external services
    """

    def __init__(self, parent: QtWidgets.QWidget) -> None:
        super().__init__(parent, None, 'main_connection')

        self.ros_client_connection_widget: RosConnectionWidget | None = None
        self.controller_connect_button = None
        self.setWindowTitle("Connections")

    def build(self) -> None:
        """
        Build the GUI layout
        """
        layout = QtWidgets.QVBoxLayout(self)
        self.setLayout(layout)

        rosbridge_groupbox = QtWidgets.QGroupBox("Rosbridge")
        rosbridge_layout = QtWidgets.QVBoxLayout(rosbridge_groupbox)

        self.ros_client_connection_widget = RosConnectionWidget(self)
        self.ros_client_connection_widget.build()
        rosbridge_layout.addWidget(self.ros_client_connection_widget)

        rosbridge_groupbox.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed
        )
        layout.addWidget(rosbridge_groupbox)

        self.controller_connect_button = TonalPushButton("Connect DualSense Controller", self)
        layout.addWidget(self.controller_connect_button)
