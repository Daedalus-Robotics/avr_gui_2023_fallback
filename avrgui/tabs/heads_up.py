from PySide6 import QtWidgets

from avrgui.tabs.base import BaseTabWidget


class HeadsUpDisplayWidget(BaseTabWidget):
    def __init__(self, parent: QtWidgets.QWidget) -> None:
        super().__init__(parent)

        self.setWindowTitle("HUD")

    def build(self) -> None:
        layout = QtWidgets.QGridLayout()
        self.setLayout(layout)

    def process_message(self, topic: str, payload: str) -> None:
        pass

    def clear(self) -> None:
        pass
