from __future__ import annotations

import logging
import os
from enum import IntEnum
from pathlib import Path
from typing import Optional

from click import ClickException
from pathspec import PathSpec
from pathspec.patterns.gitwildmatch import GitWildMatchPattern
from vmodule import VLOG_2

LOG = logging.getLogger(__name__)


def infer_top_level_dir(path: Path) -> Optional[Path]:
    """
    Extremely rough guess at a relative path to the (a) top-level python dir.
    """
    try:
        return next(path.glob("src/*")).relative_to(path)
    except StopIteration:
        try:
            return next(path.glob("*/__init__.py")).parent.relative_to(path)
        except StopIteration:
            return None


class Env:
    def __init__(self, path: Path) -> None:
        # The (read-only) path representing this environment
        self.path = path
        self.next_steps: list[str] = []

        # A relative path (or None) to a top-level python dir
        self.top_level_dir: Optional[Path] = infer_top_level_dir(path)

        self.repo_root = self._find_repo_root()
        self.py_projects = self.find_py_projects()

    def get(self, func, *args, **kwargs):  # type: ignore[no-untyped-def]
        """
        Basicalize a memoize decorator but one whose cache lifetime is tied to
        the Env, and doesn't require all functions to be known in advance.
        """
        LOG.log(VLOG_2, "get %s", func.__qualname__)
        return func(*args, **kwargs)  # TODO

    def find_py_projects(self) -> list[Path]:
        """
        Find every project in a mono-repo (or not).
        """
        # A mono-repo may contain multiple projects.
        # The project root is  a directory containing a setup.py or pyproject.toml.
        project_indicators = {"setup.py", "pyproject.toml"}
        projects = []
        root = self.repo_root
        ignore = self.gitignore(root) + PathSpec.from_lines(
            GitWildMatchPattern, ["__pycache__", "*.egg-info", "*.dist-info", ".venv"]
        )

        for dirpath, dirnames, filenames in os.walk(self.path):
            # Ignore directories that are ignored by .gitignore.
            if ignore.match_file(Path(dirpath).resolve().relative_to(root)):
                # Don't go any deeper into a directory that is ignored.
                dirnames.clear()
                continue

            # If we find a project indicator, we've found a project.
            if project_indicators.intersection(filenames):
                projects.append(Path(dirpath).resolve().relative_to(root))
                # Don't go any deeper into this directory.
                dirnames.clear()

        if not projects:
            raise ClickException("No python projects found in repo")
        return projects

    def _find_repo_root(self) -> Path:
        """
        Find the project root, looking upward from the given path.

        Looks through all parent paths until either the root is reached, or a directory
        is found that contains any of :attr:`ROOT_MARKERS`.
        """
        root_markers: list[Path] = [Path(".git"), Path(".hg")]
        real_path = self.path.resolve()

        parents = list(real_path.parents)
        if real_path.is_dir():
            parents.insert(0, real_path)

        for parent in parents:
            if any((parent / marker).exists() for marker in root_markers):
                return parent

        return self.path.resolve()

    @staticmethod
    def gitignore(path: Path) -> PathSpec:
        """
        Generate a `PathSpec` object for a .gitignore file in the given directory.

        If none is found, an empty PathSpec is returned. If the path is not a directory,
        `ValueError` is raised.
        """
        if not path.is_dir():
            raise ValueError(f"path {path} not a directory")

        gi_path = path / ".gitignore"

        if gi_path.is_file():
            lines = gi_path.read_text().splitlines()
        else:
            lines = []

        return PathSpec.from_lines(GitWildMatchPattern, lines)


class FixConfidence(IntEnum):
    UNSET = 0
    RED = 10
    YELLOW = 20
    GREEN = 30


class Mode(IntEnum):
    check = 10
    diff = 20
    apply = 30


class BaseCheck:
    """
    This is the main class that you subclass to propose your own fixes.

    Depending on what the Workflow does, this might run apply in the user-provided dir or a tempdir.
    """

    confidence: FixConfidence = FixConfidence.UNSET
    order: int = 50

    # Setting either of these requires extra user intent to run, within the confidence band.
    manual: bool = False
    preview: bool = False

    def __init__(self, env: Env) -> None:
        self.env = env

    def check(self) -> bool:
        """
        Return true if this check wants to run.
        """
        raise NotImplementedError

    def apply(self, workdir: Path) -> None:
        """
        Apply this check's fix to the `workdir`, optionally using information
        from `self.env`.  Assume that if a commit is being made by the Workflow
        that any added, modified, or deleted files will automatically be
        included (you should not generally use scm commands here).
        """
        raise NotImplementedError

    def run(self) -> bool:
        """
        Intended for sub-classing. Apply this check's fix in `self.env`.

        Return value is whether it made changes.

        Assume that if a commit is being made that any added, modified or deleted files will
        automatically be included (you should not generally use scm commands here).
        """
        if self.check():
            self.apply(self.env.path)
            return True
        return False
