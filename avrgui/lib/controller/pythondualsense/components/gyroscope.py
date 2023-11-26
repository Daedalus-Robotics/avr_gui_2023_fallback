class Gyroscope:
    def __init__(self) -> None:
        self._pitch = 0
        self._roll = 0
        self._yaw = 0

    @property
    def pitch(self) -> int:
        """
        Get the current pitch

        :return: The pitch
        """
        return self._pitch

    @property
    def roll(self) -> int:
        """
        Get the current roll

        :return: The roll
        """
        return self._roll

    @property
    def yaw(self) -> int:
        """
        Get the current yaw

        :return: The yaw
        """
        return self._yaw

    def update(self, rpy) -> None:
        """
        Sets the rpy values.
        This is not meant to be use outside this library.

        :param rpy: A tuple of the rpy values.
        """
        self._roll, self._pitch, self._yaw = rpy
