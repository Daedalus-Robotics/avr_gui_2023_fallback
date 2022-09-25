from PySide6 import QtWidgets


class GraphicsView(QtWidgets.QGraphicsView):
    def __init__(self, parent = None):
        super().__init__(parent)
        self.aspect_ratio = (16, 9)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, w):
        h = int(w * (self.aspect_ratio[1] / self.aspect_ratio[0]))
        self.setFixedHeight(h)
        return h
