import click

from ..status import format_status

from .common import pass_cli_context, printer_for, invoke_cli, CliContext


@click.command("status")
@click.option(
  "--debug",
  is_flag=True,
  help="Show raw status values alongside the resolved fields.",
)
@pass_cli_context
def status_command(cli: CliContext, debug: bool) -> None:
  status = invoke_cli(printer_for(cli).status)
  click.echo(format_status(status, debug=debug))
