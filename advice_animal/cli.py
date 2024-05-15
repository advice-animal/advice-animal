from __future__ import annotations

import logging
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import click
from vmodule import vmodule_init

from .api import Env, FixConfidence, Mode

from .runner import Runner
from .update_checkout import update_local_cache
from .workflow import compare, TestWorkflow

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


@main.group()
def self() -> None:
    """Commands for interacting with advice-animal itself."""
    pass


@self.command()
@click.pass_context
def show_effective_advice_dir(ctx: click.Context) -> None:
    """
    Prints the path to advice dir that would be used with this set of args.
    """
    print(ctx.obj.advice_path)


@self.command()
@click.pass_context
@click.option("--show-exception", is_flag=True)
def test(ctx: click.Context, show_exception: bool) -> None:
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


@main.command()
@click.pass_context
@click.argument("target", default=".")
def check(ctx: click.Context, target: str) -> None:
    runner = Runner(Path(ctx.obj.advice_path), inplace=False, mode=Mode.check)
    results = runner.run(
        repo=Path(target),
        confidence_filter=ctx.obj.confidence_filter,
        preview_filter=ctx.obj.preview_filter,
        name_filter=ctx.obj.name_filter,
    )
    for advice_name, result in results.items():
        if result.success:
            click.echo(click.style(advice_name, fg="green") + ": " + result.message)
        else:
            click.echo(
                click.style(advice_name, fg="red") + " failed: " + result.message
            )


@main.command()
@click.pass_context
@click.argument("target", default=".")
def diff(ctx: click.Context, target: str) -> None:
    runner = Runner(Path(ctx.obj.advice_path), inplace=False, mode=Mode.diff)
    results = runner.run(
        repo=Path(target),
        confidence_filter=ctx.obj.confidence_filter,
        preview_filter=ctx.obj.preview_filter,
        name_filter=ctx.obj.name_filter,
    )
    for advice_name, result in results.items():
        if result.success:
            if result.changes_needed:
                click.echo(click.style(advice_name, fg="green") + ": Changes Needed:")
                click.echo(click.style(advice_name, fg="green") + result.message)
            else:
                click.echo(click.style(advice_name, fg="green") + ": No changes needed")
        else:
            click.echo(
                click.style(advice_name, fg="red") + " failed: " + result.message
            )


@main.command()
@click.pass_context
@click.argument("target", default=".")
@click.option("--inplace", is_flag=True)
def apply(ctx: click.Context, target: str, inplace: bool) -> None:
    runner = Runner(Path(ctx.obj.advice_path), inplace=False, mode=Mode.apply)
    results = runner.run(
        repo=Path(target),
        confidence_filter=ctx.obj.confidence_filter,
        preview_filter=ctx.obj.preview_filter,
        name_filter=ctx.obj.name_filter,
    )
    for advice_name, result in results.items():
        if result.success:
            if result.changes_needed:
                click.echo(click.style(advice_name, fg="green") + result.message)
            else:
                click.echo(click.style(advice_name, fg="green") + ": No changes needed")
        else:
            click.echo(
                click.style(advice_name, fg="red") + " failed: " + result.message
            )


if __name__ == "__main__":
    main()
