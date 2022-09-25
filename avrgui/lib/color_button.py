from PySide6 import QtGui, QtWidgets
from PySide6.QtCore import Qt, Signal


class ColorButton(QtWidgets.QPushButton):
    '''
    Custom Qt Widget to show a chosen color.

    Left-clicking the button shows the color-chooser, while
    right-clicking resets the color to None (no-color).
    '''

    color_changed = Signal(object)

    def __init__(self, *args, color: QtGui.QColor = QtGui.QColor("white"), **kwargs):
        super(ColorButton, self).__init__(*args, **kwargs)

        self._color: QtGui.QColor = color
        self._default: QtGui.QColor = color
        self.pressed.connect(self.on_color_picker)

        # Set the initial/default state.
        self.set_color(self._default)

    def set_color(self, color):
        if color != self._color:
            self._color = color
            # noinspection PyUnresolvedReferences
            self.color_changed.emit(color)
            # pixelmap = QtGui.QPixmap(self.size().width(), self.size().height() - 10)
            # pixelmap.fill(color)
            # self.setIcon(QtGui.QIcon(pixelmap))
        if self._color:
            self.setStyleSheet("background-color: %s;" % self._color.name())
        else:
            self.setStyleSheet("")

    def color(self):
        return self._color

    def on_color_picker(self):
        '''
        Show color-picker dialog to select color.

        Qt will use the native dialog by default.

        '''
        dlg = QtWidgets.QColorDialog(self)
        if self._color:
            dlg.setCurrentColor(QtGui.QColor(self._color))

        if dlg.exec_():
            self.set_color(dlg.currentColor())

    def mousePressEvent(self, e):
        if e.button() == Qt.RightButton:
            self.set_color(self._default)

        return super(ColorButton, self).mousePressEvent(e)