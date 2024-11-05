import os

from advice_animal.cli import main
from click.testing import CliRunner


def test_smoke():
    runner = CliRunner()
    result = runner.invoke(main)
    assert result.exit_code == 0


def test_self_test():
    runner = CliRunner()
    result = runner.invoke(main, ["--selftest"])
    assert result.exit_code == 0


def test_check():
    runner = CliRunner()
    result = runner.invoke(main, ["-a"])
    assert result.exit_code == 0


def test_list():
    os.environ["ADVICE_DIR"] = "tests/advice"
    runner = CliRunner()
    result = runner.invoke(main, ["--preview"])
    assert "* pip-tools - (preview)\n* shouty\n" in result.output
    assert result.exit_code == 0
