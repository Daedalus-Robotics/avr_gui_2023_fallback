from enum import IntEnum

from ..const import BrightnessLevel, LedFlags, UpdateFlags2


class PlayerLedArrangement(IntEnum):
    l_____l = 0x0
    l__0__l = 0x4
    l_0_0_l = 0x2
    l0___0l = 0x1
    l_000_l = 0x6
    l0_0_0l = 0x5
    l00_00l = 0x3
    l00000l = 0x7


PLAYER_NUMBERS = [
    PlayerLedArrangement.l_____l,
    PlayerLedArrangement.l__0__l,
    PlayerLedArrangement.l_0_0_l,
    PlayerLedArrangement.l0_0_0l,
    PlayerLedArrangement.l00_00l,
    PlayerLedArrangement.l00000l
]


class PlayerLed:
    def __init__(self) -> None:
        self._raw_value = 0x0
        self._player_num = 0
        self._player_changed = False
        self._led_brightness_changed = False
        self._led_brightness = BrightnessLevel.HIGH

    @property
    def raw(self) -> int:
        """
        Get the raw value being sent to the controller

        :return: The raw value
        """
        return self._raw_value

    @raw.setter
    def raw(self, value: int) -> None:
        """
        Set the raw value being sent to the controller
        :param value: The raw value
        """
        if value is not self._raw_value:
            if 0x00 <= value <= 0xff:
                self._player_changed = True
                self._player_num = self.raw_to_player(value)
                self._raw_value = value

    @property
    def player_num(self) -> int:
        """
        Get the current player number

        :return: The player number
        """
        return self._player_num

    @player_num.setter
    def player_num(self, player: int) -> None:
        """
        Set the player number below the touchpad

        :param player: The player number
        """
        if player is not self._player_num:
            raw = self.player_to_raw(player)
            if raw is not None and 0x00 <= raw <= 0xff:
                self._player_changed = True
                self._player_num = player
                self._raw_value = raw

    @property
    def brightness(self) -> BrightnessLevel:
        """
        Get the current brightness of the mic and player LEDs

        :return: The brightness
        """
        return self._led_brightness

    @brightness.setter
    def brightness(self, level: BrightnessLevel) -> None:
        """
        Set the brightness level of the mic and player LEDs

        :param level: The new brightness level
        """
        if level is not self._led_brightness:
            self._led_brightness_changed = True
            self._led_brightness = level

    def update_brightness(self, level: BrightnessLevel) -> None:
        """
        Sets the brightness without setting the changed flag.
        This is not meant to be use outside this library.

        :param level: The new brightness level
        """
        self._led_brightness = level

    def force_update(self) -> None:
        """
        Send the next report as if the player leds were changed
        """
        self._player_changed = True

    def get_report(self) -> tuple[int, int, int, int]:
        """
        Get the next output report from the player_led.
        Do not call this unless you plan on sending it manually.
        This will set _player_changed to False and not change the player LEDs.

        :return: A tuple containing a flag to tell what was changed, the report, and two flags for the brightness.
        """
        flag = UpdateFlags2.PLAYER_LEDS if self._player_changed else UpdateFlags2.NONE
        led_flag = LedFlags.PLAYER_MIC if self._led_brightness_changed else LedFlags.NONE
        brightness_flag = self._led_brightness if self._led_brightness_changed else BrightnessLevel.HIGH

        self._player_changed = False
        self._led_brightness_changed = False
        return flag, self._raw_value, led_flag, brightness_flag

    @staticmethod
    def raw_to_player(raw: int | PlayerLedArrangement) -> int | None:
        """
        Convert a raw player led value to a player number. Returns None if the raw value has no player number.

        :param raw: Raw player led value
        :return: Player number or None
        """
        if raw in PLAYER_NUMBERS:
            return PLAYER_NUMBERS.index(raw)
        else:
            return None

    @staticmethod
    def player_to_raw(player: int) -> int | None:
        """
        Convert a raw player led value to a player number. Returns None if the player number is invalid.

        :param player: Player number
        :return: Raw player led value or None
        """
        if 0 <= player < len(PLAYER_NUMBERS):
            return PLAYER_NUMBERS[player]
        else:
            return None
