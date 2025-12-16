import contextlib
import io
import os
import signal
import sys
from pathlib import Path
from unittest import mock

import click
import pytest
from packaging import version
from requests.exceptions import ConnectionError
from rich.console import Console

import cumulusci
from cumulusci.cli import cci
from cumulusci.cli.tests.utils import run_click_command
from cumulusci.cli.utils import get_installed_version
from cumulusci.core.config import BaseProjectConfig
from cumulusci.core.exceptions import CumulusCIException
from cumulusci.utils import temporary_dir

MagicMock = mock.MagicMock()
CONSOLE = mock.Mock()


@pytest.fixture(autouse=True)
def reset_signal_handler_flag():
    """Reset signal handler flag to ensure clean state for tests"""
    cci._signal_handler_active = False
    yield
    cci._signal_handler_active = False


@mock.patch("cumulusci.cli.cci.tee_stdout_stderr")
@mock.patch("cumulusci.cli.cci.get_tempfile_logger")
@mock.patch("cumulusci.cli.cci.init_logger")
@mock.patch("cumulusci.cli.cci.check_latest_version")
@mock.patch("cumulusci.cli.cci._set_windows_console_encoding")
@mock.patch("cumulusci.cli.cci.CliRuntime")
@mock.patch("cumulusci.cli.cci.cli")
def test_main(
    cli,
    CliRuntime,
    set_windows_encoding,
    check_latest_version,
    init_logger,
    get_tempfile_logger,
    tee,
):
    get_tempfile_logger.return_value = mock.Mock(), "tempfile.log"
    cci.main()

    # Verify _set_windows_console_encoding is called
    set_windows_encoding.assert_called_once()
    check_latest_version.assert_called_once()
    init_logger.assert_called_once()
    CliRuntime.assert_called_once()
    cli.assert_called_once()
    tee.assert_called_once()


@mock.patch("cumulusci.cli.cci.tee_stdout_stderr")
@mock.patch("cumulusci.cli.cci.get_tempfile_logger")
@mock.patch("cumulusci.cli.cci.init_logger")
@mock.patch("cumulusci.cli.cci.check_latest_version")
@mock.patch("cumulusci.cli.cci._set_windows_console_encoding")
@mock.patch("cumulusci.cli.cci.CliRuntime")
@mock.patch("cumulusci.cli.cci.cli")
@mock.patch("pdb.post_mortem")
@mock.patch("sys.exit")
def test_main__debug(
    sys_exit,
    post_mortem,
    cli,
    CliRuntime,
    set_windows_encoding,
    check_latest_version,
    init_logger,
    get_tempfile_logger,
    tee,
):
    cli.side_effect = Exception
    get_tempfile_logger.return_value = (mock.Mock(), "tempfile.log")

    cci.main(["cci", "--debug"])

    set_windows_encoding.assert_called_once()
    check_latest_version.assert_called_once()
    init_logger.assert_called_once_with(debug=True)
    CliRuntime.assert_called_once()
    cli.assert_called_once()
    post_mortem.assert_called_once()
    sys_exit.assert_called_once_with(1)
    get_tempfile_logger.assert_called_once()
    tee.assert_called_once()


@mock.patch("cumulusci.cli.cci.tee_stdout_stderr")
@mock.patch("cumulusci.cli.cci.get_tempfile_logger")
@mock.patch("cumulusci.cli.cci.init_logger")
@mock.patch("cumulusci.cli.cci.check_latest_version")
@mock.patch("cumulusci.cli.cci.CliRuntime")
@mock.patch("cumulusci.cli.cci.cli")
@mock.patch("pdb.post_mortem")
def test_main__cci_show_stacktraces(
    post_mortem,
    cli,
    CliRuntime,
    check_latest_version,
    init_logger,
    get_tempfile_logger,
    tee,
    capsys,
):
    runtime = mock.Mock()
    runtime.universal_config.cli__show_stacktraces = True
    CliRuntime.return_value = runtime
    cli.side_effect = Exception
    get_tempfile_logger.return_value = (mock.Mock(), "tempfile.log")

    with pytest.raises(SystemExit):
        cci.main(["cci"])

    check_latest_version.assert_called_once()
    init_logger.assert_called_once_with(debug=False)
    CliRuntime.assert_called_once()
    cli.assert_called_once()
    post_mortem.assert_not_called()
    captured = capsys.readouterr()
    assert "Traceback (most recent call last)" in captured.err


