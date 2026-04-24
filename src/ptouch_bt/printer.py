from enum import Enum
from pathlib import Path
from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageFont

from .rfcomm import write_all

MAX_PIXELS = 128
RASTER_BYTES = MAX_PIXELS // 8
DEFAULT_FONT = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
DEFAULT_TEXT_FONT_SIZE = 22
TAPE_WIDTHS_PX = {
    4: 24,
    6: 32,
    9: 52,
    12: 76,
    18: 120,
    21: 124,
    24: 128,
    36: 192,
}

INIT_COMMAND = (b"\x00" * 100) + b"\x1b\x40"
PACKBITS_COMMAND = bytes.fromhex("4d02")
RASTER_MODE_COMMAND = bytes.fromhex("1b695201")
CHAIN_FINALIZE_COMMAND = b"\x0c"
FEED_FINALIZE_COMMAND = b"\x1a"


class FinalizeMode(Enum):
    CHAIN = "chain"
    FEED_CUT = "feed_cut"

    @property
    def command(self):
        if self is FinalizeMode.CHAIN:
            return CHAIN_FINALIZE_COMMAND
        return FEED_FINALIZE_COMMAND

    @property
    def label(self):
        if self is FinalizeMode.CHAIN:
            return "chain/no-cut 0x0c"
        return "feed/cut 0x1a"


class ImageFit(Enum):
    CONTAIN = "contain"
    NONE = "none"


@dataclass(frozen=True)
class PrintJob:
    chunks: tuple
    image: Image.Image
    finalize: FinalizeMode

    @property
    def byte_count(self):
        return sum(len(chunk) for chunk in self.chunks)

    @property
    def chunk_count(self):
        return len(self.chunks)

    def to_bytes(self):
        return b"".join(self.chunks)


