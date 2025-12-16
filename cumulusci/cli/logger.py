""" CLI logger """
import logging
import os
import sys
import tempfile

import requests
from rich.logging import RichHandler

try:
    import colorama
except ImportError:
    # coloredlogs only installs colorama on Windows
    pass


def _set_windows_console_encoding():
    """Set Windows console encoding to UTF-8 to support Unicode characters.

    This function attempts multiple methods to set UTF-8 encoding on Windows:
    1. Sets PYTHONIOENCODING environment variable
    2. Sets sys.stdout and sys.stderr encoding
    3. Uses Windows console API if available
    """
    if os.name != "nt":  # Only on Windows
        return

    try:
        # Method 1: Set environment variable (affects subprocesses too)
        os.environ.setdefault("PYTHONIOENCODING", "utf-8")

        # Method 2: Reconfigure stdout/stderr with UTF-8 encoding
        # This works if the streams support reconfiguration
        if hasattr(sys.stdout, "reconfigure"):
            try:
                sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            except (AttributeError, ValueError):
                pass

        if hasattr(sys.stderr, "reconfigure"):
            try:
                sys.stderr.reconfigure(encoding="utf-8", errors="replace")
            except (AttributeError, ValueError):
                pass

        # Method 3: Use Windows console API to set code page to UTF-8 (65001)
        try:
            import ctypes

            kernel32 = ctypes.windll.kernel32
            # Set console output code page to UTF-8
            kernel32.SetConsoleOutputCP(65001)
            # Set console input code page to UTF-8 (optional, for input)
            kernel32.SetConsoleCP(65001)
        except (AttributeError, OSError):
            # Windows API not available or failed, continue with other methods
            pass

    except Exception:
        # If any method fails, continue - encoding setup is best-effort
        # The console should handle UTF-8 if Windows API calls succeed
        pass


def init_logger(debug=False):
    """Initialize the logger"""

    logger = logging.getLogger(__name__.split(".")[0])
    for handler in logger.handlers:  # pragma: no cover
        logger.removeHandler(handler)

    # Set Windows console encoding to UTF-8 before initializing colorama
    _set_windows_console_encoding()

    if os.name == "nt" and "colorama" in sys.modules:  # pragma: no cover
        colorama.init()

    logger.addHandler(
        RichHandler(
            rich_tracebacks=True,
            show_level=debug,
            show_path=debug,
            tracebacks_show_locals=debug,
        )
    )
    logger.setLevel(logging.DEBUG if debug else logging.INFO)
    logger.propagate = False

    if debug:  # pragma: no cover
        # Referenced from:
        # https://github.com/urllib3/urllib3/blob/cd55f2fe98df4d499ab5c826433ee4995d3f6a60/src/urllib3/__init__.py#L48
        def add_rich_logger(
            module: str, level: int = logging.DEBUG if debug else logging.INFO
        ) -> logging.StreamHandler:
            """Retrieve the logger for the given module.
            Remove all handlers from it, and add a single RichHandler."""
            logger = logging.getLogger(module)
            for handler in logger.handlers:
                logger.removeHandler(handler)

            handler = RichHandler()
            logger.addHandler(handler)
            logger.setLevel(level)
            logger.debug(f"Added rich.logging.RichHandler to logger: {module}")
            return handler

        # monkey patch urllib3 logger
        requests.packages.urllib3.add_stderr_logger = add_rich_logger
        requests.packages.urllib3.add_stderr_logger("urllib3")


def get_tempfile_logger():
    """Creates a logger that writes to a temporary
    logfile. Returns the logger and path to tempfile"""
    logger = logging.getLogger("tempfile_logger")
    file_handle, filepath = tempfile.mkstemp()
    # close the file as it will be opened again by FileHandler
    os.close(file_handle)
    handler = logging.FileHandler(filepath, encoding="utf-8")
    handler.terminator = ""
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    return logger, filepath
