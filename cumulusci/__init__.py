import os
import sys
import warnings
from importlib.metadata import PackageNotFoundError, version

# Suppress pkg_resources deprecation warnings from dependencies
warnings.filterwarnings("ignore", message=".*pkg_resources.*", category=UserWarning)

__location__ = os.path.dirname(os.path.realpath(__file__))

try:
    __version__ = version("cumulusci-plus")
except PackageNotFoundError:
    __version__ = "unknown"

try:
    version("cumulusci")
    raise Exception("CumulusCI installation found, Remove the CumulusCI package.")
except PackageNotFoundError:
    pass

if sys.version_info < (3, 11):  # pragma: no cover
    raise Exception("CumulusCI requires Python 3.11+.")
