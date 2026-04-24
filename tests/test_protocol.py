import unittest
from tempfile import TemporaryDirectory
from pathlib import Path

from PIL import Image

from ptouch_bt import (
  ConnectionConfig,
  FinalizeMode,
  ImageFit,
  LabelColor,
  MediaType,
  PTouchPrinter,
  Status,
  build_image_print_job,
  build_print_job,
  build_test_print_job,
  build_text_print_job,
  format_status,
  label_color_name,
  prepare_image,
  render_text_image,
)
from ptouch_bt.printer import packbits_raster_line, rasterline_setpixel, tape_width_px


class ProtocolTests(unittest.TestCase):
  def test_status_decodes_observed_response(self):
    status = Status.from_bytes(
      bytes.fromhex("802042307630000000000c010000000000000000000000000108000000000000")
    )

    self.assertEqual(status.header.hex(), "8020")
    self.assertEqual(status.marker.hex(), "4230")
    self.assertEqual(status.model.hex(), "7630")
    self.assertEqual(status.error_1, 0)
    self.assertEqual(status.error_2, 0)
    self.assertEqual(status.media_width, 12)
    self.assertEqual(status.media_width_mm, 12)
    self.assertEqual(status.media_type, 1)
    self.assertEqual(status.media_type_enum, MediaType.LAMINATE)
    self.assertEqual(status.media_type_name, "laminate")
    self.assertEqual(status.media_color, 1)
    self.assertEqual(status.text_color, 8)
    self.assertEqual(status.media_color_enum, LabelColor.WHITE)
    self.assertEqual(status.text_color_enum, LabelColor.BLACK)
    self.assertEqual(status.media_color_name, "white")
    self.assertEqual(status.text_color_name, "black")

    formatted = format_status(status)
    self.assertIn("media_mm:     12", formatted)
    self.assertIn("media_kind:   laminate", formatted)

  def test_status_and_config_are_pydantic_models(self):
    raw = bytes.fromhex(
      "802042307630000000000c010000000000000000000000000108000000000000"
    )

    self.assertEqual(Status.from_bytes(raw).model_dump(), {"raw": raw})
    self.assertEqual(
      ConnectionConfig().model_dump(),
      {
        "address": "BC:31:98:A0:59:EE",
        "channel": 1,
        "device": "/dev/rfcomm0",
      },
    )

  def test_unknown_label_color_maps_to_unsupported(self):
    self.assertEqual(label_color_name(999), "unsupport")

  def test_rasterline_bit_layout_matches_ptouch_print(self):
    rasterline = bytearray(16)

    rasterline_setpixel(rasterline, 0)
    rasterline_setpixel(rasterline, 64)
    rasterline_setpixel(rasterline, 127)

    self.assertEqual(rasterline.hex(), "80000000000000010000000000000001")

  def test_packbits_fake_uncompressed_line_shape(self):
    rasterline = bytes(range(16))

    self.assertEqual(
      packbits_raster_line(rasterline),
      bytes.fromhex("4711000f000102030405060708090a0b0c0d0e0f"),
    )

  def test_default_test_job_matches_proven_minimal_stream_shape(self):
    job = build_test_print_job(finalize=FinalizeMode.CHAIN)

    self.assertEqual(job.chunk_count, 28)
    self.assertEqual(job.byte_count, 589)
    self.assertEqual(job.chunks[0], (b"\x00" * 100) + b"\x1b\x40")
    self.assertEqual(job.chunks[1].hex(), "4d02")
    self.assertEqual(job.chunks[2].hex(), "1b695201")
    self.assertEqual(job.chunks[-1].hex(), "0c")

  def test_feed_cut_finalize_byte(self):
    job = build_test_print_job(finalize=FinalizeMode.FEED_CUT)

    self.assertEqual(job.chunks[-1].hex(), "1a")

  def test_text_and_image_share_print_job_path(self):
    text_image = render_text_image("Test", tape_width_px(12))
    image = Image.new("1", text_image.size, 1)

    text_job = build_print_job(text_image)
    image_job = build_print_job(image)

    self.assertEqual(text_job.chunk_count, image_job.chunk_count)
    self.assertEqual(text_job.chunks[0], image_job.chunks[0])
    self.assertEqual(text_job.chunks[1], image_job.chunks[1])
    self.assertEqual(text_job.chunks[2], image_job.chunks[2])
    self.assertEqual(text_job.chunks[-1], image_job.chunks[-1])

  def test_text_print_job_is_public_library_entrypoint(self):
    job = build_text_print_job("Text", tape_width_px(12), finalize=FinalizeMode.CHAIN)

    self.assertGreater(job.image.size[0], 0)
    self.assertEqual(job.image.size[1], 76)
    self.assertEqual(job.chunks[0], (b"\x00" * 100) + b"\x1b\x40")
    self.assertEqual(job.chunks[-1].hex(), "0c")
    self.assertEqual(job.to_bytes(), b"".join(job.chunks))

  def test_printer_builds_text_jobs_without_hardware(self):
    printer = PTouchPrinter()
    job = printer.text_job(
      "Text", tape_width=tape_width_px(12), finalize=FinalizeMode.FEED_CUT
    )

    self.assertEqual(job.image.size[1], 76)
    self.assertEqual(job.chunks[-1].hex(), "1a")

  def test_prepare_image_scales_height_to_tape_width(self):
    source = Image.new("L", (100, 152), 255)

    image = prepare_image(source, tape_width_px(12), dither=False)

    self.assertEqual(image.mode, "1")
    self.assertEqual(image.size, (50, 76))

  def test_prepare_image_none_fit_rejects_too_tall_image(self):
    source = Image.new("L", (10, 77), 255)

    with self.assertRaises(ValueError):
      prepare_image(source, tape_width_px(12), fit=ImageFit.NONE)

  def test_prepare_image_threshold_without_dither(self):
    source = Image.new("L", (2, 1))
    source.putdata([127, 128])

    image = prepare_image(source, tape_width_px(12), dither=False, threshold=128)

    self.assertEqual([image.getpixel((0, 0)), image.getpixel((1, 0))], [0, 255])

  def test_prepare_image_flattens_alpha_to_white(self):
    source = Image.new("RGBA", (2, 1), (0, 0, 0, 0))
    source.putpixel((1, 0), (0, 0, 0, 255))

    image = prepare_image(source, tape_width_px(12), dither=False)

    self.assertEqual([image.getpixel((0, 0)), image.getpixel((1, 0))], [255, 0])

  def test_image_print_job_accepts_path_like_source(self):
    with TemporaryDirectory() as directory:
      path = Path(directory) / "label.png"
      Image.new("L", (12, 8), 255).save(path)

      job = build_image_print_job(
        path, tape_width_px(12), finalize=FinalizeMode.CHAIN, dither=False
      )

    self.assertEqual(job.image.size, (12, 8))
    self.assertEqual(job.chunk_count, 16)
    self.assertEqual(job.chunks[-1].hex(), "0c")
    self.assertEqual(job.model_dump()["finalize"], FinalizeMode.CHAIN)

  def test_printer_builds_image_jobs_without_hardware(self):
    printer = PTouchPrinter()
    source = Image.new("L", (100, 152), 255)

    job = printer.image_job(
      source, tape_width=tape_width_px(12), finalize=FinalizeMode.FEED_CUT, dither=False
    )

    self.assertEqual(job.image.size, (50, 76))
    self.assertEqual(job.chunks[-1].hex(), "1a")
    self.assertEqual(job.model_dump()["finalize"], FinalizeMode.FEED_CUT)


if __name__ == "__main__":
  unittest.main()
