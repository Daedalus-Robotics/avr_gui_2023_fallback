import json
import os
import sys
from typing import Any

if getattr(sys, "frozen", False):
    DATA_DIR = sys._MEIPASS  # type: ignore
    ROOT_DIR = os.path.dirname(sys.executable)
else:
    DATA_DIR = os.path.join(os.path.dirname(__file__), "../../app", "..")
    ROOT_DIR = DATA_DIR

# root dir is the directory of the main entrypoint
ROOT_DIR = os.path.abspath(ROOT_DIR)
# data dir is the root directory within the application itself
DATA_DIR = os.path.abspath(DATA_DIR)
# directory that contains images
IMG_DIR = os.path.join(DATA_DIR, "assets", "img")


class _Config:
    config_file = os.path.join(ROOT_DIR, "settings.json")

    def __read(self) -> dict:
        if not os.path.isfile(self.config_file):
            return {}

        with open(self.config_file) as fp:
            return json.load(fp)

    def __write(self, data: dict) -> None:
        with open(self.config_file, "w") as fp:
            json.dump(data, fp)

    def __get(self, key: str, default: Any = None) -> Any:
        data = self.__read()
        if key in data:
            return data[key]
        return default

    def __set(self, key: str, value: Any) -> None:
        data = self.__read()
        data[key] = value
        self.__write(data)

    @property
    def ros_client_host(self) -> str:
        return self.__get("ros_client_host", "")

    @ros_client_host.setter
    def ros_client_host(self, value: str) -> None:
        self.__set("ros_client_host", value)

    @property
    def ros_client_port(self) -> int:
        return self.__get("ros_client_port", 1883)

    @ros_client_port.setter
    def ros_client_port(self, value: int) -> None:
        self.__set("ros_client_port", value)

    @property
    def log_file_directory(self) -> str:
        return self.__get("log_file_directory", os.path.join(ROOT_DIR, "logs"))

    @log_file_directory.setter
    def log_file_directory(self, value: str) -> None:
        return self.__set("log_file_directory", value)


config = _Config()
