from click.testing import CliRunner
from advice_animal.cli import main

def test_smoke():
    runner = CliRunner()
    result = runner.invoke(main)
    assert result.exit_code == 0

def test_self_test():
    runner = CliRunner()
    result = runner.invoke(main, ["selftest-advice"])
    assert result.exit_code == 0


def test_check():
    runner = CliRunner()
    result = runner.invoke(main, ["check", "."])
    assert result.exit_code == 0
