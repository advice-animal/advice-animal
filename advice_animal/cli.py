from __future__ import annotations

import json
import logging
import os
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import click
from vmodule import vmodule_init

from .api import Env, FixConfidence, Mode
from .naming import advice_name_re

from .runner import Runner
from .update_checkout import update_local_cache
from .workflow import compare

LOG = logging.getLogger(__name__)

ADVICE_URL_ENV_VAR = "ADVICE_URL"
ADVICE_DIR_ENV_VAR = "ADVICE_DIR"
ADVICE_SAMPLE_URL = "https://github.com/advice-animal/advice-sample"
# The following are intended to be adjusted by wrappers after import, see `docs/integration.md`
DEFAULT_ADVICE_URL = ADVICE_SAMPLE_URL
VERSION_PROJECT = "advice-animal"
VERSION_DESC = "%(prog)s, version %(version)s"


@dataclass
class Settings:
    advice_url: Optional[str]  # only set if used
    advice_path: Path
    confidence_filter: FixConfidence
    preview_filter: bool
    name_filter: re.Pattern[str]
    dry_run: bool


def version_callback(ctx: click.Context, param: click.Parameter, value: bool) -> None:
    if not value or ctx.resilient_parsing:
        return
    import importlib.metadata

    version = importlib.metadata.version(VERSION_PROJECT)
    click.echo(
        VERSION_DESC % {"prog": ctx.find_root().info_name, "version": version},
        color=ctx.color,
    )
    ctx.exit()


@click.command
@click.pass_context
@click.option(
    "--version",
    callback=version_callback,
    is_flag=True,
    is_eager=True,
    expose_value=False,
)
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
case.  (Click's API prevents showing the actual live url here, but check --config)
""",
)
@click.option(
    "--skip-update",
    is_flag=True,
    help="When loading advice from a url, don't pull if some version already exists locally.",
)
# Filtering
@click.option(
    "--confidence", default="unset", help="Filter advice to be at least this confident"
)
@click.option("--preview", is_flag=True, help="Allow preview advice")
@click.option("-a", "--all", is_flag=True, help="Use all advice")
@click.argument("advice_names", nargs=-1)
# Modifying how fixing happens
@click.option("-n", "--dry-run", is_flag=True)
@click.option("--target", default=".", help="Path to check, defaulting to current dir")
@click.option(
    "--in-branches", is_flag=True, help="In independent branches instead of inplace"
)
# Special non-fixing modes
@click.option("--selftest", is_flag=True, help="Check viability of advice repo")
@click.option("--config", is_flag=True, help="Show configuration")
def main(
    ctx: click.Context,
    # Logging config
    v: Optional[int],
    vmodule: Optional[str],
    # Advice dir
    advice_url: str,
    advice_dir: Optional[str],
    skip_update: bool,
    # Choice of advice
    confidence: str,
    preview: bool,
    dry_run: bool,
    target: str,
    in_branches: bool,
    all: bool,
    advice_names: list[str],
    # Operation
    selftest: bool,
    config: bool,
) -> None:
    vmodule_init(v, vmodule)
    if advice_dir is None:
        advice_path = update_local_cache(advice_url, skip_update)
    else:
        advice_path = Path(advice_dir)

    if config and selftest:
        raise Exception("Can't enable both --config and --selftest simultaneously")

    if all and advice_names:
        raise Exception("Can't enable both -a and provide advice names simultaneously")

    if advice_names:
        only = "|".join(advice_name_re(name) for name in advice_names)
    else:
        only = ".*"

    # TODO resolve path, in case it's relative
    # TODO advice_repo, and autoupdate
    ctx.obj = Settings(
        advice_url=advice_url if advice_dir is None else None,
        advice_path=advice_path,
        confidence_filter=FixConfidence[confidence.upper()],
        preview_filter=preview,
        name_filter=re.compile(only),
        dry_run=dry_run,
    )
    LOG.info("Using settings %s", ctx.obj)

    if selftest:
        perform_selftest(ctx)
    elif config:
        show_config(ctx)
    elif advice_names or all:
        apply(ctx, target, not in_branches)
    else:
        show_list(ctx)


def show_config(ctx: click.Context) -> None:
    """
    Prints the path to advice dir that would be used with this set of args.
    """
    print(json.dumps(ctx.obj.__dict__, default=str))


def perform_selftest(ctx: click.Context, show_exception: bool = True) -> None:
    """
    Runs the a/ -> b/ tests contained in the currently-selected advice repo.
    """
    rv = 0
    advice_path = ctx.obj.advice_path.resolve()

    for n, cls in Runner(advice_path, inplace=True, mode=Mode.apply).iter_check_classes(
        preview_filter=True,
        confidence_filter=FixConfidence.UNSET,
        name_filter=re.compile(".*"),
    ):
        if (a_dir := advice_path.joinpath(n, "a")).exists():
            try:
                with tempfile.TemporaryDirectory() as d:
                    workdir = Path(d, "workdir")
                    shutil.copytree(a_dir, workdir)
                    Path(workdir, "pyproject.toml").touch()
                    old_pwd = os.getcwd()
                    try:
                        os.chdir(workdir)
                        inst = cls(Env(workdir))
                        status = inst.run()
                        lrv = compare(advice_path.joinpath(n, "b"), workdir)

                        if cls(Env(workdir)).run():
                            result = click.style("NOT DONE", fg="yellow")
                        elif lrv:
                            result = click.style("FAIL", fg="red")
                        elif not status:
                            result = click.style("DID NOT RUN", fg="red")
                        else:
                            result = click.style("PASS", fg="green")
                        LOG.debug("past second check")
                    finally:
                        os.chdir(old_pwd)

                click.echo(n.ljust(25) + result)
                rv |= int(lrv)  # 0/1
            except Exception as e:
                LOG.warning("Testing %s got %s", n, repr(e))
                rv |= 8
                if show_exception:
                    LOG.exception(n)
    sys.exit(rv)


def show_list(ctx: click.Context) -> None:
    runner = Runner(Path(ctx.obj.advice_path), inplace=False, mode=Mode.check)
    print("Available advice:")
    for advice_name, check_cls in runner.iter_check_classes(
        ctx.obj.confidence_filter, ctx.obj.preview_filter, ctx.obj.name_filter
    ):
        if check_cls.confidence.name != "UNSET":
            name = click.style(advice_name, fg=check_cls.confidence.name.lower())
        else:
            name = click.style(advice_name, fg="green")
        click.echo(f"* {name}{' - (preview)' if check_cls.preview else ''}")


def apply(ctx: click.Context, target: str, inplace: bool) -> None:
    runner = Runner(Path(ctx.obj.advice_path), inplace=inplace, mode=Mode.apply)
    results = runner.run(
        repo=Path(target),
        confidence_filter=ctx.obj.confidence_filter,
        preview_filter=ctx.obj.preview_filter,
        name_filter=ctx.obj.name_filter,
    )
    for advice_name, result in results.items():
        if result.success:
            if result.modified:
                click.echo(click.style(advice_name, fg="green") + ": " + result.message)
                for next_step in result.next_steps:
                    click.echo(click.style(advice_name, fg="yellow") + ": " + next_step)
            else:
                click.echo(click.style(advice_name, fg="green") + ": No changes needed")
        else:
            click.echo(click.style(advice_name, fg="red") + " failed: " + result.error)


if __name__ == "__main__":
    # Allow using "advice-animal pave --args" to still work
    if sys.argv[1:2] == ["pave"]:
        del sys.argv[1:2]

    main()
