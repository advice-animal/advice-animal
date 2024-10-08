import os

from advice_animal.cli import main
from click.testing import CliRunner


def test_smoke():
    runner = CliRunner()
    result = runner.invoke(main)
    assert result.exit_code == 0


def test_self_test():
    runner = CliRunner()
    result = runner.invoke(main, ["self", "test"])
    assert result.exit_code == 0


def test_self_check():
    runner = CliRunner()
    result = runner.invoke(main, ["check", "."])
    assert result.exit_code == 0


def test_list():
    os.environ["ADVICE_DIR"] = "tests/advice"
    runner = CliRunner()
    result = runner.invoke(main, ["list"])
    assert "pip-tools - (preview)\nshouty\n" in result.output
    assert result.exit_code == 0
