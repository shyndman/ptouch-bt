from dataclasses import dataclass

from .media import label_color, label_color_name
from .rfcomm import drain, ptouch_connection, read_exact, write_all

STATUS_COMMAND = bytes.fromhex("1b6953")
STATUS_LENGTH = 32


@dataclass(frozen=True)
class Status:
    raw: bytes

    @classmethod
    def from_bytes(cls, raw):
        if len(raw) != STATUS_LENGTH:
            raise ValueError(f"expected {STATUS_LENGTH} bytes, got {len(raw)}: {raw.hex()}")
        return cls(raw=raw)

    @property
    def header(self):
        return self.raw[0:2]

    @property
    def marker(self):
        return self.raw[2:4]

    @property
    def model(self):
        return self.raw[4:6]

    @property
    def error_1(self):
        return self.raw[8]

    @property
    def error_2(self):
        return self.raw[9]

    @property
    def media_width(self):
        return self.raw[10]

    @property
    def media_type(self):
        return self.raw[11]

    @property
    def media_color(self):
        return self.raw[24]

    @property
    def media_color_enum(self):
        return label_color(self.media_color)

    @property
    def media_color_name(self):
        return label_color_name(self.media_color)

    @property
    def text_color(self):
        return self.raw[25]

    @property
    def text_color_enum(self):
        return label_color(self.text_color)

    @property
    def text_color_name(self):
        return label_color_name(self.text_color)

    @property
    def has_error(self):
        return self.error_1 != 0 or self.error_2 != 0


def request_status(fd, timeout, drain_first=True):
    if drain_first:
        drain(fd)
    write_all(fd, STATUS_COMMAND)
    return Status.from_bytes(read_exact(fd, STATUS_LENGTH, timeout))


def read_status(config, timeout=2.0):
    with ptouch_connection(config) as fd:
        return request_status(fd, timeout)


def format_status(status):
    return "\n".join(
        [
            f"raw:          {status.raw.hex()}",
            f"length:       {len(status.raw)}",
            f"header:       {status.header.hex()}",
            f"marker:       {status.marker.hex()}",
            f"model:        {status.model.hex()}",
            f"error_1:      0x{status.error_1:02x}",
            f"error_2:      0x{status.error_2:02x}",
            f"media_width:  0x{status.media_width:02x}",
            f"media_type:   0x{status.media_type:02x}",
            f"media_color:  0x{status.media_color:02x}",
            f"media_name:   {status.media_color_name}",
            f"text_color:   0x{status.text_color:02x}",
            f"text_name:    {status.text_color_name}",
        ]
    )
