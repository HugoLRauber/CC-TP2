from dataclasses import dataclass, asdict
from enum import IntEnum
import json
import time


class MessageType(IntEnum):
    READY = 0
    MISSION = 1
    ACK = 2
    ERROR = 3


@dataclass
class MissionHeader:
    msg_type: MessageType
    id_rover : int
    id_missao: int
    more_fragments: bool
    fragment_offset: int
    payload_size: int
    seq_number: int
    timestamp: float = 0.0
    #checksum --- A IMPLEMENTAR

    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()


    def to_dict(self):
        return {
            "msg_type": self.msg_type.value,
            "id_rover": self.id_rover,
            "id_missao": self.id_missao,
            "more_fragments": self.more_fragments,
            "fragment_offset": self.fragment_offset,
            "payload_size": self.payload_size,
            "seq_number": self.seq_number,
            "timestamp": self.timestamp,
        }


    @staticmethod
    def from_dict(data: dict):
        return MissionHeader(
            msg_type=MessageType(data["msg_type"]),
            id_rover=data["id_rover"],
            id_missao=data["id_missao"],
            more_fragments=data["more_fragments"],
            fragment_offset=data["fragment_offset"],
            payload_size=data["payload_size"],
            seq_number=data.get("seq_number", 0),
            timestamp=data.get("timestamp", time.time()),
        )


@dataclass
class MissionMessage:
    header: MissionHeader
    payload: dict


    def encode(self) -> bytes:
        data = {
            "header": self.header.to_dict(),
            "payload": self.payload,
        }
        return json.dumps(data).encode()


    @staticmethod
    def decode(raw: bytes):
        data = json.loads(raw.decode())
        header = MissionHeader.from_dict(data["header"])
        payload = data["payload"]
        return MissionMessage(header=header, payload=payload)


@dataclass
class ACK:
    seq_number: int
    id_rover: int
    id_missao: int
    msg_type: MessageType
    timestamp: float = 0.0

    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()

    def to_dict(self):
        return {
            "seq_number": self.seq_number,
            "id_rover": self.id_rover,
            "id_missao": self.id_missao,
            "msg_type": self.msg_type if isinstance(self.msg_type, int) else self.msg_type.value,
            "timestamp": self.timestamp
        }

    @staticmethod
    def from_dict(data: dict):
        return ACK(
            seq_number=data["seq_number"],
            id_rover=data["id_rover"],
            id_missao=data["id_missao"],
            msg_type=data["msg_type"],
            timestamp=data.get("timestamp", time.time())
        )

@dataclass
class TelemetryMessage:
    id_rover: int
    pos_rover: tuple[float, float]  # (x, y) coordinates
    estado: int                      # could be an enum for rover state
    battery: float                   # battery percentage
    timestamp: float = 0.0

    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()

    def to_dict(self):
        return {
            "id_rover": self.id_rover,
            "pos_rover": self.pos_rover,
            "estado": self.estado,
            "battery": self.battery,
            "timestamp": self.timestamp
        }

    @staticmethod
    def from_dict(data: dict):
        return TelemetryMessage(
            id_rover=data["id_rover"],
            pos_rover=tuple(data["pos_rover"]),
            estado=data["estado"],
            battery=data["battery"],
            timestamp=data.get("timestamp", time.time())
        )