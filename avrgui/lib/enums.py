from enum import Enum, auto


class ConnectionState(Enum):
    CONNECTING = auto()
    CONNECTED = auto()
    DISCONNECTING = auto()
    DISCONNECTED = auto()
    FAILURE = auto()
