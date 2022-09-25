from PySide6 import QtCore, QtWidgets


class ComboBox(QtWidgets.QComboBox):
    clicked = QtCore.Signal()
    unclicked = QtCore.Signal()

    def showPopup(self) -> None:
        self.clicked.emit()
        super(ComboBox, self).showPopup()

    def hidePopup(self) -> None:
        self.unclicked.emit()
        super(ComboBox, self).hidePopup()
