import logging
import os
import subprocess
from pathlib import Path
from typing import Generator, List, Union

import moreorless.click

LOG = logging.getLogger(__name__)


def run(cmd: List[Union[str, Path]], check: bool = True) -> str:
    LOG.info("Run %s in %s", cmd, os.getcwd())
    proc = subprocess.run(cmd, encoding="utf-8", capture_output=True, check=check)
    LOG.debug("Ran %s -> %s", cmd, proc.returncode)
    LOG.debug("Stdout: %s", proc.stdout)
    return proc.stdout


def files(a: Path) -> Generator[Path, None, None]:
    for root, dirs, files in os.walk(a):
        for f in files:
            if f == ".DS_Store" or (f[0] == "." and f[-4:-1] == ".sw"):
                continue
            yield Path(root, f).relative_to(a)


def compare(a: Path, b: Path) -> bool:
    # TODO recursive?
    rv = False
    a_files = set(files(a))
    b_files = set(files(b))

    for entry in (a_files & b_files):
        a_text = Path(a, entry).read_text()
        b_text = Path(b, entry).read_text()
        if a_text != b_text:
            rv = True
        moreorless.click.echo_color_unified_diff(a_text, b_text, entry.name)

    for entry in (a_files - b_files):
        a_text = Path(a, entry).read_text()
        rv = True
        moreorless.click.echo_color_unified_diff(a_text, "", entry.name)
    for entry in (b_files - a_files):
        b_text = Path(b, entry).read_text()
        if entry.name == "pyproject.toml" and len(b_text) == 0:
            # We create empty pyproject.toml files to make test directories
            # look like real projects. We don't want to show this as a diff.
            continue
        rv = True
        moreorless.click.echo_color_unified_diff("", b_text, entry.name)

    return rv
