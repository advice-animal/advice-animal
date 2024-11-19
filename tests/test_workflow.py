from pathlib import Path
from advice_animal.workflow import files

def test_files_ignore_some_dots(tmp_path):
    (tmp_path / ".DS_Store").touch()
    (tmp_path / ".foo.swp").touch()
    (tmp_path / ".pre-commit-config.yaml").touch()
    (tmp_path / "foo").touch()
    filenames = set(files(tmp_path))
    assert filenames == {Path(".pre-commit-config.yaml"), Path("foo")}
