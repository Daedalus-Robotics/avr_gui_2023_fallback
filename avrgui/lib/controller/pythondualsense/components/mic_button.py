from .button import Button
from ..const import LedFlags, UpdateFlags2, BrightnessLevel


class MicButton(Button):
    def __init__(self) -> None:
        super().__init__()

        self._led_state = False
        self._led_pulsating = False
        self._led_changed = False
        self._led_brightness_changed = False
        self._led_brightness = BrightnessLevel.HIGH

    @property
    def led_state(self) -> bool:
        """
        Returns the current state of the mic LED

        :return: Current state of the mic LED
        """
        return self._led_state

    @led_state.setter
    def led_state(self, state: bool) -> None:
        """
        Sets the state of the mic LED

        :param state: State of the mic LED
        """
        if state is not self._led_state:
            self._led_changed = True
            self._led_state = state

    @property
    def led_pulsating(self) -> bool:
        """
        Get whether the LED is currently pulsing

        :return: Whether the LED is pulsing
        """
        return self._led_pulsating

    @led_pulsating.setter
    def led_pulsating(self, pulsating: bool) -> None:
        """
        Set whether the LED is pulsing

        :param pulsating: Whether the LED is pulsing
        """
        if pulsating is not self._led_pulsating:
            self._led_changed = True
            self._led_pulsating = pulsating

    @property
    def led_brightness(self) -> BrightnessLevel:
        """
        Get the current brightness of the mic and player LEDs

        :return: The brightness
        """
        return self._led_brightness

    @led_brightness.setter
    def led_brightness(self, level: BrightnessLevel) -> None:
        """
        Set the brightness level of the mic and player LEDs

        :param level: The new brightness level
        """
        if level is not self._led_brightness:
            self._led_brightness_changed = True
            self._led_brightness = level

    def update_led_brightness(self, level: BrightnessLevel) -> None:
        """
        Sets the brightness without setting the changed flag.
        This is not meant to be use outside this library.

        :param level: The new brightness level
        """
        self._led_brightness = level

    def force_update(self) -> None:
        """
        Send the next report as if the mic led state was changed
        """
        self._led_changed = True

    def get_report(self) -> tuple[int, int, int, int]:
        """
        Get the next output report from the mic_button.
        Do not call this unless you plan on sending it manually.
        This will set _led_changed to False and not change the mic LED.

        :return: A tuple containing a flag to tell what was changed, the report, and two flags for the brightness.
        """
        flag = UpdateFlags2.MICROPHONE_LED if self._led_changed else UpdateFlags2.NONE
        state = int(self._led_pulsating) + 1 if self._led_state else 0
        led_flag = LedFlags.PLAYER_MIC if self._led_brightness_changed else LedFlags.NONE
        brightness_flag = self._led_brightness if self._led_brightness_changed else BrightnessLevel.HIGH

        self._led_changed = False
        self._led_brightness_changed = False
        return flag, state, led_flag, brightness_flag
