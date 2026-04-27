from pathlib import Path

import click

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
@save_preview_option
@pass_print_context
def print_test_command(
  cli: PrintContext,
  save_preview: Path | None,
) -> None:
  printer = printer_for(cli.cli)
  if save_preview is not None:
    prepared = invoke_cli(printer.preview_test)
    emit_prepared_image(prepared, save_preview)
    return

  result = invoke_cli(printer.print_test, finalize=cli.finalize)
  emit_print_result(result)
