import logging
import os
import os.path
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Generator, Optional, Sequence, Tuple, Type, Union

from click import ClickException
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
    branch_name: Optional[str] = None
    next_steps: Sequence[str] = ()
    modified: bool = False
    message: str = ""
    error: str = ""


@dataclass
class Filter:
    confidence_filter: FixConfidence
    preview_filter: bool
    name_filter: re.Pattern[str]

    def include(self, display_name: str, check: BaseCheck) -> bool:
        if not self.name_filter.fullmatch(display_name):
            LOG.log(VLOG_1, "%s: name does not match, skip", display_name)
            return False
        if check.confidence < self.confidence_filter:
            LOG.log(
                VLOG_1,
                "%s: confidence %s < filter %s, skip",
                display_name,
                check.confidence,
                self.confidence_filter,
            )
            return False
        if check.preview and not self.preview_filter:
            LOG.log(
                VLOG_1,
                "%s: preview with filter %s, skip",
                display_name,
                self.preview_filter,
            )
            return False

        LOG.log(VLOG_1, "%s: include", display_name)
        return True


class Runner:
    def __init__(self, advice_path: Path, inplace: bool, mode: Mode) -> None:
        if not advice_path.is_dir():
            raise ClickException(f"{advice_path} is not a directory")

        if inplace and mode != Mode.apply:
            raise ClickException("inplace only valid with mode 'apply'")

        self.advice_path = advice_path
        self.inplace = inplace
        self.mode = mode

    def run(
        self,
        repo: Path,
        filter: Filter,
    ) -> dict[str, Result]:
        git_head_path = repo / ".git" / "HEAD"
        if git_head_path.exists():
            current_branch = git_head_path.read_text().strip().split("/")[-1]
        else:  # This is a detached HEAD or not a git repo
            current_branch = None
            raise ClickException("Not a git repo")
        results = {}
        if self.inplace:  # This is only applicable for `apply` command
            cur_cwd = os.getcwd()
            try:
                os.chdir(repo)
                output, exit_code = run_cmd(
                    ["git", "diff", "--name-only", "--exit-code"], check=False
                )
                if exit_code != 0:
                    raise ClickException(
                        f"Uncommited changes found in\n{output}\nPlease commit or stash them."
                    ) from None

                for advice_name, check_cls in self.order_check_classes(filter):
                    LOG.log(VLOG_1, "Running check %s", advice_name)
                    env = Env(repo)
                    for project in env.py_projects:
                        os.chdir(project)
                        try:
                            check = check_cls(env)
                            changes_needed = bool(check.run())
                            results[advice_name] = Result(
                                advice_name=advice_name,
                                success=True,
                                modified=changes_needed,
                            )
                        except Exception as e:
                            results[advice_name] = Result(
                                advice_name=advice_name,
                                success=False,
                                error=repr(e),
                            )
                            return results
                        os.chdir(cur_cwd)
            finally:
                os.chdir(cur_cwd)
        else:
            assert current_branch is not None
            cur_cwd = os.getcwd()
            with tempfile.TemporaryDirectory() as d:
                run_cmd(["git", "clone", repo, d])
                os.chdir(d)
                env = Env(Path(d))
                try:
                    for advice_name, check_cls in self.order_check_classes(filter):
                        results[advice_name] = self._branch_run(
                            advice_name, check_cls, env, current_branch
                        )

                finally:
                    os.chdir(cur_cwd)

        return results

    def _branch_run(
        self,
        advice_name: str,
        check_cls: type[BaseCheck],
        env: Env,
        current_branch: str,
    ) -> Result:
        try:
            output = ""
            del env.next_steps[:]
            branch_name = f"advice-{advice_name}"
            changes_needed = False
            LOG.log(VLOG_1, "Running check %s", advice_name)
            # In case a previous branch hit an exception, make sure we're in a fresh
            # clean state.
            run_cmd(["git", "clean", "-fdx"])
            run_cmd(
                [
                    "git",
                    "checkout",
                    "-b",
                    branch_name,
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
                message = f"Apply {advice_name}"
                if env.next_steps:
                    message += "\n\n"
                    for next_step in env.next_steps:
                        message += next_step + "\n"
                if not changes_needed:
                    output = "No changes needed"
                else:
                    run_cmd(["git", "commit", "-m", message])
                    run_cmd(["git", "push", "-f", "origin", branch_name])
                    output = f"Changes applied to branch {branch_name}. Push the branch to create a PR."
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
            return Result(
                advice_name=advice_name,
                success=True,
                modified=changes_needed,
                message=output,
                branch_name=branch_name,
            )
        except Exception as e:
            return Result(
                advice_name=advice_name,
                success=False,
                error=str(e),
            )

    def order_check_classes(self, filter: Filter) -> list[tuple[str, Type[BaseCheck]]]:
        return sorted(
            self.iter_check_classes(filter),
            key=(lambda x: (x[1].order, x[0])),
        )

    def iter_check_classes(
        self,
        filter: Filter,
    ) -> Generator[tuple[str, Type[BaseCheck]], None, None]:
        try:
            # allow people to import their own utils, etc by altering sys.path
            sys.path.insert(0, self.advice_path.as_posix())
            for dirpath, dirnames, filenames in os.walk(self.advice_path):
                dirnames[:] = sorted([d for d in dirnames if not d.startswith(".")])
                if "__init__.py" not in filenames:
                    continue

                del dirnames[:]
                display_name = os.path.relpath(dirpath, self.advice_path)
                import_name = display_name.replace("/", ".")

                LOG.log(VLOG_1, "Handling %s", display_name)

                __import__(import_name)
                mod = sys.modules[import_name]
                if filter.include(display_name, mod.Check):
                    yield display_name, mod.Check

        finally:
            sys.path.pop(0)
