from __future__ import annotations

import functools
from typing import List, Literal, Tuple

from PySide6.QtGui import QColor
from bell.avr.mqtt.payloads import (
    AvrPcmSetTempColorPayload
)
from PySide6 import QtCore, QtGui, QtWidgets

from ..lib.color import wrap_text
from .base import BaseTabWidget
from ..lib.color_button import ColorButton
from ..lib.widgets import StatusLabel


class VMCControlWidget(BaseTabWidget):
    # This is the primary control widget for the drone. This allows the user
    # to set LED color

    def __init__(self, parent: QtWidgets.QWidget) -> None:
        super().__init__(parent)

        self.vmc_status_label = None
        self.pcm_status_label = None
        self.fcm_status_label = None
        self.mavp2p_status_label = None
        self.frame_server_status_label = None
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
        led_groupbox.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)

        self.led_color_picker = ColorButton(color = QtGui.QColor("white"))
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

        y = 0

        self.mavp2p_status_label = StatusLabel("MavP2P")
        restart_button = QtWidgets.QPushButton("Restart")
        restart_button.clicked.connect(lambda: self.restart_service("mavp2p", False))
        services_layout.addWidget(self.mavp2p_status_label, y, 0)
        services_layout.addWidget(restart_button, y, 1)

        y += 1

        self.fcm_status_label = StatusLabel("Flight Controller")
        restart_button = QtWidgets.QPushButton("Restart")
        fcm_restart_message = "This will restart the flight controller.\nIf the avr drone is currently flying, it will fall."
        restart_button.clicked.connect(lambda: self.restart_service("fcm", True, fcm_restart_message))
        services_layout.addWidget(self.fcm_status_label, y, 0)
        services_layout.addWidget(restart_button, y, 1)

        y += 1

        self.pcm_status_label = StatusLabel("Peripheral Controller")
        restart_button = QtWidgets.QPushButton("Restart")
        restart_button.clicked.connect(lambda: self.restart_service("pcm", False))
        services_layout.addWidget(self.pcm_status_label, y, 0)
        services_layout.addWidget(restart_button, 2, 1)

        y += 1

        self.vmc_status_label = StatusLabel("Vehicle Management")
        restart_button = QtWidgets.QPushButton("Restart")
        vmc_restart_message = "This will restart the vehicle management computer.\nThis will disable all autonomy for at least a minute."
        restart_button.clicked.connect(lambda: self.restart_service("vmc", True, vmc_restart_message))
        services_layout.addWidget(self.vmc_status_label, y, 0)
        services_layout.addWidget(restart_button, y, 1)

        layout.addWidget(services_groupbox, 1, 0, 1, 0)
        layout.setRowStretch(1, 1)

    def restart_service(self, service: str, show_dialog: bool, message: str = ""):
        do_reset = True
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
            dialog.setWindowTitle(f"Restart {service}")
            dialog.setText(message)
            if info is not None:
                dialog.setInformativeText(info)
            dialog.setIcon(QtWidgets.QMessageBox.Critical)
            dialog.setStandardButtons(QtWidgets.QMessageBox.Cancel | QtWidgets.QMessageBox.Ok)
            dialog.setDefaultButton(QtWidgets.QMessageBox.Ok)
            dialog.setEscapeButton(QtWidgets.QMessageBox.Cancel)
            if dialog.exec_() != QtWidgets.QMessageBox.Ok:
                do_reset = False
        if do_reset:
            command = "restart"
            if service == "pcm":
                command = "reset"
            self.send_message(f"avr/{service}/{command}", {})

    def blink_led(self, color: QColor, location: int):
        if location == 0:
            self.blink_pcc_led((color.alpha(), color.red(), color.green(), color.blue()))
        else:
            self.blink_vmc_led((color.alpha(), color.red(), color.green(), color.blue()))

    def blink_pcc_led(self, color: Tuple[int, int, int, int]) -> None:
        """
        Set LED color
        """
        self.send_message(
                "avr/pcm/set_temp_color", AvrPcmSetTempColorPayload(wrgb = color, time = 1)
        )

    def blink_vmc_led(self, color: Tuple[int, int, int, int]) -> None:
        """
        Set LED color
        """
        # ToDo: Make this actually do the right thing
        self.send_message(
                "avr/pcm/set_temp_color", AvrPcmSetTempColorPayload(wrgb = color, time = 1)
        )