@mock.patch("cumulusci.cli.cci.tee_stdout_stderr")
@mock.patch("cumulusci.cli.cci.get_tempfile_logger")
@mock.patch("cumulusci.cli.cci.init_logger")
@mock.patch("cumulusci.cli.cci.cli")
@mock.patch("sys.exit")
def test_main__abort(
    sys_exit, cli, init_logger, get_tempfile_logger, tee_stdout_stderr
):
    get_tempfile_logger.return_value = (mock.Mock(), "tempfile.log")
    cli.side_effect = click.Abort
    cci.main(["cci"])
    cli.assert_called_once()
    sys_exit.assert_called_once_with(1)


@mock.patch("cumulusci.cli.cci.tee_stdout_stderr")
@mock.patch("cumulusci.cli.cci.get_tempfile_logger")
@mock.patch("cumulusci.cli.cci.init_logger")
@mock.patch("cumulusci.cli.cci.check_latest_version")
@mock.patch("cumulusci.cli.cci.CliRuntime")
@mock.patch("cumulusci.cli.cci.cli")
@mock.patch("pdb.post_mortem")
@mock.patch("sys.exit")
def test_main__error(
    sys_exit,
    post_mortem,
    cli,
    CliRuntime,
    check_latest_version,
    init_logger,
    get_tempfile_logger,
    tee,
):
    runtime = mock.Mock()
    runtime.universal_config.cli__show_stacktraces = False
    CliRuntime.return_value = runtime

    cli.side_effect = Exception
    get_tempfile_logger.return_value = mock.Mock(), "tempfile.log"

    cci.main(["cci", "org", "info"])

    check_latest_version.assert_called_once()
    init_logger.assert_called_once_with(debug=False)
    CliRuntime.assert_called_once()
    cli.assert_called_once()
    post_mortem.call_count == 0
    sys_exit.assert_called_once_with(1)
    get_tempfile_logger.assert_called_once()
    tee.assert_called_once()

    os.remove("tempfile.log")


@mock.patch("cumulusci.cli.cci.tee_stdout_stderr")
@mock.patch("cumulusci.cli.cci.get_tempfile_logger")
@mock.patch("cumulusci.cli.cci.CliRuntime")
def test_main__CliRuntime_error(CliRuntime, get_tempfile_logger, tee):
    CliRuntime.side_effect = CumulusCIException("something happened")
    get_tempfile_logger.return_value = mock.Mock(), "tempfile.log"

    with contextlib.redirect_stderr(io.StringIO()) as stderr:
        with mock.patch("sys.exit") as sys_exit:
            sys_exit.side_effect = SystemExit  # emulate real sys.exit
            with pytest.raises(SystemExit):
                cci.main(["cci", "org", "info"])

    assert "something happened" in stderr.getvalue()

    tempfile = Path("tempfile.log")
    tempfile.unlink()


