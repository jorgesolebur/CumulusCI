import json
from unittest import mock

import pytest
import sarge

from cumulusci.core.exceptions import SalesforceDXException
from cumulusci.tasks.salesforce.SfPackageCommands import (
    PackageCreateTask,
    PackageDisplayTask,
    PackageListTask,
    PackageVersionCreateTask,
    PackageVersionDeleteTask,
    PackageVersionDisplayTask,
    PackageVersionListTask,
    PackageVersionReportTask,
    PackageVersionUpdateTask,
    SfPackageCommands,
)

from . import create_task


def create_mock_sarge_command(stdout="", stderr="", returncode=0):
    """Create a mock sarge.Command that satisfies type checking"""
    mock_command = mock.Mock(spec=sarge.Command)
    mock_command.returncode = returncode

    # Mock stdout_text
    stdout_lines = stdout.split("\n") if stdout else []
    mock_stdout_text = mock.Mock()
    mock_stdout_text.__iter__ = mock.Mock(return_value=iter(stdout_lines))
    mock_stdout_text.read = mock.Mock(return_value=stdout)
    mock_command.stdout_text = mock_stdout_text

    # Mock stderr_text
    stderr_lines = stderr.split("\n") if stderr else []
    mock_stderr_text = mock.Mock()
    mock_stderr_text.__iter__ = mock.Mock(return_value=iter(stderr_lines))
    mock_stderr_text.read = mock.Mock(return_value=stderr)
    mock_command.stderr_text = mock_stderr_text

    return mock_command


def setup_devhub_mock(mock_devhub):
    """Helper function to set up devhub mock"""
    mock_devhub.return_value.username = "test-devhub@example.com"


@mock.patch("cumulusci.tasks.salesforce.SfPackageCommands.get_devhub_config")
@mock.patch("cumulusci.tasks.salesforce.SfPackageCommands.sfdx")
class TestSfPackageCommands:
    def test_init_options_basic(self, mock_sfdx, mock_devhub):
        mock_sfdx.return_value = create_mock_sarge_command()
        setup_devhub_mock(mock_devhub)
        task = create_task(SfPackageCommands, {})
        task()
        assert task.package_command == "package "
        assert len(task.args) == 2
        assert "--target-dev-hub" in task.args
        assert "test-devhub@example.com" in task.args

    def test_init_options_all_flags(self, mock_sfdx, mock_devhub):
        json_response = {"status": 0, "result": {}}
        mock_sfdx.return_value = create_mock_sarge_command(
            stdout=json.dumps(json_response)
        )
        setup_devhub_mock(mock_devhub)
        task = create_task(
            SfPackageCommands,
            {
                "json_output": True,
                "api_version": "50.0",
                "flags_dir": "/tmp/flags",
            },
        )
        task()
        expected_args = [
            "--flags-dir",
            "/tmp/flags",
            "--json",
            "--api-version",
            "50.0",
            "--target-dev-hub",
            "test-devhub@example.com",
        ]
        assert all(arg in task.args for arg in expected_args)

    def test_load_json_output_success(self, mock_sfdx, mock_devhub):
        json_response = {"status": 0, "result": {"packageVersionId": "04t000000000001"}}
        stdout = json.dumps(json_response)
        mock_command = create_mock_sarge_command(stdout=stdout)
        mock_sfdx.return_value = mock_command
        setup_devhub_mock(mock_devhub)

        task = create_task(SfPackageCommands, {"json_output": True})
        task()

        assert task.return_values == json_response

    def test_load_json_output_decode_error(self, mock_sfdx, mock_devhub):
        mock_command = create_mock_sarge_command(stdout="invalid json")
        mock_sfdx.return_value = mock_command
        setup_devhub_mock(mock_devhub)

        task = create_task(SfPackageCommands, {"json_output": True})

        with pytest.raises(SalesforceDXException, match="Failed to parse the output"):
            task()

    def test_logging_stdout_and_stderr(self, mock_sfdx, mock_devhub):
        mock_command = create_mock_sarge_command(
            stdout="Success: Package version updated\nVersion ID: 04t000000000001",
            stderr="Warning: Some non-critical issue",
        )
        mock_sfdx.return_value = mock_command
        setup_devhub_mock(mock_devhub)

        task = create_task(SfPackageCommands, {})
        with mock.patch.object(task, "logger") as mock_logger:
            task()

            # Check that stdout lines were logged as info
            mock_logger.info.assert_any_call("Success: Package version updated")
            mock_logger.info.assert_any_call("Version ID: 04t000000000001")

            # Check that stderr lines were logged as error
            mock_logger.error.assert_called_with("Warning: Some non-critical issue")


