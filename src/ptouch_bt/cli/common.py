from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import ParamSpec, TypeVar

import click

from ..client import PTouchPrinter, PreparedImage, PrintResult
from ..printer import FinalizeMode
from ..rfcomm import ConnectionConfig
from ..status import format_status

P = ParamSpec("P")
T = TypeVar("T")
F = TypeVar("F", bound=Callable[..., object])


@dataclass(frozen=True)
class CliContext:
  connection: ConnectionConfig
  timeout: float


@dataclass(frozen=True)
class PrintContext:
  cli: CliContext
  finalize: FinalizeMode


pass_cli_context = click.make_pass_decorator(CliContext)
pass_print_context = click.make_pass_decorator(PrintContext)


def build_cli_context(
  *, device: str, address: str, channel: int, timeout: float
) -> CliContext:
  return CliContext(
    connection=ConnectionConfig(device=device, address=address, channel=channel),
    timeout=timeout,
  )


def build_print_context(cli: CliContext, chain: bool) -> PrintContext:
  finalize = FinalizeMode.CHAIN if chain else FinalizeMode.FEED_CUT
  return PrintContext(cli=cli, finalize=finalize)


def printer_for(cli: CliContext) -> PTouchPrinter:
  return PTouchPrinter(cli.connection, timeout=cli.timeout)


def invoke_cli(callback: Callable[P, T], /, *args: P.args, **kwargs: P.kwargs) -> T:
  try:
    return callback(*args, **kwargs)
  except Exception as error:
    raise click.ClickException(str(error)) from error


def save_preview_option(function: F) -> F:
  return click.option(
    "--save-preview",
    type=click.Path(path_type=Path, dir_okay=False),
    help="Save the prepared 1-bit preview instead of printing.",
  )(function)


def emit_prepared_image(prepared: PreparedImage, path: Path) -> None:
  prepared.image.save(path)
  click.echo(f"saved preview: {path}")


def emit_print_result(result: PrintResult) -> None:
  click.echo("before print:")
  click.echo(format_status(result.before))
  click.echo(f"sent:         {result.byte_count} bytes in {result.chunk_count} chunks")
  click.echo(f"finalize:     {result.finalize.label}")
  if result.after is not None:
    click.echo("after print:")
    click.echo(format_status(result.after))
    return
  click.echo(f"after print:  status unavailable: {result.after_error}")