@mock.patch("cumulusci.cli.cci.init_logger")  # side effects break other tests
@mock.patch("cumulusci.cli.cci.get_tempfile_logger")
@mock.patch("cumulusci.cli.cci.tee_stdout_stderr")
@mock.patch("cumulusci.cli.cci.CliRuntime")
@mock.patch("sys.exit", MagicMock())
def test_handle_org_name(
    CliRuntime, tee_stdout_stderr, get_tempfile_logger, init_logger
):

    # get_tempfile_logger doesn't clean up after itself which breaks other tests
    get_tempfile_logger.return_value = mock.Mock(), ""

    with contextlib.redirect_stdout(io.StringIO()) as stdout:
        cci.main(["cci", "org", "default", "xyzzy"])
    assert "xyzzy is now the default org" in stdout.getvalue()

    with contextlib.redirect_stdout(io.StringIO()) as stdout:
        cci.main(["cci", "org", "default", "--org", "xyzzy2"])
    assert "xyzzy2 is now the default org" in stdout.getvalue()

    with contextlib.redirect_stderr(io.StringIO()) as stderr:
        cci.main(["cci", "org", "default", "xyzzy1", "--org", "xyzzy2"])
    assert "not both" in stderr.getvalue()

    CliRuntime().keychain.get_default_org.return_value = ("xyzzy3", None)

    # cci org remove should really need an attached org
    with contextlib.redirect_stderr(io.StringIO()) as stderr:
        cci.main(["cci", "org", "remove"])
    assert "Please specify ORGNAME or --org ORGNAME" in stderr.getvalue()


@mock.patch("cumulusci.cli.cci.init_logger")  # side effects break other tests
@mock.patch("cumulusci.cli.cci.get_tempfile_logger")
@mock.patch("cumulusci.cli.cci.tee_stdout_stderr")
@mock.patch("sys.exit")
@mock.patch("cumulusci.cli.cci.CliRuntime")
def test_cci_org_default__no_orgname(
    CliRuntime, exit, tee_stdout_stderr, get_tempfile_logger, init_logger
):
    # get_tempfile_logger doesn't clean up after itself which breaks other tests
    get_tempfile_logger.return_value = mock.Mock(), ""

    CliRuntime().keychain.get_default_org.return_value = ("xyzzy4", None)
    with contextlib.redirect_stdout(io.StringIO()) as stdout:
        cci.main(["cci", "org", "default"])
    assert "xyzzy4 is the default org" in stdout.getvalue()

    CliRuntime().keychain.get_default_org.return_value = (None, None)
    with contextlib.redirect_stdout(io.StringIO()) as stdout:
        cci.main(["cci", "org", "default"])
    assert "There is no default org" in stdout.getvalue()


DEPLOY_CLASS_PATH = f"cumulusci.tasks.salesforce.Deploy{'.Deploy' if sys.version_info >= (3, 11) else ''}"


@mock.patch(
    "cumulusci.cli.cci.init_logger", mock.Mock()
)  # side effects break other tests
@mock.patch("cumulusci.cli.cci.tee_stdout_stderr", mock.MagicMock())
@mock.patch(f"{DEPLOY_CLASS_PATH}.__call__", mock.Mock())
@mock.patch("sys.exit", mock.Mock())
@mock.patch("cumulusci.cli.cci.get_tempfile_logger")
@mock.patch("cumulusci.cli.cci.CliRuntime")
@mock.patch(f"{DEPLOY_CLASS_PATH}.__init__")
def test_cci_run_task_options__with_dash(
    Deploy,
    CliRuntime,
    get_tempfile_logger,
):
    # get_tempfile_logger doesn't clean up after itself which breaks other tests
    Deploy.return_value = None
    get_tempfile_logger.return_value = mock.Mock(), ""
    CliRuntime.return_value = runtime = mock.Mock()
    runtime.get_org.return_value = ("test", mock.Mock())
    runtime.project_config = BaseProjectConfig(
        runtime.universal_config,
        {
            "project": {"name": "Test"},
            "tasks": {"deploy": {"class_path": "cumulusci.tasks.salesforce.Deploy"}},
        },
    )

    cci.main(
        ["cci", "task", "run", "deploy", "--path", "x", "--clean-meta-xml", "False"]
    )
    task_config = Deploy.mock_calls[0][1][1]
    assert "clean_meta_xml" in task_config.options


