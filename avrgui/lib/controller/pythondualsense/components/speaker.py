from ..const import AudioEnableFlags, AudioMuteFlags, UpdateFlags1, UpdateFlags2


class Speaker:
    def __init__(self) -> None:
        self._internal_volume_changed = False
        self._internal_volume = 0
        self._internal_mute_changed = False
        self._internal_mute = True

        self._headset_volume_changed = False
        self._headset_volume = 0
        self._headset_mute_changed = False
        self._headset_mute = True

    @property
    def volume(self) -> int:
        """
        Get the current volume of the controller's speaker.
        This will only get the volume of the internal speaker because I couldn't think of a better way to do it.

        :return: The internal speaker volume (0-100)
        """
        return self._internal_volume

    @volume.setter
    def volume(self, value: int) -> None:
        """
        Set the volume of the controller's speaker and connected headphones.
        This will set the volume of both the internal speaker and the connected headphones.

        :param value: The new volume level (0-100)
        """
        if (value != self._internal_volume or value != self._headset_volume) and 0 <= value <= 100:
            self._internal_volume_changed = True
            self._headset_volume_changed = True
            self._internal_volume = value
            self._headset_volume = value
            if (value == 0) != self._internal_mute or (value == 0) != self._headset_mute:
                self._internal_mute_changed = True
                self._internal_mute = value == 0
                self._headset_mute_changed = True
                self._headset_mute = value == 0

    @property
    def internal_volume(self) -> int:
        """
        Get the current volume of the controller's speaker.
        This is only the internal speaker.

        :return: The volume (0-100)
        """
        return self._internal_volume

    @internal_volume.setter
    def internal_volume(self, value: int) -> None:
        """
        Set the volume of the controller's speaker.
        This is only the internal speaker.

        :param value: The new volume level (0-100)
        """
        if value != self._internal_volume and 0 <= value <= 100:
            self._internal_volume_changed = True
            self._internal_volume = value
            if (value == 0) != self._internal_mute:
                self._internal_mute_changed = True
                self._internal_mute = value == 0

    @property
    def headset_volume(self) -> int:
        """
        Get the current volume of the connected headphones.
        This is only the headphones.

        :return: The volume (0-100)
        """
        return self._headset_volume

    @headset_volume.setter
    def headset_volume(self, value: int) -> None:
        """
        Set the volume of the connected headphones.
        This is only the headphones.

        :param value: The new volume level (0-100)
        """
        if value != self._headset_volume and 0 <= value <= 100:
            self._headset_volume_changed = True
            self._headset_volume = value
            if (value == 0) != self._headset_mute:
                self._headset_mute_changed = True
                self._headset_mute = value == 0

    def force_update(self) -> None:
        """
        Send the next report as if the speaker or headphone state was changed
        """
        self._internal_volume_changed = True
        self._internal_mute_changed = True
        self._internal_mute = (self._internal_volume == 0)

        self._headset_volume_changed = True
        self._headset_mute_changed = True
        self._headset_mute = (self._headset_volume == 0)

    def get_report(self) -> tuple[int, int, tuple[int, int], int, int]:
        """
        Get the next output report from the speaker.
        Do not call this unless you plan on sending it manually.
        This will set _volume_changed and _mute_changed to False and not change the volume or mute state.

        :return: A tuple containing two flags to tell what was changed, the report, a flag for enablement,
        and a flag for what is muted.
        """
        flag1 = UpdateFlags1.INTERNAL_SPEAKER_VOLUME if self._internal_volume_changed else UpdateFlags1.NONE
        flag1 |= UpdateFlags1.HEADSET_VOLUME if self._headset_volume_changed else UpdateFlags1.NONE
        flag2 = UpdateFlags2.AUDIO_MIC_MUTE if self._headset_mute_changed else UpdateFlags2.NONE

        report = (self._headset_volume, self._internal_volume)

        enable_flag = AudioEnableFlags.INTERNAL_SPEAKER if not self._internal_mute else AudioEnableFlags.NONE
        enable_flag |= AudioEnableFlags.DISABLE_HEADPHONES if self._headset_mute else AudioEnableFlags.NONE

        muted_flag = AudioMuteFlags.INTERNAL if self._internal_mute else AudioMuteFlags.NONE
        muted_flag |= AudioMuteFlags.HEADSET if self._headset_mute else AudioMuteFlags.NONE

        self._internal_volume_changed = False
        self._internal_mute_changed = False
        self._headset_volume_changed = False
        self._headset_mute_changed = False
        return flag1, flag2, report, enable_flag, muted_flag
