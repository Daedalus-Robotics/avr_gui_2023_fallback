from ..const import AudioEnableFlags, AudioMuteFlags, UpdateFlags1, UpdateFlags2


class Microphone:
    def __init__(self) -> None:
        self._volume_changed = False
        self._volume = 0
        self._mute_changed = False
        self._mute = True

    @property
    def volume(self) -> int:
        """
        Get the current mic volume

        :return: The mic volume
        """
        return self._volume

    @volume.setter
    def volume(self, value: int) -> None:
        """
        Set the mic volume

        :param value: The new mic volume (0-100)
        """
        if value != self._volume and 0 <= value <= 100:
            self._volume_changed = True
            self._volume = value
            if (value == 0) != self._mute:
                self._mute_changed = True
                self._mute = (value == 0)

    def force_update(self) -> None:
        """
        Send the next report as if the mic state was changed
        """
        self._volume_changed = True
        self._mute_changed = True
        self._mute = (self._volume == 0)

    def get_report(self) -> tuple[int, int, int, int, int]:
        """
        Get the next output report from the speaker.
        Do not call this unless you plan on sending it manually.
        This will set _volume_changed and _mute_changed to False and not change the volume or mute state.

        :return: A tuple containing two flags to tell what was changed, the report, a flag for enablement,
        and a flag for what is muted.
        """
        flag1 = UpdateFlags1.MICROPHONE_VOLUME if self._volume_changed else UpdateFlags1.NONE
        # flag1 |= UpdateFlags1.HEADSET_VOLUME if self._headset_volume_changed else UpdateFlags1.NONE
        flag2 = UpdateFlags2.AUDIO_MIC_MUTE if self._mute_changed else UpdateFlags2.NONE
        report = self._volume
        enable_flag = AudioEnableFlags.MICROPHONE if not self._mute else AudioEnableFlags.NONE
        muted_flag = AudioMuteFlags.MICROPHONE if self._mute else AudioMuteFlags.NONE

        self._volume_changed = False
        self._mute_changed = False
        return flag1, flag2, report, enable_flag, muted_flag
