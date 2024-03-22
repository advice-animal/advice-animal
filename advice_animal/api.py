from __future__ import annotations

from pathlib import Path

from typing import Optional


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
        return func(*args, **kwargs)  # TODO


class Check:
    def __init__(self, env: Env) -> None:
        self.env = env

    def pred(self) -> bool:
        """
        Return true if this check wants to run.
        """
        raise NotImplementedError

    def apply(self, workdir: Path) -> None:
        """
        Apply this check's fix to the `workdir`, optionally using information
        from `self.env`.  Any added, modified, or deleted files will
        automatically be included in the branch.
        """
        pass
