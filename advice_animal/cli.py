from __future__ import annotations

import logging
import os
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import click
from pathspec import PathSpec
from pathspec.patterns.gitwildmatch import GitWildMatchPattern
from vmodule import VLOG_1, vmodule_init

from .api import Env, FixConfidence

from .runner import Runner
from .update_checkout import update_local_cache
from .workflow import BaseWorkflow, compare, TestWorkflow

LOG = logging.getLogger(__name__)

ADVICE_URL_ENV_VAR = "ADVICE_URL"
ADVICE_DIR_ENV_VAR = "ADVICE_DIR"
ADVICE_SAMPLE_URL = "https://github.com/advice-animal/advice-sample"
# The following is intended to be adjusted by wrappers after import, see `docs/advice.md`
DEFAULT_ADVICE_URL = ADVICE_SAMPLE_URL


@dataclass
class Settings:
    advice_path: Path
    confidence_filter: FixConfidence
    preview_filter: bool
    name_filter: re.Pattern[str]
    dry_run: bool


@click.group()
@click.version_option()
@click.pass_context
@click.option("-v", type=int)
@click.option("--vmodule")
@click.option(
    "--advice-dir",
    envvar=ADVICE_DIR_ENV_VAR,
    type=click.Path(),
    help="""\
Use a local directory for dispensing advice, typically during testing.  This
takes prescedence over the normal way to find advice, using --advice-url below.
""",
)
@click.option(
    "--advice-url",
    envvar=ADVICE_URL_ENV_VAR,
    default=lambda: DEFAULT_ADVICE_URL,
    metavar="URL",
    help=f"""\
Set the repo url from which advice is dispensed.  This is typically set by
wrappers, the ADVICE_URL env var, or has a default of {ADVICE_SAMPLE_URL} worst
case.  (Click's API prevents showing the actual live url here.)
""",
)
@click.option(
    "--skip-update",
    is_flag=True,
    help="When loading advice from a url, don't pull if some version already exists locally.",
)
@click.option(
    "--confidence", default="unset", help="Filter advice to be at least this confident"
)
@click.option("--preview", is_flag=True, help="Allow preview advice")
@click.option("--only", default=".*", help="Filter advice names by regex")
@click.option("-n", "--dry-run", is_flag=True)
def main(
    ctx: click.Context,
    v: Optional[int],
    vmodule: Optional[str],
    advice_url: str,
    advice_dir: Optional[str],
    skip_update: bool,
    confidence: str,
    preview: bool,
    only: str,
    dry_run: bool,
) -> None:
    vmodule_init(v, vmodule)
    if advice_dir is None:
        advice_path = update_local_cache(advice_url, skip_update)
    else:
        advice_path = Path(advice_dir)

    # TODO resolve path, in case it's relative
    # TODO advice_repo, and autoupdate
    ctx.obj = Settings(
        advice_path=advice_path,
        confidence_filter=FixConfidence[confidence.upper()],
        preview_filter=preview,
        name_filter=re.compile(only),
        dry_run=dry_run,
    )
    LOG.info("Using settings %s", ctx.obj)


@main.command()
@click.pass_context
def show_effective_advice_dir(ctx: click.Context) -> None:
    """
    Prints the path to advice dir that would be used with this set of args.
    """
    print(ctx.obj.advice_path)


@main.command()
@click.pass_context
@click.option("--show-exception", is_flag=True)
def selftest_advice(ctx: click.Context, show_exception: bool) -> None:
    """
    Runs the a/ -> b/ tests contained in the currently-selected advice repo.
    """
    rv = 0
    advice_path = ctx.obj.advice_path.resolve()

    for n, cls in Runner(Env(Path()), advice_path).iter_check_classes(
        preview_filter=True,
        confidence_filter=FixConfidence.UNSET,
        name_filter=re.compile(".*"),
    ):
        if (a_dir := advice_path.joinpath(n, "a")).exists():
            try:
                inst = cls(Env(a_dir))
                assert inst.check()  # it wants to run
                LOG.debug("past check")

                wf = TestWorkflow(Env(a_dir))
                LOG.debug("past TestWorkflow")

                with wf.work_in_branch("", "") as workdir:
                    LOG.debug("past work_in_branch")
                    inst.apply(workdir)
                    LOG.debug("past apply")
                    lrv = compare(advice_path.joinpath(n, "b"), workdir)

                    if cls(Env(workdir)).check():
                        result = click.style("NOT DONE", fg="yellow")
                    elif lrv:
                        result = click.style("FAIL", fg="red")
                    else:
                        result = click.style("PASS", fg="green")
                    LOG.debug("past second check")

                click.echo(n.ljust(25) + result)
                rv |= int(lrv)  # 0/1
            except Exception as e:
                LOG.warning("Testing %s got %s", n, repr(e))
                rv |= 8
                if show_exception:
                    LOG.exception(n)
    sys.exit(rv)


