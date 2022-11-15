from ..const import UpdateFlags1


class RumbleMotor:
    def __init__(self) -> None:
        self._rumble_changed = False
        self._rumble_value = 0

    @property
    def value(self) -> int:
        """
        Get the current value of the rumble motor

        :return: The value of the rumble motor (0-255)
        """
        return self._rumble_value

    @value.setter
    def value(self, rumble_value: int) -> None:
        """
        Set the current value of the rumble motor

        :param rumble_value: The new value of the rumble motor (0-255)
        """
        if rumble_value is not self._rumble_value and 0 <= rumble_value <= 255:
            self._rumble_changed = True
            self._rumble_value = rumble_value

    def force_update(self) -> None:
        """
        Send the next report as if the rumble motor state was changed
        """
        self._rumble_changed = True

    def get_report(self) -> tuple[int, int]:
        """
        Get the next output report from the mic_button.

        :return: A tuple containing a flag to tell what was changed, the report.
        """
        flag = UpdateFlags1.RUMBLE if self._rumble_value > 0 else UpdateFlags1.NONE

        self._rumble_changed = False
        return flag, self._rumble_value
