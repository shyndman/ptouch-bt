from pathlib import Path

import click

from ..printer import ImageFit

from .common import (
  PrintContext,
  emit_prepared_image,
  emit_print_result,
  invoke_cli,
  pass_print_context,
  printer_for,
  save_preview_option,
)

FIT_VALUES = [fit.value for fit in ImageFit]


@click.command("image")
@click.argument("image", type=click.Path(path_type=Path, dir_okay=False))
@click.option(
  "--fit",
  default=ImageFit.CONTAIN.value,
  show_default=True,
  type=click.Choice(FIT_VALUES),
)
@click.option("--dither/--no-dither", default=True, show_default=True)
@click.option(
  "--threshold", default=128, show_default=True, type=click.IntRange(min=0, max=255)
)
@save_preview_option
@pass_print_context
def print_image_command(
  cli: PrintContext,
  image: Path,
  fit: str,
  dither: bool,
  threshold: int,
  save_preview: Path | None,
) -> None:
  printer = printer_for(cli.cli)
  image_fit = ImageFit(fit)
  if save_preview is not None:
    prepared = invoke_cli(
      printer.preview_image,
      image,
      fit=image_fit,
      dither=dither,
      threshold=threshold,
    )
    emit_prepared_image(prepared, save_preview)
    return

  result = invoke_cli(
    printer.print_image,
    image,
    finalize=cli.finalize,
    fit=image_fit,
    dither=dither,
    threshold=threshold,
  )
  emit_print_result(result)
