import time
from dataclasses import dataclass

from .printer import DEFAULT_TEXT_FONT_SIZE, FinalizeMode, ImageFit, build_image_print_job, build_text_print_job, tape_width_px, write_print_job
from .rfcomm import ConnectionConfig, ptouch_connection
from .status import request_status


@dataclass(frozen=True)
class PrintResult:
    before: object
    after: object
    after_error: str
    byte_count: int
    chunk_count: int
    finalize: FinalizeMode


class PTouchPrinter:
    def __init__(self, config=ConnectionConfig(), timeout=2.0):
        self.config = config
        self.timeout = timeout

    def status(self):
        with ptouch_connection(self.config) as fd:
            return request_status(fd, self.timeout)

    def text_job(self, text, *, tape_width, finalize=FinalizeMode.FEED_CUT, font_path=None, font_size=DEFAULT_TEXT_FONT_SIZE, margin=4):
        return build_text_print_job(
            text,
            tape_width,
            finalize=finalize,
            font_path=font_path,
            font_size=font_size,
            margin=margin,
        )

    def image_job(self, image, *, tape_width, finalize=FinalizeMode.FEED_CUT, fit=ImageFit.CONTAIN, dither=True, threshold=128):
        return build_image_print_job(
            image,
            tape_width,
            finalize=finalize,
            fit=fit,
            dither=dither,
            threshold=threshold,
        )

    def print_text(self, text, *, finalize=FinalizeMode.FEED_CUT, font_path=None, font_size=DEFAULT_TEXT_FONT_SIZE, margin=4):
        return self._print(lambda tape_width: self.text_job(
            text,
            tape_width=tape_width,
            finalize=finalize,
            font_path=font_path,
            font_size=font_size,
            margin=margin,
        ))

    def print_image(self, image, *, finalize=FinalizeMode.FEED_CUT, fit=ImageFit.CONTAIN, dither=True, threshold=128):
        return self._print(lambda tape_width: self.image_job(
            image,
            tape_width=tape_width,
            finalize=finalize,
            fit=fit,
            dither=dither,
            threshold=threshold,
        ))

    def _print(self, build_job):
        with ptouch_connection(self.config) as fd:
            before = request_status(fd, self.timeout)
            if before.has_error:
                raise RuntimeError(f"before print: printer reports error 0x{before.error_1:02x} 0x{before.error_2:02x}")

            job = build_job(tape_width_px(before.media_width))
            byte_count, chunk_count = write_print_job(fd, job.chunks)

            after = None
            after_error = None
            time.sleep(0.5)
            try:
                after = request_status(fd, self.timeout, drain_first=False)
            except Exception as error:
                after_error = str(error)

            return PrintResult(before, after, after_error, byte_count, chunk_count, job.finalize)
