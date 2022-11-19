from typing import Any

from hid import enumerate, device
from .crc32 import crc32_le
from ..const import (
    VENDOR_ID,
    PRODUCT_ID,
    CRC32_SEED
)


def find_devices(
        vendor_id: int = VENDOR_ID,
        product_id: int = PRODUCT_ID,
        serial_number: str = None,
        path: bytes | str = None
) -> list[dict[str, Any]] | dict[str, Any] | None:
    """
    Finds all devices with the given information

    :param vendor_id: The vendor id of the device
    :param product_id: The product id of the device
    :param serial_number: The serial number of the device. When this is defined, the function will return None or a
    single device
    :param path: The path to the device. When this is defined, the function will return None or a single device
    :return: A list of dictionaries describing all the devices that were found or a single dictionary for one device
    """
    devices = enumerate(vendor_id, product_id)
    # There is only one device with a given path
    if path is not None:
        if isinstance(path, str):
            path = bytes(path, "utf8")
        for hid_device in devices:
            if hid_device['path'] == path:
                return hid_device
        return None
    # There should only be one device with a given serial number
    elif serial_number is not None:
        for hid_device in devices:
            if hid_device['serial_number'] == serial_number:
                return hid_device
        return None
    # Return all the devices found with the vendor_id and the product_id
    else:
        return devices


def get_device(
        device_dict: dict[str, Any] = None,
        vendor_id: int = VENDOR_ID,
        product_id: int = PRODUCT_ID,
        serial_number: str = None,
        path: bytes = None
) -> device:
    """
    Opens the device with the given information

    :param device_dict: A dictionary describing the device
    :param vendor_id: The vendor id of the device
    :param product_id: The product id of the device
    :param serial_number: The serial number of the device
    :param path: The path to the device
    :return: The hidapi device object
    :raises IOError: If there was any error in connecting or if the device is already open
    """
    # This is so you can pass in a dict returned by the find_devices function
    if device_dict is not None:
        vendor_id = device_dict.get('vendor_id', None)
        product_id = device_dict.get('product_id', None)
        serial_number = device_dict.get('serial_number', None)
    hid_device = device()
    # Open using the most specific identifier
    if path is not None:
        hid_device.open_path(path)
    elif serial_number is not None and len(serial_number) > 0:
        hid_device.open(serial_number = serial_number)
    else:
        hid_device.open(vendor_id, product_id)
    return hid_device


def get_checksum(report: list[int]) -> list[int]:
    """
    Calculates the checksum of a report and appends it onto the report

    :param report: The report to get the checksum of
    :return: The report with the checksum appended onto it
    """
    # Make a copy of report
    # report = report[:]

    # Get the crc32 hash of the first 74 values in the report
    crc = crc32_le(0xFFFFFFFF, [CRC32_SEED])
    crc = ~crc32_le(crc, report[:-4])

    # Convert the checksum from signed to unsigned
    crc = crc % (1 << 32)

    # Insert the checksum into the last four indices of the report
    report[-4:] = crc.to_bytes(4, 'little')

    return report
