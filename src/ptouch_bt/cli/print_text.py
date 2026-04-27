from pathlib import Path

import click

from ..printer import DEFAULT_TEXT_FONT_SIZE

from .common import (
  PrintContext,
  emit_prepared_image,
  emit_print_result,
  invoke_cli,
  pass_print_context,
  printer_for,
  save_preview_option,
)


@click.command("text")
@click.argument("text")
@click.option("--font", type=click.Path(path_type=Path, dir_okay=False))
@click.option(
  "--font-size",
  default=DEFAULT_TEXT_FONT_SIZE,
  show_default=True,
  type=click.IntRange(min=1),
)
@click.option("--margin", default=4, show_default=True, type=click.IntRange(min=0))
@save_preview_option
@pass_print_context
def print_text_command(
  cli: PrintContext,
  text: str,
  font: Path | None,
  font_size: int,
  margin: int,
  save_preview: Path | None,
) -> None:
  printer = printer_for(cli.cli)
  if save_preview is not None:
    prepared = invoke_cli(
      printer.preview_text,
      text,
      font_path=font,
      font_size=font_size,
      margin=margin,
    )
    emit_prepared_image(prepared, save_preview)
    return

  result = invoke_cli(
    printer.print_text,
    text,
    finalize=cli.finalize,
    font_path=font,
    font_size=font_size,
    margin=margin,
  )
  emit_print_result(result)
