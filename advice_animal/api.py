from __future__ import annotations

import logging
from enum import IntEnum
from pathlib import Path
from typing import Optional

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


def infer_python_versions(path: Path) -> list[str]:
    """
    Read the "most authoritative" python version(s) to allow fixes to ensure
    those are mirrored e.g. in CI.
    """


class Env:
    def __init__(self, path: Path) -> None:
        # The (read-only) path representing this environment
        self.path = path

        # A relative path (or None) to a top-level python dir
        self.top_level_dir: Optional[Path] = infer_top_level_dir(path)

        # Intended to be overridden, the python versions for this env that can
        # be inferred from other config.
        self.python_versions = infer_python_versions(path)

    def get(self, func, *args, **kwargs):
        """
        Basicalize a memoize decorator but one whose cache lifetime is tied to
        the Env, and doesn't require all functions to be known in advance.
        """
        LOG.log(VLOG_2, "get %s", func.__qualname__)
        return func(*args, **kwargs)  # TODO


class FixConfidence(IntEnum):
    UNSET = 0
    RED = 10
    YELLOW = 20
    GREEN = 30


class BaseCheck:
    """
    This is the main class that you subclass to propose your own fixes.

    Depending on what the Workflow does, this might run apply in the user-provided dir or a tempdir.
    """

    confidence: FixConfidence = FixConfidence.UNSET

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