@mock.patch("cumulusci.tasks.salesforce.SfPackageCommands.get_devhub_config")
@mock.patch("cumulusci.tasks.salesforce.SfPackageCommands.sfdx")
class TestPackageVersionUpdateTask:
    def test_init_task_sets_command(self, mock_sfdx, mock_devhub):
        mock_sfdx.return_value = create_mock_sarge_command()
        setup_devhub_mock(mock_devhub)
        task = create_task(PackageVersionUpdateTask, {"package_id": "0Ho000000000001"})
        task()
        assert task.package_command == "package version update"

    def test_init_options_all_parameters(self, mock_sfdx, mock_devhub):
        json_response = {"status": 0, "result": {"packageVersionId": "04t000000000001"}}
        mock_sfdx.return_value = create_mock_sarge_command(
            stdout=json.dumps(json_response)
        )
        task = create_task(
            PackageVersionUpdateTask,
            {
                "package_id": "0Ho000000000001",
                "version_name": "Updated Version",
                "version_description": "Updated description",
                "branch": "main",
                "tag": "v1.1.0",
                "installation_key": "secret-key",
                "api_version": "50.0",
                "flags_dir": "/tmp/flags",
                "json_output": True,
            },
        )
        task()

        call_args = mock_sfdx.call_args[1]["args"]
        assert mock_sfdx.call_args[1]["log_note"] == "Running package command"
        assert "--package" in call_args
        assert "0Ho000000000001" in call_args
        assert "--version-name" in call_args
        assert "Updated Version" in call_args
        assert "--version-description" in call_args
        assert "Updated description" in call_args
        assert "--branch" in call_args
        assert "main" in call_args
        assert "--tag" in call_args
        assert "v1.1.0" in call_args
        assert "--installation-key" in call_args
        assert "secret-key" in call_args
        assert "--api-version" in call_args
        assert "50.0" in call_args
        assert "--flags-dir" in call_args
        assert "/tmp/flags" in call_args
        assert "--json" in call_args

    def test_minimal_options(self, mock_sfdx, mock_devhub):
        mock_sfdx.return_value = create_mock_sarge_command()
        task = create_task(PackageVersionUpdateTask, {"package_id": "0Ho000000000001"})
        task()

        call_args = mock_sfdx.call_args[1]["args"]
        assert "--package" in call_args
        assert "0Ho000000000001" in call_args

    def test_json_output_logging(self, mock_sfdx, mock_devhub):
        json_response = {"status": 0, "result": {"packageVersionId": "04t000000000001"}}
        stdout = json.dumps(json_response)
        mock_sfdx.return_value = create_mock_sarge_command(stdout=stdout)

        task = create_task(
            PackageVersionUpdateTask,
            {"package_id": "0Ho000000000001", "json_output": True},
        )

        with mock.patch.object(task, "logger") as mock_logger:
            task()
            mock_logger.info.assert_called_with(json_response)

    def test_missing_required_options(self, mock_sfdx, mock_devhub):
        from cumulusci.core.exceptions import TaskOptionsError

        with pytest.raises(TaskOptionsError, match="field required"):
            create_task(PackageVersionUpdateTask, {})


