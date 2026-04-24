from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import ClassVar, cast

from pydantic import BaseModel, ConfigDict, model_validator

from .media import (
  LabelColor,
  MediaType,
  label_color as _label_color,
  label_color_name as _label_color_name,
  media_type as _media_type,
  media_type_name as _media_type_name,
)
from .rfcomm import (
  ConnectionConfig,
  drain as _drain,
  ptouch_connection as _ptouch_connection,
  read_exact as _read_exact,
  write_all as _write_all,
)

STATUS_COMMAND = bytes.fromhex("1b6953")
STATUS_LENGTH = 32

LabelColorLookup = Callable[[int], LabelColor]
MediaTypeLookup = Callable[[int], MediaType]
ColorNameLookup = Callable[[int], str]
MediaNameLookup = Callable[[int], str]
Drain = Callable[[int], None]
ReadExact = Callable[[int, int, float], bytes]
WriteAll = Callable[[int, bytes], None]
PtouchConnection = Callable[[ConnectionConfig], AbstractContextManager[int]]

label_color = cast(LabelColorLookup, _label_color)
label_color_name = cast(ColorNameLookup, _label_color_name)
media_type = cast(MediaTypeLookup, _media_type)
media_type_name = cast(MediaNameLookup, _media_type_name)
drain = cast(Drain, _drain)
read_exact = cast(ReadExact, _read_exact)
write_all = cast(WriteAll, _write_all)
ptouch_connection = cast(PtouchConnection, _ptouch_connection)


class Status(BaseModel):
  model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

  raw: bytes

  @model_validator(mode="after")
  def validate_raw(self) -> "Status":
    if len(self.raw) != STATUS_LENGTH:
      raise ValueError(
        f"expected {STATUS_LENGTH} bytes, got {len(self.raw)}: {self.raw.hex()}"
      )
    return self

  @classmethod
  def from_bytes(cls, raw: bytes) -> "Status":
    return cls(raw=raw)

  @property
  def header(self) -> bytes:
    return self.raw[0:2]

  @property
  def marker(self) -> bytes:
    return self.raw[2:4]

  @property
  def model(self) -> bytes:
    return self.raw[4:6]

  @property
  def error_1(self) -> int:
    return self.raw[8]

  @property
  def error_2(self) -> int:
    return self.raw[9]

  @property
  def media_width(self) -> int:
    return self.raw[10]

  @property
  def media_type(self) -> int:
    return self.raw[11]

  @property
  def media_type_enum(self) -> MediaType:
    return media_type(self.media_type)

  @property
  def media_type_name(self) -> str:
    return media_type_name(self.media_type)

  @property
  def media_width_mm(self) -> int:
    return self.media_width

  @property
  def media_color(self) -> int:
    return self.raw[24]

  @property
  def media_color_enum(self) -> LabelColor:
    return label_color(self.media_color)

  @property
  def media_color_name(self) -> str:
    return label_color_name(self.media_color)

  @property
  def text_color(self) -> int:
    return self.raw[25]

  @property
  def text_color_enum(self) -> LabelColor:
    return label_color(self.text_color)

  @property
  def text_color_name(self) -> str:
    return label_color_name(self.text_color)

  @property
  def has_error(self) -> bool:
    return self.error_1 != 0 or self.error_2 != 0


def request_status(fd: int, timeout: float, drain_first: bool = True) -> Status:
  if drain_first:
    drain(fd)
  write_all(fd, STATUS_COMMAND)
  return Status.from_bytes(read_exact(fd, STATUS_LENGTH, timeout))


def read_status(config: ConnectionConfig, timeout: float = 2.0) -> Status:
  with ptouch_connection(config) as fd:
    return request_status(fd, timeout)


def format_status(status: Status) -> str:
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
      f"media_mm:     {status.media_width_mm}",
      f"media_type:   0x{status.media_type:02x}",
      f"media_kind:   {status.media_type_name}",
      f"media_color:  0x{status.media_color:02x}",
      f"media_name:   {status.media_color_name}",
      f"text_color:   0x{status.text_color:02x}",
      f"text_name:    {status.text_color_name}",
    ]
  )
