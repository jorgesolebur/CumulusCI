import contextlib
import io
import json
import tempfile
from pathlib import Path
from unittest import mock
from unittest.mock import Mock, patch

import click
import pytest

from cumulusci.cli import cci as cci_module
from cumulusci.cli.runtime import CliRuntime
from cumulusci.core.config import BaseProjectConfig
from cumulusci.core.exceptions import CumulusCIUsageError

from .. import task
from .utils import DummyTask, run_click_command

color_opts = {"options": {"color": {}}}
multiple_opts = {"options": {"foo": {}, "bar": {}, "baz": {}}}

test_tasks = {
    "dummy-task": {
        "class_path": "cumulusci.cli.tests.utils.DummyTask",
        "description": "This is a dummy task.",
    },
    "dummy-derived-task": {
        "class_path": "cumulusci.cli.tests.test_run_task.DummyDerivedTask"
    },
}


@pytest.fixture
def runtime():
    runtime = CliRuntime(load_keychain=False)
    runtime.project_config.config["tasks"] = {**test_tasks}

    runtime.keychain = Mock()
    runtime.keychain.get_default_org.return_value = (None, None)
    runtime._load_keychain = Mock()

    yield runtime


def test_task_run(runtime):
    DummyTask._run_task = Mock()
    multi_cmd = task.RunTaskCommand()
    with click.Context(multi_cmd, obj=runtime) as ctx:
        cmd = multi_cmd.get_command(ctx, "dummy-task")
        cmd.callback(runtime, "dummy-task", color="blue")

    DummyTask._run_task.assert_called_once()


def test_task_run__no_project(runtime):
    # Add task to universal_config so it can be found
    runtime.universal_config.config["tasks"] = {**test_tasks}
    runtime.project_config = None
    runtime.project_config_error = Exception("Broken")
    multi_cmd = task.RunTaskCommand()
    with pytest.raises(Exception, match="Broken"):
        with click.Context(multi_cmd, obj=runtime) as ctx:
            multi_cmd.get_command(ctx, "dummy-task")


def test_task_run__global_task_without_project(runtime):
    """Test that a global task can run without a project context."""
    # Define a global task
    global_task = {
        "global-dummy-task": {
            "class_path": "cumulusci.cli.tests.utils.DummyTask",
            "description": "This is a global dummy task.",
            "is_global": True,
        }
    }

    # Add global task to universal_config
    runtime.universal_config.config["tasks"] = {**global_task}
    runtime.project_config = None
    runtime.project_config_error = Exception("No project config")

    DummyTask._run_task = Mock()
    multi_cmd = task.RunTaskCommand()

    # Should NOT raise an exception because the task is global
    with click.Context(multi_cmd, obj=runtime) as ctx:
        cmd = multi_cmd.get_command(ctx, "global-dummy-task")
        cmd.callback(runtime, "global-dummy-task", color="blue")

    # Verify the task was executed
    DummyTask._run_task.assert_called_once()


def test_task_run__debug_before(runtime):
    DummyTask._run_task = Mock()
    multi_cmd = task.RunTaskCommand()
    set_trace = Mock(side_effect=SetTrace)

    with click.Context(multi_cmd, obj=runtime) as ctx:
        with patch("pdb.set_trace", set_trace):
            with pytest.raises(SetTrace):
                cmd = multi_cmd.get_command(ctx, "dummy-task")
                cmd.callback(
                    runtime,
                    "dummy_task",
                    color="blue",
                    debug_before=True,
                    debug_after=False,
                )


def test_task_run__debug_after(runtime):
    DummyTask._run_task = Mock()
    multi_cmd = task.RunTaskCommand()
    set_trace = Mock(side_effect=SetTrace)

    with click.Context(multi_cmd, obj=runtime) as ctx:
        with patch("pdb.set_trace", set_trace):
            with pytest.raises(SetTrace):
                cmd = multi_cmd.get_command(ctx, "dummy-task")
                cmd.callback(
                    runtime,
                    "dummy-task",
                    color="blue",
                    debug_before=False,
                    debug_after=True,
                )


