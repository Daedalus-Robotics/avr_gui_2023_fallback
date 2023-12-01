from PySide6.QtCore import Qt
from PySide6 import QtCore, QtGui, QtWidgets
from qmaterialwidgets import InfoBarPosition, InfoBarIcon, InfoBar

HEIGHT = 40
BOTTOM_OFFSET = 50
ALPHA = 180
DEFAULT_TIMEOUT = 2.0


class Toast(QtCore.QObject):
    _instance = None
    send_message = QtCore.Signal(str, str, object, float)

    @classmethod
    def get(cls, parent: QtWidgets.QWidget = None) -> "Toast":
        if cls._instance is None:
            cls._instance = Toast(parent)
        return cls._instance

    def __init__(self, parent: QtWidgets.QWidget):
        super().__init__(parent)
        self.send_message.connect(self.show_message)

        self.parent = parent

    def show_message(self,
                     title: str, text: str,
                     icon: InfoBarIcon = InfoBarIcon.INFORMATION,
                     timeout: float = DEFAULT_TIMEOUT):
        InfoBar(
            icon,
            title,
            text,
            isClosable=False,
            duration=int(timeout * 1000),
            position=InfoBarPosition.BOTTOM_LEFT,
            parent=self.parent
        ).show()
