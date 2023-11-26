import asyncio

from .button import Button
from ..lib.callback import Callback


class Thumbstick(Button):
    def __init__(self, event_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()) -> None:
        super().__init__(event_loop)

        self.on_move = Callback[tuple[int, int]](event_loop)
        """
        This is called every time the x or y axis value changes.
        A tuple containing the current x and y values will be passed to the callback.
        """

        self._pos = (0, 0)

    @property
    def x(self) -> int:
        """
        Get the current value for the x-axis of the thumbstick

        :return: The current value for the x-axis (-127 - 128)
        """
        return self._pos[0]

    @property
    def y(self) -> int:
        """
        Get the current value for the y-axis of the thumbstick

        :return: The current value for the y-axis (-127 - 128)
        """
        return self._pos[1]

    @property
    def pos(self) -> tuple[int, int]:
        """
        Get the current position of the thumbstick

        :return: The current position as a tuple of (x, y)
        """
        return self._pos

    def update(self, pressed: bool, pos: tuple[int, int] | list[int] = None) -> None:
        """
        Update the current position of the thumbstick.
        This is an internal method!

        :param pressed: Whether the stick is pressed
        :param pos: The position of the stick tuple[x (-127 - 128), y (-127 - 128)]
        """
        super().update(pressed)
        if pos is not None and pos != self._pos:
            self._pos = pos
            self.on_move(pos)
