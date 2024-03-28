import os
import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

import moreorless.click

from .api import Env


# TODO support parallel workflow, which will work extremely well for git on
# fixers that we don't know if they generate changes until after they run.
class BaseWorkflow:
    def __init__(self, env: Env) -> None:
        self.env = env
        self.current_branch = (
            (env.path / ".git" / "HEAD").read_text().strip().split("/")[-1]
        )
        # TODO consider how to handle dirty working copy

    @contextmanager
    def work_in_branch(
        self,
        branch_name: str,
        commit_message: str,
        inplace: bool = False,
        commit: bool = True,
    ) -> Generator[Path, None, None]:
        # TODO: A future option to do commit-per-fix in current working copy
        # might be nice, right now inplace ignores the commit var.
        if inplace:
            cur_cwd = os.getcwd()
            try:
                os.chdir(self.env.path)
                yield self.env.path
            finally:
                os.chdir(cur_cwd)
        else:
            with tempfile.TemporaryDirectory() as d:
                # TODO consider --single-branch --no-tags -b main, but that doesn't
                # appear to be able to check out arbitrary revs or origin/main.
                subprocess.check_output(["git", "clone", self.env.path, d])
                cur_cwd = os.getcwd()
                try:
                    os.chdir(d)
                    subprocess.check_output(["git", "checkout", "-b", branch_name])
                    yield Path(d)
                    subprocess.check_output(["git", "add", "-A"])
                    if commit:
                        subprocess.check_output(["git", "commit", "-m", commit_message])
                        subprocess.check_output(
                            ["git", "push", "-f", "origin", branch_name]
                        )
                    else:
                        subprocess.check_call(["git", "status"])
                        subprocess.check_call(["git", "diff"])
                finally:
                    os.chdir(cur_cwd)


class TestWorkflow(BaseWorkflow):
    @contextmanager
    def work_in_branch(
        self, branch_name: str, commit_message: str
    ) -> Generator[Path, None, None]:
        with tempfile.TemporaryDirectory() as d:
            shutil.copytree(self.env.path, Path(d, "work"))
            yield Path(d, "work")


def files(a: Path) -> Generator[Path, None, None]:
    for root, dirs, files in os.walk(a):
        for f in files:
            yield Path(root, f).relative_to(a)


def compare(a: Path, b: Path) -> bool:
    # TODO recursive?
    rv = False
    for entry in files(a):
        a_text = Path(a, entry).read_text()
        b_text = Path(b, entry).read_text()
        if a_text != b_text:
            rv = True
        moreorless.click.echo_color_unified_diff(a_text, b_text, entry.name)
    return rv
