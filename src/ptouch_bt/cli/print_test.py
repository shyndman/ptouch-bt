from pathlib import Path

import click

from ..printer import MAX_PIXELS

from .common import (
  PrintContext,
  emit_prepared_image,
  emit_print_result,
  invoke_cli,
  pass_print_context,
  printer_for,
  save_preview_option,
)


@click.command("test")
@click.option("--columns", default=24, show_default=True, type=click.IntRange(min=1))
@click.option("--mark-width", default=8, show_default=True, type=click.IntRange(min=1))
@click.option(
  "--mark-height",
  default=8,
  show_default=True,
  type=click.IntRange(min=1, max=MAX_PIXELS),
)
@save_preview_option
@pass_print_context
def print_test_command(
  cli: PrintContext,
  columns: int,
  mark_width: int,
  mark_height: int,
  save_preview: Path | None,
) -> None:
  printer = printer_for(cli.cli)
  if save_preview is not None:
    prepared = invoke_cli(
      printer.preview_test,
      columns=columns,
      mark_width=mark_width,
      mark_height=mark_height,
    )
    emit_prepared_image(prepared, save_preview)
    return

  result = invoke_cli(
    printer.print_test,
    columns=columns,
    mark_width=mark_width,
    mark_height=mark_height,
    finalize=cli.finalize,
  )
  emit_print_result(result)