def project_root(path: Path) -> Path:
    """
    Find the project root, looking upward from the given path.

    Looks through all parent paths until either the root is reached, or a directory
    is found that contains any of :attr:`ROOT_MARKERS`.
    """
    root_markers: list[Path] = [Path(".git"), Path(".hg")]
    real_path = path.resolve()

    parents = list(real_path.parents)
    if real_path.is_dir():
        parents.insert(0, real_path)

    for parent in parents:
        if any((parent / marker).exists() for marker in root_markers):
            return parent

    return parent


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


def find_python_projects(path: Path) -> list[Path]:
    """
    Find every project in a mono-repo (or not).
    """
    # A mono-repo may contain multiple projects.
    # The project root is  a directory containing a setup.py or pyproject.toml.
    project_indicators = {"setup.py", "pyproject.toml"}
    projects = []
    root = project_root(path)
    ignore = gitignore(root) + PathSpec.from_lines(
        GitWildMatchPattern, ["__pycache__", "*.egg-info", "*.dist-info", ".venv"]
    )

    for dirpath, dirnames, filenames in os.walk(path):
        # Ignore directories that are ignored by .gitignore.
        if ignore.match_file(dirpath):
            # Don't go any deeper into a directory that is ignored.
            dirnames.clear()
            continue

        # If we find a project indicator, we've found a project.
        if project_indicators.intersection(filenames):
            projects.append(Path(dirpath))
            # Don't go any deeper into this directory.
            dirnames.clear()

    return projects


@main.command()
@click.pass_context
@click.argument("target")
@click.option("-r", "--recursive", is_flag=True)
def check(ctx: click.Context, target: str, recursive: bool) -> None:
    if recursive:
        projects = find_python_projects(Path(target))
    else:
        projects = [Path(target)]
    for project_path in projects:
        results_by_confidence: dict[
            FixConfidence, list[tuple[str, bool]]
        ] = defaultdict(list)
        env = Env(project_path)

        for n, cls in Runner(Env(Path()), Path(ctx.obj.advice_path)).iter_check_classes(
            confidence_filter=ctx.obj.confidence_filter,
            preview_filter=ctx.obj.preview_filter,
            name_filter=ctx.obj.name_filter,
        ):
            inst = cls(env)
            result = inst.check()
            LOG.log(VLOG_1, "Check %s returned %s", n, result)
            if result:
                results_by_confidence[inst.confidence].append((n, result))

        for conf, results in sorted(results_by_confidence.items()):
            print(project_path.absolute())
            print(conf.name)
            print("=" * len(conf.name))
            for n, r in sorted(results):
                print(n.ljust(25) + "needs to run")


@main.command()
@click.pass_context
@click.argument("target")
def diff(ctx: click.Context, target: str) -> None:
    env = Env(Path(target))
    wf = BaseWorkflow(env)

    for n, cls in Runner(env, Path(ctx.obj.advice_path)).iter_check_classes(
        confidence_filter=ctx.obj.confidence_filter,
        preview_filter=ctx.obj.preview_filter,
        name_filter=ctx.obj.name_filter,
    ):
        inst = cls(env)
        if inst.check():
            click.echo(click.style(n, fg="red") + " would make changes")
            with wf.work_in_branch("advice-" + n, "", commit=False) as workdir:
                inst.apply(workdir)


@main.command()
@click.pass_context
@click.option("--inplace", is_flag=True)
@click.argument("target")
def apply(ctx: click.Context, inplace: bool, target: str) -> None:
    env = Env(Path(target))
    wf = BaseWorkflow(env)
    projects = find_python_projects(Path(target))
    for project_path in projects:
        env = Env(project_path)
        wf = BaseWorkflow(env)

        for n, cls in Runner(env, Path(ctx.obj.advice_path)).iter_check_classes(
            confidence_filter=ctx.obj.confidence_filter,
            preview_filter=ctx.obj.preview_filter,
            name_filter=ctx.obj.name_filter,
        ):
            inst = cls(env)
            if inst.check():
                click.echo(click.style(n, fg="red") + " would make changes")
                with wf.work_in_branch(
                    "advice-" + n,
                    f"Autogenerated changes from {n}",
                    commit=not inplace,
                    inplace=inplace,
                ) as workdir:
                    inst.apply(workdir)


if __name__ == "__main__":
    main()
