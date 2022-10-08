from PySide6 import QtWidgets


class GraphicsLabel(QtWidgets.QLabel):
    def __init__(self, aspect_ratio = (16, 9), parent = None):
        super().__init__(parent)
        self.aspect_ratio = aspect_ratio
        self.setMinimumSize(1, 1)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, w):
        h = int(w * (self.aspect_ratio[1] / self.aspect_ratio[0]))
        #self.setFixedHeight(h)
        return h
