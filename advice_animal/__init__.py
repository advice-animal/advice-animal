try:
    from .version import __version__
except ImportError:
    __version__ = "dev"

from .api import BaseCheck, FixConfidence  # noqa: F401
