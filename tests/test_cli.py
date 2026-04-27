import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from PIL import Image
from click.testing import CliRunner

from ptouch_bt import FinalizeMode, PTouchPrinter, PreparedImage, PrintResult, Status
from ptouch_bt.cli import cli

RAW_STATUS = bytes.fromhex(
  "802042307630000000000c010000000000000000000000000108000000000000"
)


def sample_status() -> Status:
  return Status.from_bytes(RAW_STATUS)


def sample_result(
  finalize: FinalizeMode = FinalizeMode.FEED_CUT,
) -> PrintResult:
  status = sample_status()
  return PrintResult(
    before=status,
    after=status,
    after_error=None,
    byte_count=123,
    chunk_count=4,
    finalize=finalize,
  )


class CliTests(unittest.TestCase):
  def setUp(self) -> None:
    self.runner = CliRunner()

  def test_root_help_lists_top_level_commands(self):
    result = self.runner.invoke(cli, ["--help"])

    self.assertEqual(result.exit_code, 0)
    self.assertIn("status", result.output)
    self.assertIn("print", result.output)

  def test_print_help_lists_leaf_commands(self):
    result = self.runner.invoke(cli, ["print", "--help"])

    self.assertEqual(result.exit_code, 0)
    self.assertIn("text", result.output)
    self.assertIn("image", result.output)
    self.assertIn("test", result.output)

  def test_status_command_formats_status(self):
    with patch.object(
      PTouchPrinter, "status", autospec=True, return_value=sample_status()
    ):
      result = self.runner.invoke(cli, ["status"])

    self.assertEqual(result.exit_code, 0)
    self.assertIn("Printer status", result.output)
    self.assertIn("Tape width:    12 mm", result.output)
    self.assertNotIn("Raw:", result.output)

  def test_status_command_debug_includes_raw_values(self):
    with patch.object(
      PTouchPrinter, "status", autospec=True, return_value=sample_status()
    ):
      result = self.runner.invoke(cli, ["status", "--debug"])

    self.assertEqual(result.exit_code, 0)
    self.assertIn("Tape width:    12 mm (0x0c)", result.output)
    self.assertIn(
      "Raw:           802042307630000000000c010000000000000000000000000108000000000000",
      result.output,
    )

  def test_text_preview_saves_image_without_printing(self):
    prepared = PreparedImage(status=sample_status(), image=Image.new("1", (4, 76), 1))

    with TemporaryDirectory() as directory:
      output = Path(directory) / "preview.png"

      with (
        patch.object(
          PTouchPrinter,
          "preview_text",
          autospec=True,
          return_value=prepared,
        ) as preview_text,
        patch.object(PTouchPrinter, "print_text", autospec=True) as print_text,
      ):
        result = self.runner.invoke(
          cli,
          ["print", "text", "Hello", "--save-preview", str(output)],
        )

      self.assertEqual(result.exit_code, 0)
      self.assertTrue(output.exists())
      self.assertIn(f"saved preview: {output}", result.output)
      preview_text.assert_called_once()
      print_text.assert_not_called()

  def test_chain_flag_flows_into_text_print(self):
    with patch.object(
      PTouchPrinter,
      "print_text",
      autospec=True,
      return_value=sample_result(FinalizeMode.CHAIN),
    ) as print_text:
      result = self.runner.invoke(cli, ["print", "--chain", "text", "Hello"])

    self.assertEqual(result.exit_code, 0)
    self.assertIn("finalize:     chain/no-cut 0x0c", result.output)
    self.assertEqual(print_text.call_args.kwargs["finalize"], FinalizeMode.CHAIN)

  def test_default_text_print_uses_feed_cut(self):
    with patch.object(
      PTouchPrinter,
      "print_text",
      autospec=True,
      return_value=sample_result(),
    ) as print_text:
      result = self.runner.invoke(cli, ["print", "text", "Hello"])

    self.assertEqual(result.exit_code, 0)
    self.assertIn("finalize:     feed/cut 0x1a", result.output)
    self.assertEqual(print_text.call_args.kwargs["finalize"], FinalizeMode.FEED_CUT)


if __name__ == "__main__":
  unittest.main()