def test_task_run__help(runtime):
    DummyTask._run_task = Mock()
    multi_cmd = task.RunTaskCommand()
    with click.Context(multi_cmd, obj=runtime) as ctx:
        cmd = multi_cmd.get_command(ctx, "dummy-task")

    assert "This is a dummy task." in cmd.help  # task description


def test_task_run__list_commands(runtime):
    multi_cmd = task.RunTaskCommand()
    with click.Context(multi_cmd, obj=runtime) as ctx:
        commands = multi_cmd.list_commands(ctx)
    assert commands == ["dummy-derived-task", "dummy-task"]


def test_format_help(runtime):
    runtime.universal_config = Mock()
    multi_cmd = task.RunTaskCommand()
    with contextlib.redirect_stdout(io.StringIO()) as stdout:
        with click.Context(multi_cmd, obj=runtime) as ctx:
            multi_cmd.format_help(ctx, Mock())

    stdout = stdout.getvalue()
    assert "Usage: cci task run <task_name> [TASK_OPTIONS...]" in stdout
    assert "See above for a complete list of available tasks." in stdout
    assert "Use cci task info <task_name>" in stdout
    assert len(runtime.universal_config.method_calls) == 0


def test_get_default_command_options():
    opts = task.RunTaskCommand()._get_default_command_options(is_salesforce_task=False)
    assert len(opts) == 4  # no-prompt, debug, debug-before, debug-after

    opts = task.RunTaskCommand()._get_default_command_options(is_salesforce_task=True)
    assert len(opts) == 5  # +1 for org
    assert any([o.name == "org" for o in opts])


def test_collect_task_options():
    new_options = {"debug-before": None}
    old_options = (("color", "green"),)

    opts = task.RunTaskCommand()._collect_task_options(
        new_options, old_options, "dummy-task", color_opts["options"]
    )
    assert opts == {"color": "green"}


def test_collect_task_options__duplicate():
    new_options = {"color": "aqua"}
    old_options = (("color", "green"),)

    with pytest.raises(CumulusCIUsageError):
        task.RunTaskCommand()._collect_task_options(
            new_options, old_options, "dummy-task", color_opts["options"]
        )


def test_collect_task_options__not_in_task():
    new_options = {}
    old_options = (("color", "green"),)

    with pytest.raises(CumulusCIUsageError):
        task.RunTaskCommand()._collect_task_options(
            new_options, old_options, "dummy-task", {"not-color": {}}
        )


@patch("cumulusci.cli.task.CliTable")
def test_task_list(cli_tbl):
    runtime = Mock()
    runtime.universal_config.cli__plain_output = None
    runtime.get_available_tasks.return_value = [
        {"name": "test_task", "description": "Test Task", "group": "Test Group"}
    ]

    run_click_command(task.task_list, runtime=runtime, plain=False, print_json=False)

    cli_tbl.assert_called_with(
        [["Task", "Description"], ["test_task", "Test Task"]], "Test Group"
    )


def test_task_list__json(capsys):
    expected_output = {
        "name": "test_task",
        "description": "This can be a really long description that might need a newline if some library is formatting it for ANSI output.",
        "group": "Test Group",
    }
    runtime = Mock()
    runtime.universal_config.cli__plain_output = None
    runtime.get_available_tasks.return_value = [expected_output]

    run_click_command(task.task_list, runtime=runtime, plain=False, print_json=True)

    captured = capsys.readouterr()
    parsed_output = json.loads(captured.out)[0]
    assert parsed_output == expected_output


@patch("cumulusci.cli.task.doc_task", return_value="docs")
def test_task_doc(doc_task):
    runtime = Mock()
    runtime.universal_config.tasks = {"test": {}}
    run_click_command(task.task_doc, runtime=runtime, project=False)
    doc_task.assert_called()