def rasterline_setpixel(rasterline, pixel):
    if pixel < 0 or pixel >= len(rasterline) * 8:
        return
    rasterline[(len(rasterline) - 1) - (pixel // 8)] |= 1 << (pixel % 8)


def packbits_raster_line(rasterline):
    return bytes([0x47, len(rasterline) + 1, 0x00, len(rasterline) - 1]) + bytes(rasterline)


def load_image(source):
    if isinstance(source, Image.Image):
        return source.copy()
    with Image.open(source) as image:
        return image.copy()


def coerce_image_fit(fit):
    if isinstance(fit, ImageFit):
        return fit
    return ImageFit(fit)


def grayscale_image(image):
    if image.mode in ("RGBA", "LA") or "transparency" in image.info:
        rgba = image.convert("RGBA")
        background = Image.new("RGBA", rgba.size, "white")
        background.alpha_composite(rgba)
        return background.convert("L")
    return image.convert("L")


def resize_to_fit_tape(image, tape_width, fit=ImageFit.CONTAIN):
    if tape_width < 1:
        raise ValueError("tape width must be at least 1px")

    fit = coerce_image_fit(fit)
    width, height = image.size
    if width < 1 or height < 1:
        raise ValueError("image must not be empty")

    printable_height = min(tape_width, MAX_PIXELS)
    if height <= printable_height:
        return image

    if fit is ImageFit.NONE:
        raise ValueError(f"image height {height}px exceeds tape printable width {printable_height}px")

    scale = printable_height / height
    resized_width = max(1, round(width * scale))
    return image.resize((resized_width, printable_height), Image.Resampling.LANCZOS)


def monochrome_image(image, *, dither=True, threshold=128):
    if threshold < 0 or threshold > 255:
        raise ValueError("threshold must be between 0 and 255")
    if dither:
        return image.convert("1", dither=Image.Dither.FLOYDSTEINBERG)
    return image.point(lambda pixel: 0 if pixel < threshold else 255, "1")


def prepare_image(source, tape_width, *, fit=ImageFit.CONTAIN, dither=True, threshold=128):
    image = grayscale_image(load_image(source))
    image = resize_to_fit_tape(image, tape_width, fit)
    return monochrome_image(image, dither=dither, threshold=threshold)


def image_to_raster_chunks(image):
    bitmap = image.convert("1")
    width, height = bitmap.size
    if height > MAX_PIXELS:
        raise ValueError(f"image height {height}px exceeds printer max {MAX_PIXELS}px")

    vertical_offset = (MAX_PIXELS // 2) - (height // 2)
    pixels = bitmap.load()

    for x in range(width):
        rasterline = bytearray(RASTER_BYTES)
        for i in range(height):
            y = height - 1 - i
            if pixels[x, y] == 0:
                rasterline_setpixel(rasterline, vertical_offset + i)
        yield packbits_raster_line(rasterline)


def build_print_job(image, finalize=FinalizeMode.FEED_CUT):
    chunks = (
        INIT_COMMAND,
        PACKBITS_COMMAND,
        RASTER_MODE_COMMAND,
        *image_to_raster_chunks(image),
        finalize.command,
    )
    return PrintJob(chunks, image, finalize)


def build_image_print_job(source, tape_width, finalize=FinalizeMode.FEED_CUT, *, fit=ImageFit.CONTAIN, dither=True, threshold=128):
    return build_print_job(prepare_image(source, tape_width, fit=fit, dither=dither, threshold=threshold), finalize)


def write_print_job(fd, chunks):
    for chunk in chunks:
        write_all(fd, chunk)
    return sum(len(chunk) for chunk in chunks), len(chunks)


def build_test_image(columns=24, mark_width=8, mark_height=8):
    if columns < 1:
        raise ValueError("columns must be at least 1")
    if mark_width < 1 or mark_width > columns:
        raise ValueError("mark_width must be between 1 and columns")
    if mark_height < 1 or mark_height > MAX_PIXELS:
        raise ValueError(f"mark_height must be between 1 and {MAX_PIXELS}")

    image = Image.new("1", (columns, mark_height), 1)
    draw = ImageDraw.Draw(image)
    mark_start = (columns - mark_width) // 2
    draw.rectangle((mark_start, 0, mark_start + mark_width - 1, mark_height - 1), fill=0)
    return image


def build_test_print_job(columns=24, mark_width=8, mark_height=8, finalize=FinalizeMode.CHAIN):
    return build_print_job(build_test_image(columns, mark_width, mark_height), finalize)


def build_text_print_job(text, tape_width, finalize=FinalizeMode.FEED_CUT, font_path=None, font_size=DEFAULT_TEXT_FONT_SIZE, margin=4):
    return build_print_job(render_text_image(text, tape_width, font_path, font_size, margin), finalize)


def render_text_image(text, tape_width_px, font_path=DEFAULT_FONT, font_size=DEFAULT_TEXT_FONT_SIZE, margin=4):
    if not text:
        raise ValueError("text must not be empty")
    if tape_width_px <= margin * 2:
        raise ValueError(f"tape width {tape_width_px}px leaves no room after {margin}px margins")

    font_path = Path(font_path or DEFAULT_FONT)
    while font_size > 1:
        font = ImageFont.truetype(str(font_path), font_size)
        bbox = ImageDraw.Draw(Image.new("1", (1, 1), 1)).textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        if text_height <= tape_width_px - (margin * 2):
            break
        font_size -= 1
    else:
        raise ValueError("could not fit text on tape")

    image = Image.new("1", (text_width + margin * 2, tape_width_px), 1)
    draw = ImageDraw.Draw(image)
    y = (tape_width_px - text_height) // 2 - bbox[1]
    draw.text((margin - bbox[0], y), text, font=font, fill=0)
    return image


def tape_width_px(media_width):
    width = TAPE_WIDTHS_PX.get(media_width)
    if width is None:
        raise ValueError(f"unknown tape width {media_width}mm")
    return width
