import os
import subprocess
from pathlib import Path

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


def test_check(tmp_git):
    runner = CliRunner()
    result = runner.invoke(main, ["-a"])
    assert result.exit_code == 0


def test_list():
    os.environ["ADVICE_DIR"] = "tests/advice"
    runner = CliRunner()
    result = runner.invoke(main, ["--preview"])
    assert "* shouty\n* pip-tools - (preview)\n" in result.output
    assert result.exit_code == 0


def test_apply(tmp_path):
    (tmp_path / "README.txt").write_text("Hello")
    (tmp_path / "pyproject.toml").write_text("")
    subprocess.check_call(
        ["git", "init", "--initial-branch", "fancy-branch"], cwd=tmp_path
    )
    subprocess.check_call(["git", "add", "-A"], cwd=tmp_path)
    subprocess.check_call(["git", "commit", "-m", "foo"], cwd=tmp_path)
    os.environ["ADVICE_DIR"] = str(Path(__file__).parent / "advice")
    cur_dir = os.getcwd()
    try:
        os.chdir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(main, ["-a", "--preview"])
        assert result.exit_code == 0
        assert result.output == "shouty: Changes made\npip-tools: No changes needed\n"
    finally:
        os.chdir(cur_dir)


def test_no_match(tmp_git):
    os.environ["ADVICE_DIR"] = str(Path(__file__).parent / "advice")
    runner = CliRunner()
    result = runner.invoke(main, ["non_existent"])
    assert result.exit_code == 1
    assert (
        "No advices matched.\nAvailable advice:\n* shouty\n* pip-tools - (preview)\n"
        in result.output
    )
