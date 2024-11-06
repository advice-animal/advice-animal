import subprocess
import pytest

@pytest.fixture()
def tmp_git(tmp_path, monkeypatch):

    monkeypatch.chdir(tmp_path)

    subprocess.run(["git", "init"])
    (tmp_path / "pyproject.toml").write_text("")
    subprocess.run(["git", "add", "pyproject.toml"])
    subprocess.run(["git", "commit", "-m", "initial"])
    yield tmp_path
