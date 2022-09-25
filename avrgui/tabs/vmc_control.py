from __future__ import annotations

import functools
from typing import List, Literal, Tuple

from PySide6.QtGui import QColor
from bell.avr.mqtt.payloads import (
    AvrPcmSetBaseColorPayload,
    AvrPcmSetServoOpenClosePayload,
)
from PySide6 import QtCore, QtGui, QtWidgets

from ..lib.color import wrap_text
from .base import BaseTabWidget
from ..lib.color_button import ColorButton
from ..lib.widgets import StatusLabel


class VMCControlWidget(BaseTabWidget):
    # This is the primary control widget for the drone. This allows the user
    # to set LED color, open/close servos etc.

    def __init__(self, parent: QtWidgets.QWidget) -> None:
        super().__init__(parent)

        self.vmc_status_label = None
        self.pcm_status_label = None
        self.fcm_status_label = None
        self.mavp2p_status_label = None
        self.led_color_picker = None
        self.setWindowTitle("VMC Control")

    def build(self) -> None:
        """
        Build the GUI layout
        """
        layout = QtWidgets.QGridLayout(self)
        self.setLayout(layout)

        # ==========================
        # LEDs
        led_groupbox = QtWidgets.QGroupBox("LEDs")
        led_layout = QtWidgets.QHBoxLayout()
        led_groupbox.setLayout(led_layout)

        # red_led_button = QtWidgets.QPushButton("Red")
        # red_led_button.setStyleSheet("background-color: red")
        # red_led_button.clicked.connect(lambda: self.set_led((255, 255, 0, 0)))  # type: ignore
        # led_layout.addWidget(red_led_button)
        #
        # green_led_button = QtWidgets.QPushButton("Green")
        # green_led_button.setStyleSheet("background-color: green")
        # green_led_button.clicked.connect(lambda: self.set_led((255, 0, 255, 0)))  # type: ignore
        # led_layout.addWidget(green_led_button)
        #
        # blue_led_button = QtWidgets.QPushButton("Blue")
        # blue_led_button.setStyleSheet("background-color: blue; color: white")
        # blue_led_button.clicked.connect(lambda: self.set_led((255, 0, 0, 255)))  # type: ignore
        # led_layout.addWidget(blue_led_button)
        #
        # clear_led_button = QtWidgets.QPushButton("Clear")
        # clear_led_button.setStyleSheet("background-color: white")
        # clear_led_button.clicked.connect(lambda: self.set_led((0, 0, 0, 0)))  # type: ignore
        # led_layout.addWidget(clear_led_button)

        self.led_color_picker = ColorButton(color = QtGui.QColor("white"))
        # self.led_color_picker.setStyleSheet("max-width: 25px; height: 20px;")
        # self.led_color_picker.setFixedSize(QtCore.QSize(25, 20))
        led_layout.addWidget(self.led_color_picker)

        blink_pcc_led_button = QtWidgets.QPushButton("Flash PCC Leds")
        blink_pcc_led_button.clicked.connect(lambda: self.blink_led(self.led_color_picker.color(), 0))
        led_layout.addWidget(blink_pcc_led_button)

        blink_pcc_led_button = QtWidgets.QPushButton("Flash VMC Leds")
        blink_pcc_led_button.clicked.connect(lambda: self.blink_led(self.led_color_picker.color(), 1))
        led_layout.addWidget(blink_pcc_led_button)

        layout.addWidget(led_groupbox, 0, 0)

        services_groupbox = QtWidgets.QGroupBox("Services")
        services_layout = QtWidgets.QGridLayout()
        services_groupbox.setLayout(services_layout)

        self.mavp2p_status_label = StatusLabel("MavP2P")
        restart_button = QtWidgets.QPushButton("Restart")
        restart_button.clicked.connect(lambda: self.restart_service("mavp2p", False))
        services_layout.addWidget(self.mavp2p_status_label, 0, 0)
        services_layout.addWidget(restart_button, 0, 1)

        self.fcm_status_label = StatusLabel("Flight Controller")
        restart_button = QtWidgets.QPushButton("Restart")
        fcm_restart_message = "This will restart the flight controller.\nIf the avr drone is currently flying, it will fall."
        restart_button.clicked.connect(lambda: self.restart_service("fcm", True, fcm_restart_message))
        services_layout.addWidget(self.fcm_status_label, 1, 0)
        services_layout.addWidget(restart_button, 1, 1)

        self.pcm_status_label = StatusLabel("Peripheral Controller")
        restart_button = QtWidgets.QPushButton("Restart")
        restart_button.clicked.connect(lambda: self.restart_service("pcm", False))
        services_layout.addWidget(self.pcm_status_label, 2, 0)
        services_layout.addWidget(restart_button, 2, 1)

        self.vmc_status_label = StatusLabel("Vehicle Management")
        restart_button = QtWidgets.QPushButton("Restart")
        vmc_restart_message = "This will restart the vehicle management computer.\nThis will disable all autonomy for at least a minute."
        restart_button.clicked.connect(lambda: self.restart_service("vmc", True, vmc_restart_message))
        services_layout.addWidget(self.vmc_status_label, 3, 0)
        services_layout.addWidget(restart_button, 3, 1)

        layout.addWidget(services_groupbox, 1, 0)

        # ==========================
        # Servos
        # self.number_of_servos = 4
        # self.servo_labels: List[QtWidgets.QLabel] = []
        #
        # servos_groupbox = QtWidgets.QGroupBox("Servos")
        # servos_layout = QtWidgets.QVBoxLayout()
        # servos_groupbox.setLayout(servos_layout)
        #
        # servo_all_layout = QtWidgets.QHBoxLayout()
        #
        # servo_all_open_button = QtWidgets.QPushButton("Open all")
        # servo_all_open_button.clicked.connect(lambda: self.set_servo_all("open"))  # type: ignore
        # servo_all_layout.addWidget(servo_all_open_button)
        #
        # servo_all_close_button = QtWidgets.QPushButton("Close all")
        # servo_all_close_button.clicked.connect(lambda: self.set_servo_all("close"))  # type: ignore
        # servo_all_layout.addWidget(servo_all_close_button)
        #
        # servos_layout.addLayout(servo_all_layout)
        #
        # for i in range(self.number_of_servos):
        #     servo_groupbox = QtWidgets.QGroupBox(f"Servo {i + 1}")
        #     servo_layout = QtWidgets.QHBoxLayout()
        #     servo_groupbox.setLayout(servo_layout)
        #
        #     servo_open_button = QtWidgets.QPushButton("Open")
        #     servo_open_button.clicked.connect(functools.partial(self.set_servo, i, "open"))  # type: ignore
        #     servo_layout.addWidget(servo_open_button)
        #
        #     servo_close_button = QtWidgets.QPushButton("Close")
        #     servo_close_button.clicked.connect(functools.partial(self.set_servo, i, "close"))  # type: ignore
        #     servo_layout.addWidget(servo_close_button)
        #
        #     servo_label = QtWidgets.QLabel()
        #     servo_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        #     servo_layout.addWidget(servo_label)
        #     self.servo_labels.append(servo_label)
        #
        #     servos_layout.addWidget(servo_groupbox)
        #
        # layout.addWidget(servos_groupbox, 0, 1, 3, 3)

        # # ==========================
        # # PCC Reset
        # reset_groupbox = QtWidgets.QGroupBox("Reset")
        # reset_layout = QtWidgets.QVBoxLayout()
        # reset_groupbox.setLayout(reset_layout)

        # reset_button = QtWidgets.QPushButton("Reset PCC")
        # reset_button.setStyleSheet("background-color: yellow")
        # reset_button.clicked.connect(lambda: self.send_message("avr/pcm/reset", AvrPcmResetPayload()))  # type: ignore
        # reset_layout.addWidget(reset_button)

        # layout.addWidget(reset_groupbox, 3, 3, 1, 1)

    def restart_service(self, service: str, show_dialog: bool, message: str = ""):
        if show_dialog:
            if '\n' in message:
                split = message.split('\n')
                message = ""
                num = 0
                for text in split[0:-1]:
                    message += text
                    if not num == len(split[0:-1]) - 1:
                        message += "\n"
                    num += 1
                info = split[-1]
            else:
                info = None

            dialog = QtWidgets.QMessageBox()
            dialog.setWindowTitle(f"Restart { service }")
            dialog.setText(message)
            if info is not None:
                dialog.setInformativeText(info)
            dialog.setIcon(QtWidgets.QMessageBox.Critical)
            dialog.setStandardButtons(QtWidgets.QMessageBox.Cancel | QtWidgets.QMessageBox.Ok)
            dialog.setDefaultButton(QtWidgets.QMessageBox.Cancel)
            dialog.setEscapeButton(QtWidgets.QMessageBox.Cancel)
            dialog.exec_()
        else:
            self.send_message(f"avr/{ service }/restart", {})

    def blink_led(self, color: QColor, location: int):
        if location == 0:
            self.blink_pcc_led((color.alpha(), color.red(), color.green(), color.blue()))

    def set_servo(self, number: int, action: Literal["open", "close"]) -> None:
        """
        Set a servo state
        """
        self.send_message(
                "avr/pcm/set_servo_open_close",
                AvrPcmSetServoOpenClosePayload(servo = number, action = action),
        )

        if action == "open":
            text = "Opened"
            color = "blue"
        else:
            text = "Closed"
            color = "chocolate"

        self.servo_labels[number].setText(wrap_text(text, color))

    def set_servo_all(self, action: Literal["open", "close"]) -> None:
        """
        Set all servos to the same state
        """
        for i in range(self.number_of_servos):
            self.set_servo(i, action)

    def blink_pcc_led(self, color: Tuple[int, int, int, int]) -> None:
        """
        Set LED color
        """
        self.send_message(
                "avr/pcm/set_temp_color", AvrPcmSetBaseColorPayload(wrgb = color)
        )