@mock.patch("cumulusci.tasks.salesforce.SfPackageCommands.get_devhub_config")
@mock.patch("cumulusci.tasks.salesforce.SfPackageCommands.sfdx")
class TestPackageVersionCreateTask:
    def test_init_task_sets_command(self, mock_sfdx, mock_devhub):
        mock_sfdx.return_value = create_mock_sarge_command()
        task = create_task(PackageVersionCreateTask, {"package_id": "0Ho000000000001"})
        task()
        assert task.package_command == "package version create"

    def test_init_options_all_parameters(self, mock_sfdx, mock_devhub):
        json_response = {"status": 0, "result": {"packageVersionId": "04t000000000001"}}
        mock_sfdx.return_value = create_mock_sarge_command(
            stdout=json.dumps(json_response)
        )
        task = create_task(
            PackageVersionCreateTask,
            {
                "package_id": "0Ho000000000001",
                "version_name": "New Version",
                "version_description": "New description",
                "branch": "main",
                "tag": "v1.0.0",
                "installation_key": "secret-key",
                "wait": 10,
                "code_coverage": True,
                "skip_validation": True,
                "json_output": True,
            },
        )
        task()

        call_args = mock_sfdx.call_args[1]["args"]
        assert "--package" in call_args
        assert "0Ho000000000001" in call_args
        assert "--version-name" in call_args
        assert "New Version" in call_args
        assert "--version-description" in call_args
        assert "New description" in call_args
        assert "--branch" in call_args
        assert "main" in call_args
        assert "--tag" in call_args
        assert "v1.0.0" in call_args
        assert "--installation-key" in call_args
        assert "secret-key" in call_args
        assert "--wait" in call_args
        assert "10" in call_args
        assert "--code-coverage" in call_args
        assert True in call_args  # Boolean flags include the value
        assert "--skip-validation" in call_args
        assert "--json" in call_args

    def test_minimal_options(self, mock_sfdx, mock_devhub):
        mock_sfdx.return_value = create_mock_sarge_command()
        task = create_task(PackageVersionCreateTask, {"package_id": "0Ho000000000001"})
        task()

        call_args = mock_sfdx.call_args[1]["args"]
        assert "--package" in call_args
        assert "0Ho000000000001" in call_args


@mock.patch("cumulusci.tasks.salesforce.SfPackageCommands.get_devhub_config")
@mock.patch("cumulusci.tasks.salesforce.SfPackageCommands.sfdx")
class TestPackageVersionListTask:
    def test_init_task_sets_command(self, mock_sfdx, mock_devhub):
        mock_sfdx.return_value = create_mock_sarge_command()
        task = create_task(PackageVersionListTask, {})
        task()
        assert task.package_command == "package version list"

    def test_init_options_all_parameters(self, mock_sfdx, mock_devhub):
        json_response = {"status": 0, "result": {"packageVersions": []}}
        mock_sfdx.return_value = create_mock_sarge_command(
            stdout=json.dumps(json_response)
        )
        task = create_task(
            PackageVersionListTask,
            {
                "package_id": "0Ho000000000001",
                "status": "Success",
                "modified": True,
                "concise": True,
                "json_output": True,
            },
        )
        task()

        call_args = mock_sfdx.call_args[1]["args"]
        assert "--package" in call_args
        assert "0Ho000000000001" in call_args
        assert "--status" in call_args
        assert "Success" in call_args
        assert "--modified" in call_args
        assert True in call_args  # Boolean flags include the value
        assert "--concise" in call_args
        assert "--json" in call_args

    def test_minimal_options(self, mock_sfdx, mock_devhub):
        mock_sfdx.return_value = create_mock_sarge_command()
        task = create_task(PackageVersionListTask, {})
        task()

        call_args = mock_sfdx.call_args[1]["args"]
        # Should only have base options, no package-specific args
        assert "--package" not in call_args


