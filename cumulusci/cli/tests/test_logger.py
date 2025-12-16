import builtins
import logging
import os
from unittest.mock import Mock, patch

from ..logger import _set_windows_console_encoding, get_tempfile_logger, init_logger


class TestLogger:
    @patch("cumulusci.cli.logger.requests")
    @patch("cumulusci.cli.logger.logging")
    def test_init_logger(self, logging, requests):
        logger = Mock(handlers=["leftover"])
        logging.getLogger.return_value = logger
        init_logger()
        logger.removeHandler.assert_called_once_with("leftover")
        logger.addHandler.assert_called_once()

    def test_get_tempfile_logger(self):
        logger, tempfile = get_tempfile_logger()
        assert os.path.isfile(tempfile)
        assert len(logger.handlers) == 1
        assert isinstance(logger.handlers[0], logging.FileHandler)
        # delete temp logfile
        logger.handlers[0].close()
        os.remove(tempfile)

    @patch("cumulusci.cli.logger.os.name", "nt")
    @patch("cumulusci.cli.logger.os.environ")
    @patch("cumulusci.cli.logger.sys.stdout")
    @patch("cumulusci.cli.logger.sys.stderr")
    @patch("builtins.__import__", wraps=builtins.__import__)
    def test_set_windows_console_encoding_on_windows(
        self, mock_import, mock_stderr, mock_stdout, mock_environ
    ):
        """Test that _set_windows_console_encoding() sets encoding on Windows"""
        # Mock stdout/stderr to have reconfigure method
        mock_stdout.reconfigure = Mock()
        mock_stderr.reconfigure = Mock()

        # Mock Windows API - intercept ctypes import
        mock_kernel32 = Mock()
        mock_ctypes = Mock()
        mock_ctypes.windll.kernel32 = mock_kernel32

        def import_side_effect(name, *args, **kwargs):
            if name == "ctypes":
                return mock_ctypes
            # For other imports, use the wrapped original import
            return mock_import.__wrapped__(name, *args, **kwargs)

        mock_import.side_effect = import_side_effect

        _set_windows_console_encoding()

        # Verify environment variable was set
        mock_environ.setdefault.assert_called_once_with("PYTHONIOENCODING", "utf-8")

        # Verify reconfigure was attempted
        mock_stdout.reconfigure.assert_called_once_with(
            encoding="utf-8", errors="replace"
        )
        mock_stderr.reconfigure.assert_called_once_with(
            encoding="utf-8", errors="replace"
        )

        # Verify Windows API was called
        assert mock_kernel32.SetConsoleOutputCP.called
        assert mock_kernel32.SetConsoleOutputCP.call_args[0] == (65001,)
        assert mock_kernel32.SetConsoleCP.called
        assert mock_kernel32.SetConsoleCP.call_args[0] == (65001,)

    @patch("cumulusci.cli.logger.os.name", "posix")
    @patch("cumulusci.cli.logger.os.environ")
    @patch("cumulusci.cli.logger.sys.stdout")
    @patch("cumulusci.cli.logger.sys.stderr")
    def test_set_windows_console_encoding_skips_on_non_windows(
        self, mock_stderr, mock_stdout, mock_environ
    ):
        """Test that _set_windows_console_encoding() does nothing on non-Windows"""
        _set_windows_console_encoding()

        # Verify nothing was called
        mock_environ.setdefault.assert_not_called()
        assert (
            not hasattr(mock_stdout, "reconfigure")
            or not mock_stdout.reconfigure.called
        )
        assert (
            not hasattr(mock_stderr, "reconfigure")
            or not mock_stderr.reconfigure.called
        )

    @patch("cumulusci.cli.logger.os.name", "nt")
    @patch("cumulusci.cli.logger.os.environ")
    @patch("cumulusci.cli.logger.sys.stdout", new_callable=lambda: Mock(spec=[]))
    @patch("cumulusci.cli.logger.sys.stderr", new_callable=lambda: Mock(spec=[]))
    def test_set_windows_console_encoding_handles_no_reconfigure(
        self, mock_stderr, mock_stdout, mock_environ
    ):
        """Test that _set_windows_console_encoding() handles streams without reconfigure"""
        # Mock stdout/stderr created with spec=[] means hasattr() will return False for reconfigure
        # Should not raise an error
        _set_windows_console_encoding()

        # Verify environment variable was still set
        mock_environ.setdefault.assert_called_once_with("PYTHONIOENCODING", "utf-8")

    @patch("cumulusci.cli.logger.os.name", "nt")
    @patch("cumulusci.cli.logger.os.environ")
    @patch("cumulusci.cli.logger.sys.stdout")
    @patch("cumulusci.cli.logger.sys.stderr")
    @patch("builtins.__import__", wraps=builtins.__import__)
    def test_set_windows_console_encoding_handles_reconfigure_error(
        self, mock_import, mock_stderr, mock_stdout, mock_environ
    ):
        """Test that _set_windows_console_encoding() handles reconfigure errors gracefully"""
        # Mock stdout/stderr to raise errors on reconfigure
        mock_stdout.reconfigure = Mock(side_effect=ValueError("Cannot reconfigure"))
        mock_stderr.reconfigure = Mock(side_effect=ValueError("Cannot reconfigure"))

        # Mock ctypes import to avoid errors
        mock_ctypes = Mock()
        mock_kernel32 = Mock()
        mock_ctypes.windll.kernel32 = mock_kernel32

        def import_side_effect(name, *args, **kwargs):
            if name == "ctypes":
                return mock_ctypes
            return mock_import.__wrapped__(name, *args, **kwargs)

        mock_import.side_effect = import_side_effect

        # Should not raise an error
        _set_windows_console_encoding()

        # Verify environment variable was still set
        mock_environ.setdefault.assert_called_once_with("PYTHONIOENCODING", "utf-8")

    @patch("cumulusci.cli.logger.os.name", "nt")
    @patch("cumulusci.cli.logger.os.environ")
    @patch("cumulusci.cli.logger.sys.stdout")
    @patch("cumulusci.cli.logger.sys.stderr")
    @patch("builtins.__import__", wraps=builtins.__import__)
    def test_set_windows_console_encoding_handles_ctypes_error(
        self, mock_import, mock_stderr, mock_stdout, mock_environ
    ):
        """Test that _set_windows_console_encoding() handles ctypes import/API errors gracefully"""
        # Mock stdout/stderr
        mock_stdout.reconfigure = Mock()
        mock_stderr.reconfigure = Mock()

        # Mock ctypes.windll.kernel32 to raise OSError (simulating Windows API failure)
        mock_kernel32 = Mock()
        mock_kernel32.SetConsoleOutputCP.side_effect = OSError("API call failed")
        mock_ctypes = Mock()
        mock_ctypes.windll.kernel32 = mock_kernel32

        def import_side_effect(name, *args, **kwargs):
            if name == "ctypes":
                return mock_ctypes
            return mock_import.__wrapped__(name, *args, **kwargs)

        mock_import.side_effect = import_side_effect

        # Should not raise an error
        _set_windows_console_encoding()

        # Verify environment variable was still set
        mock_environ.setdefault.assert_called_once_with("PYTHONIOENCODING", "utf-8")

    @patch("cumulusci.cli.logger.os.name", "nt")
    @patch("cumulusci.cli.logger.os.environ")
    @patch("cumulusci.cli.logger._set_windows_console_encoding")
    @patch("cumulusci.cli.logger.requests")
    @patch("cumulusci.cli.logger.logging")
    def test_init_logger_calls_set_windows_console_encoding(
        self, logging, requests, mock_set_encoding, mock_environ
    ):
        """Test that init_logger() calls _set_windows_console_encoding()"""
        logger = Mock(handlers=[])
        logging.getLogger.return_value = logger

        init_logger()

        # Verify _set_windows_console_encoding was called
        mock_set_encoding.assert_called_once()
