import os
import subprocess
from pathlib import Path
from textwrap import dedent

from advice_animal.cli import main

from helpers import invoke

def test_smoke():
    result = invoke(main)
    assert result.exit_code == 0


def test_self_test():
    result = invoke(main, ["--selftest"])
    assert result.exit_code == 0

def test_bad_self_test(monkeypatch):
    monkeypatch.setenv("ADVICE_DIR", str(Path(__file__).parent / "bad_advice"))
    result = invoke(main, ["--selftest"])
    assert result.exit_code == 1
    assert result.output == dedent("""\
        --- a/new_file.txt
        +++ b/new_file.txt
        @@ -1 +0,0 @@
        -This is the file that doesn't get created.
        didnt_make_file          NOT DONE
        --- a/extra_file.txt
        +++ b/extra_file.txt
        @@ -0,0 +1 @@
        +I shouldn't be here
        made_extra_file          NOT DONE
        --- a/README.txt
        +++ b/README.txt
        @@ -1 +1 @@
        -Hi there.
        +Wrong
        wrong_contents           NOT DONE
        """)

def test_check(tmp_git):
    result = invoke(main, ["-a"])
    assert result.exit_code == 0


def test_list():
    result = invoke(main, ["--preview"])
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
    cur_dir = os.getcwd()
    try:
        os.chdir(tmp_path)
        result = invoke(main, ["-a", "--preview"])
        assert result.exit_code == 0
        assert result.output == "shouty: Changes made\npip-tools: No changes needed\n"
    finally:
        os.chdir(cur_dir)


def test_no_match(tmp_git):
    result = invoke(main, ["non_existent"])
    assert result.exit_code == 1
    assert (
        "No advices matched.\nAvailable advice:\n* shouty\n* pip-tools - (preview)\n"
        in result.output
    )