@mock.patch("cumulusci.cli.cci.init_logger", mock.Mock())
@mock.patch("cumulusci.cli.cci.tee_stdout_stderr", mock.MagicMock())
@mock.patch(f"{DEPLOY_CLASS_PATH}.__call__", mock.Mock())
@mock.patch("sys.exit", mock.Mock())
@mock.patch("cumulusci.cli.cci.get_tempfile_logger")
@mock.patch("cumulusci.cli.cci.CliRuntime")
@mock.patch(f"{DEPLOY_CLASS_PATH}.__init__")
def test_cci_run_task_options__old_style_with_dash(
    Deploy,
    CliRuntime,
    get_tempfile_logger,
):
    # get_tempfile_logger doesn't clean up after itself which breaks other tests
    Deploy.return_value = None
    get_tempfile_logger.return_value = mock.Mock(), ""
    CliRuntime.return_value = runtime = mock.Mock()
    runtime.get_org.return_value = ("test", mock.Mock())
    runtime.project_config = BaseProjectConfig(
        runtime.universal_config,
        {
            "project": {"name": "Test"},
            "tasks": {"deploy": {"class_path": "cumulusci.tasks.salesforce.Deploy"}},
        },
    )

    cci.main(
        [
            "cci",
            "task",
            "run",
            "deploy",
            "--path",
            "x",
            "-o",
            "clean-meta-xml",
            "False",
        ]
    )
    task_config = Deploy.mock_calls[0][1][1]
    assert "clean_meta_xml" in task_config.options


@mock.patch("cumulusci.cli.cci.open")
@mock.patch("cumulusci.cli.cci.traceback")
def test_handle_exception(traceback, cci_open):
    console = mock.Mock()
    Console.return_value = console
    error_message = "foo"
    cci_open.__enter__.return_value = mock.Mock()

    with contextlib.redirect_stderr(io.StringIO()) as stderr:
        cci.handle_exception(error_message, False, "logfile.path")

    stderr = stderr.getvalue()
    assert f"Error: {error_message}" in stderr
    assert cci.SUGGEST_ERROR_COMMAND in stderr
    traceback.print_exc.assert_called_once()


@mock.patch("cumulusci.cli.cci.open")
def test_handle_exception__error_cmd(cci_open):
    """Ensure we don't write to logfiles when running `cci error ...` commands."""
    error_message = "foo"
    logfile_path = None

    with contextlib.redirect_stderr(io.StringIO()) as stderr:
        cci.handle_exception(error_message, False, logfile_path)

    stderr = stderr.getvalue()
    assert f"Error: {error_message}" in stderr
    assert cci.SUGGEST_ERROR_COMMAND in stderr
    cci_open.assert_not_called()


@mock.patch("cumulusci.cli.cci.open")
@mock.patch("cumulusci.cli.cci.traceback")
def test_handle_click_exception(traceback, cci_open):
    cci_open.__enter__.return_value = mock.Mock()

    with contextlib.redirect_stderr(io.StringIO()) as stderr:
        cci.handle_exception(click.ClickException("[oops]"), False, "file.path")

    stderr = stderr.getvalue()
    assert "Error: [oops]" in stderr
    traceback.assert_not_called()


@mock.patch("cumulusci.cli.cci.open")
def test_handle_connection_exception(cci_open):
    cci_open.__enter__.return_value = mock.Mock()

    with contextlib.redirect_stderr(io.StringIO()) as stderr:
        cci.handle_exception(ConnectionError(), False, "file.log")

    stderr = stderr.getvalue()
    assert "We encountered an error with your internet connection." in stderr


def test_cli():
    run_click_command(cci.cli)


@mock.patch(
    "cumulusci.cli.cci.get_latest_final_version",
    mock.Mock(return_value=version.parse("100")),
)
def test_version(capsys):
    run_click_command(cci.version)
    console_output = capsys.readouterr().out
    assert f"CumulusCI Plus version: {cumulusci.__version__}" in console_output
    assert "There is a newer version of CumulusCI Plus available" in console_output


