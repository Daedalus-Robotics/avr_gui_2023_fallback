import asyncio
from threading import Thread

import hid

from .components.button import Button
from .components.dpad import Dpad
from .components.gyroscope import Gyroscope
from .components.mic_button import MicButton
from .components.microphone import Microphone
from .components.player_led import PlayerLed
from .components.rumble_motor import RumbleMotor
from .components.speaker import Speaker
from .components.thumbstick import Thumbstick
from .components.touchpad import Touchpad
from .components.trigger import Trigger
from .const import BLUETOOTH_REPORT_LENGTH, BatteryState, FeatureReport, USB_REPORT_LENGTH, UpdateFlags1
from .lib.callback import Callback
from .lib.hid_helpers import add_checksum, find_devices, get_device
from .lib.utils import ensure_list_length


class Dualsense:
    def __init__(self,
                 serial_number: str = None,
                 path: str = None,
                 event_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()
                 ) -> None:
        """
        Create a new Dualsense object. This will control a dualsense or PS5 controller.
        If you have multiple controllers, you may need to specify a serial_number or path.

        :param serial_number: The serial of the controller (only needed for multiple controllers)
        :param path: The path to the controller device (only needed for multiple controllers)
        :param event_loop: The event loop to run asynchronous callbacks in
        """
        self.serial_number = serial_number
        self.path = path
        self._event_loop = event_loop

        self._use_bluetooth = False
        self._report_length = USB_REPORT_LENGTH

        self.circle = Button(event_loop)
        self.cross = Button(event_loop)
        self.square = Button(event_loop)
        self.triangle = Button(event_loop)

        self.dpad = Dpad(event_loop)

        self.share = Button(event_loop)
        self.options = Button(event_loop)
        self.ps = Button(event_loop)

        self.mic_button = MicButton()

        self.left_bumper = Button(event_loop)
        self.right_bumper = Button(event_loop)

        self.left_trigger = Trigger(UpdateFlags1.LEFT_TRIGGER, event_loop)
        self.right_trigger = Trigger(UpdateFlags1.RIGHT_TRIGGER, event_loop)

        self.left_stick = Thumbstick(event_loop)
        self.right_stick = Thumbstick(event_loop)

        self.touchpad = Touchpad(event_loop)

        self.player_led = PlayerLed()

        self.left_rumble = RumbleMotor()
        self.right_rumble = RumbleMotor()

        self.speaker = Speaker()
        self.microphone = Microphone()

        self.gyroscope = Gyroscope()

        self.on_update = Callback(event_loop)
        """
        Called every time the states are updated
        """
        self.on_state = Callback[bool](event_loop)
        """
        Called on connect and on disconnect
        """
        self.on_battery_percent = Callback[int](event_loop)
        """
        Called every time the battery percent changes with the current percentage as a parameter
        """
        self.on_battery_state = Callback[BatteryState](event_loop)
        """
        Called every time the battery starts or stops charging with the current battery state as a parameter
        """

        self._update_thread: Thread | None = None
        self._update_thread_running = False

        self._device: hid.device | None = None
        self._last_state = False
        self._device_mac_address = None
        self._device_hardware_version = None
        self._device_firmware_version = None
        self._battery_percent = 0
        self._battery_state = BatteryState.UNKNOWN

        # For testing
        # self.val22 = 0
        # self.val23 = 0
        # self.val24 = 0
        # self.val25 = 0
        # self.val26 = 0
        # self.val27 = 0
        # self.val28 = 0
        # self.val31 = 0

        # self.add_flag1 = 0
        # self.add_flag2 = 0
        # self.val5 = 0
        # self.val6 = 0
        # self.val7 = 0
        # self.val8 = 0
        # self.val10 = 0
        # self.val38 = 0

        self._loop_running = False

    def __del__(self) -> None:
        """
        Clean up when the controller is destroyed
        """
        self._update_thread_running = False
        if self._device is not None:
            self._device.close()
            self._device = None

    @property
    def is_open(self) -> bool:
        """
        Check if the controller is connected and updating

        :return: Whether the controller is connected
        """
        if self._update_thread is None or self._device is None:
            return False
        return self._update_thread.is_alive()

    @property
    def mac_address(self) -> str | None:
        """
        Get the mac address of the controller.
        I actually have no clue if this works correctly

        :return: The mac-address. None if the controller has not connected.
        """
        # ToDo: Test this
        if self._device_mac_address is None:
            return None

        mac_address_str = ""
        for byte in self._device_mac_address:
            mac_address_str += hex(byte)[2:] + "."
        mac_address_str = mac_address_str[:-1]

        return mac_address_str

    @property
    def hardware_version(self) -> int | None:
        """
        Get the hardware version of the controller.
        I actually have no clue if this works correctly

        :return: The hardware version. None if the controller has not connected.
        """
        # ToDo: Test this
        if self._device_hardware_version is None:
            return None

        hardware_version = self._device_hardware_version[0]
        hardware_version |= self._device_hardware_version[1] << 8
        hardware_version |= self._device_hardware_version[2] << 16
        hardware_version |= self._device_hardware_version[3] << 24
        return hardware_version

    @property
    def firmware_version(self) -> str | None:
        """
        Get the firmware version of the controller.
        I actually have no clue if this works correctly

        :return: The firmware version. None if the controller has not connected.
        """
        # ToDo: Test this
        if self._device_firmware_version is None:
            return None

        firmware_version = self._device_firmware_version[0]
        firmware_version |= self._device_firmware_version[1] << 8
        firmware_version |= self._device_firmware_version[2] << 16
        firmware_version |= self._device_firmware_version[3] << 24
        return firmware_version

    @property
    def battery(self) -> int:
        """
        Get the current battery percent

        :return: The battery percent
        """
        # For some reason this is set to 85 when the battery state is FULL
        return self._battery_percent

    @property
    def battery_charging(self) -> bool:
        """
        Get whether the battery is charging or not

        :return: The battery charging state
        """
        return self._battery_state == BatteryState.CHARGING

    @property
    def battery_state(self) -> BatteryState:
        """
        Get the current battery state

        :return: The battery charging state
        """
        return self._battery_state

    def get_calibration_info(self) -> list[int]:
        """
        Get the current calibration from the controller

        :return: The calibration info
        """
        # ToDo: Make this easier to use
        calibration_feature_report = self._device.get_feature_report(
            FeatureReport.CALIBRATION.id,
            FeatureReport.CALIBRATION.length
        )
        return calibration_feature_report

    def open(self, device: hid.device = None, hold: bool = True, force_bluetooth: bool = False) -> bool:
        """
        Open the controller hid device and start the update loop.
        You can force the Dualsense object to use a specific device by passing it in.

        :param device: The device object of the controller (Optional)
        :param hold: Whether to hold until the first input report has been received and the first output report has
        been sent.
        :param force_bluetooth: This is only needed on sometimes on macOS. The auto-detection does not work because you
        can't use the serial number
        :return: Whether the controller is connected via bluetooth
        :raise IOError: If the device is already open or there is an error
        :raise OSError: If there is an issue with hidapi
        :raise ValueError:
        """
        if not self.is_open:
            use_bt = force_bluetooth
            try:
                if self._device is not None:
                    self._device.close()
                if device is None:
                    device = get_device(
                        serial_number=self.serial_number,
                        path=self.path
                    )

                if not force_bluetooth:
                    serial_number = None
                    try:
                        serial_number = device.get_serial_number_string()
                        print(serial_number)
                    except OSError:
                        pass
                    if serial_number not in (None, ""):
                        device_dict = find_devices(serial_number=serial_number, path=self.path)
                        interface = device_dict["interface_number"]
                        if interface == -1:
                            use_bt = True

                pairing_feature_report = device.get_feature_report(
                    FeatureReport.PAIRING.id,
                    FeatureReport.PAIRING.length
                )
                firmware_feature_request = device.get_feature_report(
                    FeatureReport.FIRMWARE.id,
                    FeatureReport.FIRMWARE.length
                )

                self._device_mac_address = pairing_feature_report[1:7]
                self._device_hardware_version = firmware_feature_request[24:28]
                self._device_firmware_version = firmware_feature_request[28:32]

                self._use_bluetooth = use_bt
                self._report_length = BLUETOOTH_REPORT_LENGTH if self._use_bluetooth else USB_REPORT_LENGTH
            except (IOError, OSError, ValueError) as e:
                try:
                    device.close()
                finally:
                    raise e
            self._device = device
            self._update_thread_running = True
            # ToDo: Fix
            self._update_thread = Thread(target=self._update, daemon=True)
            self._update_thread.start()
            self._loop_running = False
            if hold:
                while not self._loop_running:
                    pass
            return use_bt

    def close(self) -> None:
        """
        Close the controller hid device and stop the update loop.
        If the device is already closed, this will do nothing.
        """
        if self.is_open:
            self._update_thread_running = False
        self._loop_running = False

    def force_update(self) -> None:
        """
        This will send everything as if it had been changed
        """
        self.mic_button.force_update()
        self.left_trigger.force_update()
        self.right_trigger.force_update()
        self.touchpad.force_update()
        self.player_led.force_update()
        self.left_rumble.force_update()
        self.right_rumble.force_update()
        self.speaker.force_update()
        self.microphone.force_update()

    def _update(self) -> None:
        """
        The main update loop for getting and setting values from the controller.
        This is not meant to be called in the main thread.
        """
        try:
            l = 0
            while self._update_thread_running:
                input_report = list(self._device.read(self._report_length, 1000))
                if len(input_report) == self._report_length:
                    self.r = input_report
                    self._update_inputs(input_report)
                else:
                    print("Got incorrect size of report: " + str(len(input_report)))

                if not self._last_state:
                    self.on_state(True)
                    self._last_state = True

                report = self._generate_report()

                self._device.write(bytes(report))

                # time.sleep(1)
                self._loop_running = True

                self.on_update()
        except OSError as e:
            print(e)
        finally:
            self._device.close()
            if not self._last_state:
                self.on_state(False)
                self._last_state = False
            self._update_thread_running = False

    def _update_inputs(self, input_report: list[int]) -> None:
        """
        Update all the inputs from a report

        :param input_report: The report to get the inputs from
        """
        # print(input_report[7:8] + input_report[11:16] + input_report[28:33] + input_report[41:])
        if self._use_bluetooth:
            input_report.pop(1)

        symbol_buttons = input_report[8]
        self.square.update(symbol_buttons & 0x10 != 0)
        self.cross.update(symbol_buttons & 0x20 != 0)
        self.circle.update(symbol_buttons & 0x40 != 0)
        self.triangle.update(symbol_buttons & 0x80 != 0)

        self.dpad.update(symbol_buttons & 0x0f)

        top_buttons = input_report[9]
        ps_mic_touch_buttons = input_report[10]

        self.share.update(top_buttons & 0x10 != 0)
        self.options.update(top_buttons & 0x20 != 0)
        self.ps.update(ps_mic_touch_buttons & 0x01 != 0)
        self.mic_button.update(ps_mic_touch_buttons & 0x04 != 0)

        self.left_bumper.update(top_buttons & 0x01 != 0)
        self.right_bumper.update(top_buttons & 0x02 != 0)

        self.left_trigger.update(input_report[5])
        self.right_trigger.update(input_report[6])

        self.left_stick.update(top_buttons & 0x40 != 0, (input_report[1] - 127, input_report[2] - 127))
        self.right_stick.update(top_buttons & 0x80 != 0, (input_report[3] - 127, input_report[4] - 127))

        touch_point_1_x = ((input_report[35] & 0x0f) << 8) | (input_report[34])
        touch_point_1_y = ((input_report[36]) << 4) | ((input_report[35] & 0xf0) >> 4)
        touch_point_1_report = (input_report[33] & 0x7F, input_report[33] & 0x80 == 0, touch_point_1_x, touch_point_1_y)

        touch_point_2_x = ((input_report[39] & 0x0f) << 8) | (input_report[38])
        touch_point_2_y = ((input_report[40]) << 4) | ((input_report[39] & 0xf0) >> 4)
        touch_point_2_report = (input_report[37] & 0x7F, input_report[37] & 0x80 == 0, touch_point_2_x, touch_point_2_y)

        self.touchpad.update(
            ps_mic_touch_buttons & 0x02 != 0,
            touch_point_1_report,
            touch_point_2_report
        )

        roll = int.from_bytes(([input_report[22], input_report[23]]), byteorder='little', signed=True)
        pitch = int.from_bytes(([input_report[24], input_report[25]]), byteorder='little', signed=True)
        yaw = int.from_bytes(([input_report[26], input_report[27]]), byteorder='little', signed=True)
        self.gyroscope.update((roll, pitch, yaw))

        status = input_report[53]
        battery_percent = min(((status & 0x0f) * 10) + 5, 100)
        if battery_percent != self._battery_percent:
            self.on_battery_percent(battery_percent)
            self._battery_percent = battery_percent
        battery_state = BatteryState.find((status & 0xf0) >> 4)
        if battery_state != self._battery_state:
            self.on_battery_state(battery_state)
            self._battery_state = battery_state

    def _generate_report(self) -> list[int]:
        """
        Generate a new output report

        :return: The output report
        """
        report = [0] * self._report_length
        if self._use_bluetooth:
            report.pop()
            report.pop()

        report[0] = 0x31 if self._use_bluetooth else 0x02

        mic_button_set_brightness = False
        mic_button_flag, mic_button_report, led_flag, brightness_flag = self.mic_button.get_report()
        report[2] |= mic_button_flag
        report[9] = mic_button_report
        report[39] |= led_flag
        if led_flag:
            self.player_led.update_brightness(self.mic_button.led_brightness)
            report[43] = brightness_flag
            mic_button_set_brightness = True

        left_trigger_flag, left_trigger_report = self.left_trigger.get_report()
        report[1] |= left_trigger_flag
        report[22:26] = left_trigger_report

        # For testing
        # report[1] = 0xff
        # report[22] = 0x26
        # report[23] = 0x0
        # report[24] = 0x02 if True else 0x00
        # report[25] = 0x5
        # report[26] = 0xff - 0x5
        # report[27] = 0xff
        # report[28] = 0x8

        # I have no idea what these values do but the triggers vibrate when I set some of them
        # report[26] = self.val26  # ?
        # report[27] = self.val27  # this seems to be the start of the vibration zone, but it only works sometimes
        # report[28] = self.val28  # this might be something else about the vibration zone, but it's not the end
        # report[31] = self.val31  # This seems to be the intensity of the vibration
        # I don't know if this is actual functionality or damaging to the controller

        right_trigger_flag, right_trigger_report = self.right_trigger.get_report()
        report[1] |= right_trigger_flag
        report[11:15] = right_trigger_report

        # I have no idea what these values do
        # report[15]
        # report[16]
        # report[17]
        # report[20]

        touchpad_led_flag, touchpad_led_report, led_flag, touchpad_led_mode = self.touchpad.get_report()
        report[2] |= touchpad_led_flag
        report[45:48] = touchpad_led_report
        report[39] |= led_flag
        report[42] = touchpad_led_mode

        player_led_flag, player_led_report, led_flag, brightness_flag = self.player_led.get_report()
        report[2] |= player_led_flag
        report[44] = player_led_report
        report[39] |= led_flag
        if led_flag and not mic_button_set_brightness:
            self.mic_button.update_led_brightness(self.player_led.brightness)
            report[43] = brightness_flag

        rumble_flag, left_rumble_report = self.left_rumble.get_report()
        report[1] |= rumble_flag
        report[4] = left_rumble_report

        rumble_flag, right_rumble_report = self.right_rumble.get_report()
        report[1] |= rumble_flag
        report[3] = right_rumble_report

        speaker_flag, mute_flag, speaker_report, speaker_enable_flag, speaker_mute_flag = self.speaker.get_report()
        report[1] |= speaker_flag
        report[2] |= mute_flag
        report[5:7] = speaker_report
        report[8] |= speaker_enable_flag
        report[10] |= speaker_mute_flag

        mic_flag, mute_flag, mic_report, mic_enable_flag, mic_mute_flag = self.microphone.get_report()
        report[1] |= mic_flag
        report[2] |= mute_flag
        report[7] = mic_report
        report[8] |= mic_enable_flag
        report[10] |= mic_mute_flag

        if self._use_bluetooth:
            report.insert(1, 0x00)
            report.insert(2, 0x10)
            add_checksum(report)

        # report[1] |= self.add_flag1
        # report[2] |= self.add_flag2
        # report[5] = self.val5
        # report[6] = self.val6
        # report[7] = self.val7
        # report[8] |= self.val8
        # report[10] |= self.val10
        # report[38] |= self.val38

        return report
