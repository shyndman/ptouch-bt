import click

from ..rfcomm import ConnectionConfig

from .common import build_cli_context
from .print import print_group
from .status import status_command

DEFAULT_CONFIG = ConnectionConfig()


@click.group()
@click.option("--device", default=DEFAULT_CONFIG.device, show_default=True)
@click.option("--address", default=DEFAULT_CONFIG.address, show_default=True)
@click.option("--channel", default=DEFAULT_CONFIG.channel, show_default=True, type=int)
@click.option("--timeout", default=2.0, show_default=True, type=float)
@click.pass_context
def cli(
  ctx: click.Context, device: str, address: str, channel: int, timeout: float
) -> None:
  ctx.obj = build_cli_context(
    device=device,
    address=address,
    channel=channel,
    timeout=timeout,
  )


cli.add_command(status_command)
cli.add_command(print_group)