@mock.patch("cumulusci.tasks.salesforce.SfPackageCommands.get_devhub_config")
@mock.patch("cumulusci.tasks.salesforce.SfPackageCommands.sfdx")
class TestPackageVersionDisplayTask:
    def test_init_task_sets_command(self, mock_sfdx, mock_devhub):
        mock_sfdx.return_value = create_mock_sarge_command()
        task = create_task(
            PackageVersionDisplayTask, {"package_version_id": "04t000000000001"}
        )
        task()
        assert task.package_command == "package version display"

    def test_init_options_all_parameters(self, mock_sfdx, mock_devhub):
        json_response = {"status": 0, "result": {"packageVersion": {}}}
        mock_sfdx.return_value = create_mock_sarge_command(
            stdout=json.dumps(json_response)
        )
        task = create_task(
            PackageVersionDisplayTask,
            {
                "package_version_id": "04t000000000001",
                "verbose": True,
                "json_output": True,
            },
        )
        task()

        call_args = mock_sfdx.call_args[1]["args"]
        assert "--package-version-id" in call_args
        assert "04t000000000001" in call_args
        assert "--verbose" in call_args
        assert True in call_args  # Boolean flags include the value
        assert "--json" in call_args

    def test_missing_required_options(self, mock_sfdx, mock_devhub):
        from cumulusci.core.exceptions import TaskOptionsError

        with pytest.raises(TaskOptionsError, match="field required"):
            create_task(PackageVersionDisplayTask, {})


@mock.patch("cumulusci.tasks.salesforce.SfPackageCommands.get_devhub_config")
@mock.patch("cumulusci.tasks.salesforce.SfPackageCommands.sfdx")
class TestPackageVersionDeleteTask:
    def test_init_task_sets_command(self, mock_sfdx, mock_devhub):
        mock_sfdx.return_value = create_mock_sarge_command()
        task = create_task(
            PackageVersionDeleteTask, {"package_version_id": "04t000000000001"}
        )
        task()
        assert task.package_command == "package version delete"

    def test_init_options_all_parameters(self, mock_sfdx, mock_devhub):
        json_response = {"status": 0, "result": {}}
        mock_sfdx.return_value = create_mock_sarge_command(
            stdout=json.dumps(json_response)
        )
        task = create_task(
            PackageVersionDeleteTask,
            {
                "package_version_id": "04t000000000001",
                "no_prompt_flag": True,
                "json_output": True,
            },
        )
        task()

        call_args = mock_sfdx.call_args[1]["args"]
        assert "--package-version-id" in call_args
        assert "04t000000000001" in call_args
        assert "--no-prompt" in call_args
        assert True in call_args  # Boolean flags include the value
        assert "--json" in call_args

    def test_missing_required_options(self, mock_sfdx, mock_devhub):
        from cumulusci.core.exceptions import TaskOptionsError

        with pytest.raises(TaskOptionsError, match="field required"):
            create_task(PackageVersionDeleteTask, {})


@mock.patch("cumulusci.tasks.salesforce.SfPackageCommands.get_devhub_config")
@mock.patch("cumulusci.tasks.salesforce.SfPackageCommands.sfdx")
class TestPackageVersionReportTask:
    def test_init_task_sets_command(self, mock_sfdx, mock_devhub):
        mock_sfdx.return_value = create_mock_sarge_command()
        task = create_task(
            PackageVersionReportTask, {"package_version_id": "04t000000000001"}
        )
        task()
        assert task.package_command == "package version report"

    def test_init_options_all_parameters(self, mock_sfdx, mock_devhub):
        json_response = {
            "status": 0,
            "result": {"reportUrl": "https://example.com/report"},
        }
        mock_sfdx.return_value = create_mock_sarge_command(
            stdout=json.dumps(json_response)
        )
        task = create_task(
            PackageVersionReportTask,
            {
                "package_version_id": "04t000000000001",
                "code_coverage": True,
                "output_dir": "/tmp/reports",
                "json_output": True,
            },
        )
        task()

        call_args = mock_sfdx.call_args[1]["args"]
        assert "--package-version-id" in call_args
        assert "04t000000000001" in call_args
        assert "--code-coverage" in call_args
        assert True in call_args  # Boolean flags include the value
        assert "--output-dir" in call_args
        assert "/tmp/reports" in call_args
        assert "--json" in call_args

    def test_missing_required_options(self, mock_sfdx, mock_devhub):
        from cumulusci.core.exceptions import TaskOptionsError

        with pytest.raises(TaskOptionsError, match="field required"):
            create_task(PackageVersionReportTask, {})


