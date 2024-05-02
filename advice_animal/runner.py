import logging
import re
import sys
from pathlib import Path
from typing import Generator, Tuple, Type

from vmodule import VLOG_1

from .api import BaseCheck, Env, FixConfidence

LOG = logging.getLogger(__name__)


class Runner:
    def __init__(self, env: Env, check_dir: Path) -> None:
        self.env = env
        self.check_dir = check_dir

    def iter_check_classes(
        self,
        confidence_filter: FixConfidence,
        preview_filter: bool,
        name_filter: re.Pattern[str],
    ) -> Generator[Tuple[str, Type[BaseCheck]], None, None]:
        try:
            # allow people to import their own utils, etc by altering sys.path
            sys.path.insert(0, self.check_dir.as_posix())
            for t in sorted(self.check_dir.iterdir()):
                if t.is_dir() and (t / "__init__.py").exists():
                    n = t.name
                else:
                    continue

                mod = __import__(n)
                if not name_filter.fullmatch(n):
                    LOG.log(
                        VLOG_1,
                        "%s: name does not match, skip",
                        n,
                    )
                    continue
                if mod.Check.confidence < confidence_filter:
                    LOG.log(
                        VLOG_1,
                        "%s: %s < filter %s, skip",
                        n,
                        mod.Check.confidence,
                        confidence_filter,
                    )
                    continue
                if mod.Check.preview and not preview_filter:
                    LOG.log(
                        VLOG_1, "%s: preview with filter %s, skip", n, preview_filter
                    )
                    continue

                yield n, mod.Check

        finally:
            sys.path.pop(0)