def test_task_doc__project__outside_project():
    runtime = Mock()
    runtime.project_config = None
    with pytest.raises(click.UsageError):
        run_click_command(task.task_doc, runtime=runtime, project=True)


@patch("click.echo")
@patch("cumulusci.cli.task.doc_task", return_value="docs")
def test_task_doc_project(doc_task, echo):
    runtime = Mock()
    runtime.universal_config = {"tasks": {}}
    runtime.project_config = BaseProjectConfig(
        runtime.universal_config,
        {
            "project": {"name": "Test"},
            "tasks": {"task1": {"a": "b"}, "task2": {}},
        },
    )
    runtime.project_config.config_project = {"tasks": {"task1": {"a": "b"}}}
    run_click_command(task.task_doc, runtime=runtime, project=True)
    doc_task.assert_called()
    echo.assert_called()


@patch("cumulusci.cli.task.Path")
@patch("click.echo")
@patch("cumulusci.cli.task.doc_task", return_value="docs")
def test_task_doc_project_write(doc_task, echo, Path):
    runtime = Mock()
    runtime.universal_config.tasks = {"test": {}}
    runtime.project_config = BaseProjectConfig(
        runtime.universal_config,
        {
            "project": {"name": "Test"},
            "tasks": {"option": {"a": "b"}},
        },
    )
    runtime.project_config.config_project = {"tasks": {"option": {"a": "b"}}}
    run_click_command(task.task_doc, runtime=runtime, project=True, write=True)
    doc_task.assert_called()
    echo.assert_not_called()


@patch("cumulusci.cli.task.rst2ansi")
@patch("cumulusci.cli.task.doc_task")
def test_task_info(doc_task, rst2ansi):
    runtime = Mock()
    runtime.project_config.tasks__test = {"options": {}}
    run_click_command(task.task_info, runtime=runtime, task_name="test")
    doc_task.assert_called_once()
    rst2ansi.assert_called_once()


class SetTrace(Exception):
    pass


class DummyDerivedTask(DummyTask):
    def _run_task(self):
        click.echo(f"<{self.__class__}>\n\tcolor: {self.options['color']}")


@mock.patch("cumulusci.cli.cci.tee_stdout_stderr")
@mock.patch("cumulusci.cli.cci.get_tempfile_logger")
@mock.patch("cumulusci.cli.cci.init_logger")
@mock.patch("cumulusci.cli.cci.check_latest_plugins")
@mock.patch("cumulusci.cli.cci.check_latest_version")
@mock.patch("cumulusci.cli.cci._set_windows_console_encoding")
@mock.patch("cumulusci.cli.cci.load_dotenv")
@mock.patch("cumulusci.cli.cci.CliRuntime")
@mock.patch("cumulusci.cli.cci.cli")
def test_task_run__loadenv_with_project_root(
    cli,
    CliRuntime,
    load_dotenv,
    set_windows_encoding,
    check_latest_version,
    check_latest_plugins,
    init_logger,
    get_tempfile_logger,
    tee,
):
    """Test that --loadenv loads .env file from project root at cci.py level."""
    with tempfile.TemporaryDirectory() as temp_dir:
        env_path = Path(temp_dir) / ".env"
        env_path.write_text("TEST_VAR=test_value\n")

        mock_runtime = mock.Mock()
        mock_runtime.project_config.repo_root = temp_dir
        CliRuntime.return_value = mock_runtime
        get_tempfile_logger.return_value = mock.Mock(), "tempfile.log"

        cci_module.main(["cci", "--loadenv", "task", "run", "dummy-task"])

        expected_path = Path(temp_dir) / ".env"
        load_dotenv.assert_called_once_with(dotenv_path=expected_path)


