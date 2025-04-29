import traceback

from click.testing import CliRunner


def invoke(cli, args=None, catch_exceptions=True):
    if args is None:
        args = []
    runner = CliRunner()
    result = runner.invoke(cli, args, catch_exceptions=catch_exceptions)
    print(result.stdout, end="")
    if result.exception:
        traceback.print_exception(
            None, result.exception, result.exception.__traceback__
        )
    return result