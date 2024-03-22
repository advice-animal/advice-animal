# advice-animal

Advice Animal answers the question of what do we do _after_ running
cookiecutter, or how to we avoid telling people we support to run a `sed` script.

## Design Goals

Existing projects such as [cookiecutter](https://cookiecutter.readthedocs.io/en/stable/) do a pretty
solid job of initial project generation, and ones such as [ruff](https://astral.sh/ruff),
[fixit](https://github.com/instagram/fixit), and [pyupgrade](https://github.com/asottile/pyupgrade/)
do a solid job of suggesting universal (that is, applicable to everyone) changes.



Advice Animal is developed to serve a central team that has opinions, but wants to leave the
application of that advice up to teams owning individual repos that have the interest and time to
apply it.

* The storage of fixes is decoupled from the release of the thing that runs them.
  * It's just a git repo, which gets pulled on each run.
  * But can also be a directory, if you want to manage distribution with puppet or your monorepo or
    are working on proposed changes.
* Fixes are run with a trivial workflow engine.
  * Creates a branch-per-fix with git.
  * Expensive fixes can record that they're done, to avoid running again
  * Fixes can be manual (think "feature add")
  * Your fix repo can customize workflow, including branch naming and commands that get run (say you
    have a FUSE/mercurial setup or need to run `tox -e stylefix` and amend).
* Your users choose what fixes they want (either by quality=their available time), or by declining a fix.
* Third-party libraries are easy to use in your fixes, and they don't even need to be public.

## Fix confidence

Using traffic light colors for simplicity:

* `FixConfidence.GREEN` are high-confidence fixes that a) something is wrong and b) this won't make it
worse (think, formatting).  Trust your tests and land these.

* `FixConfidence.YELLOW` ought to have human review (and definitely make sure the tests run), but are
low-effort to apply (think, renaming python modules that have uppercase in them, or bumping a
version to avoid a known CVE).  Meets the bar for a passing mention in release notes.

* `FixConfidence.RED` likely need a human to pick up the baton and finish it (think: you clearly use
types, you probably should enable mypy in CI).


# Version Compat

Usage of this library should work back to 3.7, but development (and mypy
compatibility) only on 3.10-3.12.  Linting requires 3.12 for full fidelity.

# Versioning

This library follows [meanver](https://meanver.org/) which basically means
[semver](https://semver.org/) along with a promise to rename when the major
version changes.

# License

advice-animal is copyright [Tim Hatch](https://timhatch.com/), and licensed under
the MIT license.  See the `LICENSE` file for details.
