from enum import IntFlag, auto

from .button import Button
from ..lib.callback import Callback


class DpadDirection(IntFlag):
    NONE = auto()
    UP = auto()
    DOWN = auto()
    LEFT = auto()
    RIGHT = auto()

    @property
    def up(self) -> bool:
        """
        Get the state of the up button on the dpad

        :return: State of the up button
        """
        return self.UP in self

    @property
    def down(self) -> bool:
        """
        Get the state of the down button on the dpad

        :return: State of the down button
        """
        return self.DOWN in self

    @property
    def left(self) -> bool:
        """
        Get the state of the left button on the dpad

        :return: State of the left button
        """
        return self.LEFT in self

    @property
    def right(self) -> bool:
        """
        Get the state of the right button on the dpad

        :return: State of the right button
        """
        return self.RIGHT in self

    @classmethod
    def build_from_value(cls, value: int) -> 'DpadDirection':
        """
        Get the DpadDirection for a given value from the controller

        Values:
            0 – Top\n
            1 – Top and Right\n
            2 – Right\n
            3 – Down and Right\n
            4 – Down\n
            5 – Down and Left\n
            6 – Left\n
            7 – Top and Left\n
            8 – None

        :param value: The dpad value returned from the controller
        :return: The DpadDirection for the current dpad state
        """
        up = True if value in (7, 0, 1) else False
        down = True if value in (3, 4, 5) else False
        left = True if value in (5, 6, 7) else False
        right = True if value in (1, 2, 3) else False

        direction = cls.NONE

        if up:
            direction |= cls.UP
        if down:
            direction |= cls.DOWN
        if left:
            direction |= cls.LEFT
        if right:
            direction |= cls.RIGHT

        return direction


class Dpad:
    def __init__(self) -> None:
        self.on_direction = Callback[DpadDirection]()
        """
        This is called every time any button on the dpad changes. This will be passed a DpadDirection. 
        """

        self.up = Button()
        self.down = Button()
        self.left = Button()
        self.right = Button()

        self._dpad_raw = 0
        self._dpad_direction = DpadDirection.NONE

    @property
    def raw(self) -> int:
        """
        Get the raw dpad value from the controller

        :return: The raw dpad value
        """
        return self._dpad_raw

    @raw.setter
    def raw(self, value: int) -> None:
        """
        Update the current raw dpad value.
        This is not meant to be used outside this library.

        :param value: The new raw dpad value
        """
        if value is not self._dpad_raw:
            self._dpad_raw = value
            self._dpad_direction = DpadDirection.build_from_value(value)

            self.on_direction(self._dpad_direction)

            self.up.pressed = self._dpad_direction.up
            self.down.pressed = self._dpad_direction.down
            self.left.pressed = self._dpad_direction.left
            self.right.pressed = self._dpad_direction.right

    @property
    def direction(self) -> DpadDirection:
        """
        Get the current dpad direction

        :return: The dpad direction
        """
        return self._dpad_direction
