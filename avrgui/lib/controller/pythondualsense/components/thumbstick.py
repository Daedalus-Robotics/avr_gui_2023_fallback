from .button import Button
from ..lib.callback import Callback


class Thumbstick(Button):
    def __init__(self) -> None:
        super().__init__()

        self.on_move = Callback[tuple[int, int]]()
        """
        This is called every time the x or y axis value changes.
        A tuple containing the current x and y values will be passed to the callback.
        """

        self._x = 0
        self._y = 0

    @property
    def x(self) -> int:
        """
        Get the current value for the x-axis of the thumbstick

        :return: The current value for the x-axis
        """
        return self._x

    @property
    def y(self) -> int:
        """
        Get the current value for the y-axis of the thumbstick

        :return: The current value for the y-axis
        """
        return self._y

    @property
    def pos(self) -> tuple[int, int]:
        """
        Get the current position of the thumbstick

        :return: The current position
        """
        return self._x, self._y

    @pos.setter
    def pos(self, position: tuple[int, int]) -> None:
        """
        Update the current position of the thumbstick.
        This is not meant to be used by anything outside this library!

        :param position:
        :return:
        """
        if position[0] != self._x or position[1] != self._y:
            self._x, self._y = position
            self.on_move((self._x, self._y))
