from typing import Any, TypeVar

ItemType = TypeVar("ItemType")


def ensure_list_length(in_list: list[ItemType], length: int, placeholder: Any = None) -> list[ItemType]:
    """
    Ensure that a list is a certain size

    :param in_list: The input list
    :param length: The ensured len
    :param placeholder: The item that is added to the list when it is too short
    :return: The list with the correct length
    """
    list_length = len(in_list)
    if list_length < length:
        add_count = length - list_length
        in_list += [placeholder] * add_count
    elif list_length > length:
        in_list = in_list[:length]

    return in_list
