import logging
import os
import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, List, Optional, Union

import moreorless.click

from .api import Env

LOG = logging.getLogger(__name__)


def run(cmd: List[Union[str, Path]], check: bool = True) -> str:
    LOG.info("Run %s in %s", cmd, os.getcwd())
    proc = subprocess.run(cmd, encoding="utf-8", capture_output=True, check=check)
    LOG.debug("Ran %s -> %s", cmd, proc.returncode)
    LOG.debug("Stdout: %s", proc.stdout)
    return proc.stdout


# TODO support parallel workflow, which will work extremely well for git on
# fixers that we don't know if they generate changes until after they run.
class BaseWorkflow:
    current_branch: Optional[str]

    def __init__(self, env: Env) -> None:
        self.env = env
        git_head_path = env.repo_root / ".git" / "HEAD"
        if git_head_path.exists():
            self.current_branch = git_head_path.read_text().strip().split("/")[-1]
        else:
            self.current_branch = None
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
                run(["git", "clone", self.env.path, d])
                cur_cwd = os.getcwd()
                try:
                    os.chdir(d)
                    run(
                        [
                            "git",
                            "checkout",
                            "-b",
                            branch_name,
                            f"origin/{self.current_branch}",
                        ]
                    )
                    yield Path(d)
                    run(["git", "add", "-A"])
                    if commit:
                        run(["git", "commit", "-m", commit_message])
                        run(["git", "push", "-f", "origin", branch_name])
                        print("pushed", branch_name)
                    else:
                        run(["git", "status"])
                        print(run(["git", "diff", "--cached"]))
                finally:
                    os.chdir(cur_cwd)


class TestWorkflow(BaseWorkflow):
    @contextmanager
    def work_in_branch(
        self,
        branch_name: str,
        commit_message: str,
        inplace: bool = False,
        commit: bool = True,
    ) -> Generator[Path, None, None]:
        with tempfile.TemporaryDirectory() as d:
            shutil.copytree(self.env.path, Path(d, "work"))
            yield Path(d, "work")


def files(a: Path) -> Generator[Path, None, None]:
    for root, dirs, files in os.walk(a):
        for f in files:
            if not f.startswith("."):
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
