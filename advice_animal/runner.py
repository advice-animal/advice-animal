import logging
import sys
from pathlib import Path

from vmodule import VLOG_1

from .api import FixConfidence

LOG = logging.getLogger(__name__)


class Runner:
    def __init__(self, advice_dir: Path) -> None:
        self.advice_dir = advice_dir

    def iter_check_classes(
        self, confidence_filter=FixConfidence.UNSET, preview_filter: bool = False
    ):
        try:
            # allow people to import their own utils, etc by altering sys.path
            sys.path.insert(0, self.advice_dir.as_posix())
            for t in sorted(self.advice_dir.iterdir()):
                if t.is_dir() and (t / "__init__.py").exists():
                    n = t.name
                else:
                    continue

                mod = __import__(n)
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
