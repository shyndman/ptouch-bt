import time
from collections.abc import Callable
from typing import ClassVar, TypeAlias

from pydantic import BaseModel, ConfigDict

from .printer import (
  DEFAULT_TEXT_FONT_SIZE,
  FinalizeMode,
  FontPath,
  ImageFit,
  ImageSource,
  PrintJob,
  build_image_print_job,
  build_text_print_job,
  tape_width_px,
  write_print_job,
)
from .rfcomm import ConnectionConfig, ptouch_connection
from .status import Status, request_status

BuildJob: TypeAlias = Callable[[int], PrintJob]


class PrintResult(BaseModel):
  model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

  before: Status
  after: Status | None
  after_error: str | None
  byte_count: int
  chunk_count: int
  finalize: FinalizeMode


class PTouchPrinter:
  config: ConnectionConfig
  timeout: float

  def __init__(
    self, config: ConnectionConfig | None = None, timeout: float = 2.0
  ) -> None:
    self.config = config or ConnectionConfig()
    self.timeout = timeout

  def status(self) -> Status:
    with ptouch_connection(self.config) as fd:
      return request_status(fd, self.timeout)

  def text_job(
    self,
    text: str,
    *,
    tape_width: int,
    finalize: FinalizeMode = FinalizeMode.FEED_CUT,
    font_path: FontPath | None = None,
    font_size: int = DEFAULT_TEXT_FONT_SIZE,
    margin: int = 4,
  ) -> PrintJob:
    return build_text_print_job(
      text,
      tape_width,
      finalize=finalize,
      font_path=font_path,
      font_size=font_size,
      margin=margin,
    )

  def image_job(
    self,
    image: ImageSource,
    *,
    tape_width: int,
    finalize: FinalizeMode = FinalizeMode.FEED_CUT,
    fit: ImageFit = ImageFit.CONTAIN,
    dither: bool = True,
    threshold: int = 128,
  ) -> PrintJob:
    return build_image_print_job(
      image,
      tape_width,
      finalize=finalize,
      fit=fit,
      dither=dither,
      threshold=threshold,
    )

  def print_text(
    self,
    text: str,
    *,
    finalize: FinalizeMode = FinalizeMode.FEED_CUT,
    font_path: FontPath | None = None,
    font_size: int = DEFAULT_TEXT_FONT_SIZE,
    margin: int = 4,
  ) -> PrintResult:
    def build_job(tape_width: int) -> PrintJob:
      return self.text_job(
        text,
        tape_width=tape_width,
        finalize=finalize,
        font_path=font_path,
        font_size=font_size,
        margin=margin,
      )

    return self._print(build_job)

  def print_image(
    self,
    image: ImageSource,
    *,
    finalize: FinalizeMode = FinalizeMode.FEED_CUT,
    fit: ImageFit = ImageFit.CONTAIN,
    dither: bool = True,
    threshold: int = 128,
  ) -> PrintResult:
    def build_job(tape_width: int) -> PrintJob:
      return self.image_job(
        image,
        tape_width=tape_width,
        finalize=finalize,
        fit=fit,
        dither=dither,
        threshold=threshold,
      )

    return self._print(build_job)

  def _print(self, build_job: BuildJob) -> PrintResult:
    with ptouch_connection(self.config) as fd:
      before = request_status(fd, self.timeout)
      if before.has_error:
        raise RuntimeError(
          f"before print: printer reports error 0x{before.error_1:02x} 0x{before.error_2:02x}"
        )

      job = build_job(tape_width_px(before.media_width))
      byte_count, chunk_count = write_print_job(fd, job.chunks)

      after: Status | None = None
      after_error: str | None = None
      time.sleep(0.5)
      try:
        after = request_status(fd, self.timeout, drain_first=False)
      except Exception as error:
        after_error = str(error)

      return PrintResult(
        before=before,
        after=after,
        after_error=after_error,
        byte_count=byte_count,
        chunk_count=chunk_count,
        finalize=job.finalize,
      )