@mock.patch(
    "cumulusci.cli.cci.get_latest_final_version",
    mock.Mock(return_value=version.parse("1")),
)
def test_version__latest(capsys):
    run_click_command(cci.version)
    console_output = capsys.readouterr().out
    assert "You have the latest version of CumulusCI" in console_output


@mock.patch("cumulusci.cli.cci.warn_if_no_long_paths")
@mock.patch("cumulusci.cli.cci.get_latest_final_version", get_installed_version)
def test_version__win_path_warning(warn_if):
    run_click_command(cci.version)
    warn_if.assert_called_once()


@mock.patch("code.interact")
def test_shell(interact):
    run_click_command(cci.shell)
    interact.assert_called_once()
    assert "config" in interact.call_args[1]["local"]
    assert "runtime" in interact.call_args[1]["local"]


@mock.patch("runpy.run_path")
def test_shell_script(runpy):
    run_click_command(cci.shell, script="foo.py")
    runpy.assert_called_once()
    assert "config" in runpy.call_args[1]["init_globals"]
    assert "runtime" in runpy.call_args[1]["init_globals"]
    assert runpy.call_args[0][0] == "foo.py", runpy.call_args[0]


@mock.patch("builtins.print")
def test_shell_code(print):
    run_click_command(cci.shell, python="print(config, runtime)")
    print.assert_called_once()


@mock.patch("cumulusci.cli.cci.print")
def test_shell_mutually_exclusive_args(print):
    with pytest.raises(Exception) as e:
        run_click_command(cci.shell, script="foo.py", python="print(config, runtime)")
    assert "Cannot specify both" in e.value.message


@mock.patch("code.interact")
def test_shell__no_project(interact):
    with temporary_dir():
        run_click_command(cci.shell)
        interact.assert_called_once()


def test_cover_command_groups():
    run_click_command(cci.project)
    run_click_command(cci.org)
    run_click_command(cci.task)
    run_click_command(cci.flow)
    run_click_command(cci.service)
    # no assertion; this test is for coverage of empty methods


@mock.patch(
    "cumulusci.cli.runtime.CliRuntime.get_org",
    lambda *args, **kwargs: (MagicMock(), MagicMock()),
)
@mock.patch("cumulusci.core.runtime.BaseCumulusCI._load_keychain", MagicMock())
@mock.patch("pdb.post_mortem", MagicMock())
@mock.patch("cumulusci.cli.cci.tee_stdout_stderr", MagicMock())
@mock.patch("cumulusci.cli.cci.init_logger", MagicMock())
@mock.patch("cumulusci.cli.cci.get_tempfile_logger")
def test_run_task_debug(get_tempfile_logger):
    get_tempfile_logger.return_value = (mock.Mock(), "tempfile.log")

    gipnew = "cumulusci.tasks.preflight.packages.GetInstalledPackages._run_task"
    with mock.patch(gipnew, mock_validate_debug(False)):
        cci.main(["cci", "task", "run", "get_installed_packages"])
    with mock.patch(gipnew, mock_validate_debug(True)):
        cci.main(["cci", "task", "run", "get_installed_packages", "--debug"])


@mock.patch(
    "cumulusci.cli.runtime.CliRuntime.get_org",
    lambda *args, **kwargs: (MagicMock(), MagicMock()),
)
@mock.patch("cumulusci.core.runtime.BaseCumulusCI._load_keychain", MagicMock())
@mock.patch("pdb.post_mortem", MagicMock())
@mock.patch("cumulusci.cli.cci.tee_stdout_stderr", MagicMock())
@mock.patch("cumulusci.cli.cci.init_logger", MagicMock())
@mock.patch("cumulusci.tasks.robotframework.RobotLibDoc", MagicMock())
@mock.patch("cumulusci.cli.cci.get_tempfile_logger")
def test_run_flow_debug(get_tempfile_logger):
    get_tempfile_logger.return_value = (mock.Mock(), "tempfile.log")
    rtd = "cumulusci.tasks.robotframework.RobotTestDoc._run_task"

    with mock.patch(rtd, mock_validate_debug(False)):
        cci.main(["cci", "flow", "run", "robot_docs"])
    with mock.patch(rtd, mock_validate_debug(True)):
        cci.main(["cci", "flow", "run", "robot_docs", "--debug"])


