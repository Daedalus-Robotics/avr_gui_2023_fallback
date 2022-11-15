from .thumbstick import Thumbstick
from ..const import LedFlags, TouchpadLedModes, UpdateFlags2


class Touchpad(Thumbstick):
    def __init__(self) -> None:
        super().__init__()

        self._led_r = 0
        self._led_g = 0
        self._led_b = 0
        self._led_changed = False

        self._fade_to_blue = False

    @property
    def x(self) -> int:
        """
        Get the current value for the x-axis of the touchpad

        :return: The current value for the x-axis
        """
        return super().x

    @property
    def y(self) -> int:
        """
        Get the current value for the y-axis of the touchpad

        :return: The current value for the y-axis
        """
        return super().y

    @property
    def pos(self) -> tuple[int, int]:
        """
        Get the current position of the touchpad

        :return: The current position
        """
        return super().pos

    @pos.setter
    def pos(self, position: tuple[int, int]) -> None:
        """
        Update the current position of the touchpad.
        This is not meant to be used by anything outside this library!

        :param position: The position
        """
        super().pos = position

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
