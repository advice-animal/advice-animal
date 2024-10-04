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
    runner = CliRunner()
    result = runner.invoke(main, ["list"])
    assert (
        "click_version_option : GREEN \nruff_show_source : YELLOW (preview)\nuse_py_typed : GREEN \n"
        in result.output
    )
    assert result.exit_code == 0
