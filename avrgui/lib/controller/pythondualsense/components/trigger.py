from enum import IntEnum

from .button import Button
from ..const import UpdateFlags1
from ..lib.callback import Callback


class TriggerMode(IntEnum):
    NO_RESISTANCE = 0x0
    """No resistance. It's a normal trigger."""
    CONTINUOUS = 0x1
    """The same amount of resistance all the way down."""
    SECTION = 0x2
    """A specific part of the trigger has a certain resistance."""
    SOME_RANDOM_VALUE_THAT_DOES_STUFF = 0xfc
    """I have no clue what this does, but it seems to do something the first time I click the trigger.
    The second time, it resets to no resistance"""


class Trigger(Button):
    def __init__(self, changed_flag: int) -> None:
        """
        Create a new trigger object

        :param changed_flag: This is the flag that determines when the trigger has changed.
        This is required because the flags are different for right and left triggers
        """
        super().__init__()

        self._changed_flag = changed_flag

        self.threshold: int = 200
        """
        This is the threshold when the on_pressed callback will be called (0-255)
        """

        self.on_pos = Callback[int]()
        """
        This will be called every time the trigger moves.
        It will be passed the current position of the trigger (0-255).
        """

        self._pos = 0
        self._trigger_changed = False
        self._trigger_mode = TriggerMode.NO_RESISTANCE
        self._trigger_force = 0
        self._trigger_section = (0, 0)

    @property
    def pos(self) -> int:
        """
        Get the current position of the trigger

        :return: The position of the trigger (0-255)
        """
        return self._pos

    @pos.setter
    def pos(self, value: int) -> None:
        """
        Update the position of the trigger.
        This is not meant to be used outside this library.

        :param value: The new position of the trigger (0-255)
        """
        if value != self._pos:
            self.on_pos(value)

            # Update pressed based on whether the trigger is passed the threshold
            if value > self.threshold > self._pos or value < self.threshold < self._pos:
                self.pressed = True if value > self.threshold > self._pos else False

            self._pos = value

    @property
    def trigger_mode(self) -> TriggerMode:
        """
        Get the current trigger mode (NO_RESISTANCE, CONTINUOUS, or SECTION).

        :return: The trigger mode
        """
        return self._trigger_mode

    @trigger_mode.setter
    def trigger_mode(self, mode: TriggerMode | int) -> None:
        """
        Set the trigger mode (NO_RESISTANCE, CONTINUOUS, or SECTION).

        :param mode: The new trigger mode
        """
        if mode != self._trigger_mode and isinstance(mode, (TriggerMode, int)) and 0 <= mode <= 255:
            self._trigger_changed = True
            self._trigger_mode = mode

    @property
    def trigger_force(self) -> int:
        """
        Get the current trigger force

        :return: The trigger force (0-255)
        """
        return self._trigger_force

    @trigger_force.setter
    def trigger_force(self, force: int) -> None:
        """
        Set the trigger force

        :param force: Trigger force (0-255)
        """
        if force != self._trigger_force and 0 <= force <= 255:
            self._trigger_changed = True
            self._trigger_force = force

    @property
    def trigger_section(self) -> tuple[int, int]:
        """
        Get the current section of the trigger that has resistance

        :return: A tuple containing the start and the end position of the section
        """
        return self._trigger_section

    @trigger_section.setter
    def trigger_section(self, section: tuple[int, int]) -> None:
        """
        Set the current section of the trigger that has resistance.
        This only does anything, when the trigger_mode is set to SECTION

        :param section: A tuple containing the start (0-255) and end (0-255) of the resistance section
        """
        section = tuple(section)
        if section != self._trigger_section and len(section) == 2 and 0 <= section[0] <= 255 and 0 <= section[1] <= 255:
            self._trigger_changed = True
            self._trigger_section = section

    def force_update(self) -> None:
        """
        Send the next report as if the trigger state was changed
        """
        self._trigger_changed = True

    def get_report(self) -> tuple[int, list[int]]:
        """
        Get the next output report from the trigger.
        Do not call this unless you plan on sending it manually.
        This will set _trigger_changed to False and not change the trigger.

        :return: A tuple containing a flag to tell what was changed and the report. self._trigger_mode != TriggerMode.NO_RESISTANCE
        """
        flag = self._changed_flag if self._trigger_changed else UpdateFlags1.NONE

        report = [0] * 4
        report[0] = self._trigger_mode
        if self._trigger_mode == TriggerMode.CONTINUOUS:
            report[1] = 0
            report[2] = self._trigger_force
            report[3] = 0
        elif self._trigger_mode == TriggerMode.SECTION:
            report[1] = self._trigger_section[0]
            report[2] = self._trigger_section[1]
            report[3] = self._trigger_force

        self._trigger_changed = False
        return flag, report
