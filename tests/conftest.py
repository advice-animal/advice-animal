import subprocess
from pathlib import Path

import pytest

@pytest.fixture()
def tmp_git(tmp_path, monkeypatch):

    monkeypatch.chdir(tmp_path)

    subprocess.run(["git", "init"])
    (tmp_path / "pyproject.toml").write_text("")
    subprocess.run(["git", "add", "pyproject.toml"])
    subprocess.run(["git", "commit", "-m", "initial"])
    yield tmp_path


@pytest.fixture(autouse=True)
def set_advice_dir(monkeypatch):
    """ADVICE_DIR should always default to our local test advice directory."""
    monkeypatch.setenv("ADVICE_DIR", str(Path(__file__).parent / "advice"))