from pathlib import Path

import pytest
from advice_animal.api import Env
from click import ClickException


def test_find_py_projects(tmp_path):
    # Create a folder with .gitignore
    (tmp_path / ".gitignore").write_text("*.pyc\nvar/\n")
    with pytest.raises(ClickException):
        e = Env(tmp_path)

    # Create sub-folders with setup.py and pyproject.toml
    (tmp_path / "proj_a").mkdir()
    (tmp_path / "proj_b").mkdir()
    (tmp_path / "proj_a" / "setup.py").touch()
    (tmp_path / "proj_b" / "pyproject.toml").touch()

    e = Env(tmp_path)
    py_projects = e.find_py_projects()
    assert sorted(py_projects) == [Path("proj_a"), Path("proj_b")]


def test_ignored_files(tmp_path):
    # Check if ignored files are ignored correctly
    (tmp_path / "var" / "proj_a").mkdir(parents=True)
    (tmp_path / "var" / "proj_a" / "setup.py").touch()
    (tmp_path / "var" / "proj_b").mkdir(parents=True)
    (tmp_path / "var" / "proj_b" / "setup.py").touch()
    (tmp_path / "var" / ".gitignore").write_text("proj_b\nvar/\n")

    e = Env(tmp_path / "var")
    py_projects = e.find_py_projects()
    assert py_projects == [Path("proj_a")]
