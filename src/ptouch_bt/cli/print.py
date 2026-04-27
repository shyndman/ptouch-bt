import click

from .common import CliContext, build_print_context
from .print_image import print_image_command
from .print_test import print_test_command
from .print_text import print_text_command


@click.group("print")
@click.option(
  "--chain",
  is_flag=True,
  help="Use chain/no-cut finalize 0x0c instead of feed/cut 0x1a.",
)
@click.pass_context
def print_group(ctx: click.Context, chain: bool) -> None:
  cli = ctx.find_object(CliContext)
  if cli is None:
    raise click.ClickException("missing CLI context")
  ctx.obj = build_print_context(cli, chain)


print_group.add_command(print_text_command)
print_group.add_command(print_image_command)
print_group.add_command(print_test_command)
