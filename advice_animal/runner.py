import sys
from pathlib import Path

from .api import Check, Env


class Runner:
    def __init__(self, env: Env, check_dir: Path) -> None:
        self.env = env
        self.check_dir = check_dir

    def iter_check_classes(self):
        try:
            # allow people to import their own utils, etc by altering sys.path
            sys.path.insert(0, self.check_dir.as_posix())
            for t in sorted(self.check_dir.iterdir()):
                if t.name.endswith(".py"):
                    n = t.name[:-3]
                elif (t / "__init__.py").exists():
                    n = t.name
                else:
                    continue

                mod = __import__(n)
                yield n, mod.Check

        finally:
            sys.path.pop(0)

    def iter_checks(self):
        for n, cls in self.iter_check_classes():
            inst = cls(self.env)
            yield n, inst.pred(), inst
