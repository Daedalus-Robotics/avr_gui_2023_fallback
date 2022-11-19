from .button import Button
from ..const import LedFlags, TouchpadLedModes, UpdateFlags2
from ..lib.callback import Callback


class TouchPoint:
    def __init__(self) -> None:
        self.on_touch = Callback[tuple[bool, int]]()
        """
        This is called every time the finger touches or releases the touchpad.
        A tuple containing a bool for whether the finger has touched the touchpad and the id of the finger will be
        passed to the callback.
        """

        self.on_move = Callback[tuple[int, int]]()
        """
        This is called every time the finger moves with a tuple containing the x and y position of the finger passed
        to the callback.
        """

        self._id = -1
        self._selected = False
        self._x = 0
        self._y = 0

    @property
    def id(self) -> int:
        """
        Get the id of the current finger

        :return: The ID of the finger
        """
        return self._id

    @id.setter
    def id(self, new_id: int) -> None:
        """
        Set the id of the current finger

        :return: The new ID of the finger
        """
        self._id = new_id

    @property
    def is_selected(self) -> bool:
        """
        Get whether the finger is touching the touchpad

        :return: Whether the finger is touching
        """
        return self._selected

    @is_selected.setter
    def is_selected(self, selected: bool) -> None:
        """
        Set whether the finger is touching the touchpad.
        This is not meant to be used outside this library!

        :param selected: Whether the finger is touching
        """
        if selected != self._selected:
            self._selected = selected
            self.on_touch((self._selected, self._id))

    @property
    def x(self) -> int:
        """
        Get the x-axis value of the touch point

        :return: The x-axis value
        """
        return self._x

    @property
    def y(self) -> int:
        """
        Get the y-axis value of the touch point

        :return: The y-axis value
        """
        return self._y

    @property
    def pos(self) -> tuple[int, int]:
        """
        Get the position of the touch point

        :return: The position
        """
        return self._x, self._y

    @pos.setter
    def pos(self, position: tuple[int, int]) -> None:
        """
        Set the current position of the touch point.
        This is not meant to be used outside this library!

        :param position: The new position
        """
        x, y = position
        if x != self._x or y != self._y:
            self._x, self._y = x, y
            self.on_move((self._x, self._y))


class Touchpad(Button):
    def __init__(self) -> None:
        super().__init__()

        self.touch_point_1 = TouchPoint()
        self.touch_point_2 = TouchPoint()

        self._led_r = 0
        self._led_g = 0
        self._led_b = 0
        self._led_changed = False

        self._fade_to_blue = False

    @property
    def led_color(self) -> tuple[int, int, int]:
        """
        Get the color of the leds on the sides of the touchpad

        :return: The current color of the leds
        """
        return self._led_r, self._led_g, self._led_b

    @led_color.setter
    def led_color(self, color: tuple[int, int, int]) -> None:
        """
        Set the color of the touchpad leds

        :param color: The color to set the leds
        """
        if len(color) == 3:
            if color is not (self._led_r, self._led_g, self._led_b):
                if 0 <= color[0] <= 255 and 0 <= color[1] <= 255 and 0 <= color[2] <= 255:
                    self._led_changed = True
                    self._led_r, self._led_g, self._led_b = color

    def force_update(self) -> None:
        """
        Send the next report as if the touchpad leds were changed
        """
        self._led_changed = True

    def get_report(self) -> tuple[int, tuple[int, int, int], int, int]:
        """
        Get the next output report from the touchpad LEDs.
        Do not call this unless you plan on sending it manually.
        This will set _led_changed to False and not change the touchpad LEDs.

        :return: A tuple containing a flag to tell what was changed, the report, and two flags for fading to blue.
        """
        flag = UpdateFlags2.TOUCHPAD_LED if self._led_changed else UpdateFlags2.NONE
        led_flag = LedFlags.TOUCHPAD if self._fade_to_blue else LedFlags.NONE
        led_mode = TouchpadLedModes.FADE_BLUE if self._fade_to_blue else TouchpadLedModes.NONE

        self._led_changed = False
        self._fade_to_blue = False
        return flag, self.led_color, led_flag, led_mode

    def fade_to_blue(self) -> None:
        """
        Fade the touchpad led strips to blue. This also seems to freeze the leds on blue.
        I have no idea why this exists.
        """
        self._fade_to_blue = True
