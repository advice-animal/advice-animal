from click.testing import CliRunner
from advice_animal.cli import main

def test_smoke():
    runner = CliRunner()
    result = runner.invoke(main)
    assert result.exit_code == 0
