from enum import Enum, IntEnum, IntFlag

VENDOR_ID = 0x054c
PRODUCT_ID = 0x0CE6
CRC32_SEED = 0xA2

USB_REPORT_LENGTH = 64
BLUETOOTH_REPORT_LENGTH = 78


class FeatureReport(Enum):
    CALIBRATION = (0x05, 41)
    PAIRING = (0x09, 20)
    FIRMWARE = (0x20, 64)

    @property
    def id(self) -> int:
        return self.value[0]

    @property
    def length(self) -> int:
        return self.value[1]


class UpdateFlags1(IntFlag):
    NONE = 0x00
    RUMBLE = 0x01 | 0x02  # For some reason both of these values are required for rumble
    LEFT_TRIGGER = 0x08
    RIGHT_TRIGGER = 0x04
    HEADSET_VOLUME = 0x10
    INTERNAL_SPEAKER_VOLUME = 0x20
    MICROPHONE_VOLUME = 0x40
    INTERNAL_MIC_HEADSET = 0x80


class UpdateFlags2(IntFlag):
    NONE = 0x00
    MICROPHONE_LED = 0x01
    AUDIO_MIC_MUTE = 0x02
    TOUCHPAD_LED = 0x04
    TURN_ALL_LEDS_OFF = 0x08  # I don't use this because it would mess up all the stored values for the leds
    PLAYER_LEDS = 0x10
    _ = 0x20  # I haven't needed this. I have no idea what its for
    MOTOR_POWER = 0x40
    __ = 0x80  # I haven't needed this. I have no idea what its for


class AudioEnableFlags(IntFlag):
    NONE = 0x00
    MICROPHONE = 0x01  # This flag is used for both the internal mic and mics on connected headphones
    _ = 0x04  # I haven't needed this. I have no idea what its for
    __ = 0x08  # I haven't needed this. I have no idea what its for
    DISABLE_HEADPHONES = 0x10
    INTERNAL_SPEAKER = 0x20


class AudioMuteFlags(IntFlag):
    NONE = 0x00
    MICROPHONE = 0x10
    INTERNAL = 0x20
    HEADSET = 0x40


class LedFlags(IntFlag):
    NONE = 0x0
    PLAYER_MIC = 0x1
    TOUCHPAD = 0x2


class TouchpadLedModes(IntFlag):
    NONE = 0x0
    FADE_BLUE = 0x1
    TURN_OFF = 0x2


class BrightnessLevel(IntEnum):
    HIGH = 0x0
    MEDIUM = 0x1
    LOW = 0x2


class BatteryState(IntEnum):
    DISCHARGING = 0x0
    FULL = 0x1
    CHARGING = 0x2
    INCORRECT_VOLTAGE = 0xa
    TEMPERATURE_ERROR = 0xf
    ERROR = 0xf
    UNKNOWN = 0xff

    @classmethod
    def find(cls, num: int):
        """
        Get the battery state from a number returned by the controller
        :param num: The number of the state
        :return: The state
        """
        for state in cls:
            if state == num:
                return state
        return cls.UNKNOWN

