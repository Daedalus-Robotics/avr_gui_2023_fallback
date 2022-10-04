import pickle
import socket

import cv2
import numpy as np
from PySide6 import QtGui
from PySide6.QtGui import QPixmap, Qt


def decode_frame(encoded_frame: bytes) -> (bool, np.ndarray):
    try:
        jpeg_frame: np.ndarray = pickle.loads(encoded_frame)
        jpeg_frame = jpeg_frame.astype(np.uint8)
        frame: np.ndarray = cv2.imdecode(jpeg_frame, 1)
        if frame is not None and type(frame) == np.ndarray:
            return True, frame
        else:
            return False, None
    except (pickle.PickleError, TypeError, EOFError, cv2.error):
        return False, None


def decode_frame_uncompressed(encoded_frame: bytes) -> (bool, np.ndarray):
    try:
        frame: np.ndarray = pickle.loads(encoded_frame)
        frame = frame.astype(np.uint8)
        return True, frame
    except (pickle.PickleError, TypeError, EOFError):
        return False, None


def convert_cv_qt(cv_img, display_size):
    rgb_image = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
    h, w, ch = rgb_image.shape
    bytes_per_line = ch * w
    convert_to_qt_format = QtGui.QImage(rgb_image.data, w, h, bytes_per_line, QtGui.QImage.Format_RGB888)
    p = convert_to_qt_format.scaled(display_size[0], display_size[1], Qt.KeepAspectRatio)
    return QPixmap.fromImage(p)


def is_socket_open(sock: socket.socket) -> bool:
    # noinspection PyBroadException
    try:
        data = sock.recv(16, socket.MSG_DONTWAIT | socket.MSG_PEEK)
        if len(data) == 0:
            return False
    except BlockingIOError:
        return True
    except ConnectionResetError:
        return False
    except Exception as e:
        return False
    return True
