import asyncio
from collections.abc import Iterator

from .button import Button
from ..const import LedFlags, TouchpadLedModes, UpdateFlags2
from ..lib.callback import Callback


class TouchPoint:
    def __init__(self, event_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()) -> None:
        self.on_touch = Callback[tuple[int, bool]](event_loop)
        """
        This is called every time the finger touches or releases the touchpad.
        A tuple containing a the id of the finger and bool for whether the finger has touched the touchpad will be
        passed to the callback.
        """

        self.on_move = Callback[tuple[int, int]](event_loop)
        """
        This is called every time the finger moves with a tuple containing the x and y position of the finger passed
        to the callback.
        """

        self._id = -1
        self._selected = False
        self._pos = (-1, -1)

    def __bool__(self) -> bool:
        return self._selected

    def __iter__(self) -> Iterator[int]:
        if self._selected:
            pos = self._pos
            for axis in pos:
                yield axis
        else:
            yield -1
            yield -1

    def __repr__(self) -> str:
        return f"TouchPoint: {tuple(self)}"

    @property
    def id(self) -> int:
        """
        Get the id of the current finger

        :return: The ID of the finger
        """
        return self._id

    @property
    def is_selected(self) -> bool:
        """
        Get whether the finger is touching the touchpad

        :return: Whether the finger is touching
        """
        return self._selected

    @property
    def x(self) -> int:
        """
        Get the x-axis value of the touch point

        :return: The x-axis value
        """
        return self._pos[0]

    @property
    def y(self) -> int:
        """
        Get the y-axis value of the touch point

        :return: The y-axis value
        """
        return self._pos[1]

    @property
    def pos(self) -> tuple[int, int]:
        """
        Get the position of the touch point

        :return: The position
        """
        return self._pos

    def update(self, touch_point_report: tuple[int, bool, int, int]) -> None:
        """
        Update the state of the touch point using the touch point report.
        This is an internal method!

        :param touch_point_report: The touch point report
        """
        self._id = touch_point_report[0]

        selected = touch_point_report[1]
        if selected != self._selected:
            self._selected = selected
            self.on_touch(touch_point_report[0:2])

        pos = touch_point_report[2:4]
        if pos != self._pos:
            self._pos = pos
            self.on_move(pos)


class Touchpad(Button):
    def __init__(self, event_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()) -> None:
        super().__init__(event_loop)

        self.touch_point_1 = TouchPoint(event_loop)
        self.touch_point_2 = TouchPoint(event_loop)

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

    def led_off(self) -> None:
        self._led_changed = True
        self._led_r, self._led_g, self._led_b = 0, 0, 0

    def fade_to_blue(self) -> None:
        """
        Fade the touchpad led strips to blue. This also seems to freeze the leds on blue.
        I have no idea why this exists.
        """
        self._fade_to_blue = True

    def update(self,
               state: bool,
               touch_point_1_report: tuple[int, bool, int, int] = None,
               touch_point_2_report: tuple[int, bool, int, int] = None
               ) -> None:
        """
        Update the state of the touchpad using the state from the controller and the two touch point reports.
        This is an internal method!

        :param state: The state of the touchpad click.
        :param touch_point_1_report: The touch point report for touch point 1
        :param touch_point_2_report: The touch point report for touch point 2
        """
        super().update(state)
        if touch_point_1_report is not None:
            self.touch_point_1.update(touch_point_1_report)
        if touch_point_2_report is not None:
            self.touch_point_2.update(touch_point_2_report)

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