@mock.patch("cumulusci.tasks.salesforce.SfPackageCommands.get_devhub_config")
@mock.patch("cumulusci.tasks.salesforce.SfPackageCommands.sfdx")
class TestPackageCreateTask:
    def test_init_task_sets_command(self, mock_sfdx, mock_devhub):
        mock_sfdx.return_value = create_mock_sarge_command()
        task = create_task(PackageCreateTask, {"name": "Test Package"})
        task()
        assert task.package_command == "package create"

    def test_init_options_all_parameters(self, mock_sfdx, mock_devhub):
        json_response = {"status": 0, "result": {"packageId": "0Ho000000000001"}}
        mock_sfdx.return_value = create_mock_sarge_command(
            stdout=json.dumps(json_response)
        )
        task = create_task(
            PackageCreateTask,
            {
                "name": "Test Package",
                "description": "Test package description",
                "package_type": "Managed",
                "path": "/tmp/package",
                "json_output": True,
            },
        )
        task()

        call_args = mock_sfdx.call_args[1]["args"]
        assert "--name" in call_args
        assert "Test Package" in call_args
        assert "--description" in call_args
        assert "Test package description" in call_args
        assert "--package-type" in call_args
        assert "Managed" in call_args
        assert "--path" in call_args
        assert "/tmp/package" in call_args
        assert "--json" in call_args

    def test_missing_required_options(self, mock_sfdx, mock_devhub):
        from cumulusci.core.exceptions import TaskOptionsError

        with pytest.raises(TaskOptionsError, match="field required"):
            create_task(PackageCreateTask, {})


@mock.patch("cumulusci.tasks.salesforce.SfPackageCommands.get_devhub_config")
@mock.patch("cumulusci.tasks.salesforce.SfPackageCommands.sfdx")
class TestPackageListTask:
    def test_init_task_sets_command(self, mock_sfdx, mock_devhub):
        mock_sfdx.return_value = create_mock_sarge_command()
        task = create_task(PackageListTask, {})
        task()
        assert task.package_command == "package list"

    def test_init_options_all_parameters(self, mock_sfdx, mock_devhub):
        json_response = {"status": 0, "result": {"packages": []}}
        mock_sfdx.return_value = create_mock_sarge_command(
            stdout=json.dumps(json_response)
        )
        task = create_task(
            PackageListTask,
            {
                "concise": True,
                "json_output": True,
            },
        )
        task()

        call_args = mock_sfdx.call_args[1]["args"]
        assert "--concise" in call_args
        assert True in call_args  # Boolean flags include the value
        assert "--json" in call_args


@mock.patch("cumulusci.tasks.salesforce.SfPackageCommands.get_devhub_config")
@mock.patch("cumulusci.tasks.salesforce.SfPackageCommands.sfdx")
class TestPackageDisplayTask:
    def test_init_task_sets_command(self, mock_sfdx, mock_devhub):
        mock_sfdx.return_value = create_mock_sarge_command()
        task = create_task(PackageDisplayTask, {"package_id": "0Ho000000000001"})
        task()
        assert task.package_command == "package display"

    def test_init_options_all_parameters(self, mock_sfdx, mock_devhub):
        json_response = {"status": 0, "result": {"package": {}}}
        mock_sfdx.return_value = create_mock_sarge_command(
            stdout=json.dumps(json_response)
        )
        task = create_task(
            PackageDisplayTask,
            {
                "package_id": "0Ho000000000001",
                "verbose": True,
                "json_output": True,
            },
        )
        task()

        call_args = mock_sfdx.call_args[1]["args"]
        assert "--package-id" in call_args
        assert "0Ho000000000001" in call_args
        assert "--verbose" in call_args
        assert True in call_args  # Boolean flags include the value
        assert "--json" in call_args

    def test_missing_required_options(self, mock_sfdx, mock_devhub):
        from cumulusci.core.exceptions import TaskOptionsError

        with pytest.raises(TaskOptionsError, match="field required"):
            create_task(PackageDisplayTask, {})
