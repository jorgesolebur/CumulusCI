import json
from unittest import mock

import pytest
import sarge

from cumulusci.core.exceptions import SalesforceDXException
from cumulusci.tasks.salesforce.SfDataCommands import (
    DataCreateRecordTask,
    DataDeleteRecordTask,
    DataQueryTask,
    SfDataCommands,
    SfDataToolingAPISupportedCommands,
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


@mock.patch("cumulusci.tasks.salesforce.SfDataCommands.sfdx")
class TestSfDataCommands:
    def test_init_options_basic(self, mock_sfdx):
        mock_sfdx.return_value = create_mock_sarge_command()
        task = create_task(SfDataCommands, {})
        task()
        assert task.data_command == "data "
        assert task.args == []

    def test_init_options_all_flags(self, mock_sfdx):
        json_response = {"status": 0, "result": {}}
        mock_sfdx.return_value = create_mock_sarge_command(
            stdout=json.dumps(json_response)
        )
        task = create_task(
            SfDataCommands,
            {
                "json_output": True,
                "api_version": "50.0",
                "flags_dir": "/tmp/flags",
            },
        )
        task()
        expected_args = [
            "--flags-dir ",
            "/tmp/flags",
            "--json",
            "--api_version",
            "50.0",
        ]
        assert all(arg in task.args for arg in expected_args)

    def test_load_json_output_success(self, mock_sfdx):
        json_response = {"status": 0, "result": {"records": []}}
        stdout = json.dumps(json_response)
        mock_command = create_mock_sarge_command(stdout=stdout)
        mock_sfdx.return_value = mock_command

        task = create_task(SfDataCommands, {"json_output": True})
        task()

        assert task.return_values == json_response

    def test_load_json_output_decode_error(self, mock_sfdx):
        mock_command = create_mock_sarge_command(stdout="invalid json")
        mock_sfdx.return_value = mock_command

        task = create_task(SfDataCommands, {"json_output": True})

        with pytest.raises(SalesforceDXException, match="Failed to parse the output"):
            task()

    def test_logging_stdout_and_stderr(self, mock_sfdx):
        mock_command = create_mock_sarge_command(
            stdout="Success: Query completed\nFound 5 records",
            stderr="Warning: Some non-critical issue",
        )
        mock_sfdx.return_value = mock_command

        task = create_task(SfDataCommands, {})
        with mock.patch.object(task, "logger") as mock_logger:
            task()

            # Check that stdout lines were logged as info
            mock_logger.info.assert_any_call("Success: Query completed")
            mock_logger.info.assert_any_call("Found 5 records")

            # Check that stderr lines were logged as error
            mock_logger.error.assert_called_with("Warning: Some non-critical issue")


@mock.patch("cumulusci.tasks.salesforce.SfDataCommands.sfdx")
class TestSfDataToolingAPISupportedCommands:
    def test_inherits_from_base(self, mock_sfdx):
        mock_sfdx.return_value = create_mock_sarge_command()
        task = create_task(SfDataToolingAPISupportedCommands, {})
        assert isinstance(task, SfDataCommands)

    def test_use_tooling_api_option(self, mock_sfdx):
        mock_sfdx.return_value = create_mock_sarge_command()
        task = create_task(SfDataToolingAPISupportedCommands, {"use_tooling_api": True})
        # Test that the option is available (would be tested in subclasses that use it)
        assert hasattr(task.parsed_options, "use_tooling_api")


@mock.patch("cumulusci.tasks.salesforce.SfDataCommands.sfdx")
class TestDataQueryTask:
    def test_init_task_sets_command(self, mock_sfdx):
        mock_sfdx.return_value = create_mock_sarge_command()
        task = create_task(DataQueryTask, {"query": "SELECT Id FROM Account"})
        task()
        assert task.data_command == "data query"

    def test_init_options_all_parameters(self, mock_sfdx):
        json_response = {"status": 0, "result": {"records": []}}
        mock_sfdx.return_value = create_mock_sarge_command(
            stdout=json.dumps(json_response)
        )
        task = create_task(
            DataQueryTask,
            {
                "query": "SELECT Id FROM Account",
                "file": "/tmp/query.soql",
                "all_rows": True,
                "result_format": "csv",
                "output_file": "/tmp/output.csv",
                "api_version": "50.0",
                "flags_dir": "/tmp/flags",
                "json_output": True,
                "use_tooling_api": True,
            },
        )
        task()

        call_args = mock_sfdx.call_args[1]["args"]
        assert mock_sfdx.call_args[1]["log_note"] == "Running data command"
        assert "--query" in call_args
        assert "SELECT Id FROM Account" in call_args
        assert "--file" in call_args
        assert "/tmp/query.soql" in call_args
        assert "--all-rows" in call_args
        assert "--result-format" in call_args
        assert "csv" in call_args
        assert "--output-file" in call_args
        assert "/tmp/output.csv" in call_args
        assert "--api_version" in call_args
        assert "50.0" in call_args
        assert "--flags-dir " in call_args
        assert "/tmp/flags" in call_args
        assert "--json" in call_args

    def test_minimal_options(self, mock_sfdx):
        mock_sfdx.return_value = create_mock_sarge_command()
        task = create_task(DataQueryTask, {"query": "SELECT Id FROM Account"})
        task()

        call_args = mock_sfdx.call_args[1]["args"]
        assert "--query" in call_args
        assert "SELECT Id FROM Account" in call_args

    def test_json_output_logging(self, mock_sfdx):
        json_response = {"status": 0, "result": {"records": [{"Id": "123"}]}}
        stdout = json.dumps(json_response)
        mock_sfdx.return_value = create_mock_sarge_command(stdout=stdout)

        task = create_task(
            DataQueryTask,
            {"query": "SELECT Id FROM Account", "json_output": True},
        )

        with mock.patch.object(task, "logger") as mock_logger:
            task()
            mock_logger.info.assert_called_with(json_response)

    def test_run_task_json_decode_error(self, mock_sfdx):
        mock_sfdx.return_value = create_mock_sarge_command(stdout="this is not json")
        task = create_task(
            DataQueryTask,
            {"query": "SELECT Id FROM Account", "json_output": True},
        )
        with pytest.raises(
            SalesforceDXException,
            match="Failed to parse the output of the data query command",
        ):
            task()


@mock.patch("cumulusci.tasks.salesforce.SfDataCommands.sfdx")
class TestDataCreateRecordTask:
    def test_init_task_sets_command(self, mock_sfdx):
        mock_sfdx.return_value = create_mock_sarge_command()
        task = create_task(
            DataCreateRecordTask,
            {"sobject": "Account", "values": "Name='Test Account'"},
        )
        task()
        assert task.data_command == "data create record"

    def test_init_options_all_parameters(self, mock_sfdx):
        json_response = {"status": 0, "result": {"id": "001000000000001"}}
        mock_sfdx.return_value = create_mock_sarge_command(
            stdout=json.dumps(json_response)
        )
        task = create_task(
            DataCreateRecordTask,
            {
                "sobject": "Account",
                "values": "Name='Test Account' Industry='Technology'",
                "api_version": "50.0",
                "flags_dir": "/tmp/flags",
                "json_output": True,
                "use_tooling_api": True,
            },
        )
        task()

        call_args = mock_sfdx.call_args[1]["args"]
        assert mock_sfdx.call_args[1]["log_note"] == "Running data command"
        assert "--sobject" in call_args
        assert "Account" in call_args
        assert "--values" in call_args
        assert "Name='Test Account' Industry='Technology'" in call_args
        assert "--api_version" in call_args
        assert "50.0" in call_args
        assert "--flags-dir " in call_args
        assert "/tmp/flags" in call_args
        assert "--json" in call_args

    def test_minimal_options(self, mock_sfdx):
        mock_sfdx.return_value = create_mock_sarge_command()
        task = create_task(
            DataCreateRecordTask,
            {"sobject": "Contact", "values": "LastName='Doe'"},
        )
        task()

        call_args = mock_sfdx.call_args[1]["args"]
        assert "--sobject" in call_args
        assert "Contact" in call_args
        assert "--values" in call_args
        assert "LastName='Doe'" in call_args

    def test_missing_required_options(self, mock_sfdx):
        # Test that required field validation works as expected
        mock_sfdx.return_value = create_mock_sarge_command()
        from cumulusci.core.exceptions import TaskOptionsError

        with pytest.raises(TaskOptionsError, match="field required"):
            create_task(DataCreateRecordTask, {})


@mock.patch("cumulusci.tasks.salesforce.SfDataCommands.sfdx")
class TestDataDeleteRecordTask:
    def test_init_task_sets_command(self, mock_sfdx):
        mock_sfdx.return_value = create_mock_sarge_command()
        task = create_task(
            DataDeleteRecordTask, {"sobject": "Account", "record_id": "001000000000001"}
        )
        task()
        assert task.data_command == "data delete record"

    def test_delete_by_record_id(self, mock_sfdx):
        json_response = {"status": 0, "result": {}}
        mock_sfdx.return_value = create_mock_sarge_command(
            stdout=json.dumps(json_response)
        )
        task = create_task(
            DataDeleteRecordTask,
            {
                "sobject": "Account",
                "record_id": "001000000000001AAA",
                "api_version": "50.0",
                "flags_dir": "/tmp/flags",
                "json_output": True,
            },
        )
        task()

        call_args = mock_sfdx.call_args[1]["args"]
        assert mock_sfdx.call_args[1]["log_note"] == "Running data command"
        assert "--sobject" in call_args
        assert "Account" in call_args
        assert "--record-id" in call_args
        assert "001000000000001AAA" in call_args
        assert "--api_version" in call_args
        assert "50.0" in call_args
        assert "--flags-dir " in call_args
        assert "/tmp/flags" in call_args
        assert "--json" in call_args

    def test_delete_by_where_clause(self, mock_sfdx):
        mock_sfdx.return_value = create_mock_sarge_command()
        task = create_task(
            DataDeleteRecordTask,
            {
                "sobject": "Account",
                "where": "Name='Test Account' AND Industry='Technology'",
                "use_tooling_api": True,
            },
        )
        task()

        call_args = mock_sfdx.call_args[1]["args"]
        # Check that sfdx was called with the right log_note
        assert mock_sfdx.call_args[1]["log_note"] == "Running data command"
        assert "--sobject" in call_args
        assert "Account" in call_args
        assert "--where" in call_args
        assert "Name='Test Account' AND Industry='Technology'" in call_args

    def test_minimal_options(self, mock_sfdx):
        mock_sfdx.return_value = create_mock_sarge_command()
        task = create_task(
            DataDeleteRecordTask,
            {"sobject": "Contact"},
        )
        task()

        call_args = mock_sfdx.call_args[1]["args"]
        assert "--sobject" in call_args
        assert "Contact" in call_args
        # Should not have --record-id or --where if not provided
        assert "--record-id" not in call_args
        assert "--where" not in call_args

    def test_both_record_id_and_where_provided(self, mock_sfdx):
        # Test that both options can be provided (though this might not be practical)
        mock_sfdx.return_value = create_mock_sarge_command()
        task = create_task(
            DataDeleteRecordTask,
            {
                "sobject": "Account",
                "record_id": "001000000000001",
                "where": "Name='Test Account'",
            },
        )
        task()

        call_args = mock_sfdx.call_args[1]["args"]
        assert "--record-id" in call_args
        assert "001000000000001" in call_args
        assert "--where" in call_args
        assert "Name='Test Account'" in call_args