def mock_validate_debug(value):
    def _run_task(self, *args, **kwargs):
        assert bool(self.debug_mode) == bool(value)

    return _run_task


@mock.patch("cumulusci.cli.cci.tee_stdout_stderr")
@mock.patch("cumulusci.cli.cci.get_tempfile_logger")
@mock.patch("cumulusci.cli.cci.init_logger")
@mock.patch("cumulusci.cli.cci.check_latest_version")
@mock.patch("cumulusci.cli.cci.CliRuntime")
@mock.patch("cumulusci.cli.cci.show_version_info")
def test_dash_dash_version(
    show_version_info,
    CliRuntime,
    check_latest_version,
    init_logger,
    get_tempfile_logger,
    tee,
):
    get_tempfile_logger.return_value = mock.Mock(), "tempfile.log"
    cci.main(["cci", "--help"])
    assert len(show_version_info.mock_calls) == 0

    cci.main(["cci", "version"])
    assert len(show_version_info.mock_calls) == 1

    cci.main(["cci", "--version"])
    assert len(show_version_info.mock_calls) == 2


@mock.patch("sys.exit")
@mock.patch("cumulusci.cli.cci.Console")
@mock.patch("os.killpg", create=True)
@mock.patch("os.getpgrp", create=True)
@mock.patch("signal.signal")
def test_signal_handler_terminates_process_group(
    mock_signal, mock_getpgrp, mock_killpg, mock_console, mock_exit
):
    """Test that the signal handler terminates the process group"""
    console_instance = mock_console.return_value
    mock_getpgrp.return_value = 1234  # Mock process group ID

    # Mock the global exit stack
    mock_exit_stack = mock.Mock()
    with mock.patch.object(cci, "_exit_stack", mock_exit_stack):
        # Mock hasattr to return True for Unix functions
        with mock.patch("builtins.hasattr", return_value=True):
            # Call the signal handler with SIGTERM
            cci._signal_handler(signal.SIGTERM, None)

            # Verify console output
            console_instance.print.assert_any_call(
                "\n[yellow]Received SIGTERM - CumulusCI is being terminated[/yellow]"
            )
            console_instance.print.assert_any_call(
                "[yellow]Exiting with failure code due to external cancellation.[/yellow]"
            )
            console_instance.print.assert_any_call(
                "[yellow]Terminating child processes...[/yellow]"
            )

            # Verify cleanup was called
            mock_exit_stack.close.assert_called_once()

            # Verify signal was temporarily ignored and then restored
            mock_signal.assert_called()

            # Verify process group was terminated
            mock_getpgrp.assert_called_once()
            mock_killpg.assert_called_once_with(1234, signal.SIGTERM)

            # Verify exit with correct code
            mock_exit.assert_called_once_with(143)


