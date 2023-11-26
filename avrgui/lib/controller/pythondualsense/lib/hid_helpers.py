from typing import Any

from hid import enumerate, device
from .crc32 import crc32_le
from ..const import (
    VENDOR_ID,
    PRODUCT_ID,
    CRC32_SEED,
    CRC32_BYTE_ORDER
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
        hid_device.open(serial_number=serial_number)
    else:
        hid_device.open(vendor_id, product_id)
    return hid_device


def get_checksum(report: list[int], seed: int) -> int:
    """
    Calculates the crc32 checksum of a report

    :param report: The report with the checksum removed
    :param seed: The seed for the checksum
    :return: The crc32 checksum
    """
    # Get the crc32 hash of the report
    crc = crc32_le(0xFFFFFFFF, [seed])
    crc = ~crc32_le(crc, report)

    # Convert the checksum from signed to unsigned
    return crc % (1 << 32)


def verify_checksum(input_report: list[int]) -> bool:
    """
    Check that the checksum included in an input report is equal to the checksum that we calculate.
    WIP: I have tested, and this does not work yet!

    :param input_report: The input report
    :return: Whether the checksum is equal
    """
    # Get the crc32 checksum included in the input report
    included_crc = int.from_bytes(input_report[-4:], CRC32_BYTE_ORDER, signed=False)
    # included_crc = input_report[-4] | (input_report[-3] << 8) | (input_report[-2] << 16) | (input_report[-1] << 24)

    # Get the crc32 hash of the first 74 values in the report
    calculated_crc = get_checksum(input_report[:-4], 0xA1)

    return included_crc == calculated_crc


def add_checksum(output_report: list[int]) -> None:
    """
    Calculates the crc32 checksum of a report and appends it onto the end

    :param output_report: The output report to append the checksum to
    """
    # Get the crc32 hash of the first 74 values in the report
    crc = get_checksum(output_report[:-4], CRC32_SEED)

    # Insert the checksum into the last four indices of the report
    output_report[-4:] = crc.to_bytes(4, CRC32_BYTE_ORDER)