@mock.patch("cumulusci.cli.cci.tee_stdout_stderr")
@mock.patch("cumulusci.cli.cci.get_tempfile_logger")
@mock.patch("cumulusci.cli.cci.init_logger")
@mock.patch("cumulusci.cli.cci.check_latest_plugins")
@mock.patch("cumulusci.cli.cci.check_latest_version")
@mock.patch("cumulusci.cli.cci._set_windows_console_encoding")
@mock.patch("cumulusci.cli.cci.load_dotenv")
@mock.patch("cumulusci.cli.cci.CliRuntime")
@mock.patch("cumulusci.cli.cci.cli")
def test_task_run__loadenv_false(
    cli,
    CliRuntime,
    load_dotenv,
    set_windows_encoding,
    check_latest_version,
    check_latest_plugins,
    init_logger,
    get_tempfile_logger,
    tee,
):
    """Test that load_dotenv is not called when --loadenv flag is absent."""
    mock_runtime = mock.Mock()
    CliRuntime.return_value = mock_runtime
    get_tempfile_logger.return_value = mock.Mock(), "tempfile.log"

    cci_module.main(["cci", "task", "run", "dummy-task"])

    load_dotenv.assert_not_called()


@mock.patch("cumulusci.cli.cci.tee_stdout_stderr")
@mock.patch("cumulusci.cli.cci.get_tempfile_logger")
@mock.patch("cumulusci.cli.cci.init_logger")
@mock.patch("cumulusci.cli.cci.check_latest_plugins")
@mock.patch("cumulusci.cli.cci.check_latest_version")
@mock.patch("cumulusci.cli.cci._set_windows_console_encoding")
@mock.patch("cumulusci.cli.cci.load_dotenv")
@mock.patch("cumulusci.cli.cci.CliRuntime")
@mock.patch("cumulusci.cli.cci.cli")
def test_task_run__loadenv_not_provided(
    cli,
    CliRuntime,
    load_dotenv,
    set_windows_encoding,
    check_latest_version,
    check_latest_plugins,
    init_logger,
    get_tempfile_logger,
    tee,
):
    """Test that load_dotenv is not called when --loadenv flag is not provided."""
    mock_runtime = mock.Mock()
    CliRuntime.return_value = mock_runtime
    get_tempfile_logger.return_value = mock.Mock(), "tempfile.log"

    cci_module.main(["cci", "task", "run", "dummy-task"])

    load_dotenv.assert_not_called()


@mock.patch("cumulusci.cli.cci.tee_stdout_stderr")
@mock.patch("cumulusci.cli.cci.get_tempfile_logger")
@mock.patch("cumulusci.cli.cci.init_logger")
@mock.patch("cumulusci.cli.cci.check_latest_plugins")
@mock.patch("cumulusci.cli.cci.check_latest_version")
@mock.patch("cumulusci.cli.cci._set_windows_console_encoding")
@mock.patch("cumulusci.cli.cci.load_dotenv")
@mock.patch("cumulusci.cli.cci.CliRuntime")
@mock.patch("cumulusci.cli.cci.cli")
def test_task_run__loadenv_none_value(
    cli,
    CliRuntime,
    load_dotenv,
    set_windows_encoding,
    check_latest_version,
    check_latest_plugins,
    init_logger,
    get_tempfile_logger,
    tee,
):
    """Test that load_dotenv is not called when project_config is None."""
    mock_runtime = mock.Mock()
    mock_runtime.project_config = None
    CliRuntime.return_value = mock_runtime
    get_tempfile_logger.return_value = mock.Mock(), "tempfile.log"

    cci_module.main(["cci", "--loadenv", "task", "run", "dummy-task"])

    load_dotenv.assert_not_called()


def test_get_default_command_options_does_not_include_loadenv():
    """Test that loadenv is not in task default options - it was moved to cci.py level."""
    opts = task.RunTaskCommand()._get_default_command_options(is_salesforce_task=False)

    assert len(opts) == 4  # no-prompt, debug, debug-before, debug-after

    loadenv_opt = None
    for opt in opts:
        if hasattr(opt, "name") and opt.name == "loadenv":
            loadenv_opt = opt
            break

    assert loadenv_opt is None