@mock.patch("sys.exit")
@mock.patch("cumulusci.cli.cci.Console")
@mock.patch("os.killpg", create=True)
@mock.patch("os.getpgrp", create=True)
@mock.patch("signal.signal")
def test_signal_handler_sigint(
    mock_signal, mock_getpgrp, mock_killpg, mock_console, mock_exit
):
    """Test that the signal handler properly handles SIGINT"""
    console_instance = mock_console.return_value
    mock_getpgrp.return_value = 1234

    # Mock the global exit stack
    mock_exit_stack = mock.Mock()
    with mock.patch.object(cci, "_exit_stack", mock_exit_stack):
        # Mock hasattr to return True for Unix functions
        with mock.patch("builtins.hasattr", return_value=True):
            # Call the signal handler with SIGINT
            cci._signal_handler(signal.SIGINT, None)

            # Verify console output
            console_instance.print.assert_any_call(
                "\n[yellow]Received SIGINT - CumulusCI is being terminated[/yellow]"
            )

            # Verify process group was terminated with SIGINT
            mock_killpg.assert_called_once_with(1234, signal.SIGINT)

            # Verify exit with correct code for SIGINT
            mock_exit.assert_called_once_with(130)


@mock.patch("sys.exit")
@mock.patch("cumulusci.cli.cci.Console")
def test_signal_handler_prevents_recursion(mock_console, mock_exit):
    """Test that the signal handler prevents recursive calls"""
    console_instance = mock_console.return_value

    # Set the flag to simulate handler already active
    with mock.patch.object(cci, "_signal_handler_active", True):
        # Call the signal handler
        cci._signal_handler(signal.SIGTERM, None)

        # Verify no console output (handler should return immediately)
        console_instance.print.assert_not_called()

        # Verify no exit call
        mock_exit.assert_not_called()


@mock.patch("sys.exit")
@mock.patch("cumulusci.cli.cci.Console")
@mock.patch("os.killpg", create=True)
@mock.patch("os.getpgrp", create=True)
@mock.patch("signal.signal")
def test_signal_handler_handles_killpg_error(
    mock_signal, mock_getpgrp, mock_killpg, mock_console, mock_exit
):
    """Test that the signal handler handles errors from killpg gracefully"""
    console_instance = mock_console.return_value
    mock_getpgrp.return_value = 1234
    mock_killpg.side_effect = OSError("Process group not found")

    # Mock hasattr to return True for Unix functions
    with mock.patch("builtins.hasattr", return_value=True):
        # Call the signal handler with SIGTERM
        cci._signal_handler(signal.SIGTERM, None)

    # Verify error message was printed
    console_instance.print.assert_any_call(
        "[red]Warning: Error terminating child processes: Process group not found[/red]"
    )

    # Verify it still exits with correct code
    mock_exit.assert_called_once_with(143)


@mock.patch("sys.exit")
@mock.patch("cumulusci.cli.cci.Console")
def test_signal_handler_without_process_group_support(mock_console, mock_exit):
    """Test that the signal handler works on Windows where process groups aren't supported"""
    console_instance = mock_console.return_value

    # Mock the global exit stack
    mock_exit_stack = mock.Mock()
    with mock.patch.object(cci, "_exit_stack", mock_exit_stack):
        # Mock hasattr to return False for Unix functions (like on Windows)
        with mock.patch("builtins.hasattr", return_value=False):
            # Call the signal handler with SIGTERM
            cci._signal_handler(signal.SIGTERM, None)

            # Verify console output
            console_instance.print.assert_any_call(
                "\n[yellow]Received SIGTERM - CumulusCI is being terminated[/yellow]"
            )
            console_instance.print.assert_any_call(
                "[yellow]Exiting with failure code due to external cancellation.[/yellow]"
            )
            console_instance.print.assert_any_call(
                "[yellow]Terminating child processes...[/yellow]"
            )
            console_instance.print.assert_any_call(
                "[yellow]Process group termination not supported on this platform[/yellow]"
            )

            # Verify cleanup was called
            mock_exit_stack.close.assert_called_once()

            # Verify exit with correct code
            mock_exit.assert_called_once_with(143)


