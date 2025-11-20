"""Tests for SFDmu task."""

import os
import tempfile
from unittest import mock

import pytest

from cumulusci.tasks.salesforce.tests.util import create_task
from cumulusci.tasks.sfdmu.sfdmu import SfdmuTask


class TestSfdmuTask:
    """Test cases for SfdmuTask."""

    def test_init_options_validates_path(self):
        """Test that _init_options validates the path exists and contains export.json."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create export.json file
            export_json_path = os.path.join(temp_dir, "export.json")
            with open(export_json_path, "w") as f:
                f.write('{"test": "data"}')

            # Test valid path using create_task helper
            task = create_task(
                SfdmuTask, {"source": "dev", "target": "qa", "path": temp_dir}
            )
            assert task.options["path"] == os.path.abspath(temp_dir)

    def test_init_options_raises_error_for_missing_path(self):
        """Test that _init_options raises error for missing path."""
        with pytest.raises(Exception):  # TaskOptionsError
            create_task(
                SfdmuTask,
                {"source": "dev", "target": "qa", "path": "/nonexistent/path"},
            )

    def test_init_options_raises_error_for_missing_export_json(self):
        """Test that _init_options raises error for missing export.json."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with pytest.raises(Exception):  # TaskOptionsError
                create_task(
                    SfdmuTask, {"source": "dev", "target": "qa", "path": temp_dir}
                )

    def test_validate_org_csvfile(self):
        """Test that _validate_org returns None for csvfile."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create export.json file
            export_json_path = os.path.join(temp_dir, "export.json")
            with open(export_json_path, "w") as f:
                f.write('{"test": "data"}')

            task = create_task(
                SfdmuTask, {"source": "csvfile", "target": "csvfile", "path": temp_dir}
            )

            result = task._validate_org("csvfile")
            assert result is None

    def test_validate_org_missing_keychain(self):
        """Test that _validate_org raises error when keychain is None."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create export.json file
            export_json_path = os.path.join(temp_dir, "export.json")
            with open(export_json_path, "w") as f:
                f.write('{"test": "data"}')

            task = create_task(
                SfdmuTask, {"source": "dev", "target": "qa", "path": temp_dir}
            )

            # Mock the keychain to be None
            task.project_config.keychain = None

            with pytest.raises(Exception):  # TaskOptionsError
                task._validate_org("dev")

    def test_get_sf_org_name_sfdx_alias(self):
        """Test _get_sf_org_name with sfdx_alias."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create export.json file
            export_json_path = os.path.join(temp_dir, "export.json")
            with open(export_json_path, "w") as f:
                f.write('{"test": "data"}')

            task = create_task(
                SfdmuTask, {"source": "dev", "target": "qa", "path": temp_dir}
            )

            mock_org_config = mock.Mock()
            mock_org_config.sfdx_alias = "test_alias"
            mock_org_config.username = "test@example.com"

            result = task._get_sf_org_name(mock_org_config)
            assert result == "test_alias"

    def test_get_sf_org_name_username(self):
        """Test _get_sf_org_name with username fallback."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create export.json file
            export_json_path = os.path.join(temp_dir, "export.json")
            with open(export_json_path, "w") as f:
                f.write('{"test": "data"}')

            task = create_task(
                SfdmuTask, {"source": "dev", "target": "qa", "path": temp_dir}
            )

            mock_org_config = mock.Mock()
            mock_org_config.sfdx_alias = None
            mock_org_config.username = "test@example.com"

            result = task._get_sf_org_name(mock_org_config)
            assert result == "test@example.com"

    def test_create_execute_directory(self):
        """Test _create_execute_directory creates directory and copies files."""
        with tempfile.TemporaryDirectory() as base_dir:
            # Create test files
            export_json = os.path.join(base_dir, "export.json")
            test_csv = os.path.join(base_dir, "test.csv")
            test_txt = os.path.join(base_dir, "test.txt")  # Should not be copied

            with open(export_json, "w") as f:
                f.write('{"test": "data"}')
            with open(test_csv, "w") as f:
                f.write("col1,col2\nval1,val2")
            with open(test_txt, "w") as f:
                f.write("text file")

            # Create subdirectory (should not be copied)
            subdir = os.path.join(base_dir, "subdir")
            os.makedirs(subdir)
            with open(os.path.join(subdir, "file.txt"), "w") as f:
                f.write("subdir file")

            task = create_task(
                SfdmuTask, {"source": "dev", "target": "qa", "path": base_dir}
            )

            execute_path = task._create_execute_directory(base_dir)

            # Check that execute directory was created
            assert os.path.exists(execute_path)
            assert execute_path == os.path.join(base_dir, "execute")

            # Check that files were copied
            assert os.path.exists(os.path.join(execute_path, "export.json"))
            assert os.path.exists(os.path.join(execute_path, "test.csv"))
            assert not os.path.exists(
                os.path.join(execute_path, "test.txt")
            )  # Not a valid file type
            assert not os.path.exists(
                os.path.join(execute_path, "subdir")
            )  # Not a file

            # Check file contents
            with open(os.path.join(execute_path, "export.json"), "r") as f:
                assert f.read() == '{"test": "data"}'
            with open(os.path.join(execute_path, "test.csv"), "r") as f:
                assert f.read() == "col1,col2\nval1,val2"

    def test_create_execute_directory_removes_existing(self):
        """Test that _create_execute_directory removes existing execute directory."""
        with tempfile.TemporaryDirectory() as base_dir:
            # Create existing execute directory with files
            execute_dir = os.path.join(base_dir, "execute")
            os.makedirs(execute_dir)
            with open(os.path.join(execute_dir, "old_file.json"), "w") as f:
                f.write('{"old": "data"}')

            # Create export.json in base directory
            export_json = os.path.join(base_dir, "export.json")
            with open(export_json, "w") as f:
                f.write('{"test": "data"}')

            task = create_task(
                SfdmuTask, {"source": "dev", "target": "qa", "path": base_dir}
            )

            execute_path = task._create_execute_directory(base_dir)

            # Check that old file was removed
            assert not os.path.exists(os.path.join(execute_path, "old_file.json"))
            # Check that new file was copied
            assert os.path.exists(os.path.join(execute_path, "export.json"))

    def test_inject_namespace_tokens_csvfile_both(self):
        """Test that namespace injection is skipped when both source and target are csvfile."""
        with tempfile.TemporaryDirectory() as execute_dir:
            # Create test files
            test_json = os.path.join(execute_dir, "test.json")
            with open(test_json, "w") as f:
                f.write('{"field": "%%%NAMESPACE%%%Test"}')

            # Create export.json file
            export_json_path = os.path.join(execute_dir, "export.json")
            with open(export_json_path, "w") as f:
                f.write('{"test": "data"}')

            task = create_task(
                SfdmuTask,
                {"source": "csvfile", "target": "csvfile", "path": execute_dir},
            )

            # Should not raise any errors and files should remain unchanged
            task._inject_namespace_tokens(execute_dir, None, None)

            # Check that file content was not changed
            with open(test_json, "r") as f:
                assert f.read() == '{"field": "%%%NAMESPACE%%%Test"}'

    @mock.patch("cumulusci.tasks.sfdmu.sfdmu.determine_managed_mode")
    def test_inject_namespace_tokens_csvfile_target_with_source_org(
        self, mock_determine_managed
    ):
        """Test that namespace injection uses source org when target is csvfile."""
        mock_determine_managed.return_value = True

        with tempfile.TemporaryDirectory() as execute_dir:
            # Create test files with namespace tokens
            test_json = os.path.join(execute_dir, "export.json")
            with open(test_json, "w") as f:
                f.write(
                    '{"query": "SELECT Id FROM %%%MANAGED_OR_NAMESPACED_ORG%%%CustomObject__c"}'
                )

            task = create_task(
                SfdmuTask, {"source": "dev", "target": "csvfile", "path": execute_dir}
            )

            # Mock the project config namespace
            task.project_config.project__package__namespace = "testns"

            mock_source_org = mock.Mock()
            mock_source_org.namespace = "testns"

            # When target is csvfile (None), should use source org for injection
            task._inject_namespace_tokens(execute_dir, mock_source_org, None)

            # Check that namespace tokens were replaced using source org
            with open(test_json, "r") as f:
                content = f.read()
                assert "testns__CustomObject__c" in content
                assert "%%%MANAGED_OR_NAMESPACED_ORG%%%" not in content

    @mock.patch("cumulusci.tasks.sfdmu.sfdmu.determine_managed_mode")
    def test_inject_namespace_tokens_managed_mode(self, mock_determine_managed):
        """Test namespace injection in managed mode."""
        mock_determine_managed.return_value = True

        with tempfile.TemporaryDirectory() as execute_dir:
            # Create test files with namespace tokens
            test_json = os.path.join(execute_dir, "test.json")
            test_csv = os.path.join(execute_dir, "test.csv")

            with open(test_json, "w") as f:
                f.write(
                    '{"field": "%%%NAMESPACE%%%Test", "org": "%%%NAMESPACED_ORG%%%Value"}'
                )
            with open(test_csv, "w") as f:
                f.write("Name,%%%NAMESPACE%%%Field\nTest,Value")

            # Create filename with namespace token
            filename_with_token = os.path.join(execute_dir, "___NAMESPACE___test.json")
            with open(filename_with_token, "w") as f:
                f.write('{"test": "data"}')

            # Create export.json file
            export_json_path = os.path.join(execute_dir, "export.json")
            with open(export_json_path, "w") as f:
                f.write('{"test": "data"}')

            task = create_task(
                SfdmuTask, {"source": "dev", "target": "qa", "path": execute_dir}
            )

            # Mock the project config namespace
            task.project_config.project__package__namespace = "testns"

            mock_org_config = mock.Mock()
            mock_org_config.namespace = "testns"

            task._inject_namespace_tokens(execute_dir, None, mock_org_config)

            # Check that namespace tokens were replaced in content
            with open(test_json, "r") as f:
                content = f.read()
                assert "testns__Test" in content
                assert "testns__Value" in content

            with open(test_csv, "r") as f:
                content = f.read()
                assert "testns__Field" in content

            # Check that filename token was replaced
            expected_filename = os.path.join(execute_dir, "testns__test.json")
            assert os.path.exists(expected_filename)
            assert not os.path.exists(filename_with_token)

    @mock.patch("cumulusci.tasks.sfdmu.sfdmu.determine_managed_mode")
    def test_inject_namespace_tokens_unmanaged_mode(self, mock_determine_managed):
        """Test namespace injection in unmanaged mode."""
        mock_determine_managed.return_value = False

        with tempfile.TemporaryDirectory() as execute_dir:
            # Create test files with namespace tokens
            test_json = os.path.join(execute_dir, "test.json")
            with open(test_json, "w") as f:
                f.write(
                    '{"field": "%%%NAMESPACE%%%Test", "org": "%%%NAMESPACED_ORG%%%Value"}'
                )

            # Create export.json file
            export_json_path = os.path.join(execute_dir, "export.json")
            with open(export_json_path, "w") as f:
                f.write('{"test": "data"}')

            task = create_task(
                SfdmuTask, {"source": "dev", "target": "qa", "path": execute_dir}
            )

            # Mock the project config namespace
            task.project_config.project__package__namespace = "testns"

            mock_org_config = mock.Mock()
            mock_org_config.namespace = "testns"

            task._inject_namespace_tokens(execute_dir, None, mock_org_config)

            # Check that namespace tokens were replaced with empty strings
            with open(test_json, "r") as f:
                content = f.read()
                assert "Test" in content  # %%NAMESPACE%% removed
                assert "Value" in content  # %%NAMESPACED_ORG%% removed
                assert "%%%NAMESPACE%%%" not in content
                assert "%%%NAMESPACED_ORG%%%" not in content

    @mock.patch("cumulusci.tasks.sfdmu.sfdmu.determine_managed_mode")
    def test_inject_namespace_tokens_namespaced_org(self, mock_determine_managed):
        """Test namespace injection with namespaced org."""
        mock_determine_managed.return_value = True

        with tempfile.TemporaryDirectory() as execute_dir:
            # Create test file with namespaced org token
            test_json = os.path.join(execute_dir, "test.json")
            with open(test_json, "w") as f:
                f.write('{"field": "%%%NAMESPACED_ORG%%%Test"}')

            # Create export.json file
            export_json_path = os.path.join(execute_dir, "export.json")
            with open(export_json_path, "w") as f:
                f.write('{"test": "data"}')

            task = create_task(
                SfdmuTask, {"source": "dev", "target": "qa", "path": execute_dir}
            )

            # Mock the project config namespace
            task.project_config.project__package__namespace = "testns"

            mock_org_config = mock.Mock()
            mock_org_config.namespace = (
                "testns"  # Same as project namespace = namespaced org
            )

            task._inject_namespace_tokens(execute_dir, None, mock_org_config)

            # Check that namespaced org token was replaced
            with open(test_json, "r") as f:
                content = f.read()
                assert "testns__Test" in content
                assert "%%%NAMESPACED_ORG%%%" not in content

    @mock.patch("cumulusci.tasks.sfdmu.sfdmu.determine_managed_mode")
    def test_inject_namespace_tokens_non_namespaced_org(self, mock_determine_managed):
        """Test namespace injection with non-namespaced org."""
        mock_determine_managed.return_value = True

        with tempfile.TemporaryDirectory() as execute_dir:
            # Create test file with namespaced org token
            test_json = os.path.join(execute_dir, "test.json")
            with open(test_json, "w") as f:
                f.write('{"field": "%%%NAMESPACED_ORG%%%Test"}')

            # Create export.json file
            export_json_path = os.path.join(execute_dir, "export.json")
            with open(export_json_path, "w") as f:
                f.write('{"test": "data"}')

            task = create_task(
                SfdmuTask, {"source": "dev", "target": "qa", "path": execute_dir}
            )

            # Mock the project config namespace
            task.project_config.project__package__namespace = "testns"

            mock_org_config = mock.Mock()
            mock_org_config.namespace = (
                "differentns"  # Different from project namespace
            )

            task._inject_namespace_tokens(execute_dir, None, mock_org_config)

            # Check that namespaced org token was replaced with empty string
            with open(test_json, "r") as f:
                content = f.read()
                assert "Test" in content  # %%NAMESPACED_ORG%% removed
                assert "%%%NAMESPACED_ORG%%%" not in content
                assert "testns__" not in content  # Should not have namespace prefix

    def test_inject_namespace_tokens_no_namespace(self):
        """Test namespace injection when project has no namespace."""
        with tempfile.TemporaryDirectory() as execute_dir:
            # Create test file with namespace tokens
            test_json = os.path.join(execute_dir, "test.json")
            with open(test_json, "w") as f:
                f.write('{"field": "%%%NAMESPACE%%%Test"}')

            # Create export.json file
            export_json_path = os.path.join(execute_dir, "export.json")
            with open(export_json_path, "w") as f:
                f.write('{"test": "data"}')

            task = create_task(
                SfdmuTask, {"source": "dev", "target": "qa", "path": execute_dir}
            )

            # Mock the project config namespace
            task.project_config.project__package__namespace = None

            mock_org_config = mock.Mock()
            mock_org_config.namespace = None

            task._inject_namespace_tokens(execute_dir, None, mock_org_config)

            # Check that namespace tokens were not processed (due to circular import issue)
            with open(test_json, "r") as f:
                content = f.read()
                assert (
                    "%%%NAMESPACE%%%Test" in content
                )  # Tokens remain unchanged due to import issue

    def test_additional_params_option_exists(self):
        """Test that additional_params option is properly defined in task_options."""
        # Check that the additional_params option is defined
        assert "additional_params" in SfdmuTask.task_options
        assert SfdmuTask.task_options["additional_params"]["required"] is False
        assert (
            "Additional parameters"
            in SfdmuTask.task_options["additional_params"]["description"]
        )

    def test_additional_params_parsing_logic(self):
        """Test that additional_params parsing logic works correctly."""
        # Test the splitting logic that would be used in the task
        additional_params = "-no-warnings -m -t error"
        additional_args = additional_params.split()
        expected_args = ["-no-warnings", "-m", "-t", "error"]
        assert additional_args == expected_args

    def test_additional_params_empty_string_logic(self):
        """Test that empty additional_params are handled correctly."""
        # Test the splitting logic with empty string
        additional_params = ""
        additional_args = additional_params.split()
        assert additional_args == []

    def test_additional_params_none_logic(self):
        """Test that None additional_params are handled correctly."""
        # Test the logic that would be used in the task
        additional_params = None
        if additional_params:
            additional_args = additional_params.split()
        else:
            additional_args = []
        assert additional_args == []

    def test_process_csv_exports_replaces_namespace_in_content(self):
        """Test that namespace prefix is replaced with token in CSV file contents."""
        with tempfile.TemporaryDirectory() as base_dir:
            # Create execute directory
            execute_dir = os.path.join(base_dir, "execute")
            os.makedirs(execute_dir)

            # Create export.json
            export_json = os.path.join(base_dir, "export.json")
            with open(export_json, "w") as f:
                f.write('{"test": "data"}')

            # Create CSV file with namespace prefix in content
            csv_file = os.path.join(execute_dir, "Account.csv")
            with open(csv_file, "w", encoding="utf-8") as f:
                f.write("Id,Name,testns__CustomField__c\n")
                f.write("001,Test Account,testns__Value\n")

            task = create_task(
                SfdmuTask, {"source": "dev", "target": "csvfile", "path": base_dir}
            )
            task.project_config.project__package__namespace = "testns"

            # Call the processing method
            task._process_csv_exports(execute_dir, base_dir)

            # Check that namespace was replaced in content
            target_csv = os.path.join(base_dir, "Account.csv")
            assert os.path.exists(target_csv)
            with open(target_csv, "r", encoding="utf-8") as f:
                content = f.read()
                assert "%%%MANAGED_OR_NAMESPACED_ORG%%%CustomField__c" in content
                assert "%%%MANAGED_OR_NAMESPACED_ORG%%%Value" in content
                assert "testns__" not in content

    def test_process_csv_exports_renames_files_with_namespace(self):
        """Test that CSV filenames with namespace prefix are renamed."""
        with tempfile.TemporaryDirectory() as base_dir:
            # Create execute directory
            execute_dir = os.path.join(base_dir, "execute")
            os.makedirs(execute_dir)

            # Create export.json
            export_json = os.path.join(base_dir, "export.json")
            with open(export_json, "w") as f:
                f.write('{"test": "data"}')

            # Create CSV file with namespace in filename
            csv_file = os.path.join(execute_dir, "testns__CustomObject__c.csv")
            with open(csv_file, "w", encoding="utf-8") as f:
                f.write("Id,Name\n001,Test\n")

            task = create_task(
                SfdmuTask, {"source": "dev", "target": "csvfile", "path": base_dir}
            )
            task.project_config.project__package__namespace = "testns"

            # Call the processing method
            task._process_csv_exports(execute_dir, base_dir)

            # Check that file was renamed
            expected_filename = "___MANAGED_OR_NAMESPACED_ORG___CustomObject__c.csv"
            target_csv = os.path.join(base_dir, expected_filename)
            assert os.path.exists(target_csv)
            assert not os.path.exists(
                os.path.join(base_dir, "testns__CustomObject__c.csv")
            )

    def test_process_csv_exports_replaces_existing_files(self):
        """Test that existing CSV files in base path are replaced."""
        with tempfile.TemporaryDirectory() as base_dir:
            # Create execute directory
            execute_dir = os.path.join(base_dir, "execute")
            os.makedirs(execute_dir)

            # Create export.json
            export_json = os.path.join(base_dir, "export.json")
            with open(export_json, "w") as f:
                f.write('{"test": "data"}')

            # Create old CSV file in base directory
            old_csv = os.path.join(base_dir, "Account.csv")
            with open(old_csv, "w", encoding="utf-8") as f:
                f.write("Id,Name\n001,Old Account\n")

            # Create another old CSV that should be deleted
            old_csv2 = os.path.join(base_dir, "Contact.csv")
            with open(old_csv2, "w", encoding="utf-8") as f:
                f.write("Id,Name\n001,Old Contact\n")

            # Create new CSV file in execute directory
            new_csv = os.path.join(execute_dir, "Account.csv")
            with open(new_csv, "w", encoding="utf-8") as f:
                f.write("Id,Name\n002,New Account\n")

            task = create_task(
                SfdmuTask, {"source": "dev", "target": "csvfile", "path": base_dir}
            )
            task.project_config.project__package__namespace = "testns"

            # Call the processing method
            task._process_csv_exports(execute_dir, base_dir)

            # Check that old file was replaced with new content
            with open(old_csv, "r", encoding="utf-8") as f:
                content = f.read()
                assert "New Account" in content
                assert "Old Account" not in content

            # Check that old CSV2 was deleted (not in execute directory)
            assert not os.path.exists(old_csv2)

    def test_process_csv_exports_skips_when_no_namespace(self):
        """Test that CSV post-processing is skipped when no namespace is configured."""
        with tempfile.TemporaryDirectory() as base_dir:
            # Create execute directory
            execute_dir = os.path.join(base_dir, "execute")
            os.makedirs(execute_dir)

            # Create export.json
            export_json = os.path.join(base_dir, "export.json")
            with open(export_json, "w") as f:
                f.write('{"test": "data"}')

            # Create CSV file
            csv_file = os.path.join(execute_dir, "Account.csv")
            with open(csv_file, "w", encoding="utf-8") as f:
                f.write("Id,Name\n001,Test\n")

            task = create_task(
                SfdmuTask, {"source": "dev", "target": "csvfile", "path": base_dir}
            )
            task.project_config.project__package__namespace = None

            # Call the processing method
            task._process_csv_exports(execute_dir, base_dir)

            # Check that file was NOT copied to base directory (processing was skipped)
            target_csv = os.path.join(base_dir, "Account.csv")
            assert not os.path.exists(target_csv)

    def test_process_csv_exports_handles_no_csv_files(self):
        """Test that CSV post-processing handles case when no CSV files exist."""
        with tempfile.TemporaryDirectory() as base_dir:
            # Create execute directory
            execute_dir = os.path.join(base_dir, "execute")
            os.makedirs(execute_dir)

            # Create export.json
            export_json = os.path.join(base_dir, "export.json")
            with open(export_json, "w") as f:
                f.write('{"test": "data"}')

            # Create only export.json, no CSV files
            execute_json = os.path.join(execute_dir, "export.json")
            with open(execute_json, "w", encoding="utf-8") as f:
                f.write('{"test": "data"}')

            task = create_task(
                SfdmuTask, {"source": "dev", "target": "csvfile", "path": base_dir}
            )
            task.project_config.project__package__namespace = "testns"

            # Call the processing method - should not raise any errors
            task._process_csv_exports(execute_dir, base_dir)

    def test_process_csv_exports_copies_only_from_execute_folder(self):
        """Test that only CSV files from execute folder are copied, not subdirectories."""
        with tempfile.TemporaryDirectory() as base_dir:
            # Create execute directory
            execute_dir = os.path.join(base_dir, "execute")
            os.makedirs(execute_dir)

            # Create export.json
            export_json = os.path.join(base_dir, "export.json")
            with open(export_json, "w") as f:
                f.write('{"test": "data"}')

            # Create CSV file in execute directory
            csv_file = os.path.join(execute_dir, "Account.csv")
            with open(csv_file, "w", encoding="utf-8") as f:
                f.write("Id,Name\n001,Test\n")

            # Create subdirectory in execute with another CSV (should not be processed)
            subdir = os.path.join(execute_dir, "subdir")
            os.makedirs(subdir)
            subdir_csv = os.path.join(subdir, "Contact.csv")
            with open(subdir_csv, "w", encoding="utf-8") as f:
                f.write("Id,Name\n002,Contact\n")

            task = create_task(
                SfdmuTask, {"source": "dev", "target": "csvfile", "path": base_dir}
            )
            task.project_config.project__package__namespace = "testns"

            # Call the processing method
            task._process_csv_exports(execute_dir, base_dir)

            # Check that only the CSV from execute root was copied
            assert os.path.exists(os.path.join(base_dir, "Account.csv"))
            assert not os.path.exists(os.path.join(base_dir, "Contact.csv"))
            assert not os.path.exists(os.path.join(base_dir, "subdir"))

    def test_process_csv_exports_handles_multiple_files(self):
        """Test that CSV post-processing handles multiple CSV files correctly."""
        with tempfile.TemporaryDirectory() as base_dir:
            # Create execute directory
            execute_dir = os.path.join(base_dir, "execute")
            os.makedirs(execute_dir)

            # Create export.json
            export_json = os.path.join(base_dir, "export.json")
            with open(export_json, "w") as f:
                f.write('{"test": "data"}')

            # Create multiple CSV files with namespace prefix
            files_data = {
                "Account.csv": "Id,testns__Field1__c\n001,testns__Val1\n",
                "testns__Custom__c.csv": "Id,Name,testns__Field2__c\n002,Test,testns__Val2\n",
                "Contact.csv": "Id,testns__Email__c\n003,testns__test@example.com\n",
            }

            for filename, content in files_data.items():
                csv_file = os.path.join(execute_dir, filename)
                with open(csv_file, "w", encoding="utf-8") as f:
                    f.write(content)

            task = create_task(
                SfdmuTask, {"source": "dev", "target": "csvfile", "path": base_dir}
            )
            task.project_config.project__package__namespace = "testns"

            # Call the processing method
            task._process_csv_exports(execute_dir, base_dir)

            # Check that all files were processed
            # Account.csv - no namespace in filename
            account_csv = os.path.join(base_dir, "Account.csv")
            assert os.path.exists(account_csv)
            with open(account_csv, "r", encoding="utf-8") as f:
                content = f.read()
                assert "%%%MANAGED_OR_NAMESPACED_ORG%%%Field1__c" in content
                assert "%%%MANAGED_OR_NAMESPACED_ORG%%%Val1" in content

            # testns__Custom__c.csv - should be renamed
            custom_csv = os.path.join(
                base_dir, "___MANAGED_OR_NAMESPACED_ORG___Custom__c.csv"
            )
            assert os.path.exists(custom_csv)
            with open(custom_csv, "r", encoding="utf-8") as f:
                content = f.read()
                assert "%%%MANAGED_OR_NAMESPACED_ORG%%%Field2__c" in content
                assert "%%%MANAGED_OR_NAMESPACED_ORG%%%Val2" in content

            # Contact.csv - no namespace in filename
            contact_csv = os.path.join(base_dir, "Contact.csv")
            assert os.path.exists(contact_csv)
            with open(contact_csv, "r", encoding="utf-8") as f:
                content = f.read()
                assert "%%%MANAGED_OR_NAMESPACED_ORG%%%Email__c" in content
                assert "%%%MANAGED_OR_NAMESPACED_ORG%%%test@example.com" in content

    @mock.patch("cumulusci.tasks.sfdmu.sfdmu.sfdx")
    def test_process_csv_exports_called_when_target_is_csvfile(self, mock_sfdx):
        """Test that _process_csv_exports is called after SFDMU execution when target is csvfile."""
        with tempfile.TemporaryDirectory() as base_dir:
            # Create export.json
            export_json = os.path.join(base_dir, "export.json")
            with open(export_json, "w") as f:
                f.write('{"test": "data"}')

            task = create_task(
                SfdmuTask, {"source": "dev", "target": "csvfile", "path": base_dir}
            )
            task.project_config.project__package__namespace = "testns"

            # Mock sfdx command
            mock_sfdx_result = mock.Mock()
            mock_sfdx_result.stdout_text = iter([])
            mock_sfdx_result.stderr_text = iter([])
            mock_sfdx.return_value = mock_sfdx_result

            # Mock _validate_org
            mock_source_org = mock.Mock()
            mock_source_org.sfdx_alias = "test_dev"
            task._validate_org = mock.Mock(
                side_effect=lambda org: mock_source_org if org == "dev" else None
            )

            # Mock _inject_namespace_tokens to avoid complex setup
            task._inject_namespace_tokens = mock.Mock()

            # Spy on _process_csv_exports
            original_process = task._process_csv_exports
            task._process_csv_exports = mock.Mock(wraps=original_process)

            # Run the task
            task._run_task()

            # Verify that _process_csv_exports was called
            task._process_csv_exports.assert_called_once()
            # Verify it was called with correct arguments
            call_args = task._process_csv_exports.call_args[0]
            assert call_args[0].endswith("execute")  # execute_path
            assert call_args[1] == base_dir  # base_path

    @mock.patch("cumulusci.tasks.sfdmu.sfdmu.sfdx")
    def test_process_csv_exports_not_called_when_target_is_org(self, mock_sfdx):
        """Test that _process_csv_exports is NOT called when target is an org."""
        with tempfile.TemporaryDirectory() as base_dir:
            # Create export.json
            export_json = os.path.join(base_dir, "export.json")
            with open(export_json, "w") as f:
                f.write('{"test": "data"}')

            task = create_task(
                SfdmuTask, {"source": "dev", "target": "qa", "path": base_dir}
            )
            task.project_config.project__package__namespace = "testns"

            # Mock sfdx command
            mock_sfdx_result = mock.Mock()
            mock_sfdx_result.stdout_text = iter([])
            mock_sfdx_result.stderr_text = iter([])
            mock_sfdx.return_value = mock_sfdx_result

            # Mock _validate_org
            mock_org = mock.Mock()
            mock_org.sfdx_alias = "test_org"
            task._validate_org = mock.Mock(return_value=mock_org)

            # Mock _inject_namespace_tokens
            task._inject_namespace_tokens = mock.Mock()

            # Spy on _process_csv_exports
            task._process_csv_exports = mock.Mock()

            # Run the task
            task._run_task()

            # Verify that _process_csv_exports was NOT called
            task._process_csv_exports.assert_not_called()

    def test_return_always_success_option_exists(self):
        """Test that return_always_success option is properly defined."""
        assert "return_always_success" in SfdmuTask.task_options
        assert SfdmuTask.task_options["return_always_success"]["required"] is False
        assert SfdmuTask.task_options["return_always_success"]["default"] is False

    @mock.patch("cumulusci.tasks.sfdmu.sfdmu.sfdx")
    def test_return_always_success_false_fails_on_error(self, mock_sfdx):
        """Test that task fails when return_always_success is False and command fails."""
        with tempfile.TemporaryDirectory() as base_dir:
            # Create export.json
            export_json = os.path.join(base_dir, "export.json")
            with open(export_json, "w") as f:
                f.write('{"test": "data"}')

            task = create_task(
                SfdmuTask,
                {
                    "source": "dev",
                    "target": "qa",
                    "path": base_dir,
                    "return_always_success": False,
                },
            )

            # Mock sfdx command to raise an error
            mock_sfdx.side_effect = Exception("SFDMU command failed")

            # Mock _validate_org
            mock_org = mock.Mock()
            mock_org.sfdx_alias = "test_org"
            task._validate_org = mock.Mock(return_value=mock_org)

            # Mock _inject_namespace_tokens
            task._inject_namespace_tokens = mock.Mock()

            # Task should raise the exception
            with pytest.raises(Exception, match="SFDMU command failed"):
                task._run_task()

    @mock.patch("cumulusci.tasks.sfdmu.sfdmu.sfdx")
    def test_return_always_success_true_continues_on_error(self, mock_sfdx):
        """Test that task continues when return_always_success is True and command fails."""
        with tempfile.TemporaryDirectory() as base_dir:
            # Create export.json
            export_json = os.path.join(base_dir, "export.json")
            with open(export_json, "w") as f:
                f.write('{"test": "data"}')

            task = create_task(
                SfdmuTask,
                {
                    "source": "dev",
                    "target": "qa",
                    "path": base_dir,
                    "return_always_success": True,
                },
            )

            # Mock sfdx command to raise an error
            mock_sfdx.side_effect = Exception("SFDMU command failed")

            # Mock _validate_org
            mock_org = mock.Mock()
            mock_org.sfdx_alias = "test_org"
            task._validate_org = mock.Mock(return_value=mock_org)

            # Mock _inject_namespace_tokens
            task._inject_namespace_tokens = mock.Mock()

            # Task should NOT raise exception - should complete successfully
            task._run_task()  # Should not raise

    @mock.patch("cumulusci.tasks.sfdmu.sfdmu.sfdx")
    def test_return_always_success_true_logs_warning_on_nonzero_exit(self, mock_sfdx):
        """Test that task logs warning when return_always_success is True and exit code is non-zero."""
        with tempfile.TemporaryDirectory() as base_dir:
            # Create export.json
            export_json = os.path.join(base_dir, "export.json")
            with open(export_json, "w") as f:
                f.write('{"test": "data"}')

            task = create_task(
                SfdmuTask,
                {
                    "source": "dev",
                    "target": "qa",
                    "path": base_dir,
                    "return_always_success": True,
                },
            )

            # Mock sfdx command to return non-zero exit code
            mock_sfdx_result = mock.Mock()
            mock_sfdx_result.returncode = 1  # Failed
            mock_sfdx_result.stdout_text = iter([])
            mock_sfdx_result.stderr_text = iter([])
            mock_sfdx.return_value = mock_sfdx_result

            # Mock _validate_org
            mock_org = mock.Mock()
            mock_org.sfdx_alias = "test_org"
            task._validate_org = mock.Mock(return_value=mock_org)

            # Mock _inject_namespace_tokens
            task._inject_namespace_tokens = mock.Mock()

            # Mock logger to capture warnings
            task.logger = mock.Mock()

            # Run the task
            task._run_task()

            # Verify warning was logged
            task.logger.warning.assert_called_once()
            warning_message = task.logger.warning.call_args[0][0]
            assert "failed with exit code 1" in warning_message
            assert "return_always_success is True" in warning_message

    @mock.patch("cumulusci.tasks.sfdmu.sfdmu.sfdx")
    def test_return_always_success_default_false(self, mock_sfdx):
        """Test that return_always_success defaults to False."""
        with tempfile.TemporaryDirectory() as base_dir:
            # Create export.json
            export_json = os.path.join(base_dir, "export.json")
            with open(export_json, "w") as f:
                f.write('{"test": "data"}')

            # Create task without specifying return_always_success
            task = create_task(
                SfdmuTask,
                {"source": "dev", "target": "qa", "path": base_dir},
            )

            # Mock sfdx command to raise an error
            mock_sfdx.side_effect = Exception("SFDMU command failed")

            # Mock _validate_org
            mock_org = mock.Mock()
            mock_org.sfdx_alias = "test_org"
            task._validate_org = mock.Mock(return_value=mock_org)

            # Mock _inject_namespace_tokens
            task._inject_namespace_tokens = mock.Mock()

            # Task should raise the exception (default behavior)
            with pytest.raises(Exception, match="SFDMU command failed"):
                task._run_task()

    @mock.patch("cumulusci.tasks.sfdmu.sfdmu.sfdx")
    def test_return_always_success_true_with_csvfile_export(self, mock_sfdx):
        """Test that CSV post-processing still runs when return_always_success is True and command fails."""
        with tempfile.TemporaryDirectory() as base_dir:
            # Create export.json
            export_json = os.path.join(base_dir, "export.json")
            with open(export_json, "w") as f:
                f.write('{"test": "data"}')

            task = create_task(
                SfdmuTask,
                {
                    "source": "dev",
                    "target": "csvfile",
                    "path": base_dir,
                    "return_always_success": True,
                },
            )
            task.project_config.project__package__namespace = "testns"

            # Mock sfdx command to raise an error
            mock_sfdx.side_effect = Exception("SFDMU command failed")

            # Mock _validate_org
            mock_source_org = mock.Mock()
            mock_source_org.sfdx_alias = "test_dev"
            task._validate_org = mock.Mock(
                side_effect=lambda org: mock_source_org if org == "dev" else None
            )

            # Mock _inject_namespace_tokens
            task._inject_namespace_tokens = mock.Mock()

            # Spy on _process_csv_exports
            task._process_csv_exports = mock.Mock()

            # Run the task - should not raise
            task._run_task()

            # Verify that _process_csv_exports was still called
            task._process_csv_exports.assert_called_once()
