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
  PILImage,
  PrintJob,
  build_image_print_job,
  build_print_job,
  build_test_image,
  build_text_print_job,
  prepare_image,
  render_text_image,
  tape_width_px,
  write_print_job,
)
from .rfcomm import ConnectionConfig, ptouch_connection
from .status import Status, request_status

BuildImage: TypeAlias = Callable[[int], PILImage]


class PreparedImage(BaseModel):
  model_config: ClassVar[ConfigDict] = ConfigDict(
    frozen=True, arbitrary_types_allowed=True
  )

  status: Status
  image: PILImage


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

  def preview_text(
    self,
    text: str,
    *,
    font_path: FontPath | None = None,
    font_size: int = DEFAULT_TEXT_FONT_SIZE,
    margin: int = 4,
  ) -> PreparedImage:
    def build_image(tape_width: int) -> PILImage:
      return render_text_image(text, tape_width, font_path, font_size, margin)

    return self._prepare(build_image)

  def preview_image(
    self,
    image: ImageSource,
    *,
    fit: ImageFit = ImageFit.CONTAIN,
    dither: bool = True,
    threshold: int = 128,
  ) -> PreparedImage:
    def build_image(tape_width: int) -> PILImage:
      return prepare_image(
        image, tape_width, fit=fit, dither=dither, threshold=threshold
      )

    return self._prepare(build_image)

  def preview_test(
    self,
    columns: int = 24,
    mark_width: int = 8,
    mark_height: int = 8,
  ) -> PreparedImage:
    def build_image(tape_width: int) -> PILImage:
      self._validate_test_height(mark_height, tape_width)
      return build_test_image(columns, mark_width, mark_height)

    return self._prepare(build_image)

  def print_text(
    self,
    text: str,
    *,
    finalize: FinalizeMode = FinalizeMode.FEED_CUT,
    font_path: FontPath | None = None,
    font_size: int = DEFAULT_TEXT_FONT_SIZE,
    margin: int = 4,
  ) -> PrintResult:
    def build_image(tape_width: int) -> PILImage:
      return render_text_image(text, tape_width, font_path, font_size, margin)

    return self._print(build_image, finalize)

  def print_image(
    self,
    image: ImageSource,
    *,
    finalize: FinalizeMode = FinalizeMode.FEED_CUT,
    fit: ImageFit = ImageFit.CONTAIN,
    dither: bool = True,
    threshold: int = 128,
  ) -> PrintResult:
    def build_image(tape_width: int) -> PILImage:
      return prepare_image(
        image, tape_width, fit=fit, dither=dither, threshold=threshold
      )

    return self._print(build_image, finalize)

  def print_test(
    self,
    columns: int = 24,
    mark_width: int = 8,
    mark_height: int = 8,
    *,
    finalize: FinalizeMode = FinalizeMode.FEED_CUT,
  ) -> PrintResult:
    def build_image(tape_width: int) -> PILImage:
      self._validate_test_height(mark_height, tape_width)
      return build_test_image(columns, mark_width, mark_height)

    return self._print(build_image, finalize)

  def _prepare(self, build_image: BuildImage) -> PreparedImage:
    status = self.status()
    return PreparedImage(
      status=status,
      image=build_image(tape_width_px(status.media_width)),
    )

  def _print(self, build_image: BuildImage, finalize: FinalizeMode) -> PrintResult:
    with ptouch_connection(self.config) as fd:
      before = request_status(fd, self.timeout)
      if before.has_error:
        raise RuntimeError(
          f"before print: printer reports error 0x{before.error_1:02x} 0x{before.error_2:02x}"
        )

      job = build_print_job(
        build_image(tape_width_px(before.media_width)), finalize=finalize
      )
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

  def _validate_test_height(self, mark_height: int, tape_width: int) -> None:
    if mark_height > tape_width:
      raise ValueError(
        f"mark height {mark_height}px exceeds current tape printable width {tape_width}px"
      )