@mock.patch("os.setpgrp", create=True)
def test_main_creates_process_group(mock_setpgrp):
    """Test that main() creates a new process group"""
    # Mock dependencies to avoid actual CLI execution
    with mock.patch.multiple(
        "cumulusci.cli.cci",
        signal=mock.Mock(),
        init_requests_trust=mock.Mock(),
        check_latest_version=mock.Mock(),
        check_latest_plugins=mock.Mock(),
        get_tempfile_logger=mock.Mock(return_value=(mock.Mock(), "tempfile.log")),
        tee_stdout_stderr=mock.Mock(
            return_value=mock.Mock(__enter__=mock.Mock(), __exit__=mock.Mock())
        ),
        set_debug_mode=mock.Mock(
            return_value=mock.Mock(__enter__=mock.Mock(), __exit__=mock.Mock())
        ),
        CliRuntime=mock.Mock(),
        init_logger=mock.Mock(),
        cli=mock.Mock(),
    ):
        try:
            cci.main(["cci", "version"])
        except SystemExit:
            pass  # Expected for version command

        # Verify process group was created
        mock_setpgrp.assert_called_once()


@mock.patch("os.setpgrp", create=True)
def test_main_handles_setpgrp_error(mock_setpgrp):
    """Test that main() handles setpgrp errors gracefully"""
    mock_setpgrp.side_effect = OSError("Operation not permitted")

    # Mock dependencies to avoid actual CLI execution
    with mock.patch.multiple(
        "cumulusci.cli.cci",
        signal=mock.Mock(),
        init_requests_trust=mock.Mock(),
        check_latest_version=mock.Mock(),
        check_latest_plugins=mock.Mock(),
        get_tempfile_logger=mock.Mock(return_value=(mock.Mock(), "tempfile.log")),
        tee_stdout_stderr=mock.Mock(
            return_value=mock.Mock(__enter__=mock.Mock(), __exit__=mock.Mock())
        ),
        set_debug_mode=mock.Mock(
            return_value=mock.Mock(__enter__=mock.Mock(), __exit__=mock.Mock())
        ),
        CliRuntime=mock.Mock(),
        init_logger=mock.Mock(),
        cli=mock.Mock(),
    ):
        try:
            # Should not raise an exception even if setpgrp fails
            cci.main(["cci", "version"])
        except SystemExit:
            pass  # Expected for version command
        except OSError:
            pytest.fail("main() should handle setpgrp errors gracefully")

        # Verify setpgrp was attempted
        mock_setpgrp.assert_called_once()


@mock.patch("signal.signal")
def test_main_registers_signal_handlers(mock_signal):
    """Test that main() registers signal handlers"""
    # Create a proper context manager mock
    context_manager_mock = mock.Mock()
    context_manager_mock.__enter__ = mock.Mock(return_value=context_manager_mock)
    context_manager_mock.__exit__ = mock.Mock(return_value=None)

    # Create another context manager mock for set_debug_mode
    debug_context_mock = mock.Mock()
    debug_context_mock.__enter__ = mock.Mock(return_value=debug_context_mock)
    debug_context_mock.__exit__ = mock.Mock(return_value=None)

    # Mock dependencies to avoid actual CLI execution
    with mock.patch.multiple(
        "cumulusci.cli.cci",
        init_requests_trust=mock.Mock(),
        check_latest_version=mock.Mock(),
        check_latest_plugins=mock.Mock(),
        get_tempfile_logger=mock.Mock(return_value=(mock.Mock(), "tempfile.log")),
        tee_stdout_stderr=mock.Mock(return_value=context_manager_mock),
        set_debug_mode=mock.Mock(return_value=debug_context_mock),
        CliRuntime=mock.Mock(),
        init_logger=mock.Mock(),
        cli=mock.Mock(),
    ):
        try:
            cci.main(["cci", "version"])
        except SystemExit:
            pass  # Expected for version command

        # Verify signal handlers were registered
        expected_calls = [
            mock.call(signal.SIGTERM, cci._signal_handler),
            mock.call(signal.SIGINT, cci._signal_handler),
        ]
        mock_signal.assert_has_calls(expected_calls, any_order=True)
