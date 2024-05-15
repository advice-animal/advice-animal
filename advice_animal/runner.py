import logging
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Generator, Literal, Tuple, Type, Union

from vmodule import VLOG_1

from .api import BaseCheck, Env, FixConfidence, Mode

LOG = logging.getLogger(__name__)


def run_cmd(cmd: list[Union[str, Path]], check: bool = True) -> Tuple[str, int]:
    LOG.info("Run %s in %s", cmd, os.getcwd())
    proc = subprocess.run(cmd, encoding="utf-8", capture_output=True, check=check)
    LOG.debug("Ran %s -> %s", cmd, proc.returncode)
    LOG.debug("Stdout: %s", proc.stdout)
    return proc.stdout, proc.returncode


@dataclass
class Result:
    advice_name: str
    success: bool
    project: str = ""
    message: str = ""
    changes_needed: bool = False


class Runner:
    def __init__(self, advice_path: Path, inplace: bool, mode: Mode) -> None:
        if not advice_path.is_dir():
            raise ValueError(f"{advice_path} is not a directory")

        if inplace and mode != Mode.apply:
            raise ValueError("inplace only valid with mode 'apply'")

        self.advice_path = advice_path
        self.inplace = inplace
        self.mode = mode

    def run(
        self,
        repo: Path,
        confidence_filter: FixConfidence,
        preview_filter: bool,
        name_filter: re.Pattern[str],
    ):
        git_head_path = repo / ".git" / "HEAD"
        if git_head_path.exists():
            current_branch = git_head_path.read_text().strip().split("/")[-1]
        else:  # This is a detached HEAD or not a git repo
            current_branch = None
            if not self.inplace:
                raise ValueError("Not a git repo")
        results = {}
        if self.inplace:  # This is only applicable for `apply` command
            cur_cwd = os.getcwd()
            try:
                for advice_name, check_cls in self.iter_check_classes(
                    confidence_filter, preview_filter, name_filter
                ):
                    LOG.log(VLOG_1, "Running check %s", advice_name)
                    env = Env(repo)
                    for project in env.py_projects:
                        os.chdir(project)
                        try:
                            check = check_cls(env)
                            changes_needed = bool(check.run())
                            results[advice_name] = Result(
                                advice_name=advice_name,
                                project=project,
                                success=True,
                                changes_needed=changes_needed,
                            )
                        except Exception as e:
                            results[advice_name] = Result(
                                advice_name=advice_name,
                                project=project,
                                success=False,
                                message=str(e),
                            )
                            return results
            finally:
                os.chdir(cur_cwd)
        else:
            cur_cwd = os.getcwd()
            with tempfile.TemporaryDirectory() as d:
                run_cmd(["git", "clone", repo, d])
                os.chdir(d)
                env = Env(Path(d))
                try:
                    for advice_name, check_cls in self.iter_check_classes(
                        confidence_filter, preview_filter, name_filter
                    ):
                        try:
                            output = ""
                            changes_needed = False
                            LOG.log(VLOG_1, "Running check %s", advice_name)
                            run_cmd(
                                [
                                    "git",
                                    "checkout",
                                    "-b",
                                    f"advice-{advice_name}",
                                    f"origin/{current_branch}",
                                ]
                            )
                            for project in env.py_projects:
                                LOG.log(VLOG_1, "Checking %s", project)
                                os.chdir(project)
                                check = check_cls(env)
                                changes_needed |= bool(check.run())
                            run_cmd(["git", "add", "-A"])
                            if self.mode == Mode.apply:
                                run_cmd(["git", "commit", "-m", f"Apply {advice_name}"])
                                run_cmd(["git", "push", "-f", "origin", advice_name])
                                output = f"Changes applied to branch {advice_name}. Push the branch to create a PR."
                            elif self.mode == Mode.diff:
                                output, _ = run_cmd(["git", "diff"])
                            elif self.mode == Mode.check:
                                _, returncode = run_cmd(
                                    ["git", "diff", "--exit-code", "--cached"],
                                    check=False,
                                )
                                if returncode == 0:
                                    output = "No changes needed"
                                elif returncode == 1:
                                    output = "Changes can be applied"
                            results[advice_name] = Result(
                                advice_name=advice_name,
                                success=True,
                                changes_needed=changes_needed,
                                message=output,
                            )
                        except Exception as e:
                            results[advice_name] = Result(
                                advice_name=advice_name,
                                success=False,
                                message=str(e),
                            )
                            return results
                finally:
                    os.chdir(cur_cwd)
        return results

    def iter_check_classes(
        self,
        confidence_filter: FixConfidence,
        preview_filter: bool,
        name_filter: re.Pattern[str],
    ) -> Generator[Tuple[str, Type[BaseCheck]], None, None]:
        try:
            # allow people to import their own utils, etc by altering sys.path
            sys.path.insert(0, self.advice_path.as_posix())
            for t in sorted(self.advice_path.iterdir()):
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
